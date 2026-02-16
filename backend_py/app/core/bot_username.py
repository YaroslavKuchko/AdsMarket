"""Shared helper to resolve Telegram bot username from token or config."""
from __future__ import annotations

import httpx

from app.core.config import settings

_bot_username_cache: str | None = None


def get_bot_username() -> str:
    """Resolve bot username from TG_BOT_TOKEN via getMe; fallback to parsing webapp_url."""
    global _bot_username_cache
    if _bot_username_cache is not None:
        return _bot_username_cache
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(
                f"https://api.telegram.org/bot{settings.tg_bot_token}/getMe"
            )
            r.raise_for_status()
            data = r.json()
            if data.get("ok") and data.get("result", {}).get("username"):
                _bot_username_cache = data["result"]["username"]
                return _bot_username_cache
    except Exception:
        pass
    parts = settings.webapp_url.rstrip("/").replace("https://", "").split("/")
    if len(parts) >= 2 and parts[0] == "t.me":
        _bot_username_cache = parts[1]
        return _bot_username_cache
    return "ads_marketplacebot"
