"""
USDT withdrawal sender via TON blockchain.

Processes pending withdrawals from DB, sends USDT (Jetton) via hot wallet.
"""
from __future__ import annotations

import logging
import time
from decimal import Decimal
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import UsdtTransaction, UserBalance
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

USDT_DECIMALS = 6
USDT_WITHDRAW_FEE = Decimal("0.3")
# TON for gas (nanotons). Exit 48 / bounce = need more gas. Conservative values.
FORWARD_TON_AMOUNT = int(0.02 * 1e9)  # 0.02 TON to recipient (Jetton processing + notification)
GAS_TON_AMOUNT = int(0.03 * 1e9)  # 0.03 TON for our message (buffer for jetton transfer)


def _get_db() -> Session:
    return SessionLocal()


def _refund_withdrawal(telegram_id: int, amount_usdt: Decimal, fee: Decimal) -> None:
    """Refund user balance when withdrawal fails."""
    db = _get_db()
    try:
        gross = amount_usdt + fee
        bal = db.execute(
            select(UserBalance).where(
                UserBalance.telegram_id == telegram_id,
                UserBalance.currency == "usdt",
            )
        ).scalar_one_or_none()
        if bal:
            bal.available += gross
            bal.total_withdrawn -= gross  # revert
            db.commit()
            logger.info("Refunded %s USDT to telegram_id=%s (withdrawal failed)", gross, telegram_id)
    except Exception as e:
        logger.exception("Refund failed: %s", e)
        db.rollback()
    finally:
        db.close()


def _fetch_tx_hash_from_tonapi(
    our_wallet: str, dest_address: str, amount_raw: int, jetton_wallet: str | None = None
) -> str | None:
    """Try to get tx hash from TonAPI and TON Center after send."""
    api_key = (settings.tonapi_key or "").strip()
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    dest_norm = dest_address.replace("-", "").replace("_", "").lower()

    def _fetch_tonapi(account_addr: str) -> str | None:
        url = f"https://tonapi.io/v2/accounts/{account_addr}/events"
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.get(url, params={"limit": 50}, headers=headers or None)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.debug("TonAPI fetch (%s): %s", account_addr[:20], e)
            return None

        for ev in data.get("events") or []:
            for act in ev.get("actions") or []:
                if act.get("type") != "JettonTransfer":
                    continue
                jt = act.get("JettonTransfer") or act
                recip = jt.get("recipient") or {}
                recip_addr = (recip.get("address") if isinstance(recip, dict) else str(recip)) or ""
                recip_norm = recip_addr.replace("-", "").replace("_", "").lower()
                amt = jt.get("amount")
                if dest_norm in recip_norm and str(amt) == str(amount_raw):
                    txs = ev.get("base_transactions") or []
                    if txs and isinstance(txs[0], str):
                        return txs[0]
                    return ev.get("event_id") or (txs[0] if txs else None)
        return None

    def _fetch_toncenter(account_addr: str) -> str | None:
        """Fallback: get latest tx hash from TON Center (most recent = our send)."""
        url = "https://toncenter.com/api/v2/getTransactions"
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(url, params={"address": account_addr, "limit": 5})
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.debug("TON Center fetch (%s): %s", account_addr[:20], e)
            return None

        for tx in data.get("result") or []:
            tid = tx.get("transaction_id") or {}
            h = tid.get("hash")
            if h:
                return h
        return None

    time.sleep(8)  # Wait for block confirmation
    result = _fetch_tonapi(our_wallet)
    if not result and jetton_wallet:
        result = _fetch_tonapi(jetton_wallet)
    if not result:
        time.sleep(7)  # TonAPI indexing delay
        result = _fetch_tonapi(our_wallet)
        if not result and jetton_wallet:
            result = _fetch_tonapi(jetton_wallet)
    if not result and jetton_wallet:
        result = _fetch_toncenter(jetton_wallet)
    if not result and our_wallet:
        result = _fetch_toncenter(our_wallet)

    if result:
        logger.info("Withdrawal tx hash found: %s", result[:20] + "...")
    else:
        logger.info("Withdrawal tx hash not found for %s USDT to %s", amount_raw / 1e6, dest_address[:24])
    return result


def _verify_tx_success(tx_hash: str) -> bool | None:
    """Check via TonAPI if transaction succeeded. Returns True/False/None (unknown)."""
    api_key = (settings.tonapi_key or "").strip()
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = f"https://tonapi.io/v2/blockchain/transactions/{quote(tx_hash, safe='')}"
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, headers=headers or None)
            resp.raise_for_status()
            data = resp.json()
        return bool(data.get("success"))
    except Exception as e:
        logger.debug("TonAPI tx verify (%s): %s", tx_hash[:16], e)
        return None


