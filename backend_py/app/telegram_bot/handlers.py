"""Handlers for ad post flow: /start post_{order_id}, seller_post_{order_id}, etc."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from decimal import Decimal
from datetime import datetime, timezone

import httpx
from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, ChatMemberUpdated, InlineKeyboardButton, InlineKeyboardMarkup, Message, PreCheckoutQuery, WebAppInfo
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.bot_username import get_bot_username
from app.core.config import settings
from app.db.models import Channel, ChannelAdFormat, Order, StarsTransaction, UserBalance
from app.db.session import SessionLocal
from app.telegram_bot.fsm import PostFlow, SellerFlow

logger = logging.getLogger(__name__)
router = Router()


def _get_db() -> Session:
    return SessionLocal()


def _get_order_and_channel(order_id: int) -> tuple[Order | None, Channel | None]:
    db = _get_db()
    try:
        order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not order:
            return None, None
        channel = db.execute(select(Channel).where(Channel.id == order.channel_id)).scalar_one_or_none()
        return order, channel
    finally:
        db.close()


def _get_order_format(order_id: int) -> ChannelAdFormat | None:
    """Get the ad format for an order."""
    db = _get_db()
    try:
        order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not order:
            return None
        return db.execute(
            select(ChannelAdFormat).where(ChannelAdFormat.id == order.format_id)
        ).scalar_one_or_none()
    finally:
        db.close()


def _get_order_and_channel_by_post_ref(ref: str) -> tuple[Order | None, Channel | None]:
    """Resolve post_ ref (token or legacy order_id) to (order, channel)."""
    ref = (ref or "").strip()
    if not ref:
        return None, None
    db = _get_db()
    try:
        order = None
        try:
            order_id = int(ref)
            order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        except ValueError:
            order = db.execute(select(Order).where(Order.post_token == ref)).scalar_one_or_none()
        if not order:
            return None, None
        channel = db.execute(select(Channel).where(Channel.id == order.channel_id)).scalar_one_or_none()
        return order, channel
    finally:
        db.close()


def _update_order_post(order_id: int, post_text_html: str | None, post_media_file_id: str | None) -> bool:
    db = _get_db()
    try:
        order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not order:
            return False
        order.post_text_html = post_text_html
        order.post_media_file_id = post_media_file_id
        db.commit()
        return True
    except Exception as e:
        logger.exception("Update order post: %s", e)
        db.rollback()
        return False
    finally:
        db.close()


def _update_order_button(order_id: int, name: str | None, url: str | None) -> bool:
    db = _get_db()
    try:
        order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not order:
            return False
        order.post_button_name = name
        order.post_button_url = url
        db.commit()
        return True
    except Exception as e:
        logger.exception("Update order button: %s", e)
        db.rollback()
        return False
    finally:
        db.close()


def _set_order_pending_seller(order_id: int) -> bool:
    db = _get_db()
    try:
        order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not order:
            return False
        order.status = "pending_seller"
        db.commit()
        return True
    except Exception as e:
        logger.exception("Set order pending_seller: %s", e)
        db.rollback()
        return False
    finally:
        db.close()


def _clear_order_draft(order_id: int) -> bool:
    db = _get_db()
    try:
        order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not order:
            return False
        order.post_text_html = None
        order.post_media_file_id = None
        order.post_button_name = None
        order.post_button_url = None
        db.commit()
        return True
    except Exception as e:
        logger.exception("Clear order draft: %s", e)
        db.rollback()
        return False
    finally:
        db.close()


def _get_order(order_id: int) -> Order | None:
    db = _get_db()
    try:
        return db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    finally:
        db.close()


def _set_order_done(
    order_id: int,
    published_post_link: str | None = None,
    published_channel_message_id: int | None = None,
) -> bool:
    from app.services.order_payment import release_to_seller
    db = _get_db()
    try:
        order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not order:
            return False
        order.status = "done"
        order.done_at = datetime.now(timezone.utc)
        order.seller_revision_comment = None
        if published_post_link is not None:
            order.published_post_link = published_post_link
        if published_channel_message_id is not None:
            order.published_channel_message_id = published_channel_message_id
        db.commit()
        release_to_seller(order_id)
        return True
    except Exception as e:
        logger.exception("Set order done: %s", e)
        db.rollback()
        return False
    finally:
        db.close()


def _set_order_revision(order_id: int, comment: str) -> bool:
    db = _get_db()
    try:
        order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not order:
            return False
        order.status = "writing_post"
        order.seller_revision_comment = comment
        db.commit()
        return True
    except Exception as e:
        logger.exception("Set order revision: %s", e)
        db.rollback()
        return False
    finally:
        db.close()


def _set_order_cancelled(order_id: int) -> bool:
    from app.services.order_payment import refund_to_buyer
    db = _get_db()
    try:
        order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
        if not order:
            return False
        order.status = "cancelled"
        db.commit()
        refund_to_buyer(order_id)
        return True
    except Exception as e:
        logger.exception("Set order cancelled: %s", e)
        db.rollback()
        return False
    finally:
        db.close()


# --- Inline keyboards ---

def _kb_pause(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пауза", callback_data=f"pause_{order_id}")],
    ])


def _kb_skip_button(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data=f"skip_btn_{order_id}")],
    ])


def _kb_agree_redo(order_id: int, order: Order | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if order and order.post_button_name and order.post_button_url:
        rows.append([InlineKeyboardButton(text=order.post_button_name, url=order.post_button_url)])
    rows.append([
        InlineKeyboardButton(text="Согласен", callback_data=f"agree_{order_id}"),
        InlineKeyboardButton(text="Переделать", callback_data=f"redo_{order_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _kb_seller_actions(order_id: int, order: Order | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if order and order.post_button_name and order.post_button_url:
        rows.append([InlineKeyboardButton(text=order.post_button_name, url=order.post_button_url)])
    rows.extend([
        [InlineKeyboardButton(text="Отправить", callback_data=f"seller_approve_{order_id}")],
        [InlineKeyboardButton(text="Отправить на доработку", callback_data=f"seller_revision_{order_id}")],
        [InlineKeyboardButton(text="Отказаться", callback_data=f"seller_decline_{order_id}")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _kb_post_button(order: Order | None) -> InlineKeyboardMarkup | None:
    """Keyboard with only the ad button for publishing to channel."""
    if not order or not order.post_button_name or not order.post_button_url:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=order.post_button_name, url=order.post_button_url)]
    ])


# --- Handlers ---


def _get_webapp_url() -> str:
    """HTTPS URL for opening Web App (web_app=, Menu Button). Must be https://."""
    url = settings.webapp_url
    if url.startswith("https://"):
        return url
    if url.startswith("http://"):
        return url.replace("http://", "https://", 1)
    # t.me/bot/app - cannot use for web_app; fallback to production domain
    if url.startswith("t.me/"):
        return "https://adsmarket.app"
    return f"https://{url}"


