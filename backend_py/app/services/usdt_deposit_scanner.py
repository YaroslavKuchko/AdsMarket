"""
USDT deposit scanner for TON network.

Polls TonAPI for incoming Jetton transfers to our USDT deposit wallet.
Memo (comment) = telegram_id to attribute deposit to user.
"""
from __future__ import annotations

import logging
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import UsdtTransaction, UserBalance
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# USDT has 6 decimals
USDT_DECIMALS = 6

# Event ID prefix for uniqueness (event_id from API can collide across accounts)
PREFIX = "usdt_"


def _get_db() -> Session:
    return SessionLocal()


def _format_usdt_amount(amount: Decimal) -> str:
    """Format USDT amount for display (e.g. 1, 10.5, 0.25)."""
    amount = amount.quantize(Decimal("0.000001"))
    if amount == amount.to_integral_value():
        return str(int(amount))
    return str(amount).rstrip("0").rstrip(".")


def _notify_usdt_deposit(telegram_id: int, amount: Decimal) -> None:
    """Send Telegram notification when USDT is credited."""
    token = (settings.tg_bot_token or "").strip()
    if not token:
        return
    amt_str = _format_usdt_amount(amount)
    text = f'<tg-emoji emoji-id="5458525793921546124">😌</tg-emoji> <b>+{amt_str} USDT зачислено на ваш баланс.</b>'
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": telegram_id, "text": text, "parse_mode": "HTML"},
            )
            resp.raise_for_status()
    except Exception as e:
        logger.warning("Failed to send USDT deposit notification to %s: %s", telegram_id, e)


def _credit_usdt(telegram_id: int, amount: Decimal, event_id: str) -> bool:
    """Credit USDT to user balance. Returns True on success."""
    db = _get_db()
    try:
        bal = db.execute(
            select(UserBalance).where(
                UserBalance.telegram_id == telegram_id,
                UserBalance.currency == "usdt",
            )
        ).scalar_one_or_none()
        if bal:
            bal.available += amount
            bal.total_deposited += amount
        else:
            bal = UserBalance(
                telegram_id=telegram_id,
                currency="usdt",
                available=amount,
                total_deposited=amount,
            )
            db.add(bal)
        tx = UsdtTransaction(
            event_id=event_id,
            telegram_id=telegram_id,
            amount=amount,
            tx_type="deposit",
            status="completed",
        )
        db.add(tx)
        db.commit()
        return True
    except Exception as e:
        logger.exception("Credit USDT: %s", e)
        db.rollback()
        return False
    finally:
        db.close()


def _already_processed(event_id: str) -> bool:
    db = _get_db()
    try:
        existing = db.execute(
            select(UsdtTransaction).where(UsdtTransaction.event_id == event_id)
        ).scalar_one_or_none()
        return existing is not None
    finally:
        db.close()


def _parse_jetton_transfer(action: dict) -> tuple[Decimal | None, str | None] | None:
    """
    Parse TonAPI JettonTransfer action. Returns (amount_usdt, memo/comment) or None.
    TonAPI v2 nests data in action["JettonTransfer"]; v1 used flat structure.
    """
    atype = action.get("type", "")
    if atype not in ("JettonTransfer", "jetton_transfer"):
        return None
    # TonAPI v2: data is nested in action["JettonTransfer"]
    jt = action.get("JettonTransfer") or action
    raw_amount = jt.get("amount")
    if raw_amount is None:
        return None
    try:
        amount = Decimal(raw_amount) / Decimal(10**USDT_DECIMALS)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    # comment / memo - can be in comment, payload, or decrypted
    comment = (
        jt.get("comment")
        or jt.get("decrypted_payload")
        or jt.get("payload")
        or action.get("comment")
        or action.get("decrypted_payload")
        or action.get("payload")
        or ""
    )
    if isinstance(comment, dict):
        comment = comment.get("text") or comment.get("comment") or ""
    memo = str(comment).strip() if comment else None
    return (amount, memo or None)


def scan_usdt_deposits() -> int:
    """
    Fetch events for our USDT deposit wallet, process incoming Jetton transfers.
    Returns count of new deposits credited.
    """
    wallet = (settings.usdt_deposit_wallet or "").strip()
    api_key = (settings.tonapi_key or "").strip()
    if not wallet:
        logger.debug("USDT deposit wallet not configured, skip scan")
        return 0

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
        logger.warning("TonAPI fetch failed: %s", e)
        return 0

    events = data.get("events") or []
    credited = 0

    for ev in events:
        ev_id = ev.get("event_id") or ev.get("hash") or str(ev.get("lt", ""))
        if not ev_id:
            continue
        unique_id = f"{PREFIX}{ev_id}"

        if _already_processed(unique_id):
            continue

        actions = ev.get("actions") or []
        for act in actions:
            parsed = _parse_jetton_transfer(act)
            if not parsed:
                continue
            amount, memo = parsed
            if not memo or not memo.isdigit():
                logger.debug("Skip deposit: no valid memo (telegram_id) in event %s", ev_id)
                continue
            try:
                telegram_id = int(memo)
            except ValueError:
                continue

            if _credit_usdt(telegram_id, amount, unique_id):
                credited += 1
                logger.info("Credited %s USDT to telegram_id=%s (event %s)", amount, telegram_id, ev_id)
                _notify_usdt_deposit(telegram_id, amount)
            break  # one transfer per event

    return credited


async def scan_usdt_deposits_async() -> int:
    """Async wrapper for scheduler."""
    import asyncio
    return await asyncio.to_thread(scan_usdt_deposits)