def _notify_withdrawal_failed(
    telegram_id: int,
    net_amount: Decimal,
    address: str,
    reason: str = "Транзакция не прошла в сети. Средства возвращены на баланс.",
) -> None:
    """Notify user that withdrawal failed and was refunded."""
    token = (settings.tg_bot_token or "").strip()
    if not token:
        return
    gross = net_amount + USDT_WITHDRAW_FEE
    amt_str = str(int(gross)) if gross == gross.to_integral_value() else str(gross).rstrip("0").rstrip(".")
    text = (
        f'<b>⚠️ Вывод -{amt_str} USDT отменён</b>\n\n'
        f"<b>Причина:</b> {reason}\n"
        f"<b>Адрес:</b> <pre>{address[:48]}{'...' if len(address) > 48 else ''}</pre>\n\n"
        f"Средства возвращены на ваш баланс."
    )
    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": telegram_id, "text": text, "parse_mode": "HTML"},
            )
    except Exception as e:
        logger.warning("Failed to send withdrawal failure notification to %s: %s", telegram_id, e)


def _notify_withdrawal_completed(
    telegram_id: int,
    net_amount: Decimal,
    address: str,
    tx_hash: str | None,
    our_wallet: str | None = None,
) -> None:
    """Send Telegram notification when withdrawal is completed."""
    token = (settings.tg_bot_token or "").strip()
    if not token:
        return
    gross = net_amount + USDT_WITHDRAW_FEE  # amount user withdrew
    amt_str = str(int(gross)) if gross == gross.to_integral_value() else str(gross).rstrip("0").rstrip(".")
    if tx_hash and len(tx_hash) >= 10:
        track_url = f"https://tonscan.org/tx/{quote(tx_hash, safe='')}"
    elif our_wallet:
        track_url = f"https://tonscan.org/address/{our_wallet}"
    else:
        track_url = None

    text = (
        f'<b><tg-emoji emoji-id="5458525793921546124">😌</tg-emoji></b> <b>Вывод: -{amt_str} USDT завершён</b>\n\n'
        f"<b>Адрес получения:</b>\n<pre>{address[:64]}{'...' if len(address) > 64 else ''}</pre>\n"
        f"<b>ID транзакции:</b>\n<pre>{tx_hash or '—'}</pre>"
    )
    payload: dict = {"chat_id": telegram_id, "text": text, "parse_mode": "HTML"}
    if track_url:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "👀 Отследить", "url": track_url}]]
        }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload,
            )
            resp.raise_for_status()
    except Exception as e:
        logger.warning("Failed to send withdrawal notification to %s: %s", telegram_id, e)


def _load_withdraw_private_key() -> bytes | None:
    """Загрузить приватный ключ: из USDT_WITHDRAW_PRIVATE_KEY (hex) или из мнемоники."""
    pk_hex = (getattr(settings, "usdt_withdraw_private_key", None) or "").strip()
    if pk_hex:
        try:
            raw = bytes.fromhex(pk_hex.replace(" ", ""))
            if len(raw) == 32:
                # 32 bytes = seed, нужен nacl keypair
                from nacl.bindings import crypto_sign_seed_keypair
                _, priv_k = crypto_sign_seed_keypair(raw)
                return priv_k
            if len(raw) == 64:
                return raw
            logger.warning("USDT withdraw: private key must be 32 or 64 bytes (hex 64 or 128 chars)")
            return None
        except ValueError as e:
            logger.warning("USDT withdraw: invalid private key hex: %s", e)
            return None

    mnemonic = (settings.usdt_withdraw_mnemonic or "").strip()
    if not mnemonic:
        return None
    mnemonics = [w.lower().strip() for w in mnemonic.split() if w.strip()]
    if len(mnemonics) != 24:
        return None
    try:
        from pytoniq_core.crypto.keys import mnemonic_to_private_key
        _, priv_k = mnemonic_to_private_key(mnemonics)
        return priv_k
    except Exception:
        return None


