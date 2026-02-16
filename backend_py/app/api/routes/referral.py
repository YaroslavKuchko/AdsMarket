from __future__ import annotations

import secrets
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.bot_username import get_bot_username
from app.core.config import settings
from app.db.models import User, ReferralSettings, ReferralPayout, ReferralBalance
from app.db.session import get_db

router = APIRouter(prefix="/api/referral", tags=["referral"])


class ReferralLinkOut(BaseModel):
    referralCode: str
    referralLink: str
    webappUrl: str


class ReferralStatsOut(BaseModel):
    totalReferrals: int
    activeReferrals: int  # referrals who made at least one purchase
    earnings: dict[str, float]  # {'stars': 0, 'ton': 0, 'usdt': 0}
    pending: dict[str, float]
    referralCode: str
    referralLink: str


class ReferralSettingsOut(BaseModel):
    # Payout percentages
    starsPercent: float
    tonPercent: float
    usdtPercent: float
    # Bonus
    bonusStars: int
    # Min purchase thresholds for bonus
    minPurchaseStars: int
    minPurchaseUsdt: float
    minPurchaseTon: float
    # TON price
    tonUsdPrice: float
    # Min payout thresholds
    starsMinPayout: int
    tonMinPayout: float
    usdtMinPayout: float


def _get_telegram_id_from_auth(authorization: str | None) -> int:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing authorization")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="invalid authorization")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")
    telegram_id = payload.get("telegram_id")
    if telegram_id is None:
        raise HTTPException(status_code=401, detail="invalid token payload")
    return int(telegram_id)


def _generate_referral_code() -> str:
    """Generate a short unique referral code."""
    return secrets.token_urlsafe(6)[:8]


def _get_or_create_referral_code(db: Session, user: User) -> str:
    """Get existing referral code or create a new one."""
    if user.referral_code:
        return user.referral_code

    # Generate unique code
    for _ in range(10):
        code = _generate_referral_code()
        existing = db.execute(
            select(User).where(User.referral_code == code)
        ).scalar_one_or_none()
        if not existing:
            user.referral_code = code
            db.commit()
            return code

    # Fallback: use telegram_id based code
    code = f"u{user.telegram_id}"[-8:]
    user.referral_code = code
    db.commit()
    return code


def _get_webapp_path() -> str:
    """Extract webapp path from webapp_url (e.g. t.me/ads_marketplacebot/admarket -> admarket)."""
    raw = settings.webapp_url.rstrip("/").replace("https://", "")
    parts = raw.split("/")
    if len(parts) >= 3 and parts[0] == "t.me":
        return parts[2]
    return "admarket"


def _build_referral_link(referral_code: str) -> str:
    """Build the referral link using bot username from getMe and webapp path."""
    bot_username = get_bot_username()
    path = _get_webapp_path()
    return f"https://t.me/{bot_username}/{path}?startapp=ref_{referral_code}"


def _get_or_create_settings(db: Session) -> ReferralSettings:
    """Get referral settings or create defaults."""
    settings_row = db.execute(
        select(ReferralSettings).where(ReferralSettings.id == 1)
    ).scalar_one_or_none()

    if not settings_row:
        settings_row = ReferralSettings(id=1)
        db.add(settings_row)
        db.commit()
        db.refresh(settings_row)

    return settings_row


@router.get("/link", response_model=ReferralLinkOut)
def get_referral_link(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """Get or generate referral link for the current user."""
    telegram_id = _get_telegram_id_from_auth(authorization)

    user = db.execute(
        select(User).where(User.telegram_id == telegram_id)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    referral_code = _get_or_create_referral_code(db, user)
    referral_link = _build_referral_link(referral_code)
    webapp_url_resolved = f"https://t.me/{get_bot_username()}/{_get_webapp_path()}"

    return ReferralLinkOut(
        referralCode=referral_code,
        referralLink=referral_link,
        webappUrl=webapp_url_resolved,
    )


@router.get("/stats", response_model=ReferralStatsOut)
def get_referral_stats(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """Get referral statistics for the current user."""
    telegram_id = _get_telegram_id_from_auth(authorization)

    user = db.execute(
        select(User).where(User.telegram_id == telegram_id)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    referral_code = _get_or_create_referral_code(db, user)
    referral_link = _build_referral_link(referral_code)

    # Count total referrals
    total_referrals = db.execute(
        select(func.count()).select_from(User).where(User.referred_by == telegram_id)
    ).scalar() or 0

    # Count active referrals (those with at least one payout record)
    active_referrals = db.execute(
        select(func.count(func.distinct(ReferralPayout.referred_telegram_id)))
        .where(ReferralPayout.referrer_telegram_id == telegram_id)
    ).scalar() or 0

    # Get earnings per currency
    earnings = {"stars": 0.0, "ton": 0.0, "usdt": 0.0}
    pending = {"stars": 0.0, "ton": 0.0, "usdt": 0.0}

    balances = db.execute(
        select(ReferralBalance).where(ReferralBalance.telegram_id == telegram_id)
    ).scalars().all()

    for balance in balances:
        if balance.currency in earnings:
            earnings[balance.currency] = float(balance.total_earned)

    # Get pending payouts
    pending_payouts = db.execute(
        select(ReferralPayout.currency, func.sum(ReferralPayout.payout_amount))
        .where(
            ReferralPayout.referrer_telegram_id == telegram_id,
            ReferralPayout.status == "pending"
        )
        .group_by(ReferralPayout.currency)
    ).all()

    for currency, amount in pending_payouts:
        if currency in pending:
            pending[currency] = float(amount or 0)

    return ReferralStatsOut(
        totalReferrals=total_referrals,
        activeReferrals=active_referrals,
        earnings=earnings,
        pending=pending,
        referralCode=referral_code,
        referralLink=referral_link,
    )


@router.get("/settings", response_model=ReferralSettingsOut)
def get_referral_settings(
    db: Session = Depends(get_db),
):
    """Get current referral settings (public)."""
    ref_settings = _get_or_create_settings(db)

    return ReferralSettingsOut(
        starsPercent=float(ref_settings.stars_percent),
        tonPercent=float(ref_settings.ton_percent),
        usdtPercent=float(ref_settings.usdt_percent),
        bonusStars=ref_settings.bonus_stars,
        minPurchaseStars=ref_settings.min_purchase_stars,
        minPurchaseUsdt=float(ref_settings.min_purchase_usdt),
        minPurchaseTon=float(ref_settings.min_purchase_ton),
        tonUsdPrice=float(ref_settings.ton_usd_price),
        starsMinPayout=ref_settings.stars_min_payout,
        tonMinPayout=float(ref_settings.ton_min_payout),
        usdtMinPayout=float(ref_settings.usdt_min_payout),
    )


@router.post("/update-ton-price")
async def update_ton_price(
    db: Session = Depends(get_db),
):
    """
    Update TON price from CoinGecko API.
    Should be called daily via cron or scheduler.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "the-open-network", "vs_currencies": "usd"},
            )
            response.raise_for_status()
            data = response.json()

        ton_price = data.get("the-open-network", {}).get("usd")
        if not ton_price or ton_price <= 0:
            raise HTTPException(status_code=502, detail="Invalid price from CoinGecko")

        ref_settings = _get_or_create_settings(db)
        ref_settings.ton_usd_price = Decimal(str(ton_price))
        ref_settings.ton_price_updated_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "ok": True,
            "tonUsdPrice": float(ton_price),
            "minPurchaseTon": float(ref_settings.min_purchase_ton),
            "updatedAt": ref_settings.ton_price_updated_at.isoformat(),
        }

    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"CoinGecko API error: {str(e)}")
