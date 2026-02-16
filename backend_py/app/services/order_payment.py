"""
Order payment: freeze on create, release to seller on done, refund on cancel.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Order, UserBalance
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _get_db() -> Session:
    return SessionLocal()


def freeze_for_order(
    telegram_id: int, currency: str, amount: Decimal
) -> bool:
    """Deduct from available, add to frozen. Returns True on success."""
    db = _get_db()
    try:
        bal = db.execute(
            select(UserBalance)
            .where(
                UserBalance.telegram_id == telegram_id,
                UserBalance.currency == currency,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if not bal:
            return False
        if bal.available < amount:
            return False
        bal.available -= amount
        bal.frozen += amount
        db.commit()
        logger.info("Frozen %s %s for telegram_id=%s", amount, currency, telegram_id)
        return True
    except Exception as e:
        logger.exception("Freeze order payment: %s", e)
        db.rollback()
        return False
    finally:
        db.close()


def release_to_seller(order_id: int) -> bool:
    """On order done: unfreeze from buyer, credit seller."""
    db = _get_db()
    try:
        order = db.execute(
            select(Order).where(Order.id == order_id)
        ).scalar_one_or_none()
        if not order or not order.payment_currency or order.payment_amount is None:
            return True  # legacy order, nothing to do
        if order.status != "done":
            return False

        curr = order.payment_currency
        amt = order.payment_amount

        buyer_bal = db.execute(
            select(UserBalance)
            .where(
                UserBalance.telegram_id == order.buyer_telegram_id,
                UserBalance.currency == curr,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if not buyer_bal or buyer_bal.frozen < amt:
            logger.warning("Order %s: buyer frozen insufficient", order_id)
            return False

        buyer_bal.frozen -= amt

        seller_bal = db.execute(
            select(UserBalance)
            .where(
                UserBalance.telegram_id == order.seller_telegram_id,
                UserBalance.currency == curr,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if seller_bal:
            seller_bal.available += amt
        else:
            seller_bal = UserBalance(
                telegram_id=order.seller_telegram_id,
                currency=curr,
                available=amt,
                frozen=Decimal("0"),
            )
            db.add(seller_bal)

        db.commit()
        logger.info("Released %s %s to seller %s (order %s)", amt, curr, order.seller_telegram_id, order_id)
        return True
    except Exception as e:
        logger.exception("Release order payment: %s", e)
        db.rollback()
        return False
    finally:
        db.close()


def refund_to_buyer(order_id: int) -> bool:
    """On order cancelled: unfreeze from buyer, add back to available."""
    db = _get_db()
    try:
        order = db.execute(
            select(Order).where(Order.id == order_id)
        ).scalar_one_or_none()
        if not order or not order.payment_currency or order.payment_amount is None:
            return True

        curr = order.payment_currency
        amt = order.payment_amount

        buyer_bal = db.execute(
            select(UserBalance)
            .where(
                UserBalance.telegram_id == order.buyer_telegram_id,
                UserBalance.currency == curr,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if not buyer_bal or buyer_bal.frozen < amt:
            logger.warning("Order %s: buyer frozen insufficient for refund", order_id)
            return False

        buyer_bal.frozen -= amt
        buyer_bal.available += amt
        db.commit()
        logger.info("Refunded %s %s to buyer %s (order %s)", amt, curr, order.buyer_telegram_id, order_id)
        return True
    except Exception as e:
        logger.exception("Refund order payment: %s", e)
        db.rollback()
        return False
    finally:
        db.close()