async def _send_jetton_withdrawal(
    destination_address: str,
    amount_usdt: Decimal,
    comment: str | None,
) -> str | None:
    """
    Send USDT Jetton to destination. Returns tx hash on success, None on failure.
    Supports USDT_WITHDRAW_PRIVATE_KEY (hex) or USDT_WITHDRAW_MNEMONIC.
    """
    jetton_master = (settings.usdt_jetton_master or "").strip()
    if not jetton_master:
        logger.warning("USDT withdraw: jetton_master not configured")
        return None

    private_key = _load_withdraw_private_key()
    if not private_key:
        logger.warning("USDT withdraw: usdt_withdraw_private_key or usdt_withdraw_mnemonic required")
        return None

    try:
        from pytoniq import LiteBalancer, WalletV3R2, WalletV4R2, WalletV5R1, begin_cell, Address
    except ImportError as e:
        logger.error("pytoniq not installed: %s", e)
        return None

    destination_address = destination_address.strip()
    if len(destination_address) < 40:
        logger.warning("Invalid destination address: %s", destination_address[:20])
        return None

    # Amount in minimal units (USDT = 6 decimals)
    amount_raw = int(amount_usdt * Decimal(10**USDT_DECIMALS))
    if amount_raw <= 0:
        return None

    expected = (getattr(settings, "usdt_withdraw_wallet", None) or "").strip() or (getattr(settings, "usdt_deposit_wallet", None) or "").strip()

    def _raw_addr(addr) -> str:
        """Extract parseable address string (pytoniq may return 'Address<EQ...>')."""
        if hasattr(addr, "to_str"):
            return addr.to_str()
        s = str(addr).strip()
        if s.startswith("Address<") and ">" in s:
            s = s[8 : s.rindex(">")]
        return s

    def addr_match(got: str, exp: str) -> bool:
        """Compare addresses by hash_part (bounceable/non-bounceable have same hash)."""
        try:
            from pytoniq_core.boc.address import Address as AddrCls
            return AddrCls(got).hash_part == AddrCls(exp).hash_part and AddrCls(got).wc == AddrCls(exp).wc
        except Exception:
            # Fallback: compare hash part (exclude 2-char tag and 4-char checksum)
            g = got.replace("-", "").replace("_", "").lower()
            e = exp.replace("-", "").replace("_", "").lower()
            if len(g) >= 10 and len(e) >= 10:
                return g[2:-4] == e[2:-4]
            return g == e

    try:
        provider = LiteBalancer.from_mainnet_config(1)
        await provider.start_up()

        wallet = None
        # Tonkeeper uses V5R1 by default; try v5r1 first, then v4r2, v3r2
        for version_name, create_fn in [
            ("v5r1", lambda: WalletV5R1.from_private_key(
                provider, private_key, wc=0, network_global_id=-239
            )),
            ("v4r2", lambda: WalletV4R2.from_private_key(
                provider, private_key, version="v4r2"
            )),
            ("v3r2", lambda: WalletV3R2.from_private_key(
                provider, private_key, version="v3r2"
            )),
        ]:
            w = await create_fn()
            if not expected or addr_match(_raw_addr(w.address), expected):
                wallet = w
                logger.debug("USDT wallet matched: %s", version_name)
                break

        if not wallet:
            got_addr = _raw_addr(w.address) if w else "?"
            logger.error(
                "USDT wallet address mismatch: got %s, expected %s",
                got_addr[:50] if got_addr else "?",
                expected[:50] if expected else "?",
            )
            await provider.close_all()
            return None

        owner_address = wallet.address

        # Get our Jetton wallet address from Jetton Master
        jetton_master_addr = Address(jetton_master)
        stack = [begin_cell().store_address(owner_address).end_cell().begin_parse()]
        result = await provider.run_get_method(
            address=jetton_master_addr,
            method="get_wallet_address",
            stack=stack,
        )
        user_jetton_wallet = result[0].load_address()
        dest_address = Address(destination_address)

        # Build forward_payload (comment) if provided; TEP-74 requires ref even if empty
        if comment and comment.strip():
            forward_payload = (
                begin_cell()
                .store_uint(0, 32)  # TextComment opcode
                .store_snake_string(comment.strip()[:120])
                .end_cell()
            )
        else:
            forward_payload = begin_cell().end_cell()

        transfer_cell = (
            begin_cell()
            .store_uint(0xF8A7EA5, 32)  # Jetton Transfer op
            .store_uint(0, 64)  # query_id
            .store_coins(amount_raw)  # Jetton amount
            .store_address(dest_address)  # destination
            .store_address(owner_address)  # response_destination
            .store_bit(0)  # no custom_payload
            .store_coins(FORWARD_TON_AMOUNT)  # forward_ton_amount
            .store_bit(1)  # forward_payload as ref
            .store_ref(forward_payload)
            .end_cell()
        )

        try:
            await wallet.transfer(
                destination=user_jetton_wallet,
                amount=GAS_TON_AMOUNT,
                body=transfer_cell,
            )
        except Exception as deploy_check:
            # exit_code -256 = account not deployed (uninit); deploy first
            exit_code = getattr(deploy_check, "exit_code", None)
            if exit_code == -256 and hasattr(wallet, "send_init_external"):
                logger.info("USDT wallet undeployed, deploying via send_init_external...")
                await wallet.send_init_external()
                time.sleep(15)  # wait for deploy confirmation on chain
                await wallet.transfer(
                    destination=user_jetton_wallet,
                    amount=GAS_TON_AMOUNT,
                    body=transfer_cell,
                )
            else:
                raise

        await provider.close_all()
        jetton_addr = _raw_addr(user_jetton_wallet) if user_jetton_wallet else None
        return ("sent", jetton_addr)
    except Exception as e:
        logger.exception("USDT Jetton transfer failed: %s", e)
        return None


