"""
TON native deposit scanner.

Polls TonAPI for incoming TON transfers to our deposit wallet.
Matches sender address to TonWallet (connected user wallets) - no memo needed.
"""
from __future__ import annotations

import logging
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import TonTransaction, TonWallet, UserBalance
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

NANOTON = 10**9
PREFIX = "ton_dep_"


def _get_db() -> Session:
    return SessionLocal()


def _addr_match(a: str, b: str) -> bool:
    """Compare TON addresses by hash_part (robust for any format: raw, bounceable, etc.)."""
    if not a or not b:
        return False
    try:
        from pytoniq_core.boc.address import Address
        return Address(a.strip()).hash_part == Address(b.strip()).hash_part
    except Exception:
        # Fallback: normalize and compare (bounceable/non-bounceable)
        na = a.replace("-", "").replace("_", "").strip().lower()
        nb = b.replace("-", "").replace("_", "").strip().lower()
        if len(na) >= 10 and len(nb) >= 10:
            return na[2:-4] == nb[2:-4]
        return na == nb


def _notify_ton_deposit(telegram_id: int, amount: Decimal) -> None:
    """Send Telegram notification when TON is credited."""
    token = (settings.tg_bot_token or "").strip()
    if not token:
        return
    amt_str = str(amount.quantize(Decimal("0.01")))
    text = f'<tg-emoji emoji-id="5467756490389469348">😤</tg-emoji> <b>+{amt_str} TON зачислено на ваш баланс.</b>'
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": telegram_id, "text": text, "parse_mode": "HTML"},
            )
            resp.raise_for_status()
    except Exception as e:
        logger.warning("Failed to send TON deposit notification to %s: %s", telegram_id, e)


def _credit_ton(telegram_id: int, amount: Decimal, tx_hash: str, from_addr: str, to_addr: str) -> bool:
    """Credit TON to user balance. Returns True on success."""
    db = _get_db()
    try:
        bal = db.execute(
            select(UserBalance).where(
                UserBalance.telegram_id == telegram_id,
                UserBalance.currency == "ton",
            )
        ).scalar_one_or_none()
        if bal:
            bal.available += amount
            bal.total_deposited += amount
        else:
            bal = UserBalance(
                telegram_id=telegram_id,
                currency="ton",
                available=amount,
                total_deposited=amount,
            )
            db.add(bal)
        tx = TonTransaction(
            tx_hash=tx_hash,
            telegram_id=telegram_id,
            from_address=from_addr,
            to_address=to_addr,
            amount_nano=int(amount * NANOTON),
            amount_ton=amount,
            tx_type="top_up",
            status="processed",
        )
        db.add(tx)
        db.commit()
        return True
    except Exception as e:
        logger.exception("Credit TON: %s", e)
        db.rollback()
        return False
    finally:
        db.close()


def _already_processed(tx_hash: str) -> bool:
    db = _get_db()
    try:
        existing = db.execute(
            select(TonTransaction).where(TonTransaction.tx_hash == tx_hash)
        ).scalar_one_or_none()
        return existing is not None
    finally:
        db.close()


def _get_telegram_id_by_wallet_address(sender_addr: str) -> int | None:
    """Find telegram_id by connected wallet address (any format)."""
    db = _get_db()
    try:
        wallets = db.execute(
            select(TonWallet).where(
                TonWallet.is_active == True,
                TonWallet.address.isnot(None),
            )
        ).scalars().all()
        for w in wallets:
            if _addr_match(w.address, sender_addr):
                return w.telegram_id
            if w.friendly_address and _addr_match(w.friendly_address, sender_addr):
                return w.telegram_id
        return None
    finally:
        db.close()


def _parse_ton_transfer(action: dict, event: dict, our_wallet_addr: str) -> tuple[Decimal, str, str, str] | None:
    """
    Parse TonAPI TonTransfer action (incoming to our wallet).
    Returns (amount_ton, sender_addr, recipient_addr, tx_hash) or None.
    """
    atype = action.get("type", "")
    if atype not in ("TonTransfer", "ton_transfer"):
        return None
    data = action.get("TonTransfer") or action
    amount_raw = data.get("amount")
    if amount_raw is None:
        return None
    try:
        amount_ton = Decimal(amount_raw) / Decimal(NANOTON)
    except (TypeError, ValueError):
        return None
    if amount_ton <= 0:
        return None

    def _get_addr(obj, key: str) -> str:
        v = obj.get(key) if isinstance(obj, dict) else None
        if v is None:
            return ""
        if isinstance(v, dict):
            return (v.get("address") or v.get("value") or "").strip()
        return str(v).strip()

    recipient = _get_addr(data, "recipient") or _get_addr(data, "destination")
    sender = _get_addr(data, "sender") or _get_addr(data, "source") or _get_addr(data, "from")
    if not sender or not recipient:
        return None
    if not _addr_match(recipient, our_wallet_addr):
        return None  # not incoming to us

    txs = event.get("base_transactions") or action.get("base_transactions") or []
    tx_hash = txs[0] if txs and isinstance(txs[0], str) else None
    if not tx_hash:
        tx_hash = event.get("event_id") or event.get("hash") or action.get("event_id")
    if not tx_hash:
        norm = sender.replace("-", "").replace("_", "").strip().lower()[:20]
        tx_hash = f"{PREFIX}{norm}_{amount_raw}"
    return (amount_ton, sender, recipient, str(tx_hash))


def scan_ton_deposits() -> int:
    """
    Fetch events for our TON deposit wallet, process incoming TonTransfer.
    Match sender to TonWallet (connected user). Returns count of new deposits credited.
    """
    wallet = (settings.ton_deposit_wallet or "").strip()
    api_key = (settings.tonapi_key or "").strip()
    if not wallet:
        logger.debug("TON deposit wallet not configured, skip scan")
        return 0

    our_wallet_addr = wallet
    url = f"https://tonapi.io/v2/accounts/{wallet}/events"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params={"limit": 50}, headers=headers or None)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("TonAPI fetch TON deposits failed: %s", e)
        return 0

    events = data.get("events") or []
    credited = 0

    for ev in events:
        actions = ev.get("actions") or []
        for act in actions:
            parsed = _parse_ton_transfer(act, ev, our_wallet_addr)
            if not parsed:
                continue
            amount_ton, sender_addr, recipient_addr, tx_hash = parsed

            if _already_processed(tx_hash):
                continue

            telegram_id = _get_telegram_id_by_wallet_address(sender_addr)
            if not telegram_id:
                logger.debug("Skip TON deposit: sender %s not in TonWallet", sender_addr[:24])
                continue

            if _credit_ton(telegram_id, amount_ton, tx_hash, sender_addr, recipient_addr):
                credited += 1
                logger.info("Credited %s TON to telegram_id=%s (tx %s)", amount_ton, telegram_id, tx_hash[:20])
                _notify_ton_deposit(telegram_id, amount_ton)
            break  # one transfer per action
        # Could process multiple actions per event, but avoid double-count

    return credited


async def scan_ton_deposits_async() -> int:
    """Async wrapper for scheduler."""
    import asyncio
    return await asyncio.to_thread(scan_ton_deposits)