def _get_webapp_orders_url() -> str:
    """t.me link to Mini App orders section: https://t.me/ads_marketplacebot/adsmarket?startapp=orders"""
    url = (settings.webapp_url or "").strip()
    if url.startswith("t.me/"):
        base = "https://" + url.rstrip("/")
    elif url.startswith("https://t.me/"):
        base = url.rstrip("/")
    else:
        base = f"https://t.me/{get_bot_username()}/adsmarket"
    base = base.replace("/admarket", "/adsmarket")  # ensure correct app slug
    return f"{base}?startapp=orders" if "?" not in base else f"{base}&startapp=orders"


def _lang_ru(user) -> bool:
    return bool(user and getattr(user, "language_code") and str(user.language_code).lower().startswith("ru"))


def _html_title(title: str) -> str:
    """Escape channel title for HTML."""
    return title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _channel_title_html(title: str, emoji_status_id: str | None = None) -> str:
    """Channel title for HTML messages, optionally with premium emoji."""
    t = _html_title(title)
    if emoji_status_id:
        return f'<i>{t}</i> <tg-emoji emoji-id="{emoji_status_id}">⏳</tg-emoji>'
    return f"<i>{t}</i>"


async def _get_channel_custom_emoji_id(
    chat_id: int,
    bot: Bot,
    channel_title: str,
    from_user: object | None,
    *,
    fetch_photo: bool = True,
) -> str | None:
    """Get custom_emoji_id for channel: from DB, or create from photo if possible."""
    db = _get_db()
    try:
        channel = db.execute(select(Channel).where(Channel.telegram_id == chat_id)).scalar_one_or_none()
        if channel and channel.custom_emoji_id:
            return channel.custom_emoji_id
    finally:
        db.close()
    if not fetch_photo or not from_user:
        return None
    try:
        chat_info = await bot.get_chat(chat_id)
        if not chat_info.photo:
            return getattr(chat_info, "emoji_status_custom_emoji_id", None) or None
        file = await bot.get_file(chat_info.photo.big_file_id)
        if not file.file_path:
            return getattr(chat_info, "emoji_status_custom_emoji_id", None) or None
        photo_resp = await httpx.AsyncClient(timeout=15.0).get(
            f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        )
        if photo_resp.status_code != 200:
            return getattr(chat_info, "emoji_status_custom_emoji_id", None) or None
        from app.services.channel_emoji import create_channel_emoji_from_photo

        emoji_id = await create_channel_emoji_from_photo(
            bot.token,
            photo_resp.content,
            getattr(from_user, "id", 0),
            chat_id,
        )
        if emoji_id:
            db = _get_db()
            try:
                ch = db.execute(select(Channel).where(Channel.telegram_id == chat_id)).scalar_one_or_none()
                if ch:
                    ch.custom_emoji_id = emoji_id
                    db.commit()
            finally:
                db.close()
        return emoji_id or (getattr(chat_info, "emoji_status_custom_emoji_id", None) or None)
    except Exception as e:
        logger.debug("_get_channel_custom_emoji_id: %s", e)
        return None


