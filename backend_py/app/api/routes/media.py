"""
Media proxy endpoints - fetches media from Telegram on demand.
Channel photos are stored on disk (media/channels/) and path saved in DB.
"""
import asyncio
import logging
from io import BytesIO
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Channel
from app.db.session import get_db
from app.services.channel_collector import channel_collector
from app.services.scheduler import update_single_channel_info

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/media", tags=["media"])

# media/ лежит рядом с app/, а этот файл находится в app/api/routes/,
# поэтому поднимаемся на четыре уровня вверх до корня backend_py.
MEDIA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "media"
CHANNELS_PHOTO_DIR = MEDIA_DIR / "channels"

# Cache for media (in-memory, simple TTL would be better in production)
_media_cache: dict[str, bytes] = {}


@router.get("/channel/{username}/{message_id}")
async def get_channel_media(username: str, message_id: int):
    """
    Proxy endpoint to fetch channel post media from Telegram.
    
    Returns the image directly so it can be used in <img> tags.
    """
    cache_key = f"{username}_{message_id}"
    
    # Check cache first
    if cache_key in _media_cache:
        return StreamingResponse(
            BytesIO(_media_cache[cache_key]),
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*",
            },
        )
    
    try:
        # Connect to Telegram
        if not await channel_collector.connect():
            raise HTTPException(status_code=503, detail="Telegram connection failed")
        
        # Get the message
        async with channel_collector._lock:
            try:
                msg = await channel_collector.client.get_messages(username, ids=message_id)
                
                if not msg or not msg.media:
                    raise HTTPException(status_code=404, detail="Media not found")
                
                # Download media to bytes
                media_bytes = await channel_collector.client.download_media(
                    msg,
                    file=BytesIO(),
                    thumb=-1  # Smallest thumbnail for speed
                )
                
                if not media_bytes:
                    raise HTTPException(status_code=404, detail="Could not download media")
                
                # Read bytes from BytesIO
                if isinstance(media_bytes, BytesIO):
                    media_bytes.seek(0)
                    data = media_bytes.read()
                else:
                    data = media_bytes
                
                # Cache it (limit cache size in production)
                if len(_media_cache) < 100:
                    _media_cache[cache_key] = data
                
                return StreamingResponse(
                    BytesIO(data),
                    media_type="image/jpeg",
                    headers={
                        "Cache-Control": "public, max-age=86400",  # Cache for 24h
                        "Access-Control-Allow-Origin": "*",
                    },
                )
                
            except Exception as e:
                logger.error(f"Error fetching media {username}/{message_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Media proxy error: {e}")
        raise HTTPException(status_code=500, detail="Internal error")


def _channel_photo_media_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".png",):
        return "image/png"
    if ext in (".webp",):
        return "image/webp"
    return "image/jpeg"


@router.api_route("/channel-photo/{channel_id}", methods=["GET", "HEAD"])
async def get_channel_photo(channel_id: int, db: Session = Depends(get_db)):
    """
    Serve channel photo. Prefer stored file on disk (media/channels/); fallback to Telegram.
    """
    cache_key = f"channel_photo_{channel_id}"

    # Get channel from database
    channel = db.execute(
        select(Channel).where(Channel.id == channel_id)
    ).scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    photo_url = channel.photo_url

    # 0) Backward compatibility: if DB doesn't have photo_url, but file exists on disk, use it
    if not photo_url:
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            candidate = CHANNELS_PHOTO_DIR / f"{channel_id}{ext}"
            if candidate.is_file():
                rel = f"/media/channels/{channel_id}{ext}"
                channel.photo_url = rel
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                photo_url = rel
                break

    # 1) Stored on disk: photo_url is /media/channels/{id}.jpg
    if photo_url and photo_url.startswith("/media/channels/"):
        name = photo_url.split("/")[-1]
        local_path = CHANNELS_PHOTO_DIR / name
        if local_path.is_file():
            return FileResponse(
                local_path,
                media_type=_channel_photo_media_type(local_path),
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Allow-Origin": "*",
                },
            )

    # 2) In-memory cache (legacy Telegram-fetched)
    if cache_key in _media_cache:
        return StreamingResponse(
            BytesIO(_media_cache[cache_key]),
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*",
            },
        )

    # 3) No stored file: fetch from Telegram, update and store for next time
    if not channel.telegram_id:
        raise HTTPException(status_code=404, detail="Channel has no Telegram ID")

    await update_single_channel_info(channel, db)
    db.refresh(channel)
    photo_url = channel.photo_url

    if photo_url and photo_url.startswith("/media/channels/"):
        name = photo_url.split("/")[-1]
        local_path = CHANNELS_PHOTO_DIR / name
        if local_path.is_file():
            return FileResponse(
                local_path,
                media_type=_channel_photo_media_type(local_path),
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Allow-Origin": "*",
                },
            )

    # 4) Old Telegram URL in DB (e.g. before we stored on disk)
    if photo_url and photo_url.startswith("https://"):
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(photo_url)
                if response.status_code == 200 and response.content:
                    if len(_media_cache) < 100:
                        _media_cache[cache_key] = response.content
                    return StreamingResponse(
                        BytesIO(response.content),
                        media_type="image/jpeg",
                        headers={
                            "Cache-Control": "public, max-age=86400",
                            "Access-Control-Allow-Origin": "*",
                        },
                    )
        except Exception as e:
            logger.warning(f"Failed to fetch Telegram photo for channel {channel_id}: {e}")

    raise HTTPException(status_code=404, detail="Channel photo not found")