async def process_pending_withdrawals() -> int:
    """
    Process pending USDT withdrawals: send via TON, update status.
    Returns count of successfully processed withdrawals.
    """
    if not _load_withdraw_private_key():
        logger.debug("USDT withdraw: private key / mnemonic not configured, skip")
        return 0

    db = _get_db()
    processed = 0
    try:
        rows = db.execute(
            select(UsdtTransaction)
            .where(
                UsdtTransaction.tx_type == "withdrawal",
                UsdtTransaction.status == "pending",
            )
            .order_by(UsdtTransaction.created_at.asc())
            .limit(10)
        ).scalars().all()

        our_wallet = (getattr(settings, "usdt_withdraw_wallet", None) or "").strip() or (getattr(settings, "usdt_deposit_wallet", None) or "").strip()

        for tx in rows:
            if not tx.memo or len(tx.memo) < 40:
                logger.warning("Withdrawal %s: invalid address in memo", tx.event_id)
                tx.status = "failed"
                _refund_withdrawal(tx.telegram_id, tx.amount, USDT_WITHDRAW_FEE)
                db.commit()
                continue

            # Re-verify balance in DB before send (amount was deducted at request time)
            gross = tx.amount + USDT_WITHDRAW_FEE
            bal = db.execute(
                select(UserBalance).where(
                    UserBalance.telegram_id == tx.telegram_id,
                    UserBalance.currency == "usdt",
                )
            ).scalar_one_or_none()
            if not bal:
                logger.warning("Withdrawal %s: no balance record for user %s, skip", tx.event_id, tx.telegram_id)
                tx.status = "failed"
                _refund_withdrawal(tx.telegram_id, tx.amount, USDT_WITHDRAW_FEE)
                db.commit()
                continue
            if bal.available < 0:
                logger.error("Withdrawal %s: negative balance %.2f for user %s, skip", tx.event_id, bal.available, tx.telegram_id)
                tx.status = "failed"
                _refund_withdrawal(tx.telegram_id, tx.amount, USDT_WITHDRAW_FEE)
                db.commit()
                continue

            result = await _send_jetton_withdrawal(
                destination_address=tx.memo,
                amount_usdt=tx.amount,
                comment=tx.destination_memo,
            )
            if result:
                _, jetton_wallet_addr = result
                amount_raw = int(tx.amount * Decimal(10**USDT_DECIMALS))
                tx.tx_hash = (
                    _fetch_tx_hash_from_tonapi(our_wallet, tx.memo, amount_raw, jetton_wallet_addr)
                    if our_wallet else None
                )

                verified = None
                if tx.tx_hash:
                    for attempt in range(3):
                        verified = _verify_tx_success(tx.tx_hash)
                        if verified is not None:
                            break
                        time.sleep(5)

                if verified is False:
                    tx.status = "failed"
                    _refund_withdrawal(tx.telegram_id, tx.amount, USDT_WITHDRAW_FEE)
                    _notify_withdrawal_failed(
                        tx.telegram_id, tx.amount, tx.memo or "",
                        reason="Транзакция не прошла в сети (недостаточно газа или ошибка контракта).",
                    )
                    logger.warning("Withdrawal %s tx failed on-chain (hash=%s), refunded", tx.event_id, tx.tx_hash[:24])
                    db.commit()
                    continue
                elif verified is True:
                    tx.status = "completed"
                    processed += 1
                    logger.info("Withdrawal %s verified: %s USDT to %s (tx=%s)", tx.event_id, tx.amount, tx.memo[:20], tx.tx_hash or "sent")
                    _notify_withdrawal_completed(
                        tx.telegram_id, tx.amount, tx.memo or "", tx.tx_hash, our_wallet
                    )
                    db.commit()
                else:
                    tx.status = "completed"
                    processed += 1
                    logger.warning("Withdrawal %s tx unverified (TonAPI?), marked completed: %s USDT to %s", tx.event_id, tx.amount, tx.memo[:20])
                    _notify_withdrawal_completed(
                        tx.telegram_id, tx.amount, tx.memo or "", tx.tx_hash, our_wallet
                    )
                    db.commit()
            else:
                tx.status = "failed"
                _refund_withdrawal(tx.telegram_id, tx.amount, USDT_WITHDRAW_FEE)
                logger.warning("Withdrawal %s failed to send, refunded", tx.event_id)
                db.commit()

    except Exception as e:
        logger.exception("Process withdrawals: %s", e)
        db.rollback()
    finally:
        db.close()

    return processed
