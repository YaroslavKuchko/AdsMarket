"""
Channel statistics collector using Pyrogram userbot.

Collects:
- Subscriber counts
- Post views, reactions, comments, shares
- Posting frequency
- Engagement metrics
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Channel, ChannelPost, ChannelStats, ChannelStatsHistory
from app.db.session import SessionLocal

if TYPE_CHECKING:
    from pyrogram import Client
    from pyrogram.types import Message

logger = logging.getLogger(__name__)


class StatsCollector:
    """Collects channel statistics using Pyrogram userbot."""

    def __init__(self):
        self.client: Client | None = None
        self._started = False

    async def start(self):
        """Initialize and start the Pyrogram client."""
        if self._started:
            return

        if not settings.pyrogram_api_id or not settings.pyrogram_api_hash:
            logger.warning("Pyrogram API credentials not configured. Stats collection disabled.")
            return

        try:
            from pyrogram import Client

            self.client = Client(
                name="stats_collector",
                api_id=settings.pyrogram_api_id,
                api_hash=settings.pyrogram_api_hash,
                phone_number=settings.pyrogram_phone or None,
                workdir="./sessions",
            )

            await self.client.start()
            self._started = True
            logger.info("Stats collector started successfully")
        except Exception as e:
            logger.error(f"Failed to start stats collector: {e}")
            self.client = None

    async def stop(self):
        """Stop the Pyrogram client."""
        if self.client and self._started:
            await self.client.stop()
            self._started = False
            logger.info("Stats collector stopped")

    async def collect_all_channels(self):
        """Collect statistics for all active channels."""
        if not self.client or not self._started:
            logger.warning("Stats collector not started, skipping collection")
            return

        db = SessionLocal()
        try:
            # Get all active channels
            channels = db.execute(
                select(Channel).where(
                    Channel.status.in_(["active", "pending", "paused"])
                )
            ).scalars().all()

            logger.info(f"Collecting stats for {len(channels)} channels")

            for channel in channels:
                try:
                    await self.collect_channel_stats(db, channel)
                    await asyncio.sleep(2)  # Rate limiting
                except Exception as e:
                    logger.error(f"Failed to collect stats for channel {channel.id}: {e}")

            db.commit()
            logger.info("Stats collection completed")
        except Exception as e:
            logger.error(f"Stats collection failed: {e}")
            db.rollback()
        finally:
            db.close()

    def _convert_channel_id(self, telegram_id: int) -> int | str:
        """
        Convert Telegram Bot API channel ID to Pyrogram format.
        Bot API: -1001234567890
        Pyrogram: 1234567890 or @username
        """
        id_str = str(telegram_id)
        if id_str.startswith("-100"):
            return int(id_str[4:])  # Remove -100 prefix
        elif id_str.startswith("-"):
            return int(id_str[1:])  # Remove - prefix
        return telegram_id

    async def collect_channel_stats(self, db: Session, channel: Channel):
        """Collect statistics for a single channel."""
        if not self.client:
            return

        try:
            # Convert channel ID for Pyrogram
            pyrogram_id = self._convert_channel_id(channel.telegram_id)
            
            # Try username first if available
            chat_identifier = f"@{channel.username}" if channel.username else pyrogram_id
            
            # Get chat info
            chat = await self.client.get_chat(chat_identifier)

            # Update subscriber count
            member_count = chat.members_count or 0
            old_subscriber_count = channel.subscriber_count
            channel.subscriber_count = member_count

            # Get or create stats record
            stats = db.execute(
                select(ChannelStats).where(ChannelStats.channel_id == channel.id)
            ).scalar_one_or_none()

            if not stats:
                stats = ChannelStats(channel_id=channel.id)
                db.add(stats)

            # Calculate subscriber growth
            stats.subscriber_count = member_count

            # Get recent messages for engagement calculation
            messages = []
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            async for msg in self.client.get_chat_history(chat_identifier, limit=50):
                if msg.date:
                    msg_date = msg.date
                    if msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=timezone.utc)
                    if msg_date > week_ago:
                        messages.append(msg)

            if messages:
                # Calculate metrics from messages
                total_views = 0
                total_reactions = 0
                total_comments = 0
                total_shares = 0
                posts_24h = 0
                posts_7d = len(messages)

                now = datetime.now(timezone.utc)
                day_ago = now - timedelta(days=1)

                for msg in messages:
                    views = msg.views or 0
                    total_views += views

                    # Reactions
                    if msg.reactions:
                        for reaction in msg.reactions.reactions:
                            total_reactions += reaction.count

                    # Comments (replies)
                    if hasattr(msg, 'replies') and msg.replies:
                        total_comments += msg.replies.replies or 0

                    # Forwards
                    if hasattr(msg, 'forwards'):
                        total_shares += msg.forwards or 0

                    # Count posts in last 24h (handle timezone-naive dates)
                    if msg.date:
                        msg_date = msg.date
                        if msg_date.tzinfo is None:
                            msg_date = msg_date.replace(tzinfo=timezone.utc)
                        if msg_date > day_ago:
                            posts_24h += 1

                    # Save post data
                    await self._save_post(db, channel.id, msg)

                # Update stats
                stats.avg_post_views = total_views // max(len(messages), 1)
                stats.avg_reach_24h = stats.avg_post_views  # Simplified
                
                # Calculate views in last 24h with timezone handling
                views_24h = 0
                for m in messages:
                    if m.date:
                        m_date = m.date
                        if m_date.tzinfo is None:
                            m_date = m_date.replace(tzinfo=timezone.utc)
                        if m_date > day_ago:
                            views_24h += m.views or 0
                stats.total_views_24h = views_24h
                stats.total_views_7d = total_views

                stats.avg_reactions = total_reactions // max(len(messages), 1)
                stats.avg_comments = total_comments // max(len(messages), 1)
                stats.avg_shares = total_shares // max(len(messages), 1)

                stats.posts_24h = posts_24h
                stats.posts_7d = posts_7d
                stats.avg_posts_per_day = Decimal(str(round(posts_7d / 7, 2)))

                # Calculate engagement rate
                if member_count > 0:
                    stats.engagement_rate = Decimal(
                        str(round((stats.avg_post_views / member_count) * 100, 2))
                    )

                # Determine dynamics
                if messages:
                    last_date = messages[0].date
                    if last_date and last_date.tzinfo is None:
                        last_date = last_date.replace(tzinfo=timezone.utc)
                    stats.last_post_at = last_date

                # Calculate dynamics based on subscriber growth
                stats.subscriber_growth_24h = member_count - old_subscriber_count
                # For 7d and 30d, we need historical data
                await self._calculate_growth(db, stats, channel.id)

            # Save daily snapshot
            await self._save_daily_snapshot(db, channel.id, stats)

            logger.info(f"Updated stats for channel {channel.title}: {member_count} subs, {stats.avg_post_views} avg views")

        except Exception as e:
            logger.error(f"Error collecting stats for channel {channel.telegram_id}: {e}")
            raise

    async def _save_post(self, db: Session, channel_id: int, msg: "Message"):
        """Save or update post data."""
        from app.db.models import ChannelPost

        # Check if post exists
        existing = db.execute(
            select(ChannelPost).where(
                ChannelPost.channel_id == channel_id,
                ChannelPost.message_id == msg.id,
            )
        ).scalar_one_or_none()

        if existing:
            # Update stats
            existing.views = msg.views or 0
            if msg.reactions:
                existing.reactions = sum(r.count for r in msg.reactions.reactions)
            if hasattr(msg, 'replies') and msg.replies:
                existing.comments = msg.replies.replies or 0
            if hasattr(msg, 'forwards'):
                existing.shares = msg.forwards or 0
            existing.stats_updated_at = datetime.now(timezone.utc)
        else:
            # Create new
            text_preview = ""
            if msg.text:
                text_preview = msg.text[:200]
            elif msg.caption:
                text_preview = msg.caption[:200]

            post = ChannelPost(
                channel_id=channel_id,
                message_id=msg.id,
                text_preview=text_preview,
                has_media=bool(msg.photo or msg.video or msg.document),
                views=msg.views or 0,
                reactions=sum(r.count for r in msg.reactions.reactions) if msg.reactions else 0,
                comments=msg.replies.replies if hasattr(msg, 'replies') and msg.replies else 0,
                shares=msg.forwards if hasattr(msg, 'forwards') else 0,
                posted_at=msg.date.replace(tzinfo=timezone.utc) if msg.date and msg.date.tzinfo is None else (msg.date or datetime.now(timezone.utc)),
                stats_updated_at=datetime.now(timezone.utc),
            )
            db.add(post)

    async def _calculate_growth(self, db: Session, stats: ChannelStats, channel_id: int):
        """Calculate subscriber growth from historical data."""
        from datetime import date as date_type
        today = date_type.today()

        # 7 days ago
        seven_days_ago = today - timedelta(days=7)
        history_7d = db.execute(
            select(ChannelStatsHistory)
            .where(
                ChannelStatsHistory.channel_id == channel_id,
                ChannelStatsHistory.date >= seven_days_ago,
            )
            .order_by(ChannelStatsHistory.date.asc())
            .limit(1)
        ).scalar_one_or_none()

        if history_7d:
            stats.subscriber_growth_7d = stats.subscriber_count - history_7d.subscriber_count

        # 30 days ago
        thirty_days_ago = today - timedelta(days=30)
        history_30d = db.execute(
            select(ChannelStatsHistory)
            .where(
                ChannelStatsHistory.channel_id == channel_id,
                ChannelStatsHistory.date >= thirty_days_ago,
            )
            .order_by(ChannelStatsHistory.date.asc())
            .limit(1)
        ).scalar_one_or_none()

        if history_30d:
            stats.subscriber_growth_30d = stats.subscriber_count - history_30d.subscriber_count

        # Determine dynamics
        growth_rate = 0
        if history_7d and history_7d.subscriber_count > 0:
            growth_rate = (stats.subscriber_count - history_7d.subscriber_count) / history_7d.subscriber_count * 100

        if growth_rate > 2:
            stats.dynamics = "growing"
            stats.dynamics_score = min(int(growth_rate * 10), 100)
        elif growth_rate < -2:
            stats.dynamics = "declining"
            stats.dynamics_score = max(int(growth_rate * 10), -100)
        else:
            stats.dynamics = "stable"
            stats.dynamics_score = 0

    async def _save_daily_snapshot(self, db: Session, channel_id: int, stats: ChannelStats):
        """Save daily statistics snapshot for charts."""
        today = datetime.now(timezone.utc).date()  # Use date, not datetime

        # Check if snapshot exists for today
        existing = db.execute(
            select(ChannelStatsHistory).where(
                ChannelStatsHistory.channel_id == channel_id,
                ChannelStatsHistory.date == today,
            )
        ).scalar_one_or_none()

        if existing:
            # Update existing snapshot
            existing.subscriber_count = stats.subscriber_count
            existing.total_views = stats.total_views_24h
            existing.total_posts = stats.posts_24h
            existing.avg_post_views = stats.avg_post_views
            existing.engagement_rate = stats.engagement_rate
            existing.reactions = stats.avg_reactions * stats.posts_24h
            existing.comments = stats.avg_comments * stats.posts_24h
            existing.shares = stats.avg_shares * stats.posts_24h
        else:
            # Create new snapshot
            snapshot = ChannelStatsHistory(
                channel_id=channel_id,
                date=today,
                subscriber_count=stats.subscriber_count,
                total_views=stats.total_views_24h,
                total_posts=stats.posts_24h,
                avg_post_views=stats.avg_post_views,
                engagement_rate=stats.engagement_rate,
                reactions=stats.avg_reactions * stats.posts_24h,
                comments=stats.avg_comments * stats.posts_24h,
                shares=stats.avg_shares * stats.posts_24h,
            )
            db.add(snapshot)


# Global instance
stats_collector = StatsCollector()

