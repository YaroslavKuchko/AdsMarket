"""
TON native withdrawal sender.

Processes pending TON withdrawals from DB, sends native TON via hot wallet.
Reuses usdt_withdraw_* wallet (same TON wallet).
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
from app.db.models import TonWithdrawal, UserBalance
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

TON_WITHDRAW_FEE = Decimal("0.15")
TON_WITHDRAW_MIN = Decimal("0.1")


def _get_db() -> Session:
    return SessionLocal()


def _refund_ton_withdrawal(telegram_id: int, amount: Decimal, fee: Decimal = TON_WITHDRAW_FEE) -> None:
    """Refund user balance when TON withdrawal fails (amount + fee)."""
    total = amount + fee
    db = _get_db()
    try:
        bal = db.execute(
            select(UserBalance).where(
                UserBalance.telegram_id == telegram_id,
                UserBalance.currency == "ton",
            )
        ).scalar_one_or_none()
        if bal:
            bal.available += total
            bal.total_withdrawn -= total
            db.commit()
            logger.info("Refunded %s TON to telegram_id=%s (withdrawal failed)", total, telegram_id)
    except Exception as e:
        logger.exception("Refund TON failed: %s", e)
        db.rollback()
    finally:
        db.close()


def _fetch_ton_tx_hash(our_wallet: str, dest_address: str, amount_nano: int) -> str | None:
    """Get tx hash from TonAPI events after send."""
    api_key = (settings.tonapi_key or "").strip()
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    dest_norm = dest_address.replace("-", "").replace("_", "").lower()

    def _fetch_tonapi(addr: str) -> str | None:
        url = f"https://tonapi.io/v2/accounts/{addr}/events"
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.get(url, params={"limit": 30}, headers=headers or None)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.debug("TonAPI fetch (%s): %s", addr[:20], e)
            return None
        for ev in data.get("events") or []:
            for act in ev.get("actions") or []:
                if act.get("type") not in ("TonTransfer", "ton_transfer"):
                    continue
                data_ = act.get("TonTransfer") or act
                amount_raw = data_.get("amount")
                recip = data_.get("recipient") or data_.get("destination") or {}
                recip_addr = recip.get("address") if isinstance(recip, dict) else str(recip)
                recip_norm = (recip_addr or "").replace("-", "").replace("_", "").lower()
                if dest_norm in recip_norm and str(amount_raw) == str(amount_nano):
                    txs = ev.get("base_transactions") or []
                    if txs and isinstance(txs[0], str):
                        return txs[0]
                    return ev.get("event_id") or (txs[0] if txs else None)
        return None

    time.sleep(6)
    result = _fetch_tonapi(our_wallet)
    if not result:
        time.sleep(6)
        result = _fetch_tonapi(our_wallet)
    if not result and our_wallet:
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    "https://toncenter.com/api/v2/getTransactions",
                    params={"address": our_wallet, "limit": 5},
                )
                resp.raise_for_status()
                for tx in (resp.json().get("result") or [])[:3]:
                    tid = tx.get("transaction_id") or {}
                    h = tid.get("hash")
                    if h:
                        return h
        except Exception as e:
            logger.debug("TON Center fetch: %s", e)
    return result


def _verify_tx_success(tx_hash: str) -> bool | None:
    """Check via TonAPI if transaction succeeded."""
    api_key = (settings.tonapi_key or "").strip()
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = f"https://tonapi.io/v2/blockchain/transactions/{quote(tx_hash, safe='')}"
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, headers=headers or None)
            resp.raise_for_status()
            return bool(resp.json().get("success"))
    except Exception as e:
        logger.debug("TonAPI tx verify (%s): %s", tx_hash[:16], e)
        return None


def _notify_ton_withdraw_failed(telegram_id: int, amount: Decimal, address: str) -> None:
    """Notify user that TON withdrawal failed and was refunded."""
    token = (settings.tg_bot_token or "").strip()
    if not token:
        return
    amt_str = str(amount.quantize(Decimal("0.01")))
    text = (
        f'<b>⚠️ Вывод -{amt_str} TON отменён</b>\n\n'
        f"<b>Причина:</b> Транзакция не прошла в сети. Средства возвращены на баланс.\n"
        f"<b>Адрес:</b> <pre>{address[:48]}{'...' if len(address) > 48 else ''}</pre>"
    )
    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": telegram_id, "text": text, "parse_mode": "HTML"},
            )
    except Exception as e:
        logger.warning("Failed to send TON withdrawal failure notification: %s", e)


def _notify_ton_withdraw_completed(
    telegram_id: int, amount: Decimal, address: str, tx_hash: str | None, our_wallet: str | None
) -> None:
    """Notify user that TON withdrawal completed."""
    token = (settings.tg_bot_token or "").strip()
    if not token:
        return
    amt_str = str(amount.quantize(Decimal("0.01")))
    if tx_hash and len(tx_hash) >= 10:
        track_url = f"https://tonscan.org/tx/{quote(tx_hash, safe='')}"
    elif our_wallet:
        track_url = f"https://tonscan.org/address/{our_wallet}"
    else:
        track_url = None
    text = (
        f'<b>😌 Вывод: -{amt_str} TON завершён</b>\n\n'
        f"<b>Адрес получения:</b>\n<pre>{address[:64]}{'...' if len(address) > 64 else ''}</pre>\n"
        f"<b>ID транзакции:</b>\n<pre>{tx_hash or '—'}</pre>"
    )
    payload: dict = {"chat_id": telegram_id, "text": text, "parse_mode": "HTML"}
    if track_url:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": "👀 Отследить", "url": track_url}]]}
    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
    except Exception as e:
        logger.warning("Failed to send TON withdrawal notification: %s", e)


def _load_withdraw_private_key() -> bytes | None:
    """Reuse USDT withdraw key (same hot wallet)."""
    pk_hex = (getattr(settings, "usdt_withdraw_private_key", None) or "").strip()
    if pk_hex:
        try:
            raw = bytes.fromhex(pk_hex.replace(" ", ""))
            if len(raw) == 32:
                from nacl.bindings import crypto_sign_seed_keypair
                _, priv_k = crypto_sign_seed_keypair(raw)
                return priv_k
            if len(raw) == 64:
                return raw
            return None
        except ValueError:
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


async def _send_ton(dest_address: str, amount_ton: Decimal) -> bool:
    """Send native TON to address. Returns True on success."""
    private_key = _load_withdraw_private_key()
    if not private_key:
        return False
    expected = (
        (getattr(settings, "usdt_withdraw_wallet", None) or "").strip()
        or (getattr(settings, "usdt_deposit_wallet", None) or "").strip()
    )

    try:
        from pytoniq import LiteBalancer, WalletV3R2, WalletV4R2, WalletV5R1, Address
    except ImportError:
        logger.error("pytoniq not installed")
        return False

    amount_nano = int(amount_ton * 1e9)
    if amount_nano <= 0:
        return False

    def _raw_addr(addr) -> str:
        if hasattr(addr, "to_str"):
            return addr.to_str()
        s = str(addr).strip()
        if s.startswith("Address<") and ">" in s:
            s = s[8 : s.rindex(">")]
        return s

    def addr_match(got: str, exp: str) -> bool:
        g = (got or "").replace("-", "").replace("_", "").lower()
        e = (exp or "").replace("-", "").replace("_", "").lower()
        return len(g) >= 10 and len(e) >= 10 and g[2:-4] == e[2:-4]

    try:
        provider = LiteBalancer.from_mainnet_config(1)
        await provider.start_up()
        wallet = None
        w = None
        for version_name, create_fn in [
            ("v5r1", lambda: WalletV5R1.from_private_key(
                provider, private_key, wc=0, network_global_id=-239
            )),
            ("v4r2", lambda: WalletV4R2.from_private_key(provider, private_key, version="v4r2")),
            ("v3r2", lambda: WalletV3R2.from_private_key(provider, private_key, version="v3r2")),
        ]:
            w = await create_fn()
            if not expected or addr_match(_raw_addr(w.address), expected):
                wallet = w
                logger.debug("TON wallet matched: %s", version_name)
                break

        if not wallet:
            logger.error("TON wallet address mismatch")
            await provider.close_all()
            return False

        dest = Address(dest_address.strip())
        # Send amount_nano (user receives). Wallet pays amount + small fee automatically.
        await wallet.transfer(destination=dest, amount=amount_nano)
        await provider.close_all()
        return True
    except Exception as e:
        logger.exception("TON transfer failed: %s", e)
        return False


async def process_pending_ton_withdrawals() -> int:
    """Process pending TON withdrawals. Returns count processed."""
    if not _load_withdraw_private_key():
        return 0

    our_wallet = (
        (getattr(settings, "usdt_withdraw_wallet", None) or "").strip()
        or (getattr(settings, "usdt_deposit_wallet", None) or "").strip()
    )

    db = _get_db()
    processed = 0
    try:
        rows = db.execute(
            select(TonWithdrawal)
            .where(TonWithdrawal.status == "pending")
            .order_by(TonWithdrawal.created_at.asc())
            .limit(10)
        ).scalars().all()

        for tx in rows:
            if not tx.memo or len(tx.memo) < 40:
                tx.status = "failed"
                _refund_ton_withdrawal(tx.telegram_id, tx.amount, TON_WITHDRAW_FEE)
                db.commit()
                continue

            bal = db.execute(
                select(UserBalance).where(
                    UserBalance.telegram_id == tx.telegram_id,
                    UserBalance.currency == "ton",
                )
            ).scalar_one_or_none()
            if not bal or bal.available < 0:
                tx.status = "failed"
                _refund_ton_withdrawal(tx.telegram_id, tx.amount, TON_WITHDRAW_FEE)
                db.commit()
                continue

            ok = await _send_ton(tx.memo, tx.amount)
            if not ok:
                tx.status = "failed"
                _refund_ton_withdrawal(tx.telegram_id, tx.amount, TON_WITHDRAW_FEE)
                db.commit()
                continue

            amount_nano = int(tx.amount * 1e9)
            tx.tx_hash = _fetch_ton_tx_hash(our_wallet, tx.memo, amount_nano) if our_wallet else None

            verified = None
            if tx.tx_hash:
                for _ in range(3):
                    verified = _verify_tx_success(tx.tx_hash)
                    if verified is not None:
                        break
                    time.sleep(5)

            if verified is False:
                tx.status = "failed"
                _refund_ton_withdrawal(tx.telegram_id, tx.amount, TON_WITHDRAW_FEE)
                _notify_ton_withdraw_failed(tx.telegram_id, tx.amount, tx.memo or "")
                db.commit()
                continue

            tx.status = "completed"
            processed += 1
            _notify_ton_withdraw_completed(
                tx.telegram_id, tx.amount, tx.memo or "", tx.tx_hash, our_wallet
            )
            db.commit()
    except Exception as e:
        logger.exception("Process TON withdrawals: %s", e)
        db.rollback()
    finally:
        db.close()
    return processed