# Premium Telegram emoji (custom emoji with emoji-id)
_TG_EMOJI_OK = '<tg-emoji emoji-id="5305417687357203905">✅</tg-emoji>'
_TG_EMOJI_CROSS = '<tg-emoji emoji-id="5429452773747860261">❌</tg-emoji>'
_TG_EMOJI_WARN = '<tg-emoji emoji-id="5447644880824181073">⚠️</tg-emoji>'
_TG_EMOJI_MEGAPHONE = '<tg-emoji emoji-id="5305417940760273444">📢</tg-emoji>'
_TG_EMOJI_CHAT = '<tg-emoji emoji-id="5818740758257077530">💬</tg-emoji>'
_TG_EMOJI_CHAT_COMMENT = '<tg-emoji emoji-id="5974187156686507310">💬</tg-emoji>'
_TG_EMOJI_POINT = '<tg-emoji emoji-id="5305244857873214182">👉</tg-emoji>'
_TG_EMOJI_WRENCH = '<tg-emoji emoji-id="5323267236431929679">🔩</tg-emoji>'
_TG_EMOJI_BUTTON = '<tg-emoji emoji-id="4970142833605345805">🔘</tg-emoji>'
_TG_EMOJI_CHAT_INPUT = '<tg-emoji emoji-id="6012499476147604376">💬</tg-emoji>'
_TG_EMOJI_SEND = '<tg-emoji emoji-id="5062291541624619917">✈️</tg-emoji>'
_TG_EMOJI_STORE = '<tg-emoji emoji-id="5208573502046610594">🏪</tg-emoji>'
_TG_EMOJI_TON = '<tg-emoji emoji-id="5467756490389469348">😤</tg-emoji>'
_TG_EMOJI_USDT = '<tg-emoji emoji-id="5458525793921546124">😌</tg-emoji>'
_TG_EMOJI_STAR = '<tg-emoji emoji-id="5972187557352443077">⭐️</tg-emoji>'
_TG_EMOJI_POINT_DOWN = '<tg-emoji emoji-id="5231102735817918643">👇</tg-emoji>'


@router.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated, bot: Bot) -> None:
    """Handle bot added/removed/demoted/restored in channel or supergroup."""
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    chat = event.chat
    from_user = event.from_user

    if chat.type not in ("channel", "supergroup"):
        return

    channel_title = chat.title or "Unknown"
    api_base = settings.api_base_url.rstrip("/")
    headers = {"content-type": "application/json"}
    if settings.internal_secret:
        headers["x-internal-secret"] = settings.internal_secret
    lang = "ru" if _lang_ru(from_user) else "en"

    async def _notify_channel_added(payload: dict) -> dict | None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(f"{api_base}/api/internal/channel-added", json=payload, headers=headers)
            if not res.is_success:
                logger.error("channel-added API failed: %s %s", res.status_code, res.text)
                return None
            return res.json()

    async def _notify_channel_removed() -> dict | None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(f"{api_base}/api/internal/channel-removed", json={"chatId": chat.id}, headers=headers)
            if not res.is_success:
                return None
            return res.json()

    async def _notify_channel_demoted() -> dict | None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(f"{api_base}/api/internal/channel-demoted", json={"chatId": chat.id}, headers=headers)
            if not res.is_success:
                return None
            return res.json()

    # Bot was added as admin
    if old_status in ("left", "kicked") and new_status == "administrator":
        logger.info("Bot added to %s «%s» by user %s", chat.type, channel_title, from_user.id if from_user else 0)
        try:
            subscriber_count: int | None = None
            try:
                subscriber_count = await bot.get_chat_member_count(chat.id)
            except Exception:
                pass
            invite_link: str | None = None
            if not getattr(chat, "username", None):
                try:
                    invite_link = await bot.export_chat_invite_link(chat.id)
                except Exception:
                    pass
            photo_url: str | None = None
            custom_emoji_id: str | None = None
            try:
                chat_info = await bot.get_chat(chat.id)
                if chat_info.photo:
                    file = await bot.get_file(chat_info.photo.big_file_id)
                    photo_url = file.file_path and f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
                    # Create custom emoji from channel photo
                    if from_user and file.file_path:
                        try:
                            photo_resp = await httpx.AsyncClient(timeout=15.0).get(
                                f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
                            )
                            if photo_resp.status_code == 200:
                                from app.services.channel_emoji import create_channel_emoji_from_photo

                                custom_emoji_id = await create_channel_emoji_from_photo(
                                    bot.token,
                                    photo_resp.content,
                                    from_user.id,
                                    chat.id,
                                )
                        except Exception as e:
                            logger.debug("Could not create channel emoji from photo: %s", e)
                    if not custom_emoji_id:
                        custom_emoji_id = getattr(chat_info, "emoji_status_custom_emoji_id", None) or None
                else:
                    custom_emoji_id = getattr(chat_info, "emoji_status_custom_emoji_id", None) or None
            except Exception:
                pass
            payload = {
                "chatId": chat.id,
                "chatType": chat.type,
                "title": channel_title,
                "username": getattr(chat, "username", None),
                "subscriberCount": subscriber_count,
                "addedByTelegramId": from_user.id if from_user else 0,
                "inviteLink": invite_link,
                "photoUrl": photo_url,
                "customEmojiId": custom_emoji_id,
            }
            if await _notify_channel_added(payload):
                t_html = _channel_title_html(channel_title, custom_emoji_id)
                if lang == "ru":
                    msg = f'{_TG_EMOJI_OK} <b>Бот добавлен в канал</b> «{t_html}».\n<blockquote>Теперь откройте приложение, чтобы настроить канал.</blockquote>'
                else:
                    msg = f'{_TG_EMOJI_OK} <b>Bot added to channel</b> "{t_html}".\n<blockquote>Now open the app to configure the channel.</blockquote>'
                btn_text = "Открыть приложение" if lang == "ru" else "Open App"
                app_url = _get_webapp_url()
                try:
                    btn = InlineKeyboardButton(text=btn_text, web_app=WebAppInfo(url=app_url))
                    await bot.send_message(
                        from_user.id if from_user else 0,
                        msg,
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn]]),
                    )
                except Exception as e:
                    logger.warning("Could not send DM with button: %s", e)
                    try:
                        await bot.send_message(from_user.id if from_user else 0, msg, parse_mode="HTML")
                    except Exception as e2:
                        logger.warning("Could not send DM at all: %s", e2)
        except Exception as e:
            logger.exception("Failed to process channel addition: %s", e)
        return

    # Bot was demoted (lost admin, still in channel)
    if old_status == "administrator" and new_status in ("member", "restricted"):
        logger.info("Bot demoted in channel «%s»", channel_title)
        try:
            emoji_id: str | None = _get_channel_custom_emoji_id(chat.id, bot, channel_title, from_user)
            result = await _notify_channel_demoted()
            if result and result.get("ownerTelegramId"):
                t_html = _channel_title_html(channel_title, emoji_id)
                if lang == "ru":
                    msg = f'{_TG_EMOJI_WARN} <b>Бот лишён прав администратора</b> в канале «{t_html}».\n<blockquote>Канал временно неактивен. Верните боту права администратора.</blockquote>'
                else:
                    msg = f'{_TG_EMOJI_WARN} <b>Bot lost admin rights</b> in channel "{t_html}".\n<blockquote>Channel is temporarily inactive. Restore bot\'s admin rights.</blockquote>'
                try:
                    await bot.send_message(result["ownerTelegramId"], msg, parse_mode="HTML")
                except Exception:
                    pass
        except Exception as e:
            logger.exception("Failed to process channel demotion: %s", e)
        return

    # Bot was removed from channel
    if old_status in ("administrator", "member", "restricted") and new_status in ("left", "kicked"):
        logger.info("Bot removed from channel «%s»", channel_title)
        try:
            emoji_id: str | None = _get_channel_custom_emoji_id(chat.id, bot, channel_title, from_user, fetch_photo=False)
            result = await _notify_channel_removed()
            if result and result.get("ownerTelegramId"):
                t_html = _channel_title_html(channel_title, emoji_id)
                if lang == "ru":
                    msg = f'{_TG_EMOJI_CROSS} <b>Бот удалён из канала</b> «{t_html}».\n<blockquote>Канал удалён из вашего списка. Добавьте бота снова.</blockquote>'
                else:
                    msg = f'{_TG_EMOJI_CROSS} <b>Bot removed from channel</b> "{t_html}".\n<blockquote>Channel removed from your list. Add the bot again.</blockquote>'
                try:
                    await bot.send_message(result["ownerTelegramId"], msg, parse_mode="HTML")
                except Exception:
                    pass
        except Exception as e:
            logger.exception("Failed to process channel removal: %s", e)
        return

    # Bot was restored as admin
    if old_status in ("member", "restricted") and new_status == "administrator":
        logger.info("Bot restored as admin in channel «%s»", channel_title)
        try:
            emoji_id: str | None = _get_channel_custom_emoji_id(chat.id, bot, channel_title, from_user)
            payload = {
                "chatId": chat.id,
                "chatType": chat.type,
                "title": channel_title,
                "username": getattr(chat, "username", None),
                "addedByTelegramId": from_user.id if from_user else 0,
            }
            if await _notify_channel_added(payload):
                t_html = _channel_title_html(channel_title, emoji_id)
                if lang == "ru":
                    msg = f'{_TG_EMOJI_OK} <b>Права администратора восстановлены</b> в канале «{t_html}».\n<blockquote>Канал снова активен!</blockquote>'
                else:
                    msg = f'{_TG_EMOJI_OK} <b>Admin rights restored</b> in channel "{t_html}".\n<blockquote>Channel is active again!</blockquote>'
                try:
                    await bot.send_message(from_user.id if from_user else 0, msg, parse_mode="HTML")
                except Exception:
                    pass
        except Exception as e:
            logger.exception("Failed to process admin restoration: %s", e)


