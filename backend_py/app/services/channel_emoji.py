"""
Create custom emoji from channel photo for use in tg-emoji messages.

Uses Telegram Bot API: uploadStickerFile, createNewStickerSet, getStickerSet.
The sticker set is owned by the user who added the bot.
"""
from __future__ import annotations

import logging
from io import BytesIO

import httpx
from PIL import Image

from app.core.bot_username import get_bot_username
from app.core.config import settings

logger = logging.getLogger(__name__)

# Max size for static sticker: 512x512, PNG or WEBP
STICKER_MAX_SIZE = 512


async def create_channel_emoji_from_photo(
    bot_token: str,
    photo_bytes: bytes,
    owner_user_id: int,
    chat_id: int,
) -> str | None:
    """
    Create a custom emoji sticker from channel photo bytes.

    Returns custom_emoji_id (str) for use in <tg-emoji emoji-id="...">, or None on failure.
    """
    try:
        # Convert to PNG (Telegram requires PNG/WEBP for static stickers)
        img = Image.open(BytesIO(photo_bytes))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")
        # Resize if too large
        w, h = img.size
        if max(w, h) > STICKER_MAX_SIZE:
            img.thumbnail((STICKER_MAX_SIZE, STICKER_MAX_SIZE), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        png_bytes = buf.getvalue()
    except Exception as e:
        logger.warning("Failed to convert channel photo to PNG: %s", e)
        return None

    bot_username = get_bot_username()
    set_name = f"ch{abs(chat_id)}_by_{bot_username}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        base = f"https://api.telegram.org/bot{bot_token}"
        # 1. Upload sticker file
        try:
            upload_resp = await client.post(
                f"{base}/uploadStickerFile",
                data={
                    "user_id": owner_user_id,
                    "sticker_format": "static",
                },
                files={"sticker": ("sticker.png", png_bytes, "image/png")},
            )
            if upload_resp.status_code != 200:
                logger.warning("uploadStickerFile failed: %s %s", upload_resp.status_code, upload_resp.text)
                return None
            upload_data = upload_resp.json()
            if not upload_data.get("ok"):
                logger.warning("uploadStickerFile error: %s", upload_data.get("description"))
                return None
            file_id = upload_data["result"]["file_id"]
        except Exception as e:
            logger.warning("uploadStickerFile exception: %s", e)
            return None

        # 2. Create sticker set with custom_emoji type
        try:
            create_resp = await client.post(
                f"{base}/createNewStickerSet",
                json={
                    "user_id": owner_user_id,
                    "name": set_name,
                    "title": "Channel emoji",
                    "sticker_type": "custom_emoji",
                    "stickers": [
                        {
                            "sticker": file_id,
                            "format": "static",
                            "emoji_list": ["📢"],
                        }
                    ],
                },
            )
            if create_resp.status_code != 200:
                logger.warning("createNewStickerSet failed: %s %s", create_resp.status_code, create_resp.text)
                return None
            create_data = create_resp.json()
            if not create_data.get("ok"):
                # Set might already exist (e.g. re-add) - try to get it
                desc = create_data.get("description", "")
                if "STICKERSET_INVALID" in str(create_data) or "short name is occupied" in desc.lower():
                    pass  # fall through to getStickerSet
                else:
                    logger.warning("createNewStickerSet error: %s", desc)
                    return None
        except Exception as e:
            logger.warning("createNewStickerSet exception: %s", e)
            return None

        # 3. Get sticker set to retrieve custom_emoji_id
        try:
            get_resp = await client.get(
                f"{base}/getStickerSet",
                params={"name": set_name},
            )
            if get_resp.status_code != 200:
                logger.warning("getStickerSet failed: %s %s", get_resp.status_code, get_resp.text)
                return None
            get_data = get_resp.json()
            if not get_data.get("ok"):
                logger.warning("getStickerSet error: %s", get_data.get("description"))
                return None
            stickers = get_data.get("result", {}).get("stickers", [])
            if not stickers:
                return None
            emoji_id = stickers[0].get("custom_emoji_id")
            return str(emoji_id) if emoji_id else None
        except Exception as e:
            logger.warning("getStickerSet exception: %s", e)
            return None
