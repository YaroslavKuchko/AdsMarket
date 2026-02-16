"""Fetch real-time Telegram Stars/USD rate from bes-dev API."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import Lock

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

STARS_RATES_URL = "https://bes-dev.github.io/telegram_stars_rates/api.json"
CACHE_TTL_SEC = 3600  # 1 hour

_cached_rate: int | None = None
_cached_at: datetime | None = None
_lock = Lock()


def get_stars_per_usd() -> int:
    """
    Return Stars per 1 USD for UI hints.
    Fetches from bes-dev API (Fragment blockchain analysis), caches 1h, falls back to env config.
    """
    global _cached_rate, _cached_at

    with _lock:
        now = datetime.now(timezone.utc)
        if _cached_rate is not None and _cached_at is not None:
            age = (now - _cached_at).total_seconds()
            if age < CACHE_TTL_SEC:
                return _cached_rate

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(STARS_RATES_URL)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("Failed to fetch Stars rate from bes-dev API: %s", e)
        return settings.stars_per_usd

    usdt_per_star = data.get("usdt_per_star")
    if usdt_per_star is None or not isinstance(usdt_per_star, (int, float)) or usdt_per_star <= 0:
        logger.warning("Invalid usdt_per_star in response: %s", usdt_per_star)
        return settings.stars_per_usd

    rate = int(round(1 / float(usdt_per_star)))
    if rate < 1 or rate > 1000:
        logger.warning("Stars rate out of expected range: %s", rate)
        return settings.stars_per_usd

    with _lock:
        _cached_rate = rate
        _cached_at = now

    return rate