@router.pre_checkout_query()
async def on_pre_checkout(pre: PreCheckoutQuery, bot: Bot) -> None:
    """Accept Stars top-up pre-checkout (payload: topup_{telegram_id}_{amount}_{ts})."""
    payload = (pre.invoice_payload or "").strip()
    if not payload.startswith("topup_"):
        await bot.answer_pre_checkout_query(pre.id, ok=False, error_message="Unknown invoice")
        return
    await bot.answer_pre_checkout_query(pre.id, ok=True)


def _process_stars_payment(
    telegram_id: int,
    amount: int,
    telegram_payment_charge_id: str,
    provider_payment_charge_id: str,
    invoice_payload: str,
) -> bool:
    """
    Credit Stars and store transaction for refund support.
    Returns True on success. Idempotent: skips if charge_id already processed.
    """
    db = _get_db()
    try:
        existing = db.execute(
            select(StarsTransaction).where(
                StarsTransaction.telegram_payment_charge_id == telegram_payment_charge_id
            )
        ).scalar_one_or_none()
        if existing:
            logger.info("Stars payment already processed: %s", telegram_payment_charge_id)
            return True
        amt = Decimal(amount)
        bal = db.execute(
            select(UserBalance).where(
                UserBalance.telegram_id == telegram_id,
                UserBalance.currency == "stars",
            )
        ).scalar_one_or_none()
        if bal:
            bal.available += amt
            bal.total_deposited += amt
        else:
            bal = UserBalance(
                telegram_id=telegram_id,
                currency="stars",
                available=amt,
                total_deposited=amt,
            )
            db.add(bal)
        tx = StarsTransaction(
            telegram_id=telegram_id,
            amount=amount,
            invoice_payload=invoice_payload,
            telegram_payment_charge_id=telegram_payment_charge_id,
            provider_payment_charge_id=provider_payment_charge_id or "",
            status="completed",
        )
        db.add(tx)
        db.commit()
        return True
    except Exception as e:
        logger.exception("Process stars payment: %s", e)
        db.rollback()
        return False
    finally:
        db.close()


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, bot: Bot) -> None:
    """Handle successful Stars payment: credit user balance."""
    sp = message.successful_payment
    logger.info("successful_payment: currency=%s payload=%s chat_id=%s", sp.currency if sp else None, sp.invoice_payload if sp else None, message.chat.id if message.chat else None)
    if not sp or sp.currency != "XTR":
        return
    payload = (sp.invoice_payload or "").strip()
    if not payload.startswith("topup_"):
        return
    parts = payload.split("_")
    if len(parts) < 3:
        return
    try:
        telegram_id = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        return
    # Verify message.from_user matches payload
    from_user = message.from_user
    if not from_user or from_user.id != telegram_id:
        return
    if amount != sp.total_amount:
        logger.warning("Stars amount mismatch: payload=%s vs total=%s", amount, sp.total_amount)
        amount = sp.total_amount
    ok = await asyncio.to_thread(
        _process_stars_payment,
        telegram_id,
        amount,
        sp.telegram_payment_charge_id,
        sp.provider_payment_charge_id or "",
        payload,
    )
    if ok:
        logger.info("Credited %s Stars to telegram_id=%s", amount, telegram_id)
        text = f'<tg-emoji emoji-id="5972187557352443077">⭐️</tg-emoji> <b>+{amount} Stars зачислено на ваш баланс.</b>'
        # При оплате через createInvoiceLink (Mini App) message.chat может быть пустым — отправляем в личку по telegram_id
        try:
            await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
        except Exception as e:
            logger.exception("Failed to send Stars credit message to %s: %s", telegram_id, e)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    args = text.split(maxsplit=1)
    payload = (args[1].strip() if len(args) >= 2 else "") or "from_bot"
    from_id = message.from_user.id if message.from_user else 0

    # start=seller_post_{orderId} -> seller views post
    if payload.startswith("seller_post_"):
        try:
            order_id = int(payload.replace("seller_post_", "").strip())
        except ValueError:
            await state.clear()
            return
        order, channel = await asyncio.to_thread(_get_order_and_channel, order_id)
        if not order or not channel:
            await message.answer("Заказ не найден.")
            return
        if order.seller_telegram_id != from_id:
            await message.answer("Это не ваш заказ.")
            return
        if order.status != "pending_seller":
            await message.answer("Заказ уже обработан.")
            return
        await _send_seller_preview(message, order_id, order, channel.title)
        return

    # Generic /start (no post_ or seller_post_) -> show welcome + Mini App
    if not payload.startswith("post_"):
        await state.clear()
        webapp_url = _get_webapp_url()
        # Use web_app= for proper Mini App (avoids "Web App not found")
        welcome = (
            f"<b>{_TG_EMOJI_STORE}</b><b> AdsMarket — покупка и продажа рекламы в Telegram.</b>\n\n"
            f"<blockquote>     • <i>Проверенная статистика каналов</i>\n"
            f"     • <i>Оплата: </i>{_TG_EMOJI_TON}<i> TON, </i>{_TG_EMOJI_USDT}<i> USDT и </i>{_TG_EMOJI_STAR}<i> Tg Stars</i>\n"
            f"     • <i>Согласование креатива</i>\n"
            f"     • <i>Автопостинг</i></blockquote>\n\n"
            f"<b>Нажмите для запуска</b>{_TG_EMOJI_POINT_DOWN}"
        )
        btn = InlineKeyboardButton(text="Open", web_app=WebAppInfo(url=webapp_url))
        start_photo_file_id = "AgACAgIAAxkBAAIBTWmQT4XljPKiSeHAGDdIjAk4zqCfAAKKEmsbqUuJSE71-d-VXN45AQADAgADeQADOgQ"
        await message.answer_photo(
            photo=start_photo_file_id,
            caption=welcome,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn]]),
        )
        return

    post_ref = payload.replace("post_", "").strip()
    order, channel = await asyncio.to_thread(_get_order_and_channel_by_post_ref, post_ref)
    if not order or not channel:
        await state.clear()
        await message.answer("Заказ не найден.")
        return
    if order.buyer_telegram_id != message.from_user.id if message.from_user else 0:
        await message.answer("Этот заказ создан не вами.")
        return
    if order.status != "writing_post":
        await message.answer('<tg-emoji emoji-id="5974193375799152241">ℹ️</tg-emoji> <b>Этот заказ уже обработан.</b>', parse_mode="HTML")
        return

    await state.set_state(PostFlow.waiting_post)
    await state.update_data(order_id=order.id)
    title_esc = _html_title(channel.title)
    comment = (order.seller_revision_comment or "").strip()
    if comment:
        comment_esc = _html_title(comment).replace("\n", "<br>")
        msg = f"{_TG_EMOJI_CHAT_COMMENT} <b>Комментарий продавца:</b>\n<blockquote>{comment_esc}</blockquote>\n\n{_TG_EMOJI_MEGAPHONE} <b>Отправьте доработанный рекламный пост для канала</b> «<i>{title_esc}</i>»"
    else:
        msg = f"{_TG_EMOJI_MEGAPHONE} <b>Отправьте рекламный пост для канала</b> «<i>{title_esc}</i>»"
    await message.answer(msg, parse_mode="HTML", reply_markup=_kb_pause(order.id))


