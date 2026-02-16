"""Stars payment: create invoice, list transactions, refund."""
from __future__ import annotations

import time

from aiogram import Bot
from aiogram.types import LabeledPrice
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_telegram_id
from app.core.config import settings
from app.core.stars_rate import get_stars_per_usd
from app.db.models import StarsTransaction, UserBalance
from app.db.session import get_db
from decimal import Decimal

router = APIRouter(prefix="/api/stars", tags=["stars"])


class CreateInvoiceIn(BaseModel):
    amount: int = Field(ge=1, le=100_000, description="Amount in Stars (1–100,000)")


@router.post("/create-invoice")
async def create_stars_invoice(
    body: CreateInvoiceIn,
    telegram_id: int = Depends(get_current_user_telegram_id),
) -> dict:
    """
    Create a Telegram Stars invoice link for top-up.
    Returns invoice URL to open via WebApp.openInvoice().
    """
    bot = Bot(token=settings.tg_bot_token)
    payload = f"topup_{telegram_id}_{body.amount}_{int(time.time())}"
    try:
        link = await bot.create_invoice_link(
            title="Пополнение баланса Stars",
            description=f"Покупка {body.amount} Stars для AdMarketplace",
            payload=payload,
            currency="XTR",
            provider_token="",
            prices=[LabeledPrice(label="Stars", amount=body.amount)],
        )
        return {"invoiceUrl": link}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create invoice: {e}")
    finally:
        await bot.session.close()


@router.get("/transactions")
async def list_stars_transactions(
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> dict:
    """List user's Stars transactions (for history and refund requests)."""
    rows = db.execute(
        select(StarsTransaction)
        .where(StarsTransaction.telegram_id == telegram_id)
        .order_by(StarsTransaction.created_at.desc())
        .limit(100)
    ).scalars().all()
    return {
        "transactions": [
            {
                "id": t.id,
                "amount": t.amount,
                "status": t.status,
                "createdAt": t.created_at.isoformat() if t.created_at else None,
            }
            for t in rows
        ]
    }


class RefundIn(BaseModel):
    transactionId: int = Field(..., description="Stars transaction ID to refund")


@router.post("/refund")
async def refund_stars(
    body: RefundIn,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> dict:
    """
    Refund a Stars top-up. User must own the transaction.
    Uses Telegram refundStarPayment; deducts from user balance.
    """
    tx = db.execute(
        select(StarsTransaction).where(StarsTransaction.id == body.transactionId)
    ).scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.telegram_id != telegram_id:
        raise HTTPException(status_code=403, detail="Not your transaction")
    if tx.status != "completed":
        raise HTTPException(status_code=400, detail=f"Transaction status is {tx.status}")
    bal = db.execute(
        select(UserBalance).where(
            UserBalance.telegram_id == telegram_id,
            UserBalance.currency == "stars",
        )
    ).scalar_one_or_none()
    if not bal or bal.available < Decimal(tx.amount):
        raise HTTPException(status_code=400, detail="Insufficient balance to process refund")
    bot = Bot(token=settings.tg_bot_token)
    try:
        ok = await bot.refund_star_payment(
            user_id=telegram_id,
            telegram_payment_charge_id=tx.telegram_payment_charge_id,
        )
        if not ok:
            raise HTTPException(status_code=500, detail="Telegram refused refund")
        bal.available -= Decimal(tx.amount)
        bal.total_deposited -= Decimal(tx.amount)
        tx.status = "refunded"
        db.commit()
        return {"ok": True, "message": "Refund completed"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await bot.session.close()


class ExchangeIn(BaseModel):
    amount: int = Field(ge=1, description="Amount in Stars to exchange for USDT")


@router.post("/exchange")
async def exchange_stars_to_usdt(
    body: ExchangeIn,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> dict:
    """
    Exchange Stars for USDT. Uses same rate as ad format (stars_per_usd).
    1 USD = stars_per_usd Stars → 1 Star = 1/stars_per_usd USDT.
    """
    stars_per_usd = get_stars_per_usd()
    usdt_amount = Decimal(body.amount) / Decimal(stars_per_usd)
    usdt_amount = usdt_amount.quantize(Decimal("0.01"))

    stars_bal = db.execute(
        select(UserBalance).where(
            UserBalance.telegram_id == telegram_id,
            UserBalance.currency == "stars",
        )
    ).scalar_one_or_none()

    if not stars_bal or stars_bal.available < Decimal(body.amount):
        raise HTTPException(status_code=400, detail="Insufficient Stars balance")

    usdt_bal = db.execute(
        select(UserBalance).where(
            UserBalance.telegram_id == telegram_id,
            UserBalance.currency == "usdt",
        )
    ).scalar_one_or_none()

    try:
        stars_bal.available -= Decimal(body.amount)
        if usdt_bal:
            usdt_bal.available += usdt_amount
            usdt_bal.total_deposited += usdt_amount
        else:
            db.add(
                UserBalance(
                    telegram_id=telegram_id,
                    currency="usdt",
                    available=usdt_amount,
                    total_deposited=usdt_amount,
                )
            )
        db.commit()
        return {
            "ok": True,
            "starsSpent": body.amount,
            "usdtReceived": float(usdt_amount),
            "rate": stars_per_usd,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
