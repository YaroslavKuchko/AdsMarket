"""
Telegram Channel Parser using Telethon.

Parses channel messages, views, reactions, forwards for analytics.
Falls back to TGStat for initial/subscriber history data.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    FloodWaitError,
    UsernameNotOccupiedError,
)
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import Channel as TelethonChannel
from telethon.tl.types import InputChannel, Message

from app.core.config import settings
from app.db.models import Channel, ChannelPost, ChannelStats, ChannelStatsHistory
from app.services.tgstat_parser import fetch_tgstat_data

logger = logging.getLogger(__name__)


class TelegramChannelParser:
    """
    Telegram channel parser using Telethon.
    
    More reliable than Pyrogram for some operations like GetFullChannelRequest.
    """
    
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.session_path = "sessions/telethon_session"
        self._started = False
    
    async def start(self) -> bool:
        """Start the Telethon client."""
        if self._started:
            return True
        
        try:
            self.client = TelegramClient(
                self.session_path,
                settings.pyrogram_api_id,
                settings.pyrogram_api_hash,
            )
            
            await self.client.start(phone=settings.pyrogram_phone)
            self._started = True
            logger.info("Telethon client started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Telethon client: {e}")
            return False
    
    async def stop(self):
        """Stop the Telethon client."""
        if self.client:
            await self.client.disconnect()
            self._started = False
            logger.info("Telethon client disconnected")
    
    async def get_channel_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Get channel information."""
        if not self._started:
            if not await self.start():
                return None
        
        try:
            username = username.lstrip("@")
            entity = await self.client.get_entity(username)
            
            if not isinstance(entity, TelethonChannel):
                logger.warning(f"Entity {username} is not a channel")
                return None
            
            # Get full channel info for subscriber count
            input_channel = InputChannel(entity.id, entity.access_hash)
            full = await self.client(GetFullChannelRequest(input_channel))
            
            return {
                "channel_id": entity.id,
                "username": entity.username,
                "title": entity.title,
                "description": getattr(full.full_chat, "about", "") or "",
                "subscribers_count": full.full_chat.participants_count,
                "is_broadcast": entity.broadcast,
                "is_megagroup": entity.megagroup,
            }
            
        except UsernameNotOccupiedError:
            logger.error(f"Channel {username} does not exist")
            return None
        except ChannelPrivateError:
            logger.error(f"Channel {username} is private")
            return None
        except Exception as e:
            logger.error(f"Error getting channel info for {username}: {e}")
            return None
    
    async def parse_channel_messages(
        self,
        username: str,
        limit: int = 100,
        days_back: int = 30,
    ) -> List[Dict[str, Any]]:
        """Parse channel messages with all metrics."""
        if not self._started:
            if not await self.start():
                return []
        
        try:
            username = username.lstrip("@")
            messages_data = []
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            
            async for message in self.client.iter_messages(username, limit=limit):
                # Skip old messages
                msg_date = message.date
                if msg_date.tzinfo is None:
                    msg_date = msg_date.replace(tzinfo=timezone.utc)
                if msg_date < cutoff_date:
                    continue
                
                # Skip non-message types
                if not isinstance(message, Message):
                    continue
                
                message_data = self._extract_message_data(message)
                if message_data:
                    messages_data.append(message_data)
                
                # Delay to avoid flood limits
                await asyncio.sleep(settings.flood_wait_delay)
            
            logger.info(f"Parsed {len(messages_data)} messages from @{username}")
            return messages_data
            
        except FloodWaitError as e:
            logger.warning(f"Flood wait: {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return []
        except Exception as e:
            logger.error(f"Error parsing messages from {username}: {e}")
            return []
    
    def _extract_message_data(self, message: Message) -> Optional[Dict[str, Any]]:
        """Extract data from a single message."""
        try:
            # Replies count
            replies_count = 0
            if hasattr(message, "replies") and message.replies:
                replies_count = getattr(message.replies, "replies", 0) or 0
            
            # Reactions
            reactions_count = 0
            reactions_data = []
            if hasattr(message, "reactions") and message.reactions:
                for reaction in message.reactions.results:
                    emoji = "👍"
                    if hasattr(reaction.reaction, "emoji"):
                        emoji = reaction.reaction.emoji
                    reactions_data.append({
                        "emoji": emoji,
                        "count": reaction.count,
                    })
                    reactions_count += reaction.count
            
            # Media type
            media_type = None
            if message.media:
                media_type = type(message.media).__name__
            
            # Links
            links = self._extract_links(message.text or message.raw_text or "")
            
            return {
                "message_id": message.id,
                "text": message.text or message.raw_text or "",
                "date": message.date,
                "views": getattr(message, "views", 0) or 0,
                "forwards": getattr(message, "forwards", 0) or 0,
                "replies": replies_count,
                "reactions_count": reactions_count,
                "reactions_data": json.dumps(reactions_data) if reactions_data else None,
                "media_type": media_type,
                "links": json.dumps(links) if links else None,
            }
            
        except Exception as e:
            logger.error(f"Error extracting message data: {e}")
            return None
    
    def _extract_links(self, text: str) -> List[str]:
        """Extract links from text."""
        if not text:
            return []
        
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        telegram_pattern = r't\.me/[a-zA-Z0-9_]+'
        
        urls = re.findall(url_pattern, text)
        telegram_links = re.findall(telegram_pattern, text)
        
        return urls + telegram_links
    
    async def collect_channel_stats(
        self,
        db,
        channel: Channel,
        limit: int = 100,
        days_back: int = 30,
    ) -> bool:
        """
        Collect and save channel statistics.
        
        Uses Telethon for message parsing and TGStat for subscriber history.
        """
        try:
            if not channel.username:
                logger.warning(f"Channel {channel.id} has no username")
                return False
            
            username = channel.username.lstrip("@")
            logger.info(f"Collecting stats for @{username}")
            
            # 1. Get channel info from Telethon
            channel_info = await self.get_channel_info(username)
            if channel_info:
                # Update channel subscriber count
                channel.subscriber_count = channel_info["subscribers_count"]
                db.commit()
            
            # 2. Parse messages from Telethon
            messages = await self.parse_channel_messages(username, limit, days_back)
            
            if not messages:
                logger.warning(f"No messages parsed for @{username}")
                return False
            
            # 3. Calculate metrics
            subscribers = channel.subscriber_count or 1
            
            total_views = sum(m["views"] for m in messages)
            total_reactions = sum(m["reactions_count"] for m in messages)
            total_forwards = sum(m["forwards"] for m in messages)
            total_replies = sum(m["replies"] for m in messages)
            
            avg_views = total_views // len(messages) if messages else 0
            avg_reactions = total_reactions // len(messages) if messages else 0
            
            # Engagement rate: (reactions + forwards + replies) / subscribers * 100
            total_engagement = total_reactions + total_forwards + total_replies
            avg_engagement_per_post = total_engagement / len(messages) if messages else 0
            engagement_rate = (avg_engagement_per_post / subscribers) * 100
            
            # Posts per day
            if messages:
                first_date = min(m["date"] for m in messages)
                last_date = max(m["date"] for m in messages)
                days_span = max((last_date - first_date).days, 1)
                posts_per_day = len(messages) / days_span
            else:
                posts_per_day = 0
            
            # 4. Get/update ChannelStats
            stats = db.query(ChannelStats).filter(
                ChannelStats.channel_id == channel.id
            ).first()
            
            if not stats:
                stats = ChannelStats(channel_id=channel.id)
                db.add(stats)
            
            stats.subscriber_count = subscribers
            stats.avg_post_views = avg_views
            stats.avg_reach_24h = avg_views
            stats.total_views_7d = total_views
            stats.engagement_rate = Decimal(str(round(engagement_rate, 2)))
            stats.avg_reactions = avg_reactions
            stats.avg_comments = total_replies // len(messages) if messages else 0
            stats.avg_shares = total_forwards // len(messages) if messages else 0
            stats.posts_7d = len([m for m in messages if (datetime.now(timezone.utc) - m["date"].replace(tzinfo=timezone.utc)).days <= 7])
            stats.posts_30d = len(messages)
            stats.avg_posts_per_day = Decimal(str(round(posts_per_day, 2)))
            
            if messages:
                stats.last_post_at = max(m["date"] for m in messages)
            
            stats.updated_at = datetime.now(timezone.utc)
            
            # 5. Save posts to ChannelPost
            for msg in messages:
                existing = db.query(ChannelPost).filter(
                    ChannelPost.channel_id == channel.id,
                    ChannelPost.message_id == msg["message_id"],
                ).first()
                
                if existing:
                    # Update existing post
                    existing.views = msg["views"]
                    existing.forwards = msg["forwards"]
                    existing.replies = msg["replies"]
                    existing.reactions_count = msg["reactions_count"]
                    existing.reactions_data = msg["reactions_data"]
                else:
                    # Create new post
                    post = ChannelPost(
                        channel_id=channel.id,
                        message_id=msg["message_id"],
                        text=msg["text"][:4000] if msg["text"] else None,
                        date=msg["date"],
                        views=msg["views"],
                        forwards=msg["forwards"],
                        replies=msg["replies"],
                        reactions_count=msg["reactions_count"],
                        reactions_data=msg["reactions_data"],
                        media_type=msg["media_type"],
                        links=msg["links"],
                    )
                    db.add(post)
            
            # 6. Try to get subscriber history from TGStat
            try:
                tgstat_data = await fetch_tgstat_data(username)
                if tgstat_data and tgstat_data.subscriber_history:
                    logger.info(f"Got {len(tgstat_data.subscriber_history)} days history from TGStat")
                    
                    # Calculate growth from TGStat
                    if tgstat_data.growth_day:
                        stats.subscriber_growth_24h = tgstat_data.growth_day
                    if tgstat_data.growth_week:
                        stats.subscriber_growth_7d = tgstat_data.growth_week
                    if tgstat_data.growth_month:
                        stats.subscriber_growth_30d = tgstat_data.growth_month
                    
                    # Determine dynamics
                    if stats.subscriber_growth_30d > 1000:
                        stats.dynamics = "growing"
                    elif stats.subscriber_growth_30d < -1000:
                        stats.dynamics = "declining"
                    else:
                        stats.dynamics = "stable"
                    
                    # Save history
                    for h in tgstat_data.subscriber_history:
                        history_date = datetime.strptime(h.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        
                        existing = db.query(ChannelStatsHistory).filter(
                            ChannelStatsHistory.channel_id == channel.id,
                            ChannelStatsHistory.date >= history_date,
                            ChannelStatsHistory.date < history_date + timedelta(days=1),
                        ).first()
                        
                        if not existing:
                            entry = ChannelStatsHistory(
                                channel_id=channel.id,
                                date=history_date,
                                subscriber_count=h.subscribers,
                                total_views=0,
                                total_posts=0,
                            )
                            db.add(entry)
                            
            except Exception as e:
                logger.warning(f"Failed to get TGStat data: {e}")
            
            db.commit()
            logger.info(f"Stats collected for @{username}: {avg_views:,} avg views, {engagement_rate:.2f}% ER")
            return True
            
        except Exception as e:
            logger.error(f"Error collecting stats for channel {channel.id}: {e}")
            return False


# Global parser instance
channel_parser = TelegramChannelParser()

