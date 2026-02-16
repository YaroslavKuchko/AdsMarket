"""
Channels API routes.

Handles channel listing, details, and configuration for channel owners.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_telegram_id, get_optional_telegram_id
from app.db.models import Channel, ChannelAdFormat, ChannelPost, ChannelStats, ChannelStatsHistory
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/channels", tags=["channels"])


# ============================================================================
# Helper Functions
# ============================================================================

def _channel_to_out(channel: Channel) -> ChannelOut:
    """Convert Channel model to ChannelOut response."""
    return ChannelOut(
        id=channel.id,
        telegramId=channel.telegram_id,
        chatType=channel.chat_type,
        title=channel.title,
        username=channel.username,
        description=channel.description,
        photoUrl=channel.photo_url,
        subscriberCount=channel.subscriber_count,
        inviteLink=channel.invite_link,
        status=channel.status,
        isVisible=channel.is_visible,
        category=channel.category,
        language=channel.language,
        createdAt=channel.created_at,
        updatedAt=channel.updated_at,
    )


# ============================================================================
# Response Models
# ============================================================================


class ChannelOut(BaseModel):
    id: int
    telegramId: int
    chatType: str
    title: str
    username: str | None
    description: str | None
    photoUrl: str | None
    subscriberCount: int
    inviteLink: str | None
    status: str
    isVisible: bool
    category: str | None
    language: str | None
    createdAt: datetime
    updatedAt: datetime


class ChannelListOut(BaseModel):
    channels: list[ChannelOut]
    total: int


class AdFormatOut(BaseModel):
    id: int
    formatType: str
    isEnabled: bool
    priceStars: int
    priceTon: float | None
    priceUsdt: float | None
    durationHours: int
    etaHours: int
    # Arbitrary JSON settings for this format (e.g. pinned, postingMode, etc.)
    settings: dict | None = None


class ChannelDetailOut(ChannelOut):
    adFormats: list[AdFormatOut]
    # True if the current user is the channel owner (only set for market endpoint when authenticated)
    isOwnChannel: bool | None = None


class UpdateChannelIn(BaseModel):
    description: str | None = None
    category: str | None = None
    language: str | None = None
    isVisible: bool | None = None


class UpdateAdFormatIn(BaseModel):
    formatType: str
    isEnabled: bool = True
    priceStars: int = Field(ge=0)
    priceTon: float | None = None
    priceUsdt: float | None = None
    durationHours: int = Field(ge=1, default=24)
    etaHours: int = Field(ge=1, default=24)
    # Optional settings JSON (stored as text in DB)
    settings: dict | None = None


class BestPostOut(BaseModel):
    """Best performing post info."""
    messageId: int | None
    views: int
    reactions: int
    comments: int
    shares: int
    text: str | None
    fullText: str | None  # Full text for expanded view
    hasMedia: bool
    mediaUrl: str | None  # URL to post media thumbnail
    isAlbum: bool = False  # Is this a grouped media post
    mediaCount: int = 1  # Number of media items in the post


class ChannelStatsOut(BaseModel):
    """Current channel statistics."""
    subscriberCount: int
    subscriberGrowth24h: int
    subscriberGrowth7d: int
    subscriberGrowth30d: int
    
    avgPostViews: int
    avgReach24h: int
    totalViews24h: int
    totalViews7d: int
    
    engagementRate: float
    avgReactions: int
    avgComments: int
    avgShares: int
    
    # Totals
    totalReactions: int
    totalComments: int
    totalShares: int
    
    # Posts by period
    posts24h: int
    posts7d: int
    posts30d: int
    posts90d: int
    avgPostsPerDay: float
    
    # Best post
    bestPost: BestPostOut | None
    
    dynamics: str  # 'growing', 'stable', 'declining'
    dynamicsScore: int  # -100 to +100
    
    lastPostAt: datetime | None
    updatedAt: datetime
    
    # Collection status
    isCollecting: bool
    collectionStartedAt: datetime | None
    collectionError: str | None


class MarketChannelOut(BaseModel):
    """Public marketplace channel card."""
    id: int
    title: str
    username: str | None
    category: str | None
    description: str | None
    subscriberCount: int
    engagementRate: float | None
    priceFromUsdt: float | None
    priceFromStars: int | None


class StatsHistoryPointOut(BaseModel):
    """Single point in statistics history."""
    date: str  # YYYY-MM-DD
    subscriberCount: int
    totalViews: int
    totalPosts: int
    avgPostViews: int
    engagementRate: float
    reactions: int
    comments: int
    shares: int


class ChannelStatsHistoryOut(BaseModel):
    """Historical statistics for charts."""
    channelId: int
    period: str  # '7d', '30d', '90d'
    data: list[StatsHistoryPointOut]


class MarketStatsOut(BaseModel):
    """Public stats subset for marketplace viewers (aligned with ChannelStatsOut)."""
    channelId: int
    subscriberCount: int
    subscriberGrowth24h: int
    subscriberGrowth7d: int
    subscriberGrowth30d: int
    avgPostViews: int
    avgReach24h: int
    totalViews24h: int
    totalViews7d: int
    engagementRate: float
    avgReactions: int
    avgComments: int
    avgShares: int
    totalReactions: int
    totalComments: int
    totalShares: int
    posts24h: int
    posts7d: int
    posts30d: int
    posts90d: int
    avgPostsPerDay: float
    bestPost: BestPostOut | None
    dynamics: str
    dynamicsScore: int
    lastPostAt: datetime | None
    updatedAt: datetime
    isCollecting: bool
    collectionStartedAt: datetime | None
    collectionError: str | None


class TopPostOut(BaseModel):
    """Single top post for marketplace viewers."""
    messageId: int
    views: int
    reactions: int
    comments: int
    shares: int
    text: str | None
    fullText: str | None
    hasMedia: bool
    mediaUrl: str | None
    isAlbum: bool = False
    mediaCount: int = 1
    postedAt: str | None


class TopPostsOut(BaseModel):
    """Top posts for a channel."""
    posts: list[TopPostOut]


# ============================================================================
# Routes
# ============================================================================


@router.get("", response_model=ChannelListOut)
async def list_channels(
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> ChannelListOut:
    """
    List all channels owned by the current user.
    """
    channels = db.execute(
        select(Channel)
        .where(Channel.owner_telegram_id == telegram_id)
        .where(Channel.status != "removed")
        .order_by(Channel.created_at.desc())
    ).scalars().all()

    return ChannelListOut(
        channels=[_channel_to_out(ch) for ch in channels],
        total=len(channels),
    )


@router.get("/market", response_model=list[MarketChannelOut])
async def list_market_channels(
    db: Session = Depends(get_db),
) -> list[MarketChannelOut]:
    """
    Public marketplace listing: all active & visible channels with minimal price.
    """
    from app.db.models import ChannelStats

    channels = db.execute(
        select(Channel)
        .where(
            Channel.status == "active",
            Channel.is_visible.is_(True),
        )
        .order_by(Channel.created_at.desc())
    ).scalars().all()

    if not channels:
        return []

    results: list[MarketChannelOut] = []

    for ch in channels:
        # Minimal enabled price per channel
        formats = db.execute(
            select(ChannelAdFormat).where(
                ChannelAdFormat.channel_id == ch.id,
                ChannelAdFormat.is_enabled.is_(True),
            )
        ).scalars().all()

        min_usdt: float | None = None
        min_stars: int | None = None

        for f in formats:
            if f.price_usdt is not None:
                v = float(f.price_usdt)
                if min_usdt is None or v < min_usdt:
                    min_usdt = v
            if f.price_stars is not None:
                v_s = int(f.price_stars)
                if min_stars is None or v_s < min_stars:
                    min_stars = v_s

        # Engagement rate from current stats (if exists)
        stats = db.execute(
            select(ChannelStats.engagement_rate).where(ChannelStats.channel_id == ch.id)
        ).scalar_one_or_none()
        er: float | None = float(stats) if stats is not None else None

        results.append(
            MarketChannelOut(
                id=ch.id,
                title=ch.title,
                username=ch.username,
                category=ch.category,
                description=ch.description,
                subscriberCount=ch.subscriber_count,
                engagementRate= er,
                priceFromUsdt=min_usdt,
                priceFromStars=min_stars,
            )
        )

    return results


@router.get("/market/{channel_id}", response_model=ChannelDetailOut)
async def get_market_channel(
    channel_id: int,
    telegram_id: int | None = Depends(get_optional_telegram_id),
    db: Session = Depends(get_db),
) -> ChannelDetailOut:
    """
    Public channel details for marketplace viewers.
    Only active & visible channels are returned.
    When the user is authenticated, isOwnChannel is set so the client can hide "Buy" for own channel.
    """
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.status == "active",
            Channel.is_visible.is_(True),
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    db.refresh(channel)

    formats = db.execute(
        select(ChannelAdFormat).where(ChannelAdFormat.channel_id == channel_id)
    ).scalars().all()

    is_own = None if telegram_id is None else (channel.owner_telegram_id == telegram_id)

    return ChannelDetailOut(
        id=channel.id,
        telegramId=channel.telegram_id,
        chatType=channel.chat_type,
        title=channel.title,
        username=channel.username,
        description=channel.description,
        photoUrl=channel.photo_url,
        subscriberCount=channel.subscriber_count,
        inviteLink=channel.invite_link,
        status=channel.status,
        isVisible=channel.is_visible,
        category=channel.category,
        language=channel.language,
        createdAt=channel.created_at,
        updatedAt=channel.updated_at,
        adFormats=[
            AdFormatOut(
                id=f.id,
                formatType=f.format_type,
                isEnabled=f.is_enabled,
                priceStars=f.price_stars,
                priceTon=float(f.price_ton) if f.price_ton else None,
                priceUsdt=float(f.price_usdt) if f.price_usdt else None,
                durationHours=f.duration_hours,
                etaHours=f.eta_hours,
                settings=json.loads(f.settings) if f.settings else None,
            )
            for f in formats
        ],
        isOwnChannel=is_own,
    )


@router.get("/{channel_id}", response_model=ChannelDetailOut)
async def get_channel(
    channel_id: int,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> ChannelDetailOut:
    """
    Get detailed information about a channel.
    """
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.owner_telegram_id == telegram_id,
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Refresh to ensure we have latest data
    db.refresh(channel)

    # Get ad formats
    formats = db.execute(
        select(ChannelAdFormat).where(ChannelAdFormat.channel_id == channel_id)
    ).scalars().all()

    return ChannelDetailOut(
        id=channel.id,
        telegramId=channel.telegram_id,
        chatType=channel.chat_type,
        title=channel.title,
        username=channel.username,
        description=channel.description,
        photoUrl=channel.photo_url,
        subscriberCount=channel.subscriber_count,
        inviteLink=channel.invite_link,
        status=channel.status,
        isVisible=channel.is_visible,
        category=channel.category,
        language=channel.language,
        createdAt=channel.created_at,
        updatedAt=channel.updated_at,
        adFormats=[
            AdFormatOut(
                id=f.id,
                formatType=f.format_type,
                isEnabled=f.is_enabled,
                priceStars=f.price_stars,
                priceTon=float(f.price_ton) if f.price_ton else None,
                priceUsdt=float(f.price_usdt) if f.price_usdt else None,
                durationHours=f.duration_hours,
                etaHours=f.eta_hours,
                settings=json.loads(f.settings) if f.settings else None,
            )
            for f in formats
        ],
    )


@router.put("/{channel_id}", response_model=ChannelOut)
async def update_channel(
    channel_id: int,
    body: UpdateChannelIn,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> ChannelOut:
    """
    Update channel settings.
    """
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.owner_telegram_id == telegram_id,
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Update fields
    if body.description is not None:
        channel.description = body.description
    if body.category is not None:
        channel.category = body.category
    if body.language is not None:
        channel.language = body.language
    if body.isVisible is not None:
        channel.is_visible = body.isVisible
        # Activating visibility also sets status to active
        if body.isVisible and channel.status == "pending":
            channel.status = "active"

    db.commit()
    db.refresh(channel)

    return _channel_to_out(channel)


@router.post("/{channel_id}/activate", response_model=ChannelOut)
async def activate_channel(
    channel_id: int,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> ChannelOut:
    """
    Activate a pending channel and make it visible on marketplace.
    """
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.owner_telegram_id == telegram_id,
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if channel.status == "removed":
        raise HTTPException(status_code=400, detail="Cannot activate removed channel")

    # Require at least one enabled ad format before publishing to marketplace
    enabled_count = db.execute(
        select(ChannelAdFormat).where(
            ChannelAdFormat.channel_id == channel_id,
            ChannelAdFormat.is_enabled.is_(True),
        )
    ).scalars().all()
    if not enabled_count:
        raise HTTPException(
            status_code=400,
            detail="Add at least one ad format in channel settings before publishing.",
        )

    channel.status = "active"
    channel.is_visible = True
    db.commit()
    db.refresh(channel)

    return _channel_to_out(channel)


@router.post("/{channel_id}/pause", response_model=ChannelOut)
async def pause_channel(
    channel_id: int,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> ChannelOut:
    """
    Pause a channel (hide from marketplace temporarily).
    """
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.owner_telegram_id == telegram_id,
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    channel.status = "paused"
    channel.is_visible = False
    db.commit()
    db.refresh(channel)

    return _channel_to_out(channel)


@router.put("/{channel_id}/formats", response_model=list[AdFormatOut])
async def update_ad_formats(
    channel_id: int,
    formats: list[UpdateAdFormatIn],
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> list[AdFormatOut]:
    """
    Update ad formats and pricing for a channel.
    """
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.owner_telegram_id == telegram_id,
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Delete existing formats and create new ones
    db.execute(
        ChannelAdFormat.__table__.delete().where(ChannelAdFormat.channel_id == channel_id)
    )

    new_formats = []
    for f in formats:
        ad_format = ChannelAdFormat(
            channel_id=channel_id,
            format_type=f.formatType,
            is_enabled=f.isEnabled,
            price_stars=f.priceStars,
            price_ton=f.priceTon,
            price_usdt=f.priceUsdt,
            duration_hours=f.durationHours,
            eta_hours=f.etaHours,
            settings=json.dumps(f.settings) if f.settings is not None else None,
        )
        db.add(ad_format)
        new_formats.append(ad_format)

    db.commit()

    # Refresh to get IDs
    for f in new_formats:
        db.refresh(f)

    return [
        AdFormatOut(
            id=f.id,
            formatType=f.format_type,
            isEnabled=f.is_enabled,
            priceStars=f.price_stars,
            priceTon=float(f.price_ton) if f.price_ton else None,
            priceUsdt=float(f.price_usdt) if f.price_usdt else None,
            durationHours=f.duration_hours,
            etaHours=f.eta_hours,
        )
        for f in new_formats
    ]


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: int,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
):
    """
    Remove a channel from the marketplace.
    Note: This doesn't remove the bot from the channel, just hides it.
    """
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.owner_telegram_id == telegram_id,
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    channel.status = "removed"
    channel.is_visible = False
    db.commit()

    return {"ok": True, "message": "Channel removed from marketplace"}


@router.get("/market/{channel_id}/stats", response_model=MarketStatsOut)
async def get_market_channel_stats(
    channel_id: int,
    db: Session = Depends(get_db),
) -> MarketStatsOut:
    """
    Public statistics subset for marketplace viewers.
    Uses aggregated snapshot from ChannelStats (no ownership required).
    """
    # Ensure channel is active & visible
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.status == "active",
            Channel.is_visible.is_(True),
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    stats = db.execute(
        select(ChannelStats).where(ChannelStats.channel_id == channel_id)
    ).scalar_one_or_none()

    if not stats:
        return MarketStatsOut(
            channelId=channel_id,
            subscriberCount=channel.subscriber_count,
            subscriberGrowth24h=0,
            subscriberGrowth7d=0,
            subscriberGrowth30d=0,
            avgPostViews=0,
            avgReach24h=0,
            totalViews24h=0,
            totalViews7d=0,
            engagementRate=0.0,
            avgReactions=0,
            avgComments=0,
            avgShares=0,
            totalReactions=0,
            totalComments=0,
            totalShares=0,
            posts24h=0,
            posts7d=0,
            posts30d=0,
            posts90d=0,
            avgPostsPerDay=0.0,
            bestPost=None,
            dynamics="stable",
            dynamicsScore=0,
            lastPostAt=None,
            updatedAt=channel.updated_at,
            isCollecting=False,
            collectionStartedAt=None,
            collectionError=None,
        )

    # Build best post snapshot (if available)
    # Look up ChannelPost for actual has_media and media_url
    best_post: BestPostOut | None = None
    if stats.best_post_id and stats.best_post_views:
        post_row = db.execute(
            select(ChannelPost).where(
                ChannelPost.channel_id == channel_id,
                ChannelPost.message_id == stats.best_post_id,
            )
        ).scalar_one_or_none()
        media_url: str | None = None
        has_media = False
        is_album = False
        media_count = 1
        if post_row:
            has_media = bool(post_row.has_media)
            is_album = bool(post_row.is_album)
            media_count = post_row.media_count or 1
            if has_media and channel.username:
                media_url = post_row.media_url or f"/api/media/channel/{channel.username}/{stats.best_post_id}"
        best_post = BestPostOut(
            messageId=stats.best_post_id,
            views=stats.best_post_views,
            reactions=post_row.reactions if post_row else 0,
            comments=post_row.comments if post_row else 0,
            shares=post_row.shares if post_row else 0,
            text=stats.best_post_text,
            fullText=post_row.full_text if post_row and post_row.full_text else stats.best_post_text,
            hasMedia=has_media,
            mediaUrl=media_url,
            isAlbum=is_album,
            mediaCount=media_count,
        )

    return MarketStatsOut(
        channelId=channel_id,
        subscriberCount=stats.subscriber_count,
        subscriberGrowth24h=stats.subscriber_growth_24h,
        subscriberGrowth7d=stats.subscriber_growth_7d,
        subscriberGrowth30d=stats.subscriber_growth_30d,
        avgPostViews=stats.avg_post_views,
        avgReach24h=stats.avg_reach_24h,
        totalViews24h=stats.total_views_24h,
        totalViews7d=stats.total_views_7d,
        engagementRate=float(stats.engagement_rate),
        avgReactions=stats.avg_reactions,
        avgComments=stats.avg_comments,
        avgShares=stats.avg_shares,
        totalReactions=stats.total_reactions,
        totalComments=stats.total_comments,
        totalShares=stats.total_shares,
        posts24h=stats.posts_24h,
        posts7d=stats.posts_7d,
        posts30d=stats.posts_30d,
        posts90d=stats.posts_90d,
        avgPostsPerDay=float(stats.avg_posts_per_day),
        bestPost=best_post,
        dynamics=stats.dynamics,
        dynamicsScore=stats.dynamics_score,
        lastPostAt=stats.last_post_at,
        updatedAt=stats.updated_at,
        isCollecting=stats.is_collecting,
        collectionStartedAt=stats.collection_started_at,
        collectionError=stats.collection_error,
    )


@router.get("/market/{channel_id}/stats/history", response_model=ChannelStatsHistoryOut)
async def get_market_channel_stats_history(
    channel_id: int,
    period: str = "30d",
    db: Session = Depends(get_db),
) -> ChannelStatsHistoryOut:
    """
    Public historical statistics for charts (marketplace viewers).
    Period: '7d', '30d', '90d'
    """
    from datetime import timedelta

    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.status == "active",
            Channel.is_visible.is_(True),
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    days = 7 if period == "7d" else (30 if period == "30d" else 90)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    history = db.execute(
        select(ChannelStatsHistory)
        .where(
            ChannelStatsHistory.channel_id == channel_id,
            ChannelStatsHistory.date >= cutoff,
        )
        .order_by(ChannelStatsHistory.date.asc())
    ).scalars().all()

    # Fallback: build from ChannelPost when no history
    if not history:
        agg = (
            db.execute(
                select(
                    func.date(ChannelPost.posted_at).label("date"),
                    func.sum(ChannelPost.views).label("total_views"),
                    func.count(ChannelPost.id).label("total_posts"),
                    func.sum(ChannelPost.reactions).label("reactions"),
                    func.sum(ChannelPost.comments).label("comments"),
                    func.sum(ChannelPost.shares).label("shares"),
                )
                .where(
                    ChannelPost.channel_id == channel_id,
                    ChannelPost.posted_at >= cutoff,
                )
                .group_by(func.date(ChannelPost.posted_at))
                .order_by(func.date(ChannelPost.posted_at).asc())
            )
            .all()
        )
        subs = channel.subscriber_count or 0
        data = [
            StatsHistoryPointOut(
                date=str(row.date),
                subscriberCount=subs,
                totalViews=row.total_views or 0,
                totalPosts=row.total_posts or 0,
                avgPostViews=(row.total_views or 0) // max(1, row.total_posts or 1),
                engagementRate=0.0,
                reactions=row.reactions or 0,
                comments=row.comments or 0,
                shares=row.shares or 0,
            )
            for row in agg
        ]
    else:
        data = [
            StatsHistoryPointOut(
                date=h.date.strftime("%Y-%m-%d"),
                subscriberCount=h.subscriber_count,
                totalViews=h.total_views,
                totalPosts=h.total_posts,
                avgPostViews=h.avg_post_views,
                engagementRate=float(h.engagement_rate),
                reactions=h.reactions,
                comments=h.comments,
                shares=h.shares,
            )
            for h in history
        ]

    return ChannelStatsHistoryOut(
        channelId=channel_id,
        period=period,
        data=data,
    )


@router.get("/market/{channel_id}/top-posts", response_model=TopPostsOut)
async def get_market_channel_top_posts(
    channel_id: int,
    limit: int = 5,
    db: Session = Depends(get_db),
) -> TopPostsOut:
    """
    Top posts by views for marketplace viewers.
    """
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.status == "active",
            Channel.is_visible.is_(True),
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    posts = (
        db.execute(
            select(ChannelPost)
            .where(ChannelPost.channel_id == channel_id)
            .order_by(ChannelPost.views.desc())
            .limit(limit)
        )
        .scalars().all()
    )

    result = []
    for p in posts:
        media_url: str | None = None
        if p.has_media and channel.username:
            media_url = p.media_url or f"/api/media/channel/{channel.username}/{p.message_id}"
        result.append(
            TopPostOut(
                messageId=p.message_id,
                views=p.views,
                reactions=p.reactions,
                comments=p.comments,
                shares=p.shares,
                text=(p.text_preview[:256] if p.text_preview else None),
                fullText=p.full_text,
                hasMedia=p.has_media,
                mediaUrl=media_url,
                isAlbum=p.is_album,
                mediaCount=p.media_count,
                postedAt=p.posted_at.strftime("%Y-%m-%d %H:%M") if p.posted_at else None,
            )
        )

    return TopPostsOut(posts=result)


@router.get("/{channel_id}/stats", response_model=ChannelStatsOut)
async def get_channel_stats(
    channel_id: int,
    period: str = "30d",  # '7d', '30d', '90d'
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> ChannelStatsOut:
    """
    Get statistics for a channel for a specific period.
    Period: '7d', '30d', '90d'
    """
    from datetime import timedelta
    from app.db.models import ChannelPost
    from sqlalchemy import func
    
    # Verify ownership
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.owner_telegram_id == telegram_id,
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Get base stats
    stats = db.execute(
        select(ChannelStats).where(ChannelStats.channel_id == channel_id)
    ).scalar_one_or_none()

    if not stats:
        # Return default stats if not yet collected
        return ChannelStatsOut(
            subscriberCount=channel.subscriber_count,
            subscriberGrowth24h=0,
            subscriberGrowth7d=0,
            subscriberGrowth30d=0,
            avgPostViews=0,
            avgReach24h=0,
            totalViews24h=0,
            totalViews7d=0,
            engagementRate=0.0,
            avgReactions=0,
            avgComments=0,
            avgShares=0,
            totalReactions=0,
            totalComments=0,
            totalShares=0,
            posts24h=0,
            posts7d=0,
            posts30d=0,
            posts90d=0,
            avgPostsPerDay=0.0,
            bestPost=None,
            dynamics="stable",
            dynamicsScore=0,
            lastPostAt=None,
            updatedAt=channel.updated_at,
            isCollecting=False,
            collectionStartedAt=None,
            collectionError=None,
        )

    # Calculate period-based stats from posts
    days = 30
    if period == "7d":
        days = 7
    elif period == "90d":
        days = 90
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get posts for the period
    posts = db.execute(
        select(ChannelPost).where(
            ChannelPost.channel_id == channel_id,
            ChannelPost.posted_at >= cutoff,
        )
    ).scalars().all()
    
    # Calculate metrics for the period
    posts_count = len(posts)
    total_views = sum(p.views for p in posts)
    total_reactions = sum(p.reactions for p in posts)
    total_comments = sum(p.comments for p in posts)
    total_shares = sum(p.shares for p in posts)
    
    avg_views = total_views // posts_count if posts_count else 0
    avg_reactions = total_reactions // posts_count if posts_count else 0
    avg_comments = total_comments // posts_count if posts_count else 0
    avg_shares = total_shares // posts_count if posts_count else 0
    avg_posts_per_day = round(posts_count / days, 2) if days else 0
    
    # Engagement rate for the period
    total_engagement = total_reactions + total_comments + total_shares
    if total_views > 0:
        engagement_rate = round((total_engagement / total_views) * 100, 2)
    else:
        engagement_rate = 0.0
    
    # Find best post for the period
    best_post = None
    if posts:
        best = max(posts, key=lambda p: p.views)
        best_post = BestPostOut(
            messageId=best.message_id,
            views=best.views,
            reactions=best.reactions,
            comments=best.comments,
            shares=best.shares,
            text=best.text_preview[:100] if best.text_preview else None,
            fullText=best.full_text or best.text_preview,  # Full text for expanded view
            hasMedia=best.has_media,
            mediaUrl=getattr(best, 'media_url', None),  # Media thumbnail URL
            isAlbum=getattr(best, 'is_album', False),  # Is this a grouped media post
            mediaCount=getattr(best, 'media_count', 1),  # Number of media items
        )
    
    # Calculate growth for the period
    growth = 0
    if period == "7d":
        growth = stats.subscriber_growth_7d
    elif period == "30d":
        growth = stats.subscriber_growth_30d
    else:
        growth = stats.subscriber_growth_30d  # Use 30d for 90d period
    
    # Calculate dynamics for the period
    dynamics = "stable"
    dynamics_score = 0
    if posts_count >= 4:
        mid = posts_count // 2
        sorted_posts = sorted(posts, key=lambda p: p.posted_at)
        first_half_views = sum(p.views for p in sorted_posts[:mid])
        second_half_views = sum(p.views for p in sorted_posts[mid:])
        
        if first_half_views > 0:
            change = ((second_half_views - first_half_views) / first_half_views) * 100
            dynamics_score = int(min(100, max(-100, change)))
            
            if change > 10:
                dynamics = "growing"
            elif change < -10:
                dynamics = "declining"

    return ChannelStatsOut(
        subscriberCount=stats.subscriber_count,
        subscriberGrowth24h=stats.subscriber_growth_24h,
        subscriberGrowth7d=stats.subscriber_growth_7d,
        subscriberGrowth30d=stats.subscriber_growth_30d,
        avgPostViews=avg_views,
        avgReach24h=stats.avg_reach_24h,
        totalViews24h=stats.total_views_24h,
        totalViews7d=total_views if period == "7d" else stats.total_views_7d,
        engagementRate=engagement_rate,
        avgReactions=avg_reactions,
        avgComments=avg_comments,
        avgShares=avg_shares,
        totalReactions=total_reactions,
        totalComments=total_comments,
        totalShares=total_shares,
        posts24h=stats.posts_24h,
        posts7d=stats.posts_7d,
        posts30d=stats.posts_30d,
        posts90d=posts_count if period == "90d" else stats.posts_90d,
        avgPostsPerDay=avg_posts_per_day,
        bestPost=best_post,
        dynamics=dynamics,
        dynamicsScore=dynamics_score,
        lastPostAt=stats.last_post_at,
        updatedAt=stats.updated_at,
        isCollecting=stats.is_collecting,
        collectionStartedAt=stats.collection_started_at,
        collectionError=stats.collection_error,
    )


@router.get("/{channel_id}/stats/history", response_model=ChannelStatsHistoryOut)
async def get_channel_stats_history(
    channel_id: int,
    period: str = "7d",
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> ChannelStatsHistoryOut:
    """
    Get historical statistics for charts.
    Period: '7d', '30d', '90d'
    """
    # Verify ownership
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.owner_telegram_id == telegram_id,
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Determine days based on period
    days = 7
    if period == "30d":
        days = 30
    elif period == "90d":
        days = 90

    # Get history
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    history = db.execute(
        select(ChannelStatsHistory)
        .where(
            ChannelStatsHistory.channel_id == channel_id,
            ChannelStatsHistory.date >= cutoff,
        )
        .order_by(ChannelStatsHistory.date.asc())
    ).scalars().all()

    # If no history, return empty - will show loading state
    if not history:
        return ChannelStatsHistoryOut(
            channelId=channel_id,
            period=period,
            data=[],
        )

    return ChannelStatsHistoryOut(
        channelId=channel_id,
        period=period,
        data=[
            StatsHistoryPointOut(
                date=h.date.strftime("%Y-%m-%d"),
                subscriberCount=h.subscriber_count,
                totalViews=h.total_views,
                totalPosts=h.total_posts,
                avgPostViews=h.avg_post_views,
                engagementRate=float(h.engagement_rate),
                reactions=h.reactions,
                comments=h.comments,
                shares=h.shares,
            )
            for h in history
        ],
    )


class RefreshStatsOut(BaseModel):
    ok: bool
    message: str
    subscriberCount: int | None = None
    avgPostViews: int | None = None


@router.post("/{channel_id}/stats/refresh", response_model=RefreshStatsOut)
async def refresh_channel_stats(
    channel_id: int,
    background: bool = False,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> RefreshStatsOut:
    """
    Manually trigger statistics refresh for a channel.
    
    Uses Telethon to collect 90 days of posts and calculate all metrics.
    Set background=true to run collection in background (returns immediately).
    """
    import asyncio
    
    # Verify ownership
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.owner_telegram_id == telegram_id,
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Check if already collecting
    stats = db.execute(
        select(ChannelStats).where(ChannelStats.channel_id == channel_id)
    ).scalar_one_or_none()
    
    if stats and stats.is_collecting:
        return RefreshStatsOut(
            ok=False,
            message="Collection already in progress",
            subscriberCount=stats.subscriber_count,
            avgPostViews=stats.avg_post_views,
        )

    try:
        from app.services.channel_collector import channel_collector
        from app.services.scheduler import update_single_channel_info
        
        # First, update channel info (title, username, photo)
        logger.info(f"Updating channel info for channel {channel_id} (@{channel.username})")
        logger.info(f"Before update - Title: {channel.title}, Username: {channel.username}, Photo: {channel.photo_url[:50] if channel.photo_url else None}...")
        
        result = await update_single_channel_info(channel, db, update_posts_media=True)
        db.commit()
        db.refresh(channel)  # Refresh to get updated values
        
        logger.info(f"After update - Title: {channel.title}, Username: {channel.username}, Photo: {channel.photo_url[:50] if channel.photo_url else None}...")
        
        if result.get('photos', 0) > 0 or result.get('titles', 0) > 0 or result.get('usernames', 0) > 0 or result.get('subscribers', 0) > 0 or result.get('posts_media', 0) > 0:
            logger.info(f"Channel {channel_id} updated: {result}")
        else:
            logger.info(f"Channel {channel_id} info was already up to date")
        
        if background:
            # Run in background
            asyncio.create_task(channel_collector.collect_channel_stats(channel_id))
            return RefreshStatsOut(
                ok=True,
                message="Collection started in background",
                subscriberCount=channel.subscriber_count,
                avgPostViews=stats.avg_post_views if stats else 0,
            )
        else:
            # Run synchronously
            result = await channel_collector.collect_channel_stats(channel_id)
            
            # Refresh stats
            db.expire_all()
            stats = db.execute(
                select(ChannelStats).where(ChannelStats.channel_id == channel_id)
            ).scalar_one_or_none()
            
            return RefreshStatsOut(
                ok=result.get("success", False),
                message=result.get("error") or f"Collected {result.get('posts_collected', 0)} posts",
                subscriberCount=stats.subscriber_count if stats else channel.subscriber_count,
                avgPostViews=stats.avg_post_views if stats else 0,
            )
            
    except Exception as e:
        return RefreshStatsOut(
            ok=False,
            message=f"Error: {str(e)}",
            subscriberCount=channel.subscriber_count,
            avgPostViews=0,
        )


class AIInsightsOut(BaseModel):
    ok: bool
    channelId: int
    insights: str
    generatedAt: str


@router.get("/{channel_id}/ai-insights", response_model=AIInsightsOut)
async def get_ai_insights(
    channel_id: int,
    days_back: int = 30,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> AIInsightsOut:
    """
    Get AI-powered insights for a channel.
    
    Uses OpenAI/OpenRouter to analyze channel performance and provide recommendations.
    """
    # Verify ownership
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.owner_telegram_id == telegram_id,
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    try:
        from app.services.ai_analytics import ai_analytics
        
        insights = await ai_analytics.generate_insights(db, channel, days_back)
        
        return AIInsightsOut(
            ok=True,
            channelId=channel_id,
            insights=insights,
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )
        
    except Exception as e:
        return AIInsightsOut(
            ok=False,
            channelId=channel_id,
            insights=f"Error generating insights: {str(e)}",
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )


class ContentSuggestionsOut(BaseModel):
    ok: bool
    channelId: int
    suggestions: str
    generatedAt: str


@router.get("/{channel_id}/content-suggestions", response_model=ContentSuggestionsOut)
async def get_content_suggestions(
    channel_id: int,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> ContentSuggestionsOut:
    """
    Get AI-powered content suggestions based on best performing posts.
    """
    # Verify ownership
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.owner_telegram_id == telegram_id,
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    try:
        from app.services.ai_analytics import ai_analytics
        
        suggestions = await ai_analytics.generate_content_suggestions(db, channel)
        
        return ContentSuggestionsOut(
            ok=True,
            channelId=channel_id,
            suggestions=suggestions,
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )
        
    except Exception as e:
        return ContentSuggestionsOut(
            ok=False,
            channelId=channel_id,
            suggestions=f"Error generating suggestions: {str(e)}",
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )


class StructuredInsightsOut(BaseModel):
    """Structured AI insights with JSON response."""
    ok: bool
    channelId: int
    data: dict | None = None
    error: str | None = None
    generatedAt: str


@router.get("/{channel_id}/ai-insights-structured", response_model=StructuredInsightsOut)
async def get_structured_ai_insights(
    channel_id: int,
    force_refresh: bool = False,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> StructuredInsightsOut:
    """
    Get structured AI insights for a channel.
    
    Insights are cached for 7 days. Set force_refresh=true to regenerate.
    
    Returns JSON with:
    - category: channel category
    - targetAudience: target audience description
    - rating: score (1-10) with explanation
    - strengths: list of strengths
    - weaknesses: list of areas for improvement
    - growthForecast: predicted growth
    - advertisingRecommendation: why buy ads, best for, audience quality
    - contentTips: content recommendations
    """
    import json as json_module
    
    # Verify ownership
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.owner_telegram_id == telegram_id,
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Get stats
    stats = db.execute(
        select(ChannelStats).where(ChannelStats.channel_id == channel_id)
    ).scalar_one_or_none()

    if not stats:
        return StructuredInsightsOut(
            ok=False,
            channelId=channel_id,
            error="No statistics available. Collect stats first.",
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )

    # Check if we have cached insights (less than 7 days old)
    if not force_refresh and stats.ai_insights_json and stats.ai_insights_generated_at:
        age = datetime.now(timezone.utc) - stats.ai_insights_generated_at
        if age.days < 7:
            try:
                cached_data = json_module.loads(stats.ai_insights_json)
                return StructuredInsightsOut(
                    ok=True,
                    channelId=channel_id,
                    data=cached_data,
                    generatedAt=stats.ai_insights_generated_at.isoformat(),
                )
            except json_module.JSONDecodeError:
                pass  # Invalid cache, regenerate

    try:
        from app.services.ai_analytics import ai_analytics
        
        result = await ai_analytics.generate_structured_insights(db, channel)
        
        if result.get("error"):
            # Store error
            stats.ai_insights_error = result.get("error")[:256]
            db.commit()
            
            return StructuredInsightsOut(
                ok=False,
                channelId=channel_id,
                error=result.get("error"),
                generatedAt=datetime.now(timezone.utc).isoformat(),
            )
        
        # Cache the result
        stats.ai_insights_json = json_module.dumps(result, ensure_ascii=False)
        stats.ai_insights_generated_at = datetime.now(timezone.utc)
        stats.ai_insights_error = None
        db.commit()
        
        return StructuredInsightsOut(
            ok=True,
            channelId=channel_id,
            data=result,
            generatedAt=stats.ai_insights_generated_at.isoformat(),
        )
        
    except Exception as e:
        return StructuredInsightsOut(
            ok=False,
            channelId=channel_id,
            error=str(e),
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )


@router.get("/market/{channel_id}/ai-insights-structured", response_model=StructuredInsightsOut)
async def get_market_structured_ai_insights(
    channel_id: int,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
) -> StructuredInsightsOut:
    """
    Public structured AI insights for marketplace viewers.
    Same data as owner endpoint, but only for active & visible channels.
    """
    import json as json_module

    # Ensure channel is active & visible
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.status == "active",
            Channel.is_visible.is_(True),
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Get stats
    stats = db.execute(
        select(ChannelStats).where(ChannelStats.channel_id == channel_id)
    ).scalar_one_or_none()

    if not stats:
        return StructuredInsightsOut(
            ok=False,
            channelId=channel_id,
            error="No statistics available. Collect stats first.",
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )

    # Check if we have cached insights (less than 7 days old)
    if not force_refresh and stats.ai_insights_json and stats.ai_insights_generated_at:
        age = datetime.now(timezone.utc) - stats.ai_insights_generated_at
        if age.days < 7:
            try:
                cached_data = json_module.loads(stats.ai_insights_json)
                return StructuredInsightsOut(
                    ok=True,
                    channelId=channel_id,
                    data=cached_data,
                    generatedAt=stats.ai_insights_generated_at.isoformat(),
                )
            except json_module.JSONDecodeError:
                pass  # Invalid cache, regenerate

    try:
        from app.services.ai_analytics import ai_analytics
        
        result = await ai_analytics.generate_structured_insights(db, channel)
        
        if result.get("error"):
            # Store error
            stats.ai_insights_error = result.get("error")[:256]
            db.commit()
            
            return StructuredInsightsOut(
                ok=False,
                channelId=channel_id,
                error=result.get("error"),
                generatedAt=datetime.now(timezone.utc).isoformat(),
            )
        
        # Cache the result
        stats.ai_insights_json = json_module.dumps(result, ensure_ascii=False)
        stats.ai_insights_generated_at = datetime.now(timezone.utc)
        stats.ai_insights_error = None
        db.commit()
        
        return StructuredInsightsOut(
            ok=True,
            channelId=channel_id,
            data=result,
            generatedAt=stats.ai_insights_generated_at.isoformat(),
        )
        
    except Exception as e:
        return StructuredInsightsOut(
            ok=False,
            channelId=channel_id,
            error=str(e),
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )


@router.post("/{channel_id}/parse", response_model=RefreshStatsOut)
async def parse_channel_with_telethon(
    channel_id: int,
    limit: int = 100,
    days_back: int = 30,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> RefreshStatsOut:
    """
    Parse channel using Telethon for detailed post analytics.
    
    This provides more detailed data than TGStat including reactions,
    replies, and individual post performance.
    """
    # Verify ownership
    channel = db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.owner_telegram_id == telegram_id,
        )
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    try:
        from app.services.channel_parser import channel_parser
        
        success = await channel_parser.collect_channel_stats(
            db, channel, limit=limit, days_back=days_back
        )
        
        if success:
            stats = db.execute(
                select(ChannelStats).where(ChannelStats.channel_id == channel_id)
            ).scalar_one_or_none()
            
            return RefreshStatsOut(
                ok=True,
                message="Channel parsed successfully",
                subscriberCount=stats.subscriber_count if stats else channel.subscriber_count,
                avgPostViews=stats.avg_post_views if stats else 0,
            )
        else:
            return RefreshStatsOut(
                ok=False,
                message="Failed to parse channel",
            )
            
    except Exception as e:
        return RefreshStatsOut(
            ok=False,
            message=f"Error: {str(e)}",
        )