async def _send_seller_preview(message: Message, order_id: int, order: Order, channel_title: str) -> None:
    preview_body = (order.post_text_html or "") + "\n\n#Реклама"
    title_esc = _html_title(channel_title)
    header = f"{_TG_EMOJI_MEGAPHONE} <b>Рекламный пост для канала «</b><i>{title_esc}</i><b>».\nПодтвердите или отправьте на доработку:</b>"
    full_text = f"{header}\n\n{preview_body}"
    kb = _kb_seller_actions(order_id, order)
    if order.post_media_file_id:
        caption = full_text[:1024] if len(full_text) <= 1024 else (preview_body[:1000] + "...")
        await message.answer_photo(
            photo=order.post_media_file_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb,
        )
    else:
        await message.answer(full_text, parse_mode="HTML", reply_markup=kb)


@router.message(F.contact)
async def on_contact(message: Message) -> None:
    """Handle shared contact (phone verification)."""
    contact = message.contact
    from_user = message.from_user
    if not from_user or not contact:
        return
    if contact.user_id and contact.user_id != from_user.id:
        await message.answer("❌ Пожалуйста, отправьте свой собственный контакт")
        return
    phone = (contact.phone_number or "").strip()
    if not phone:
        return
    clean = re.sub(r"\D+", "", phone)
    if not clean:
        await message.answer("❌ Неверный формат номера.")
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            h = {"content-type": "application/json"}
            if settings.internal_secret:
                h["x-internal-secret"] = settings.internal_secret
            res = await client.post(
                f"{settings.api_base_url.rstrip('/')}/api/auth/phone-from-bot",
                json={"telegramId": from_user.id, "phone": clean},
                headers=h,
            )
            if res.is_success:
                data = res.json()
                lang = (data.get("language") or "en").lower().startswith("ru")
                txt = "<b>Телефон подтверждён</b> <tg-emoji emoji-id=\"5357435672661599737\">✔️</tg-emoji>" if lang else "<b>Phone verified</b> <tg-emoji emoji-id=\"5357435672661599737\">✔️</tg-emoji>"
                await message.answer(txt, parse_mode="HTML")
            else:
                raise Exception(res.text)
    except Exception as e:
        logger.warning("Phone save failed: %s", e)
        lang = _lang_ru(from_user)
        await message.answer(
            "❌ Не удалось сохранить номер. Попробуйте ещё раз через минуту." if lang else "❌ Failed to save the phone. Please try again in a minute."
        )


