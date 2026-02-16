"""Orders API: create order (with balance payment), list orders, get order details."""
from __future__ import annotations

import json
import secrets
import string
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_telegram_id
from app.core.bot_username import get_bot_username
from app.db.models import Channel, ChannelAdFormat, Order, ReferralSettings, UserBalance
from app.db.session import get_db
from app.services.order_payment import freeze_for_order, refund_to_buyer

router = APIRouter(prefix="/api/orders", tags=["orders"])


class CreateOrderIn(BaseModel):
    channelId: int
    formatId: int
    currency: str = Field(..., pattern="^(stars|usdt|ton)$", description="Payment currency")


class OrderOut(BaseModel):
    id: int
    orderId: int
    channelId: int
    channelTitle: str
    formatTitle: str
    status: str
    createdAtIso: str
    total: float | None
    totalStars: int | None
    totalTon: float | None = None
    writePostLink: str | None = None
    # Seller: link to view/approve post in bot (pending_seller only)
    sellerViewPostLink: str | None = None
    # True if current user is the seller (channel owner)
    isSeller: bool = False
    # When order was completed (seller approved); for seller UI "money after X"
    doneAtIso: str | None = None
    # From format settings: if true, seller sees "ожидайте зачисление после времени"
    autopostEnabled: bool = False
    # Link to published post in channel (when done)
    publishedPostLink: str | None = None
    # When post was verified (24h/48h - not deleted, not edited)
    verifiedAtIso: str | None = None

    class Config:
        from_attributes = True


def _format_title(f: ChannelAdFormat) -> str:
    kind = "Пост" if f.format_type == "post" else f.format_type
    return f"{kind} · {f.duration_hours}ч"


