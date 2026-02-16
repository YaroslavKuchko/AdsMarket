"""
Channel statistics collector using Telethon.

Collects 90 days of posts and calculates all metrics.
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional, Dict, Any, List

from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import Message, Channel as TelegramChannel, MessageMediaPhoto
from telethon.errors import FloodWaitError, ChannelPrivateError, UsernameNotOccupiedError

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import Channel, ChannelStats, ChannelStatsHistory, ChannelPost
from app.services.tgstat_parser import fetch_tgstat_data
from sqlalchemy import func

# Media storage directory
MEDIA_DIR = Path(__file__).parent.parent.parent / "media" / "posts"

logger = logging.getLogger(__name__)

# Collection settings
POSTS_LIMIT = 500  # Max posts to fetch
DAYS_BACK = 90     # Days of history


class ChannelCollector:
    """Collects channel statistics using Telethon userbot."""
    
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.session_path = f"{settings.pyrogram_session_dir}/telethon_session"
        self._lock = asyncio.Lock()
    
    async def connect(self) -> bool:
        """Connect to Telegram API."""
        if self.client and self.client.is_connected():
            return True
        
        try:
            self.client = TelegramClient(
                self.session_path,
                settings.pyrogram_api_id,
                settings.pyrogram_api_hash,
            )
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                logger.error("Telethon session not authorized")
                return False
            
            me = await self.client.get_me()
            logger.info(f"Connected to Telegram as {me.first_name} (@{me.username})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Telegram API."""
        if self.client:
            await self.client.disconnect()
            self.client = None
    
    async def collect_channel_stats(self, channel_id: int) -> Dict[str, Any]:
        """
        Collect full statistics for a channel.
        
        Args:
            channel_id: Database channel ID
            
        Returns:
            Dict with collection results
        """
        db = SessionLocal()
        
        try:
            # Get channel from DB
            channel = db.query(Channel).filter(Channel.id == channel_id).first()
            if not channel:
                return {"success": False, "error": "Channel not found"}
            
            # Get or create stats
            stats = db.query(ChannelStats).filter(ChannelStats.channel_id == channel_id).first()
            if not stats:
                stats = ChannelStats(channel_id=channel_id)
                db.add(stats)
                db.flush()
            
            # Mark as collecting
            stats.is_collecting = True
            stats.collection_started_at = datetime.now(timezone.utc)
            stats.collection_error = None
            db.commit()
            
            # Connect to Telegram
            async with self._lock:
                if not await self.connect():
                    stats.is_collecting = False
                    stats.collection_error = "Failed to connect to Telegram"
                    db.commit()
                    return {"success": False, "error": "Failed to connect"}
                
                try:
                    result = await self._collect_channel_data(db, channel, stats)
                    return result
                finally:
                    stats.is_collecting = False
                    db.commit()
                    
        except Exception as e:
            logger.error(f"Error collecting stats for channel {channel_id}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    async def _collect_channel_data(
        self, 
        db: SessionLocal, 
        channel: Channel, 
        stats: ChannelStats
    ) -> Dict[str, Any]:
        """Internal method to collect channel data."""
        username = channel.username
        
        try:
            # Get channel info
            entity = await self.client.get_entity(username)
            if not isinstance(entity, TelegramChannel):
                stats.collection_error = "Not a channel"
                return {"success": False, "error": "Not a channel"}
            
            full = await self.client(GetFullChannelRequest(entity))
            subscriber_count = full.full_chat.participants_count or 0
            
            # Update channel info
            channel.subscriber_count = subscriber_count
            channel.title = entity.title
            if hasattr(entity, 'about'):
                channel.description = entity.about or ""
            
            logger.info(f"Collecting posts for @{username} ({subscriber_count:,} subscribers)")
            
            # Collect posts
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
            posts_data = []
            messages_map: Dict[int, Message] = {}  # Keep raw messages for media download
            grouped_messages: Dict[int, List[Message]] = {}  # Group albums by grouped_id
            
            # First pass: collect all messages and group by grouped_id
            all_messages: List[Message] = []
            async for msg in self.client.iter_messages(username, limit=POSTS_LIMIT):
                if not isinstance(msg, Message):
                    continue
                
                msg_date = msg.date
                if msg_date.tzinfo is None:
                    msg_date = msg_date.replace(tzinfo=timezone.utc)
                
                if msg_date < cutoff_date:
                    break
                
                all_messages.append(msg)
                messages_map[msg.id] = msg
                
                # Group by grouped_id (for albums)
                if msg.grouped_id:
                    if msg.grouped_id not in grouped_messages:
                        grouped_messages[msg.grouped_id] = []
                    grouped_messages[msg.grouped_id].append(msg)
                
                await asyncio.sleep(0.02)
            
            # Second pass: process messages, merging grouped albums
            processed_groups = set()  # Track which groups we've processed
            
            for msg in all_messages:
                # If this message is part of a group
                if msg.grouped_id:
                    # Skip if we already processed this group
                    if msg.grouped_id in processed_groups:
                        continue
                    
                    processed_groups.add(msg.grouped_id)
                    
                    # Get all messages in this group
                    group_msgs = grouped_messages.get(msg.grouped_id, [msg])
                    
                    # Merge data from all messages in the group
                    post_data = self._extract_grouped_post_data(group_msgs, username)
                    posts_data.append(post_data)
                    
                    # Save with first message ID as main ID
                    main_msg_id = min(m.id for m in group_msgs)
                    await self._save_post(db, channel.id, post_data, media_url=post_data.get("media_url"))
                else:
                    # Regular single message
                    post_data = self._extract_post_data(msg)
                    posts_data.append(post_data)
                    
                    # Set media URL for posts with media
                    media_url = None
                    if msg.media and isinstance(msg.media, MessageMediaPhoto):
                        media_url = f"/api/media/channel/{username}/{msg.id}"
                    
                    await self._save_post(db, channel.id, post_data, media_url=media_url)
            
            logger.info(f"Collected {len(posts_data)} posts for @{username} (from {len(all_messages)} messages)")
            
            # Calculate stats
            self._calculate_stats(stats, posts_data, subscriber_count)
            
            # Generate daily history
            await self._generate_daily_history(db, channel.id, posts_data, subscriber_count)
            
            # Get subscriber history from TGStat and extrapolate to 90 days
            try:
                tgstat_data = await fetch_tgstat_data(username)
                if tgstat_data and tgstat_data.subscriber_history:
                    tgstat_history = tgstat_data.subscriber_history
                    logger.info(f"Got {len(tgstat_history)} days subscriber history from TGStat")
                    
                    # Update growth from TGStat (more accurate)
                    if tgstat_data.growth_day:
                        stats.subscriber_growth_24h = tgstat_data.growth_day
                    if tgstat_data.growth_week:
                        stats.subscriber_growth_7d = tgstat_data.growth_week
                    if tgstat_data.growth_month:
                        stats.subscriber_growth_30d = tgstat_data.growth_month
                    
                    # Calculate daily growth rate for extrapolation
                    if len(tgstat_history) >= 2:
                        first_subs = tgstat_history[0].subscribers
                        last_subs = tgstat_history[-1].subscribers
                        days_span = len(tgstat_history) - 1
                        daily_change = (last_subs - first_subs) / days_span if days_span > 0 else 0
                        
                        # Extrapolate 90 days: extend history backwards
                        extended_history = []
                        
                        # Parse first date from TGStat
                        first_date = datetime.strptime(tgstat_history[0].date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        
                        # Calculate how many days to extrapolate backwards (to reach 90 days total)
                        days_to_add = max(0, DAYS_BACK - len(tgstat_history))
                        
                        # Add extrapolated days before TGStat data
                        for i in range(days_to_add, 0, -1):
                            ext_date = first_date - timedelta(days=i)
                            # Extrapolate subscriber count backwards
                            ext_subs = int(first_subs - (daily_change * i))
                            if ext_subs < 0:
                                ext_subs = first_subs  # Don't go negative
                            extended_history.append({
                                "date": ext_date,
                                "subscribers": ext_subs,
                                "extrapolated": True
                            })
                        
                        # Add actual TGStat data
                        for h in tgstat_history:
                            extended_history.append({
                                "date": datetime.strptime(h.date, "%Y-%m-%d").replace(tzinfo=timezone.utc),
                                "subscribers": h.subscribers,
                                "extrapolated": False
                            })
                        
                        logger.info(f"Extended history to {len(extended_history)} days ({days_to_add} extrapolated + {len(tgstat_history)} from TGStat)")
                        
                        # Estimate 90-day growth
                        if len(extended_history) >= 90:
                            stats.subscriber_growth_30d = extended_history[-1]["subscribers"] - extended_history[-31]["subscribers"]
                    else:
                        extended_history = [{
                            "date": datetime.strptime(h.date, "%Y-%m-%d").replace(tzinfo=timezone.utc),
                            "subscribers": h.subscribers,
                            "extrapolated": False
                        } for h in tgstat_history]
                    
                    # Determine dynamics from growth
                    if stats.subscriber_growth_30d > 1000:
                        stats.dynamics = "growing"
                        stats.dynamics_score = min(100, stats.subscriber_growth_30d // 100)
                    elif stats.subscriber_growth_30d < -1000:
                        stats.dynamics = "declining"
                        stats.dynamics_score = max(-100, stats.subscriber_growth_30d // 100)
                    else:
                        stats.dynamics = "stable"
                        stats.dynamics_score = 0
                    
                    # Update history with extended subscriber data
                    for h in extended_history:
                        history_date = h["date"]
                        # Normalize to start of day for comparison
                        history_date_start = datetime.combine(history_date.date(), datetime.min.time()).replace(tzinfo=timezone.utc)
                        
                        # Find existing entry for this date (exact match by date, ignoring time)
                        existing = db.query(ChannelStatsHistory).filter(
                            ChannelStatsHistory.channel_id == channel.id,
                            func.date(ChannelStatsHistory.date) == history_date.date()
                        ).first()
                        
                        if existing:
                            # Always update subscriber count from TGStat (more accurate)
                            existing.subscriber_count = h["subscribers"]
                            logger.debug(f"Updated subscriber_count for {history_date.date()}: {h['subscribers']}")
                        else:
                            # Create new entry
                            entry = ChannelStatsHistory(
                                channel_id=channel.id,
                                date=history_date_start,
                                subscriber_count=h["subscribers"],
                                total_views=0,
                                total_posts=0,
                                avg_post_views=0,
                            )
                            db.add(entry)
                            logger.debug(f"Created new history entry for {history_date.date()}: {h['subscribers']}")
                    
                    logger.info(f"Updated {len(extended_history)} days of subscriber history for @{username}")
            except Exception as e:
                logger.warning(f"Failed to get TGStat subscriber history: {e}")
            
            db.commit()
            
            return {
                "success": True,
                "posts_collected": len(posts_data),
                "subscriber_count": subscriber_count
            }
            
        except UsernameNotOccupiedError:
            stats.collection_error = "Channel not found"
            return {"success": False, "error": "Channel not found"}
        except ChannelPrivateError:
            stats.collection_error = "Channel is private"
            return {"success": False, "error": "Channel is private"}
        except FloodWaitError as e:
            stats.collection_error = f"Rate limited: {e.seconds}s"
            logger.warning(f"Flood wait: {e.seconds} seconds")
            return {"success": False, "error": f"Rate limited, retry in {e.seconds}s"}
        except Exception as e:
            stats.collection_error = str(e)[:256]
            logger.error(f"Error collecting @{username}: {e}")
            return {"success": False, "error": str(e)}
    
    def _extract_post_data(self, msg: Message) -> Dict[str, Any]:
        """Extract data from a Telegram message."""
        views = msg.views or 0
        forwards = msg.forwards or 0
        reactions = 0
        comments = 0
        
        # Handle reactions - robust parsing
        if msg.reactions:
            try:
                if hasattr(msg.reactions, 'results') and msg.reactions.results:
                    reactions = sum(r.count for r in msg.reactions.results)
                elif hasattr(msg.reactions, 'recent_reactions'):
                    reactions = len(msg.reactions.recent_reactions)
            except Exception as e:
                logger.warning(f"Error parsing reactions for msg {msg.id}: {e}")
        
        # Handle replies/comments
        if msg.replies:
            try:
                comments = msg.replies.replies or 0
            except Exception as e:
                logger.warning(f"Error parsing replies for msg {msg.id}: {e}")
        
        msg_date = msg.date
        if msg_date.tzinfo is None:
            msg_date = msg_date.replace(tzinfo=timezone.utc)
        
        full_text = msg.text or ""
        
        return {
            "message_id": msg.id,
            "text": full_text[:200],
            "full_text": full_text,
            "date": msg_date,
            "views": views,
            "reactions": reactions,
            "comments": comments,
            "shares": forwards,
            "has_media": msg.media is not None,
            "media": msg.media
        }
    
    def _extract_grouped_post_data(self, messages: List[Message], channel_username: str) -> Dict[str, Any]:
        """
        Extract and merge data from grouped messages (albums).
        
        For grouped posts:
        - Use the FIRST message's ID as the main ID (smallest ID in group)
        - Combine views (take max, as they're usually the same or one has them all)
        - Combine reactions from all messages
        - Take comments from the message that has them (usually last or first)
        - Combine forwards
        - Merge text from all messages
        - Collect all media URLs
        """
        if not messages:
            return {}
        
        # Sort by message ID to get consistent ordering
        messages = sorted(messages, key=lambda m: m.id)
        first_msg = messages[0]
        last_msg = messages[-1]
        
        # Initialize with first message data
        msg_date = first_msg.date
        if msg_date.tzinfo is None:
            msg_date = msg_date.replace(tzinfo=timezone.utc)
        
        # Log each message in the group for debugging
        logger.info(f"Processing album with {len(messages)} messages (grouped_id: {first_msg.grouped_id})")
        for i, m in enumerate(messages):
            m_views = m.views or 0
            m_reactions = 0
            # Handle reactions - can be MessageReactions object
            if m.reactions:
                try:
                    if hasattr(m.reactions, 'results'):
                        m_reactions = sum(r.count for r in m.reactions.results)
                    elif hasattr(m.reactions, 'recent_reactions'):
                        m_reactions = len(m.reactions.recent_reactions)
                    logger.debug(f"    reactions object: {type(m.reactions)}, raw: {m.reactions}")
                except Exception as e:
                    logger.warning(f"    Error parsing reactions: {e}")
            m_comments = 0
            if m.replies:
                try:
                    m_comments = m.replies.replies or 0
                except Exception as e:
                    logger.warning(f"    Error parsing replies: {e}")
            m_forwards = m.forwards or 0
            logger.info(
                f"  [{i+1}/{len(messages)}] msg_id={m.id}: "
                f"views={m_views}, reactions={m_reactions}, comments={m_comments}, forwards={m_forwards}, "
                f"has_reactions_attr={m.reactions is not None}"
            )
        
        # Aggregate stats from all messages in the group
        # Views - take max (Telegram usually puts views on all or just one)
        views = max((m.views or 0) for m in messages)
        
        # Forwards - take max
        forwards = max((m.forwards or 0) for m in messages)
        
        # Reactions - SUM from all messages (reactions can be spread across album items)
        reactions = 0
        for m in messages:
            if m.reactions:
                try:
                    if hasattr(m.reactions, 'results') and m.reactions.results:
                        reactions += sum(r.count for r in m.reactions.results)
                    elif hasattr(m.reactions, 'recent_reactions'):
                        reactions += len(m.reactions.recent_reactions)
                except Exception as e:
                    logger.warning(f"Error summing reactions for msg {m.id}: {e}")
        
        # Comments - take MAX (Telegram puts comments on one message, usually first or last)
        comments = 0
        for m in messages:
            if m.replies:
                try:
                    c = m.replies.replies or 0
                    if c > comments:
                        comments = c
                except Exception as e:
                    logger.warning(f"Error getting comments for msg {m.id}: {e}")
        
        # Merge text from all messages (usually only first or last has text)
        full_texts = []
        for m in messages:
            if m.text:
                full_texts.append(m.text)
        full_text = "\n\n".join(full_texts) if full_texts else ""
        
        # Find first message with photo for media URL
        media_url = None
        for m in messages:
            if m.media and isinstance(m.media, MessageMediaPhoto):
                media_url = f"/api/media/channel/{channel_username}/{m.id}"
                break
        
        # Count media items
        media_count = sum(1 for m in messages if m.media)
        
        logger.info(
            f"Album aggregated (msg_id={first_msg.id}): "
            f"media_count={media_count}, views={views}, reactions={reactions}, "
            f"comments={comments}, forwards={forwards}"
        )
        
        return {
            "message_id": first_msg.id,
            "text": full_text[:200],
            "full_text": full_text,
            "date": msg_date,
            "views": views,
            "reactions": reactions,
            "comments": comments,
            "shares": forwards,
            "has_media": media_count > 0,
            "media_url": media_url,
            "media_count": media_count,
            "is_album": len(messages) > 1,
            "media": first_msg.media
        }
    
    async def _get_media_url(self, msg: Message, channel_username: str) -> Optional[str]:
        """Store media reference for later fetching via proxy."""
        if not msg.media:
            return None
        
        # Only handle photos for now
        if not isinstance(msg.media, MessageMediaPhoto):
            return None
        
        try:
            # Store reference to fetch via our proxy endpoint
            # Format: /api/media/channel/{username}/{message_id}
            return f"/api/media/channel/{channel_username}/{msg.id}"
            
        except Exception as e:
            logger.warning(f"Failed to get media URL for msg {msg.id}: {e}")
            return None
    
    async def _save_post(
        self, 
        db: SessionLocal, 
        channel_id: int, 
        post_data: Dict[str, Any],
        media_url: Optional[str] = None
    ):
        """Save or update a post in the database."""
        existing = db.query(ChannelPost).filter(
            ChannelPost.channel_id == channel_id,
            ChannelPost.message_id == post_data["message_id"]
        ).first()
        
        # Get media URL from post_data if not provided directly
        if not media_url:
            media_url = post_data.get("media_url")
        
        if existing:
            existing.views = post_data["views"]
            existing.reactions = post_data["reactions"]
            existing.comments = post_data["comments"]
            existing.shares = post_data["shares"]
            existing.stats_updated_at = datetime.now(timezone.utc)
            if post_data.get("full_text"):
                existing.full_text = post_data["full_text"]
            if media_url:
                existing.media_url = media_url
            # Update album info
            existing.is_album = post_data.get("is_album", False)
            existing.media_count = post_data.get("media_count", 1)
        else:
            post = ChannelPost(
                channel_id=channel_id,
                message_id=post_data["message_id"],
                text_preview=post_data["text"],
                full_text=post_data.get("full_text"),
                has_media=post_data["has_media"],
                media_url=media_url,
                is_album=post_data.get("is_album", False),
                media_count=post_data.get("media_count", 1),
                views=post_data["views"],
                reactions=post_data["reactions"],
                comments=post_data["comments"],
                shares=post_data["shares"],
                posted_at=post_data["date"]
            )
            db.add(post)
    
    def _calculate_stats(
        self, 
        stats: ChannelStats, 
        posts: List[Dict[str, Any]], 
        subscriber_count: int
    ):
        """Calculate all statistics from posts."""
        now = datetime.now(timezone.utc)
        
        # Time boundaries
        h24_ago = now - timedelta(hours=24)
        d7_ago = now - timedelta(days=7)
        d30_ago = now - timedelta(days=30)
        d90_ago = now - timedelta(days=90)
        
        # Filter posts by period
        posts_24h = [p for p in posts if p["date"] >= h24_ago]
        posts_7d = [p for p in posts if p["date"] >= d7_ago]
        posts_30d = [p for p in posts if p["date"] >= d30_ago]
        posts_90d = posts  # All posts (already filtered to 90 days)
        
        # Post counts
        stats.posts_24h = len(posts_24h)
        stats.posts_7d = len(posts_7d)
        stats.posts_30d = len(posts_30d)
        stats.posts_90d = len(posts_90d)
        
        # Average posts per day (based on 30 days)
        if posts_30d:
            days_span = max(1, (now - min(p["date"] for p in posts_30d)).days)
            stats.avg_posts_per_day = Decimal(str(round(len(posts_30d) / days_span, 2)))
        
        # Views
        if posts_24h:
            stats.total_views_24h = sum(p["views"] for p in posts_24h)
            stats.avg_reach_24h = stats.total_views_24h // len(posts_24h)
        
        if posts_7d:
            stats.total_views_7d = sum(p["views"] for p in posts_7d)
        
        # Average views (based on 30d)
        if posts_30d:
            stats.avg_post_views = sum(p["views"] for p in posts_30d) // len(posts_30d)
        
        # Totals (based on 90d)
        stats.total_reactions = sum(p["reactions"] for p in posts_90d)
        stats.total_comments = sum(p["comments"] for p in posts_90d)
        stats.total_shares = sum(p["shares"] for p in posts_90d)
        
        # Averages
        if posts_90d:
            stats.avg_reactions = stats.total_reactions // len(posts_90d)
            stats.avg_comments = stats.total_comments // len(posts_90d)
            stats.avg_shares = stats.total_shares // len(posts_90d)
        
        # Best post
        if posts_90d:
            best = max(posts_90d, key=lambda p: p["views"])
            stats.best_post_id = best["message_id"]
            stats.best_post_views = best["views"]
            stats.best_post_text = best["text"][:256] if best["text"] else None
        
        # Engagement rate (reactions + comments + shares) / views * 100
        total_engagement = stats.total_reactions + stats.total_comments + stats.total_shares
        total_views = sum(p["views"] for p in posts_90d) if posts_90d else 0
        if total_views > 0:
            er = (total_engagement / total_views) * 100
            stats.engagement_rate = Decimal(str(round(er, 2)))
        
        # Last post
        if posts:
            stats.last_post_at = max(p["date"] for p in posts)
        
        # Subscriber count
        stats.subscriber_count = subscriber_count
        
        # Dynamics (compare first half vs second half of posts)
        if len(posts_30d) >= 10:
            mid = len(posts_30d) // 2
            first_half_views = sum(p["views"] for p in posts_30d[:mid])
            second_half_views = sum(p["views"] for p in posts_30d[mid:])
            
            if first_half_views > 0:
                change = ((second_half_views - first_half_views) / first_half_views) * 100
                stats.dynamics_score = int(min(100, max(-100, change)))
                
                if change > 10:
                    stats.dynamics = "growing"
                elif change < -10:
                    stats.dynamics = "declining"
                else:
                    stats.dynamics = "stable"
        
        stats.updated_at = datetime.now(timezone.utc)
        logger.info(f"Stats calculated: {stats.posts_90d} posts, {stats.avg_post_views} avg views")
    
    def _get_view_decay_factor(self, days_since_post: int) -> float:
        """
        Calculate what fraction of total views a post gets on a specific day.
        
        View distribution model:
        - Day 0 (post day): ~55% of views
        - Day 1: ~20% of views
        - Day 2: ~10% of views
        - Day 3: ~5% of views
        - Day 4-6: ~7% spread (2.3% each)
        - Day 7+: ~3% spread across remaining days
        """
        if days_since_post < 0:
            return 0.0
        
        decay_map = {
            0: 0.55,  # 55% on post day
            1: 0.20,  # 20% next day
            2: 0.10,  # 10%
            3: 0.05,  # 5%
            4: 0.025,
            5: 0.025,
            6: 0.02,
        }
        
        if days_since_post in decay_map:
            return decay_map[days_since_post]
        elif days_since_post <= 14:
            return 0.003  # Small tail for 2 weeks
        elif days_since_post <= 30:
            return 0.001  # Very small for month
        else:
            return 0.0  # Negligible after a month
    
    async def _generate_daily_history(
        self, 
        db: SessionLocal, 
        channel_id: int, 
        posts: List[Dict[str, Any]],
        current_subscribers: int
    ):
        """
        Generate daily history from posts using view decay model.
        
        For each day, estimate views by summing contributions from all posts
        based on how many days have passed since each post was published.
        """
        if not posts:
            return
        
        now = datetime.now(timezone.utc)
        
        # Generate history for last 90 days
        for i in range(90):
            target_date = (now - timedelta(days=89-i)).date()
            target_datetime = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            
            # Calculate estimated views for this day from all posts
            daily_views = 0
            daily_reactions = 0
            daily_comments = 0
            daily_shares = 0
            posts_on_day = 0
            
            for post in posts:
                post_date = post["date"].date()
                days_since_post = (target_date - post_date).days
                
                # Only count posts that existed by this date
                if days_since_post < 0:
                    continue
                
                # Get decay factor for this day
                decay = self._get_view_decay_factor(days_since_post)
                
                # Add contribution from this post
                daily_views += int(post["views"] * decay)
                daily_reactions += int(post["reactions"] * decay)
                daily_comments += int(post["comments"] * decay)
                daily_shares += int(post["shares"] * decay)
                
                # Count posts published on this exact day
                if days_since_post == 0:
                    posts_on_day += 1
            
            # Calculate average views (avoid division by zero)
            avg_views = daily_views // posts_on_day if posts_on_day > 0 else (daily_views if daily_views > 0 else 0)
            
            # Estimate subscriber count (decrease by ~0.1% per day going back)
            days_back = 89 - i
            estimated_subs = int(current_subscribers * (1 - days_back * 0.001))
            
            # Check if history exists
            existing = db.query(ChannelStatsHistory).filter(
                ChannelStatsHistory.channel_id == channel_id,
                ChannelStatsHistory.date == target_datetime
            ).first()
            
            if existing:
                existing.total_views = daily_views
                existing.total_posts = posts_on_day
                existing.avg_post_views = avg_views
                existing.reactions = daily_reactions
                existing.comments = daily_comments
                existing.shares = daily_shares
                if not existing.subscriber_count:
                    existing.subscriber_count = estimated_subs
            else:
                history = ChannelStatsHistory(
                    channel_id=channel_id,
                    date=target_datetime,
                    subscriber_count=estimated_subs,
                    total_views=daily_views,
                    total_posts=posts_on_day,
                    avg_post_views=avg_views,
                    reactions=daily_reactions,
                    comments=daily_comments,
                    shares=daily_shares
                )
                db.add(history)


# Global instance
channel_collector = ChannelCollector()


async def collect_channel_stats_async(channel_id: int) -> Dict[str, Any]:
    """Async wrapper for background task."""
    return await channel_collector.collect_channel_stats(channel_id)