@router.callback_query(F.data.startswith("pause_"))
async def cb_pause(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    data = cb.data
    try:
        order_id = int(data.replace("pause_", ""))
    except ValueError:
        return
    order, _ = await asyncio.to_thread(_get_order_and_channel, order_id)
    post_ref = order.post_token if order and order.post_token else str(order_id)
    orders_url = _get_webapp_orders_url()
    await state.clear()
    text = (
        f"{_TG_EMOJI_CHAT} <b>Ожидание приостановлено.</b>\n\n"
        f"<b>Чтобы продолжить, нажмите кнопку «</b><i>Написать рекламный пост</i><b>» в Mini App</b> "
        f"<a href=\"{orders_url}\">раздел заказы</a>\n"
        f"<b>Либо отправьте</b> {_TG_EMOJI_POINT} <code>/start post_{post_ref}</code>"
    )
    await cb.message.answer(text, parse_mode="HTML")


@router.message(PostFlow.waiting_post, F.content_type.in_({"text", "photo"}))
async def on_post_content(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await state.clear()
        return

    # Text from message or caption (when sending photo with caption)
    text = (message.html_text or message.text or (message.caption or "")).strip()
    if not text and not message.photo:
        await message.answer("Отправьте текст и/или фото поста.")
        return

    photo_file_id = None
    if message.photo:
        photo_file_id = message.photo[-1].file_id

    ok = await asyncio.to_thread(_update_order_post, order_id, text or None, photo_file_id)
    if not ok:
        await message.answer("Ошибка сохранения. Попробуйте снова.")
        return

    await state.set_state(PostFlow.waiting_button)
    msg = f"{_TG_EMOJI_BUTTON} <b>Желаете добавить URL-кнопку?\nФормат: </b><i>Имя кнопки - ссылка</i>"
    await message.answer(msg, parse_mode="HTML", reply_markup=_kb_skip_button(order_id))


@router.callback_query(F.data.startswith("skip_btn_"), PostFlow.waiting_button)
async def cb_skip_button(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await cb.answer()
    try:
        order_id = int(cb.data.replace("skip_btn_", ""))
    except ValueError:
        return
    chat_id = cb.message.chat.id if cb.message else 0
    await cb.message.delete()
    if chat_id:
        await _send_preview_and_ask_approval(bot, chat_id, order_id, state)


# @router.message(F.photo)
# async def on_photo_get_id(message: Message) -> None:
#     """Return file_id for photos not in PostFlow. Use for obtaining photo IDs."""
#     fid = message.photo[-1].file_id
#     await message.answer(f"<b>file_id:</b>\n<code>{fid}</code>", parse_mode="HTML")


@router.message(PostFlow.waiting_button, F.text)
async def on_button_text(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await state.clear()
        return

    text = (message.text or "").strip()
    # Format: "name - url"
    name, url = None, None
    if " - " in text:
        parts = text.split(" - ", 1)
        name = parts[0].strip()
        url = parts[1].strip() if len(parts) > 1 else ""
    if name and url:
        await asyncio.to_thread(_update_order_button, order_id, name, url)

    await message.delete()
    await _send_preview_and_ask_approval(bot, message.chat.id, order_id, state)


async def _send_preview_and_ask_approval(bot: Bot, chat_id: int, order_id: int, state: FSMContext) -> None:
    order = await asyncio.to_thread(_get_order, order_id)
    if not order:
        await bot.send_message(chat_id, "Заказ не найден.")
        await state.clear()
        return

    preview_body = (order.post_text_html or "") + "\n\n#Реклама"
    header = f"<b>{_TG_EMOJI_WRENCH}</b><b> Вот как будет выглядеть ваш рекламный пост:</b>"
    full_text = f"{header}\n\n{preview_body}"
    kb = _kb_agree_redo(order_id, order)

    if order.post_media_file_id:
        caption = full_text[:1024] if len(full_text) <= 1024 else (preview_body[:1000] + "...")
        await bot.send_photo(
            chat_id,
            photo=order.post_media_file_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb,
        )
    else:
        await bot.send_message(
            chat_id,
            full_text,
            parse_mode="HTML",
            reply_markup=kb,
        )

    await state.set_state(PostFlow.waiting_approval)


@router.callback_query(F.data.startswith("redo_"), PostFlow.waiting_approval)
async def cb_redo(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await cb.answer()
    try:
        order_id = int(cb.data.replace("redo_", ""))
    except ValueError:
        return
    await cb.message.delete()
    await asyncio.to_thread(_clear_order_draft, order_id)
    data = await state.get_data()
    order_id = data.get("order_id", order_id)
    order, channel = await asyncio.to_thread(_get_order_and_channel, order_id)
    if not order or not channel:
        await state.clear()
        return
    await state.set_state(PostFlow.waiting_post)
    await state.update_data(order_id=order_id)
    title_esc = _html_title(channel.title)
    msg = f"{_TG_EMOJI_MEGAPHONE} <b>Отправьте рекламный пост для канала</b> «<i>{title_esc}</i>»"
    await cb.message.answer(msg, parse_mode="HTML", reply_markup=_kb_pause(order_id))


async def _notify_seller_new_order(bot: Bot, order_id: int) -> None:
    """Send notification to seller about new order (without post content)."""
    order, channel = await asyncio.to_thread(_get_order_and_channel, order_id)
    if not order or not channel:
        return
    seller_id = order.seller_telegram_id or channel.owner_telegram_id
    title_esc = _html_title(channel.title)
    text = f'{_TG_EMOJI_MEGAPHONE} <b>Новый заказ для канала</b> «<i>{title_esc}</i>»'
    bot_username = get_bot_username()
    view_link = f"https://t.me/{bot_username}?start=seller_post_{order_id}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Посмотреть пост", url=view_link)]]
    )
    try:
        await bot.send_message(
            seller_id,
            text,
            parse_mode="HTML",
            reply_markup=kb,
        )
    except Exception as e:
        logger.exception("Notify seller new order: %s", e)


@router.callback_query(F.data.startswith("agree_"), PostFlow.waiting_approval)
async def cb_agree(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    try:
        order_id = int(cb.data.replace("agree_", ""))
    except ValueError:
        return
    await cb.message.edit_reply_markup(reply_markup=None)
    ok = await asyncio.to_thread(_set_order_pending_seller, order_id)
    await state.clear()
    if ok:
        await _notify_seller_new_order(cb.bot, order_id)
        txt = (
            f"{_TG_EMOJI_OK} <b>Пост принят.</b>\n"
            f"<blockquote><i>Продавец получит уведомление о новом заказе.</i></blockquote>"
        )
        await cb.message.answer(txt, parse_mode="HTML")
    else:
        await cb.message.answer("Ошибка сохранения.")


# --- Seller flow ---

async def _notify_buyer_revision_comment(bot: Bot, order_id: int, comment: str) -> None:
    """Send seller's revision comment to buyer immediately."""
    order, channel = await asyncio.to_thread(_get_order_and_channel, order_id)
    if not order or not channel:
        return
    buyer_id = order.buyer_telegram_id
    title_esc = _html_title(channel.title)
    comment_esc = _html_title(comment).replace("\n", "<br>")
    text = (
        f"{_TG_EMOJI_CHAT_COMMENT} <b>Комментарий продавца:</b>\n"
        f"<blockquote>{comment_esc}</blockquote>\n\n"
        f"{_TG_EMOJI_MEGAPHONE} <b>Отправьте доработанный рекламный пост для канала</b> «<i>{title_esc}</i>»"
    )
    post_ref = order.post_token or str(order_id)
    bot_username = get_bot_username()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="Написать пост",
                url=f"https://t.me/{bot_username}?start=post_{post_ref}",
            )
        ]]
    )
    try:
        await bot.send_message(buyer_id, text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.exception("Notify buyer revision comment: %s", e)


async def _notify_buyer_post_approved(bot: Bot, order_id: int) -> None:
    """Send notification to buyer that post was approved by seller."""
    order, channel = await asyncio.to_thread(_get_order_and_channel, order_id)
    if not order or not channel:
        return
    buyer_id = order.buyer_telegram_id
    title_esc = _html_title(channel.title)
    text = (
        f"{_TG_EMOJI_OK} Ваш пост согласован!\n\n"
        f"<b>Реклама для канала </b>«<i>{title_esc}</i>» <b>принята продавцом.</b>"
    )
    try:
        await bot.send_message(buyer_id, text, parse_mode="HTML")
    except Exception as e:
        logger.exception("Notify buyer post approved: %s", e)


def _format_requires_pin(fmt: ChannelAdFormat | None) -> bool:
    """True if format requires pinning the post."""
    if not fmt:
        return False
    if fmt.format_type == "pin":
        return True
    if fmt.settings:
        try:
            s = json.loads(fmt.settings) if isinstance(fmt.settings, str) else fmt.settings
            return bool(s.get("pinned"))
        except (json.JSONDecodeError, TypeError):
            pass
    return False


async def _publish_post_to_channel(
    bot: Bot, order: Order, channel: Channel, fmt: ChannelAdFormat | None
) -> tuple[bool, str | None, int | None]:
    """Publish the ad post to the channel. Returns (success, link, message_id)."""
    post_body = (order.post_text_html or "") + "\n\n#Реклама"
    kb = _kb_post_button(order)
    chat_id = channel.telegram_id
    try:
        if order.post_media_file_id:
            caption = post_body[:1024] if len(post_body) <= 1024 else post_body[:1000] + "..."
            msg = await bot.send_photo(
                chat_id=chat_id,
                photo=order.post_media_file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            msg = await bot.send_message(
                chat_id=chat_id,
                text=post_body,
                parse_mode="HTML",
                reply_markup=kb,
            )
        message_id = msg.message_id if msg else None
        if _format_requires_pin(fmt) and message_id:
            try:
                await bot.pin_chat_message(chat_id=chat_id, message_id=message_id)
                logger.info("Post pinned in channel %s (order %s)", channel.title, order.id)
            except Exception as pin_err:
                logger.warning("Failed to pin post in channel %s: %s", channel.title, pin_err)
        link = None
        username = (channel.username or "").strip().lstrip("@")
        if username and message_id:
            link = f"https://t.me/{username}/{message_id}"
        logger.info("Post published to channel %s (order %s) link=%s", channel.title, order.id, link)
        return True, link, message_id
    except Exception as e:
        logger.exception("Failed to publish post to channel %s (order %s): %s", channel.title, order.id, e)
        return False, None, None


@router.callback_query(F.data.startswith("seller_approve_"))
async def cb_seller_approve(cb: CallbackQuery) -> None:
    await cb.answer()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    try:
        order_id = int(cb.data.replace("seller_approve_", ""))
    except ValueError:
        return
    order, channel = await asyncio.to_thread(_get_order_and_channel, order_id)
    if not order or not channel:
        await cb.message.answer("Заказ не найден.")
        return
    if order.status != "pending_seller":
        await cb.message.answer("Заказ уже обработан.")
        return
    fmt = await asyncio.to_thread(_get_order_format, order_id)
    published, post_link, msg_id = await _publish_post_to_channel(cb.bot, order, channel, fmt)
    if not published:
        await cb.message.answer(
            "❌ Не удалось опубликовать пост в канал. Проверьте, что бот — администратор канала. Заказ не завершён."
        )
        return
    ok = await asyncio.to_thread(_set_order_done, order_id, post_link, msg_id)
    if ok:
        await _notify_buyer_post_approved(cb.bot, order_id)
    await cb.message.answer(
        "✅ Пост опубликован в канал. Заказ выполнен. Покупатель получит уведомление." if ok
        else "Пост опубликован, но ошибка при обновлении статуса."
    )


@router.callback_query(F.data.startswith("seller_revision_"))
async def cb_seller_revision(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    try:
        order_id = int(cb.data.replace("seller_revision_", ""))
    except ValueError:
        return
    await state.set_state(SellerFlow.waiting_comment)
    await state.update_data(seller_order_id=order_id)
    txt = f"{_TG_EMOJI_CHAT_INPUT} <b>Введите комментарий для покупателя (</b><b><i>что нужно исправить в посте</i>):</b>"
    await cb.message.answer(txt, parse_mode="HTML")


@router.callback_query(F.data.startswith("seller_decline_"))
async def cb_seller_decline(cb: CallbackQuery) -> None:
    await cb.answer()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    try:
        order_id = int(cb.data.replace("seller_decline_", ""))
    except ValueError:
        return
    ok = await asyncio.to_thread(_set_order_cancelled, order_id)
    txt = '<tg-emoji emoji-id="5305724700209454594">❎</tg-emoji> <b>Заказ отклонён.</b>' if ok else "Ошибка сохранения."
    await cb.message.answer(txt, parse_mode="HTML")


@router.message(SellerFlow.waiting_comment, F.text)
async def on_seller_comment(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    order_id = data.get("seller_order_id")
    if not order_id:
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите текст комментария.")
        return
    ok = await asyncio.to_thread(_set_order_revision, order_id, text)
    await state.clear()
    if ok:
        await _notify_buyer_revision_comment(bot, order_id, text)
    if ok:
        await message.answer(
            f"<b>{_TG_EMOJI_SEND}</b><b>Комментарий отправлен покупателю.\nОн сможет доработать пост и отправить снова.</b>",
            parse_mode="HTML",
        )
    else:
        await message.answer("Ошибка сохранения.")