def _generate_post_token() -> str:
    """Generate 8-char alphanumeric secret token."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def _build_write_post_link(order: Order) -> str:
    bot = get_bot_username()
    token = order.post_token or str(order.id)  # fallback for existing orders
    return f"https://t.me/{bot}?start=post_{token}"


def _build_seller_view_post_link(order_id: int) -> str:
    bot = get_bot_username()
    return f"https://t.me/{bot}?start=seller_post_{order_id}"


def _get_ton_price_for_usdt(usdt: Decimal, db: Session) -> Decimal:
    """Convert USDT amount to TON using referral_settings.ton_usd_price."""
    rs = db.execute(select(ReferralSettings).where(ReferralSettings.id == 1)).scalar_one_or_none()
    rate = Decimal("5.0")
    if rs and rs.ton_usd_price and rs.ton_usd_price > 0:
        rate = rs.ton_usd_price
    return (usdt / rate).quantize(Decimal("0.01"))


@router.post("", response_model=OrderOut)
def create_order(
    body: CreateOrderIn,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> OrderOut:
    """Create an order with balance payment. Funds are frozen until post is published or deal cancelled."""
    channel = db.execute(
        select(Channel).where(
            Channel.id == body.channelId,
            Channel.status == "active",
            Channel.is_visible.is_(True),
        )
    ).scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found or not available")

    if channel.owner_telegram_id == telegram_id:
        raise HTTPException(
            status_code=400,
            detail="Нельзя заказать рекламу в своём канале.",
        )

    fmt = db.execute(
        select(ChannelAdFormat).where(
            ChannelAdFormat.id == body.formatId,
            ChannelAdFormat.channel_id == body.channelId,
            ChannelAdFormat.is_enabled.is_(True),
        )
    ).scalar_one_or_none()
    if not fmt:
        raise HTTPException(status_code=400, detail="Format not found or not enabled")

    currency = body.currency
    amount: Decimal

    if currency == "stars":
        if not fmt.price_stars or fmt.price_stars <= 0:
            raise HTTPException(
                status_code=400,
                detail="Оплата Stars недоступна — продавец не указал цену в Stars.",
            )
        amount = Decimal(fmt.price_stars)
    elif currency == "usdt":
        if not fmt.price_usdt or fmt.price_usdt <= 0:
            raise HTTPException(
                status_code=400,
                detail="Оплата USDT недоступна — продавец не указал цену в USDT.",
            )
        amount = fmt.price_usdt
    else:  # ton
        if not fmt.price_usdt or fmt.price_usdt <= 0:
            raise HTTPException(
                status_code=400,
                detail="Оплата TON рассчитывается из USDT — продавец не указал цену в USDT.",
            )
        amount = _get_ton_price_for_usdt(fmt.price_usdt, db)

    if not freeze_for_order(telegram_id, currency, amount):
        bal = db.execute(
            select(UserBalance).where(
                UserBalance.telegram_id == telegram_id,
                UserBalance.currency == currency,
            )
        ).scalar_one_or_none()
        avail = float(bal.available) if bal else 0
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно средств. Нужно: {amount} {currency.upper()}. Доступно: {avail:.2f}",
        )

    post_token = _generate_post_token()
    order = Order(
        channel_id=channel.id,
        format_id=fmt.id,
        buyer_telegram_id=telegram_id,
        seller_telegram_id=channel.owner_telegram_id,
        status="writing_post",
        post_token=post_token,
        payment_currency=currency,
        payment_amount=amount,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    total_usdt = float(fmt.price_usdt) if fmt.price_usdt else None
    total_stars = fmt.price_stars if fmt.price_stars else None
    total_ton = float(_get_ton_price_for_usdt(fmt.price_usdt, db)) if fmt.price_usdt else None

    return OrderOut(
        id=order.id,
        orderId=order.id,
        channelId=order.channel_id,
        channelTitle=channel.title,
        formatTitle=_format_title(fmt),
        status=order.status,
        createdAtIso=order.created_at.isoformat(),
        total=total_usdt,
        totalStars=total_stars,
        totalTon=total_ton,
        writePostLink=_build_write_post_link(order),
    )


def _order_done_at_iso(order: Order) -> str | None:
    """Safe access for done_at (column may be missing before migration)."""
    done_at = getattr(order, "done_at", None)
    return done_at.isoformat() if done_at else None


def _order_verified_at_iso(order: Order) -> str | None:
    """Safe access for verified_at."""
    verified_at = getattr(order, "verified_at", None)
    return verified_at.isoformat() if verified_at else None


@router.get("", response_model=list[OrderOut])
def list_orders(
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> list[OrderOut]:
    """List orders where current user is buyer or seller."""
    try:
        orders = (
            db.execute(
                select(Order)
                .where(or_(Order.buyer_telegram_id == telegram_id, Order.seller_telegram_id == telegram_id))
                .order_by(Order.created_at.desc())
            )
            .scalars()
            .all()
        )
    except Exception as e:
        err = str(e).lower()
        if "done_at" in err or "seller_revision" in err or "column" in err:
            raise HTTPException(
                status_code=503,
                detail="Требуется обновление БД. Выполните: backend_py/migrations/add_order_seller_fields.sql",
            ) from e
        raise

    result = []
    for order in orders:
        ch = db.execute(select(Channel).where(Channel.id == order.channel_id)).scalar_one_or_none()
        fmt = db.execute(select(ChannelAdFormat).where(ChannelAdFormat.id == order.format_id)).scalar_one_or_none()
        channel_title = ch.title if ch else ""
        format_title = _format_title(fmt) if fmt else ""
        total_usdt = float(fmt.price_usdt) if fmt and fmt.price_usdt else None
        total_stars = fmt.price_stars if fmt and fmt.price_stars else None
        total_ton = float(_get_ton_price_for_usdt(fmt.price_usdt, db)) if fmt and fmt.price_usdt else None
        write_link = None
        if order.status == "writing_post" and order.buyer_telegram_id == telegram_id:
            write_link = _build_write_post_link(order)
        seller_view_link = None
        if order.status == "pending_seller" and order.seller_telegram_id == telegram_id:
            seller_view_link = _build_seller_view_post_link(order.id)
        is_seller = order.seller_telegram_id == telegram_id
        done_at_iso = _order_done_at_iso(order)
        verified_at_iso = _order_verified_at_iso(order)
        autopost = False
        if fmt and fmt.settings:
            try:
                settings = json.loads(fmt.settings)
                autopost = settings.get("autoPost") or settings.get("postingMode") == "auto"
            except (json.JSONDecodeError, TypeError):
                pass
        published_link = getattr(order, "published_post_link", None)

        result.append(
            OrderOut(
                id=order.id,
                orderId=order.id,
                channelId=order.channel_id,
                channelTitle=channel_title,
                formatTitle=format_title,
                status=order.status,
                createdAtIso=order.created_at.isoformat(),
                total=total_usdt,
                totalStars=total_stars,
                totalTon=total_ton,
                writePostLink=write_link,
                sellerViewPostLink=seller_view_link,
                isSeller=is_seller,
                doneAtIso=done_at_iso,
                autopostEnabled=autopost,
                publishedPostLink=published_link,
                verifiedAtIso=verified_at_iso,
            )
        )
    return result


@router.post("/{order_id}/cancel")
def cancel_order(
    order_id: int,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> dict:
    """Buyer cancels order (writing_post or pending_seller). Refunds frozen funds."""
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.buyer_telegram_id != telegram_id:
        raise HTTPException(status_code=403, detail="Not your order")
    if order.status not in ("writing_post", "pending_seller"):
        raise HTTPException(status_code=400, detail="Order cannot be cancelled in this status")

    order.status = "cancelled"
    db.commit()

    refund_to_buyer(order_id)

    return {"ok": True, "status": "cancelled"}


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> OrderOut:
    """Get single order (buyer or seller only)."""
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.buyer_telegram_id != telegram_id and order.seller_telegram_id != telegram_id:
        raise HTTPException(status_code=403, detail="Not your order")

    ch = db.execute(select(Channel).where(Channel.id == order.channel_id)).scalar_one_or_none()
    fmt = db.execute(select(ChannelAdFormat).where(ChannelAdFormat.id == order.format_id)).scalar_one_or_none()
    channel_title = ch.title if ch else ""
    format_title = _format_title(fmt) if fmt else ""
    total_usdt = float(fmt.price_usdt) if fmt and fmt.price_usdt else None
    total_stars = fmt.price_stars if fmt and fmt.price_stars else None
    total_ton = float(_get_ton_price_for_usdt(fmt.price_usdt, db)) if fmt and fmt.price_usdt else None
    write_link = None
    if order.status == "writing_post" and order.buyer_telegram_id == telegram_id:
        write_link = _build_write_post_link(order)
    seller_view_link = None
    if order.status == "pending_seller" and order.seller_telegram_id == telegram_id:
        seller_view_link = _build_seller_view_post_link(order.id)
    is_seller = order.seller_telegram_id == telegram_id
    done_at_iso = _order_done_at_iso(order)
    verified_at_iso = _order_verified_at_iso(order)
    autopost = False
    if fmt and fmt.settings:
        try:
            settings = json.loads(fmt.settings)
            autopost = settings.get("autoPost") or settings.get("postingMode") == "auto"
        except (json.JSONDecodeError, TypeError):
            pass
    published_link = getattr(order, "published_post_link", None)

    return OrderOut(
        id=order.id,
        orderId=order.id,
        channelId=order.channel_id,
        channelTitle=channel_title,
        formatTitle=format_title,
        status=order.status,
        createdAtIso=order.created_at.isoformat(),
        total=total_usdt,
        totalStars=total_stars,
        totalTon=total_ton,
        writePostLink=write_link,
        sellerViewPostLink=seller_view_link,
        isSeller=is_seller,
        doneAtIso=done_at_iso,
        autopostEnabled=autopost,
        publishedPostLink=published_link,
        verifiedAtIso=verified_at_iso,
    )
