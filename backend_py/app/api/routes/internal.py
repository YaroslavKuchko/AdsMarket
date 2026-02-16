from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.bot_username import get_bot_username
from app.core.config import settings
from app.db.models import Channel, Order, User, ChannelStatsHistory
from app.db.session import get_db, SessionLocal
from app.realtime.hub import hub

router = APIRouter(prefix="/api/internal", tags=["internal"])


async def _collect_channel_stats_background(channel_id: int):
    """Background task to collect stats for a newly added channel using Telethon."""
    # Wait a bit for the channel to be fully set up
    await asyncio.sleep(2)
    
    print(f"[Internal] Starting stats collection for channel {channel_id}...")
    
    try:
        from app.services.channel_collector import channel_collector
        
        result = await channel_collector.collect_channel_stats(channel_id)
        
        if result.get("success"):
            print(f"[Internal] Successfully collected stats: {result.get('posts_collected')} posts")
            
            # Notify via WebSocket
            db = SessionLocal()
            try:
                from app.db.models import Channel, ChannelStats
                
                channel = db.execute(
                    select(Channel).where(Channel.id == channel_id)
                ).scalar_one_or_none()
                
                stats = db.execute(
                    select(ChannelStats).where(ChannelStats.channel_id == channel_id)
                ).scalar_one_or_none()
                
                if channel and stats:
                    await hub.send(
                        channel.owner_telegram_id,
                        {
                            "type": "channel_stats_updated",
                            "channelId": channel.id,
                            "subscriberCount": stats.subscriber_count,
                            "avgViews": stats.avg_post_views,
                            "totalPosts": stats.posts_90d,
                            "isCollecting": False,
                        },
                    )
                    
                    # Generate AI insights after stats collection
                    print(f"[Internal] Generating AI insights for channel {channel_id}...")
                    try:
                        from app.services.ai_analytics import ai_analytics
                        import json
                        
                        ai_result = await ai_analytics.generate_structured_insights(db, channel)
                        
                        if not ai_result.get("error"):
                            stats.ai_insights_json = json.dumps(ai_result, ensure_ascii=False)
                            stats.ai_insights_generated_at = datetime.now(timezone.utc)
                            stats.ai_insights_error = None
                            db.commit()
                            print(f"[Internal] AI insights generated successfully")
                        else:
                            stats.ai_insights_error = ai_result.get("error")[:256]
                            db.commit()
                            print(f"[Internal] AI insights failed: {ai_result.get('error')}")
                    except Exception as ai_e:
                        print(f"[Internal] AI insights error: {ai_e}")
            finally:
                db.close()
        else:
            print(f"[Internal] Stats collection failed: {result.get('error')}")
            
    except Exception as e:
        print(f"[Internal] Failed to collect stats for channel {channel_id}: {e}")


def _verify_internal_secret(x_internal_secret: str | None):
    """Verify internal secret header."""
    if not settings.internal_secret:
        raise HTTPException(status_code=500, detail="internal_secret not configured")
    if x_internal_secret != settings.internal_secret:
        raise HTTPException(status_code=403, detail="forbidden")


class TelegramContactIn(BaseModel):
    telegramId: int = Field(ge=1)
    phoneNumber: str = Field(min_length=3, max_length=32)


@router.post("/telegram/contact")
async def save_contact(
    body: TelegramContactIn,
    db: Session = Depends(get_db),
    x_internal_secret: str | None = Header(default=None),
):
    _verify_internal_secret(x_internal_secret)

    q = db.execute(select(User).where(User.telegram_id == body.telegramId))
    row = q.scalar_one_or_none()

    if row is None:
        row = User(telegram_id=body.telegramId, phone_number=body.phoneNumber)
        db.add(row)
    else:
        row.phone_number = body.phoneNumber

    db.commit()
    await hub.send(
        body.telegramId,
        {
            "type": "phone_updated",
            "phoneNumber": body.phoneNumber,
        },
    )
    return {"ok": True}


class ChannelAddedIn(BaseModel):
    chatId: int
    chatType: str
    title: str
    username: str | None = None
    subscriberCount: int | None = None
    addedByTelegramId: int
    inviteLink: str | None = None
    photoUrl: str | None = None
    customEmojiId: str | None = None


