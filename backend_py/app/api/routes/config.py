"""Public config endpoint for frontend (e.g. bot username, Stars rate)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.bot_username import get_bot_username
from app.core.stars_rate import get_stars_per_usd
from app.db.models import ReferralSettings
from app.db.session import get_db

router = APIRouter(prefix="/api/config", tags=["config"])


def _get_ton_usd_price(db: Session) -> float:
    """Get TON/USD price from referral settings for order TON conversion."""
    rs = db.execute(select(ReferralSettings).where(ReferralSettings.id == 1)).scalar_one_or_none()
    if rs and rs.ton_usd_price and rs.ton_usd_price > 0:
        return float(rs.ton_usd_price)
    return 5.0


@router.get("")
def get_config(db: Session = Depends(get_db)):
    """Return public config (bot username, Stars/USD rate, TON/USD for conversions)."""
    return {
        "botUsername": get_bot_username(),
        "starsPerUsd": get_stars_per_usd(),
        "tonUsdPrice": _get_ton_usd_price(db),
    }
