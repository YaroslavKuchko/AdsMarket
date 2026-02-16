"""
Background task scheduler for periodic jobs.

Uses APScheduler for running background tasks like:
- Channel statistics collection
- Channel photo URL updates (stored on disk, path in DB)
- TON price updates
- Cleanup tasks
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings

logger = logging.getLogger(__name__)

# Directory for storing channel photos (served at /media/channels/)
CHANNELS_PHOTO_DIR = Path(__file__).resolve().parent.parent.parent / "media" / "channels"

scheduler = AsyncIOScheduler()


async def collect_channel_stats():
    """Job: Collect statistics for all channels using Telethon."""
    from app.services.channel_collector import channel_collector
    from app.db.session import SessionLocal
    from app.db.models import Channel

    logger.info("Starting scheduled stats collection...")
    try:
        db = SessionLocal()
        try:
            # Get all active channels
            channels = db.query(Channel).filter(Channel.status == "active").all()
            logger.info(f"Found {len(channels)} active channels to collect")
            
            for channel in channels:
                try:
                    await channel_collector.collect_channel_stats(channel.id)
                    logger.info(f"Collected stats for channel {channel.id} (@{channel.username})")
                except Exception as e:
                    logger.error(f"Failed to collect stats for channel {channel.id}: {e}")
        finally:
            db.close()
        
        logger.info("Scheduled stats collection completed")
    except Exception as e:
        logger.error(f"Scheduled stats collection failed: {e}")


def setup_scheduler():
    """Configure and start the scheduler."""
    if not settings.stats_collection_enabled:
        logger.info("Stats collection is disabled in settings")
    else:
        # Add stats collection job
        scheduler.add_job(
            collect_channel_stats,
            trigger=IntervalTrigger(hours=settings.stats_collection_interval_hours),
            id="collect_channel_stats",
            name="Collect channel statistics",
            replace_existing=True,
        )

        logger.info(
            f"Stats collection scheduled every {settings.stats_collection_interval_hours} hours"
        )

    # Add channel info update job (runs every 12 hours)
    scheduler.add_job(
        update_channel_photos,
        trigger=IntervalTrigger(hours=12),
        id="update_channel_photos",
        name="Update channel info (photo, title, username)",
        replace_existing=True,
    )

    # USDT deposit scanner (runs every 1 min when wallet configured)
    if (getattr(settings, "usdt_deposit_wallet", None) or "").strip():
        from app.services.usdt_deposit_scanner import scan_usdt_deposits_async
        scheduler.add_job(
            scan_usdt_deposits_async,
            trigger=IntervalTrigger(minutes=1),
            id="scan_usdt_deposits",
            name="Scan USDT deposits (TON)",
            replace_existing=True,
        )
        logger.info("USDT deposit scanner scheduled every 1 minute")

    # TON deposit scanner (runs every 1 min when wallet configured)
    if (getattr(settings, "ton_deposit_wallet", None) or "").strip():
        from app.services.ton_deposit_scanner import scan_ton_deposits_async
        scheduler.add_job(
            scan_ton_deposits_async,
            trigger=IntervalTrigger(minutes=1),
            id="scan_ton_deposits",
            name="Scan TON deposits (by connected wallet)",
            replace_existing=True,
        )
        logger.info("TON deposit scanner scheduled every 1 minute")

    # USDT withdrawal sender (runs every 2 min when mnemonic configured)
    pk = (getattr(settings, "usdt_withdraw_private_key", None) or "").strip()
    mnem = (getattr(settings, "usdt_withdraw_mnemonic", None) or "").strip()
    if pk or mnem:
        from app.services.usdt_withdraw_sender import process_pending_withdrawals
        scheduler.add_job(
            process_pending_withdrawals,
            trigger=IntervalTrigger(minutes=2),
            id="process_usdt_withdrawals",
            name="Process USDT withdrawals (send via TON)",
            replace_existing=True,
        )
        logger.info("USDT withdrawal sender scheduled every 2 minutes")

    # TON withdrawal sender (reuses same hot wallet as USDT)
    if pk or mnem:
        from app.services.ton_withdraw_sender import process_pending_ton_withdrawals
        scheduler.add_job(
            process_pending_ton_withdrawals,
            trigger=IntervalTrigger(minutes=2),
            id="process_ton_withdrawals",
            name="Process TON withdrawals",
            replace_existing=True,
        )
        logger.info("TON withdrawal sender scheduled every 2 minutes")

    # Add order verification job (runs every hour; verifies 24h/48h posts via Bot API)
    if getattr(settings, "ad_verification_channel_id", None):
        scheduler.add_job(
            verify_order_posts,
            trigger=IntervalTrigger(hours=1),
            id="verify_order_posts",
            name="Verify ad posts (24h/48h) still in channel",
            replace_existing=True,
        )
        logger.info("Order verification scheduled every hour")
    else:
        logger.info("Order verification disabled (AD_VERIFICATION_CHANNEL_ID not set)")

    logger.info("Channel info update (photo, title, username) scheduled every 12 hours")


async def start_scheduler():
    """Start the scheduler (Telethon connects on-demand)."""
    # Setup and start scheduler
    # Note: Telethon channel_collector connects on-demand, no need to start it here
    setup_scheduler()
    scheduler.start()

    if settings.stats_collection_enabled:
        # Run initial collection after a short delay
        asyncio.create_task(delayed_initial_collection())
        logger.info("Scheduler started (Telethon will connect on-demand)")
    else:
        logger.info("Scheduler started (stats collection disabled)")


async def update_single_channel_info(channel: Channel, db, update_posts_media: bool = True) -> dict[str, int]:
    """
    Update photo URL, title, username, and subscriber count for a single channel.
    Uses Telegram Bot API: getChat, getChatMemberCount.
    Optionally update media_url for top posts.

    Returns dict with counts: {'photos': 0, 'titles': 0, 'usernames': 0, 'subscribers': 0, 'posts_media': 0}
    """
    from app.db.models import ChannelStats

    if not channel.telegram_id:
        return {'photos': 0, 'titles': 0, 'usernames': 0, 'subscribers': 0, 'posts_media': 0}

    updated_photos = 0
    updated_titles = 0
    updated_usernames = 0
    updated_subscribers = 0
    updated_posts_media = 0

    try:
        # Use Telegram Bot API to get channel info
        bot_token = settings.tg_bot_token
        chat_id = channel.telegram_id

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Get subscriber count (getChatMemberCount)
            try:
                member_resp = await client.get(
                    f"https://api.telegram.org/bot{bot_token}/getChatMemberCount",
                    params={"chat_id": chat_id},
                )
                if member_resp.status_code == 200:
                    member_data = member_resp.json()
                    if member_data.get("ok") and "result" in member_data:
                        new_count = int(member_data["result"])
                        if new_count != channel.subscriber_count:
                            old_count = channel.subscriber_count
                            channel.subscriber_count = new_count
                            updated_subscribers = 1
                            logger.info(
                                f"Updated subscriber count for channel {channel.id} (@{channel.username}): {old_count} -> {new_count}"
                            )
                        # Sync to ChannelStats if exists
                        stats = db.query(ChannelStats).filter(ChannelStats.channel_id == channel.id).first()
                        stats_updated = False
                        if stats and stats.subscriber_count != new_count:
                            stats.subscriber_count = new_count
                            stats_updated = True
                        if updated_subscribers or stats_updated:
                            db.commit()
            except Exception as e:
                logger.warning(f"getChatMemberCount failed for channel {channel.id}: {e}")

            # Get chat info
            response = await client.get(
                f"https://api.telegram.org/bot{bot_token}/getChat",
                params={"chat_id": chat_id}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok") and "result" in data:
                    chat_info = data["result"]
                    
                    # Update title if changed
                    new_title = chat_info.get("title")
                    if new_title and new_title != channel.title:
                        old_title = channel.title
                        channel.title = new_title
                        updated_titles = 1
                        logger.info(f"Updated title for channel {channel.id}: '{old_title}' -> '{new_title}'")
                    
                    # Update username if changed
                    new_username = chat_info.get("username")
                    # Handle both None and empty string
                    if new_username != channel.username:
                        old_username = channel.username
                        channel.username = new_username
                        updated_usernames = 1
                        logger.info(f"Updated username for channel {channel.id}: '{old_username}' -> '{new_username}'")
                    
                    # Update photo if available: download and store on disk, save path in DB
                    if "photo" in chat_info:
                        photo = chat_info["photo"]
                        if photo.get("big_file_id"):
                            file_response = await client.get(
                                f"https://api.telegram.org/bot{bot_token}/getFile",
                                params={"file_id": photo["big_file_id"]}
                            )
                            if file_response.status_code == 200:
                                file_data = file_response.json()
                                if file_data.get("ok") and "result" in file_data:
                                    file_path = file_data["result"].get("file_path")
                                    if file_path:
                                        # Download file content
                                        file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                                        file_resp = await client.get(file_url)
                                        if file_resp.status_code == 200 and file_resp.content:
                                            CHANNELS_PHOTO_DIR.mkdir(parents=True, exist_ok=True)
                                            ext = Path(file_path).suffix.lstrip(".") or "jpg"
                                            if ext not in ("jpg", "jpeg", "png", "webp"):
                                                ext = "jpg"
                                            local_path = CHANNELS_PHOTO_DIR / f"{channel.id}.{ext}"
                                            local_path.write_bytes(file_resp.content)
                                            new_url = f"/media/channels/{channel.id}.{ext}"
                                            if new_url != channel.photo_url:
                                                channel.photo_url = new_url
                                                updated_photos = 1
                                                db.commit()
                                                logger.info(f"Stored channel photo for channel {channel.id} (@{channel.username}): {local_path}")
                    
                    if updated_photos or updated_titles or updated_usernames:
                        logger.info(f"Channel {channel.id} updated: photos={updated_photos}, titles={updated_titles}, usernames={updated_usernames}")
                
                # Update media_url for top posts if requested
                if update_posts_media:
                    updated_posts_media = await update_top_posts_media(channel, db)
                else:
                    error_desc = data.get("description", "Unknown error") if data else "No response data"
                    logger.warning(f"Telegram API returned error for channel {channel.id}: {error_desc}")
            else:
                try:
                    error_data = response.json()
                    error_desc = error_data.get("description", f"HTTP {response.status_code}")
                except:
                    error_desc = f"HTTP {response.status_code}"
                logger.warning(f"Failed to get chat info for channel {channel.id}: {error_desc}")
                
    except Exception as e:
        logger.error(f"Failed to update channel {channel.id}: {e}")
    
    return {
        'photos': updated_photos,
        'titles': updated_titles,
        'usernames': updated_usernames,
        'subscribers': updated_subscribers,
        'posts_media': updated_posts_media,
    }


async def update_top_posts_media(channel: Channel, db, limit: int = 10) -> int:
    """
    Update media_url for top posts (by views) in a channel.
    Updates media_url for posts that have media but missing or empty media_url.
    
    Args:
        channel: Channel to update posts for
        db: Database session
        limit: Number of top posts to update (default: 10)
    
    Returns:
        Number of posts updated
    """
    from app.db.models import ChannelPost
    
    if not channel.telegram_id or not channel.username:
        return 0
    
    updated_count = 0
    
    try:
        # Get top posts by views for this channel that have media
        # Priority: posts with has_media=True but missing media_url
        top_posts_missing_url = db.query(ChannelPost).filter(
            ChannelPost.channel_id == channel.id,
            ChannelPost.has_media == True,
            (ChannelPost.media_url.is_(None) | (ChannelPost.media_url == ""))
        ).order_by(ChannelPost.views.desc()).limit(limit).all()
        
        # Also get top posts overall (even if they have media_url, we want to ensure it's correct)
        if len(top_posts_missing_url) < limit:
            top_posts_with_media = db.query(ChannelPost).filter(
                ChannelPost.channel_id == channel.id,
                ChannelPost.has_media == True,
                ChannelPost.media_url.isnot(None),
                ChannelPost.media_url != ""
            ).order_by(ChannelPost.views.desc()).limit(limit - len(top_posts_missing_url)).all()
            
            # Combine lists, avoiding duplicates
            existing_ids = {p.message_id for p in top_posts_missing_url}
            top_posts = list(top_posts_missing_url) + [p for p in top_posts_with_media if p.message_id not in existing_ids]
        else:
            top_posts = top_posts_missing_url
        
        if not top_posts:
            return 0
        
        channel_username = channel.username
        
        for post in top_posts:
            try:
                # Check if media_url needs updating (if it's None or empty)
                if not post.media_url:
                    # Generate media_url in our proxy format
                    new_media_url = f"/api/media/channel/{channel_username}/{post.message_id}"
                    post.media_url = new_media_url
                    updated_count += 1
                    logger.info(f"Updated media_url for post {post.message_id} (views: {post.views}) in channel {channel.id}: {new_media_url}")
                else:
                    # Verify media_url format is correct (should start with /api/media/channel/)
                    if not post.media_url.startswith("/api/media/channel/"):
                        # Update to correct format
                        new_media_url = f"/api/media/channel/{channel_username}/{post.message_id}"
                        old_url = post.media_url
                        post.media_url = new_media_url
                        updated_count += 1
                        logger.info(f"Fixed media_url format for post {post.message_id} in channel {channel.id}: {old_url} -> {new_media_url}")
                    
            except Exception as e:
                logger.warning(f"Failed to update media for post {post.message_id} in channel {channel.id}: {e}")
                continue
        
        if updated_count > 0:
            db.commit()
            logger.info(f"Updated media_url for {updated_count} top posts in channel {channel.id} (@{channel.username})")
        
    except Exception as e:
        logger.error(f"Failed to update top posts media for channel {channel.id}: {e}")
        db.rollback()
    
    return updated_count


async def verify_order_posts():
    """Job: Verify published ad posts after duration_hours (24/48h); set verified_at if OK."""
    from aiogram import Bot
    from app.services.order_verifier import verify_pending_orders

    if not getattr(settings, "ad_verification_channel_id", None):
        return
    try:
        bot = Bot(token=settings.tg_bot_token)
        count = await verify_pending_orders(bot)
        if count > 0:
            logger.info("Order verification: %s orders verified", count)
    except Exception as e:
        logger.exception("Order verification job failed: %s", e)


async def update_channel_photos():
    """Job: Update photo URLs, title, and username for all channels using Telegram Bot API."""
    from app.db.session import SessionLocal
    from app.db.models import Channel

    logger.info("Starting scheduled channel info update (photo, title, username)...")
    try:
        db = SessionLocal()
        try:
            # Get all channels that have a telegram_id
            channels = db.query(Channel).filter(
                Channel.telegram_id.isnot(None),
                Channel.status.in_(["active", "pending", "paused"])
            ).all()
            
            logger.info(f"Found {len(channels)} channels to update")
            
            total_updated_photos = 0
            total_updated_titles = 0
            total_updated_usernames = 0
            total_updated_subscribers = 0
            total_updated_posts_media = 0

            for channel in channels:
                result = await update_single_channel_info(channel, db, update_posts_media=True)
                total_updated_photos += result.get('photos', 0)
                total_updated_titles += result.get('titles', 0)
                total_updated_usernames += result.get('usernames', 0)
                total_updated_subscribers += result.get('subscribers', 0)
                total_updated_posts_media += result.get('posts_media', 0)

            db.commit()
            logger.info(
                f"Update completed: {total_updated_photos} photos, {total_updated_titles} titles, "
                f"{total_updated_usernames} usernames, {total_updated_subscribers} subscribers, "
                f"{total_updated_posts_media} posts media updated out of {len(channels)} channels"
            )
        finally:
            db.close()
        
        logger.info("Scheduled channel info update completed")
    except Exception as e:
        logger.error(f"Scheduled channel info update failed: {e}")


async def delayed_initial_collection():
    """Run initial stats collection after app startup."""
    await asyncio.sleep(30)  # Wait for app to fully start
    await collect_channel_stats()


async def stop_scheduler():
    """Stop the scheduler."""
    from app.services.channel_collector import channel_collector

    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    await channel_collector.disconnect()