@router.post("/channel-added")
async def channel_added(
    body: ChannelAddedIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_internal_secret: str | None = Header(default=None),
):
    """
    Called by bot when it's added to a channel/group as admin.
    Creates or updates the channel record.
    """
    _verify_internal_secret(x_internal_secret)

    # Check if channel already exists
    existing = db.execute(
        select(Channel).where(Channel.telegram_id == body.chatId)
    ).scalar_one_or_none()

    if existing:
        # Update existing channel - maybe bot was re-added
        existing.title = body.title
        existing.username = body.username
        existing.chat_type = body.chatType
        existing.subscriber_count = body.subscriberCount or existing.subscriber_count
        existing.invite_link = body.inviteLink or existing.invite_link
        existing.photo_url = body.photoUrl or existing.photo_url
        existing.custom_emoji_id = body.customEmojiId or existing.custom_emoji_id
        existing.status = "pending"
        existing.is_visible = True
        existing.bot_added_at = datetime.now(timezone.utc)
        existing.bot_removed_at = None
        # Update owner if different user re-added
        existing.owner_telegram_id = body.addedByTelegramId
        db.commit()

        # Notify user via WebSocket
        await hub.send(
            body.addedByTelegramId,
            {
                "type": "channel_updated",
                "channelId": existing.id,
                "telegramId": existing.telegram_id,
                "title": existing.title,
                "status": existing.status,
            },
        )

        # Trigger immediate stats collection
        asyncio.create_task(_collect_channel_stats_background(existing.id))

        return {"ok": True, "channelId": existing.id, "isNew": False}

    # Create new channel
    channel = Channel(
        telegram_id=body.chatId,
        owner_telegram_id=body.addedByTelegramId,
        chat_type=body.chatType,
        title=body.title,
        username=body.username,
        subscriber_count=body.subscriberCount or 0,
        invite_link=body.inviteLink,
        photo_url=body.photoUrl,
        custom_emoji_id=body.customEmojiId,
        status="pending",
        is_visible=True,
        bot_added_at=datetime.now(timezone.utc),
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Notify user via WebSocket
    await hub.send(
        body.addedByTelegramId,
        {
            "type": "channel_added",
            "channelId": channel.id,
            "telegramId": channel.telegram_id,
            "title": channel.title,
            "chatType": channel.chat_type,
            "username": channel.username,
            "photoUrl": channel.photo_url,
            "subscriberCount": channel.subscriber_count,
            "status": channel.status,
        },
    )

    # Trigger immediate stats collection for new channel
    asyncio.create_task(_collect_channel_stats_background(channel.id))

    return {"ok": True, "channelId": channel.id, "isNew": True}


class ChannelRemovedIn(BaseModel):
    chatId: int


@router.post("/channel-removed")
async def channel_removed(
    body: ChannelRemovedIn,
    db: Session = Depends(get_db),
    x_internal_secret: str | None = Header(default=None),
):
    """
    Called by bot when it's removed from a channel.
    Marks the channel as removed.
    """
    _verify_internal_secret(x_internal_secret)

    channel = db.execute(
        select(Channel).where(Channel.telegram_id == body.chatId)
    ).scalar_one_or_none()

    if not channel:
        return {"ok": True, "message": "channel not found"}

    owner_id = channel.owner_telegram_id
    title = channel.title
    channel.status = "removed"
    channel.is_visible = False
    channel.bot_removed_at = datetime.now(timezone.utc)
    db.commit()

    # Notify owner via WebSocket
    await hub.send(
        owner_id,
        {
            "type": "channel_removed",
            "channelId": channel.id,
            "telegramId": channel.telegram_id,
            "title": title,
        },
    )

    return {"ok": True, "channelId": channel.id, "ownerTelegramId": owner_id, "title": title}


class ChannelDemotedIn(BaseModel):
    chatId: int


@router.post("/channel-demoted")
async def channel_demoted(
    body: ChannelDemotedIn,
    db: Session = Depends(get_db),
    x_internal_secret: str | None = Header(default=None),
):
    """
    Called by bot when it loses admin rights in a channel.
    Marks the channel as inactive (paused).
    """
    _verify_internal_secret(x_internal_secret)

    channel = db.execute(
        select(Channel).where(Channel.telegram_id == body.chatId)
    ).scalar_one_or_none()

    if not channel:
        return {"ok": True, "message": "channel not found"}

    owner_id = channel.owner_telegram_id
    title = channel.title
    channel.status = "inactive"
    channel.is_visible = False
    db.commit()

    # Notify owner via WebSocket
    await hub.send(
        owner_id,
        {
            "type": "channel_inactive",
            "channelId": channel.id,
            "telegramId": channel.telegram_id,
            "title": title,
            "reason": "bot_demoted",
        },
    )

    return {"ok": True, "channelId": channel.id, "ownerTelegramId": owner_id, "title": title}


# --- Order post flow (for bot: start=post_{order_id}) ---

class OrderPostInfoIn(BaseModel):
    orderId: int = Field(ge=1)
    telegramId: int = Field(ge=1)


@router.post("/order-post-info")
async def order_post_info(
    body: OrderPostInfoIn,
    db: Session = Depends(get_db),
    x_internal_secret: str | None = Header(default=None),
):
    """Return order + channel title for post flow; 403 if not buyer or wrong status."""
    _verify_internal_secret(x_internal_secret)

    order = db.execute(
        select(Order).where(Order.id == body.orderId)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.buyer_telegram_id != body.telegramId:
        raise HTTPException(status_code=403, detail="Not your order")
    if order.status != "writing_post":
        raise HTTPException(status_code=400, detail="Order already processed")

    channel = db.execute(
        select(Channel).where(Channel.id == order.channel_id)
    ).scalar_one_or_none()
    channel_title = channel.title if channel else ""

    return {
        "orderId": order.id,
        "channelTitle": channel_title,
        "postTextHtml": order.post_text_html,
        "postMediaFileId": order.post_media_file_id,
        "postButtonName": order.post_button_name,
        "postButtonUrl": order.post_button_url,
        "sellerRevisionComment": order.seller_revision_comment,
    }


class OrderPostUpdateIn(BaseModel):
    orderId: int = Field(ge=1)
    telegramId: int = Field(ge=1)
    postTextHtml: str | None = None
    postMediaFileId: str | None = None


@router.patch("/order-post")
async def order_post_update(
    body: OrderPostUpdateIn,
    db: Session = Depends(get_db),
    x_internal_secret: str | None = Header(default=None),
):
    _verify_internal_secret(x_internal_secret)

    order = db.execute(
        select(Order).where(Order.id == body.orderId)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.buyer_telegram_id != body.telegramId:
        raise HTTPException(status_code=403, detail="Not your order")
    if order.status != "writing_post":
        raise HTTPException(status_code=400, detail="Order already processed")

    if body.postTextHtml is not None:
        order.post_text_html = body.postTextHtml
    if body.postMediaFileId is not None:
        order.post_media_file_id = body.postMediaFileId
    db.commit()
    return {"ok": True}


class OrderButtonUpdateIn(BaseModel):
    orderId: int = Field(ge=1)
    telegramId: int = Field(ge=1)
    name: str | None = None
    url: str | None = None


@router.patch("/order-button")
async def order_button_update(
    body: OrderButtonUpdateIn,
    db: Session = Depends(get_db),
    x_internal_secret: str | None = Header(default=None),
):
    _verify_internal_secret(x_internal_secret)

    order = db.execute(
        select(Order).where(Order.id == body.orderId)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.buyer_telegram_id != body.telegramId:
        raise HTTPException(status_code=403, detail="Not your order")
    if order.status != "writing_post":
        raise HTTPException(status_code=400, detail="Order already processed")

    if body.name is not None:
        order.post_button_name = body.name
    if body.url is not None:
        order.post_button_url = body.url
    db.commit()
    return {"ok": True}


class OrderPostApproveIn(BaseModel):
    orderId: int = Field(ge=1)
    telegramId: int = Field(ge=1)


@router.post("/order-post-approve")
async def order_post_approve(
    body: OrderPostApproveIn,
    db: Session = Depends(get_db),
    x_internal_secret: str | None = Header(default=None),
):
    _verify_internal_secret(x_internal_secret)

    order = db.execute(
        select(Order).where(Order.id == body.orderId)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.buyer_telegram_id != body.telegramId:
        raise HTTPException(status_code=403, detail="Not your order")

    order.status = "pending_seller"
    db.commit()

    channel = db.execute(
        select(Channel).where(Channel.id == order.channel_id)
    ).scalar_one_or_none()
    channel_title = channel.title if channel else ""

    bot_username = get_bot_username()
    seller_view_link = f"https://t.me/{bot_username}?start=seller_post_{order.id}"

    return {
        "ok": True,
        "sellerTelegramId": order.seller_telegram_id,
        "channelTitle": channel_title,
        "postTextHtml": order.post_text_html,
        "postMediaFileId": order.post_media_file_id,
        "postButtonName": order.post_button_name,
        "postButtonUrl": order.post_button_url,
        "orderId": order.id,
        "sellerViewPostLink": seller_view_link,
    }


class OrderPostClearDraftIn(BaseModel):
    orderId: int = Field(ge=1)
    telegramId: int = Field(ge=1)


@router.post("/order-post-clear-draft")
async def order_post_clear_draft(
    body: OrderPostClearDraftIn,
    db: Session = Depends(get_db),
    x_internal_secret: str | None = Header(default=None),
):
    _verify_internal_secret(x_internal_secret)

    order = db.execute(
        select(Order).where(Order.id == body.orderId)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.buyer_telegram_id != body.telegramId:
        raise HTTPException(status_code=403, detail="Not your order")

    order.post_text_html = None
    order.post_media_file_id = None
    order.post_button_name = None
    order.post_button_url = None
    db.commit()
    return {"ok": True}


# --- Seller flow (start=seller_post_{order_id}) ---

class OrderSellerInfoIn(BaseModel):
    orderId: int = Field(ge=1)
    telegramId: int = Field(ge=1)


@router.post("/order-seller-info")
async def order_seller_info(
    body: OrderSellerInfoIn,
    db: Session = Depends(get_db),
    x_internal_secret: str | None = Header(default=None),
):
    """Return order post content for seller to view/approve; 403 if not seller or wrong status."""
    _verify_internal_secret(x_internal_secret)

    order = db.execute(
        select(Order).where(Order.id == body.orderId)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.seller_telegram_id != body.telegramId:
        raise HTTPException(status_code=403, detail="Not your order")
    if order.status != "pending_seller":
        raise HTTPException(status_code=400, detail="Order not in pending_seller")

    channel = db.execute(
        select(Channel).where(Channel.id == order.channel_id)
    ).scalar_one_or_none()
    channel_title = channel.title if channel else ""

    return {
        "orderId": order.id,
        "channelTitle": channel_title,
        "postTextHtml": order.post_text_html,
        "postMediaFileId": order.post_media_file_id,
        "postButtonName": order.post_button_name,
        "postButtonUrl": order.post_button_url,
    }


class OrderSellerApproveIn(BaseModel):
    orderId: int = Field(ge=1)
    telegramId: int = Field(ge=1)


@router.post("/order-seller-approve")
async def order_seller_approve(
    body: OrderSellerApproveIn,
    db: Session = Depends(get_db),
    x_internal_secret: str | None = Header(default=None),
):
    _verify_internal_secret(x_internal_secret)

    order = db.execute(
        select(Order).where(Order.id == body.orderId)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.seller_telegram_id != body.telegramId:
        raise HTTPException(status_code=403, detail="Not your order")
    if order.status != "pending_seller":
        raise HTTPException(status_code=400, detail="Order not in pending_seller")

    order.status = "done"
    order.done_at = datetime.now(timezone.utc)
    order.seller_revision_comment = None
    db.commit()

    from app.services.order_payment import release_to_seller
    release_to_seller(body.orderId)

    channel = db.execute(
        select(Channel).where(Channel.id == order.channel_id)
    ).scalar_one_or_none()
    channel_title = channel.title if channel else ""

    return {
        "ok": True,
        "buyerTelegramId": order.buyer_telegram_id,
        "channelTitle": channel_title,
        "orderId": order.id,
    }


class OrderSellerRevisionIn(BaseModel):
    orderId: int = Field(ge=1)
    telegramId: int = Field(ge=1)
    comment: str = Field(min_length=1, max_length=2000)


@router.post("/order-seller-revision")
async def order_seller_revision(
    body: OrderSellerRevisionIn,
    db: Session = Depends(get_db),
    x_internal_secret: str | None = Header(default=None),
):
    _verify_internal_secret(x_internal_secret)

    order = db.execute(
        select(Order).where(Order.id == body.orderId)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.seller_telegram_id != body.telegramId:
        raise HTTPException(status_code=403, detail="Not your order")
    if order.status != "pending_seller":
        raise HTTPException(status_code=400, detail="Order not in pending_seller")

    order.status = "writing_post"
    order.seller_revision_comment = body.comment
    db.commit()
    return {"ok": True}


class OrderSellerDeclineIn(BaseModel):
    orderId: int = Field(ge=1)
    telegramId: int = Field(ge=1)


@router.post("/order-seller-decline")
async def order_seller_decline(
    body: OrderSellerDeclineIn,
    db: Session = Depends(get_db),
    x_internal_secret: str | None = Header(default=None),
):
    _verify_internal_secret(x_internal_secret)

    order = db.execute(
        select(Order).where(Order.id == body.orderId)
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.seller_telegram_id != body.telegramId:
        raise HTTPException(status_code=403, detail="Not your order")
    if order.status != "pending_seller":
        raise HTTPException(status_code=400, detail="Order not in pending_seller")

    order.status = "cancelled"
    db.commit()

    from app.services.order_payment import refund_to_buyer
    refund_to_buyer(body.orderId)

    return {"ok": True}

