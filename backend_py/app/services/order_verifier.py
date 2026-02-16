"""
Order post verification: after duration_hours (24 or 48), check that the post
is still in the channel and was not edited. Compare with stored content.
Uses Bot API forward_message - no Telethon needed.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from aiogram import Bot
from sqlalchemy import select

from app.core.config import settings
from app.db.models import Channel, ChannelAdFormat, Order
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _normalize_text(s: str) -> str:
    """Strip HTML tags and normalize whitespace for comparison."""
    if not s:
        return ""
    # Remove HTML tags
    s = re.sub(r"<[^>]+>", "", s)
    # Normalize whitespace
    return " ".join(s.split()).strip()


def _build_expected_text(order: Order, has_media: bool = False) -> str:
    """Build expected post text as stored (body + #Реклама)."""
    body = (order.post_text_html or "").strip()
    full = _normalize_text(body + "\n\n#Реклама")
    if has_media and len(full) > 1024:
        return (full[:1000] + "...").strip()
    return full


def _content_matches(expected: str, current: str, order: Order) -> bool:
    """Check if current channel content matches what we stored."""
    if not expected:
        return True
    if expected == current:
        return True
    if not current:
        return False
    if order.post_media_file_id and len(expected) > 1024:
        truncated = (expected[:1000] + "...").strip()
        if current == truncated:
            return True
        if len(current) <= 1024 and expected.startswith(current.rstrip(".")):
            return True
    return False


async def _fetch_post_content(bot: Bot, channel_telegram_id: int, message_id: int) -> tuple[bool, str]:
    """
    Forward message to get current content. Returns (exists, current_text).
    Deletes the forward after fetching.
    """
    verification_chat_id = getattr(settings, "ad_verification_channel_id", None)
    if not verification_chat_id:
        return False, ""
    try:
        fwd = await bot.forward_message(
            chat_id=verification_chat_id,
            from_chat_id=channel_telegram_id,
            message_id=message_id,
        )
        text = ""
        if fwd:
            text = (fwd.text or fwd.caption or "")
            if fwd.message_id:
                try:
                    await bot.delete_message(chat_id=verification_chat_id, message_id=fwd.message_id)
                except Exception:
                    pass
        return True, _normalize_text(text)
    except Exception as e:
        logger.debug("Forward check failed (message likely deleted): %s", e)
        return False, ""


async def _notify_post_edited(bot: Bot, order: Order, channel: Channel) -> None:
    """Notify buyer and seller that the post was edited by channel owner."""
    title = (channel.title or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    msg = (
        f'<tg-emoji emoji-id="5447644880824181073">⚠️</tg-emoji> <b>Пост был изменён</b>\n\n'
        f"<b>Владелец канала «</b><b><i>{title}</i>» изменил или удалил рекламный пост до истечения срока размещения. </b>\n"
        f"<blockquote>Сделка по заказу #{order.id} не подтверждена.</blockquote>"
    )
    try:
        if order.buyer_telegram_id:
            await bot.send_message(order.buyer_telegram_id, msg, parse_mode="HTML")
    except Exception as e:
        logger.warning("Notify buyer post edited: %s", e)
    try:
        seller_id = order.seller_telegram_id
        if seller_id and seller_id != order.buyer_telegram_id:
            await bot.send_message(seller_id, msg, parse_mode="HTML")
    except Exception as e:
        logger.warning("Notify seller post edited: %s", e)


async def verify_pending_orders(bot: Bot) -> int:
    """
    Find orders past duration_hours, verify post is still in channel (not deleted).
    Returns count of newly verified orders.
    """
    db = SessionLocal()
    verified_count = 0
    now = datetime.now(timezone.utc)

    try:
        orders = (
            db.execute(
                select(Order).where(
                    Order.status == "done",
                    Order.done_at.is_not(None),
                    Order.published_channel_message_id.is_not(None),
                    Order.verified_at.is_(None),
                )
            )
        ).scalars().all()

        for order in orders:
            fmt = (
                db.execute(select(ChannelAdFormat).where(ChannelAdFormat.id == order.format_id))
            ).scalar_one_or_none()
            duration_hours = fmt.duration_hours if fmt else 24

            if not order.done_at:
                continue
            done_at = order.done_at
            if done_at.tzinfo is None:
                done_at = done_at.replace(tzinfo=timezone.utc)
            elapsed = (now - done_at).total_seconds()
            required = duration_hours * 3600
            if elapsed < required - 60:
                continue

            channel = (
                db.execute(select(Channel).where(Channel.id == order.channel_id))
            ).scalar_one_or_none()
            if not channel:
                logger.warning("Order %s: channel not found", order.id)
                continue

            exists, current_text = await _fetch_post_content(
                bot, channel.telegram_id, order.published_channel_message_id
            )
            if not exists:
                logger.warning("Order %s: post missing in channel %s", order.id, channel.title)
                continue
            has_media = bool(order.post_media_file_id)
            expected = _build_expected_text(order, has_media)
            if expected and not _content_matches(expected, current_text, order):
                logger.warning(
                    "Order %s: post was edited in channel %s (expected len=%s, got len=%s)",
                    order.id,
                    channel.title,
                    len(expected),
                    len(current_text),
                )
                await _notify_post_edited(bot, order, channel)
                continue
            order.verified_at = now
            db.commit()
            verified_count += 1
            logger.info("Order %s verified: post unchanged after %sh", order.id, duration_hours)

    except Exception as e:
        logger.exception("Order verification failed: %s", e)
        db.rollback()
    finally:
        db.close()

    return verified_count
