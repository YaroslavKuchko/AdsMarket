from __future__ import annotations

import time
from typing import Any

import jwt
import re

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import TelegramAuthEvent, User
from app.db.session import get_db
from app.telegram.verify_init_data import verify_webapp_init_data
from app.realtime.hub import hub

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TelegramAuthIn(BaseModel):
    initData: str = Field(min_length=1)
    isAdmin: bool = False


class TelegramAuthUserOut(BaseModel):
    telegramId: int
    username: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    languageCode: str | None = None
    photoUrl: str | None = None
    phoneNumber: str | None = None
    referralCode: str | None = None
    referredBy: int | None = None


class TelegramAuthOut(BaseModel):
    token: str
    user: TelegramAuthUserOut


class PhoneFromBotIn(BaseModel):
    telegramId: int = Field(ge=1)
    phone: str = Field(min_length=3, max_length=64)


class PhoneFromBotOut(BaseModel):
    success: bool
    phone: str
    language: str


def _issue_jwt(payload: dict[str, Any]) -> str:
    now = int(time.time())
    exp = now + int(settings.jwt_expires_sec)
    token = jwt.encode(
        {**payload, "iat": now, "exp": exp},
        settings.jwt_secret,
        algorithm="HS256",
    )
    # PyJWT may return str or bytes depending on version/settings
    if isinstance(token, bytes):
        return token.decode("utf-8")
    return token


@router.post("/telegram", response_model=TelegramAuthOut)
def telegram_auth(body: TelegramAuthIn, db: Session = Depends(get_db)):
    ok, result = verify_webapp_init_data(
        init_data_raw=body.initData,
        bot_token=settings.tg_bot_token,
        max_age_sec=settings.tg_auth_max_age_sec,
    )
    if not ok:
        raise HTTPException(status_code=401, detail=str(result))

    verified = result  # type: ignore[assignment]
    if not verified.user or "id" not in verified.user:
        raise HTTPException(status_code=400, detail="user payload missing")

    tg_user = verified.user
    telegram_id = int(tg_user["id"])

    username = tg_user.get("username")
    first_name = tg_user.get("first_name")
    last_name = tg_user.get("last_name")
    language_code = tg_user.get("language_code")
    photo_url = tg_user.get("photo_url")

    existing = db.execute(select(User).where(User.telegram_id == telegram_id))
    row = existing.scalar_one_or_none()

    is_new_user = row is None

    if is_new_user:
        row = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
            photo_url=photo_url,
        )
        db.add(row)
    else:
        row.username = username
        row.first_name = first_name
        row.last_name = last_name
        row.language_code = language_code
        row.photo_url = photo_url

    # Handle referral code from start_param (format: ref_XXXXXX)
    start_param = verified.start_param
    if is_new_user and start_param and start_param.startswith("ref_"):
        ref_code = start_param[4:]  # Remove "ref_" prefix
        if ref_code:
            # Find the referrer by their referral code
            referrer = db.execute(
                select(User).where(User.referral_code == ref_code)
            ).scalar_one_or_none()
            if referrer and referrer.telegram_id != telegram_id:
                row.referred_by = referrer.telegram_id

    db.add(
        TelegramAuthEvent(
            telegram_id=telegram_id,
            auth_date=verified.auth_date,
            start_param=verified.start_param,
        )
    )

    db.commit()

    # Re-load to guarantee we return latest phone_number if it was saved separately (contact flow).
    refreshed = db.execute(select(User).where(User.telegram_id == telegram_id)).scalar_one()

    token = _issue_jwt(
        {
            "sub": str(telegram_id),
            "telegram_id": telegram_id,
            "is_admin": bool(body.isAdmin),
        }
    )

    return TelegramAuthOut(
        token=token,
        user=TelegramAuthUserOut(
            telegramId=telegram_id,
            username=refreshed.username,
            firstName=refreshed.first_name,
            lastName=refreshed.last_name,
            languageCode=refreshed.language_code,
            photoUrl=refreshed.photo_url,
            phoneNumber=refreshed.phone_number,
            referralCode=refreshed.referral_code,
            referredBy=refreshed.referred_by,
        ),
    )


@router.post("/phone-from-bot", response_model=PhoneFromBotOut)
async def phone_from_bot(
    body: PhoneFromBotIn,
    db: Session = Depends(get_db),
    x_internal_secret: str | None = Header(default=None),
):
    # Simple protection: require INTERNAL_SECRET if configured.
    if settings.internal_secret and x_internal_secret != settings.internal_secret:
        raise HTTPException(status_code=403, detail="forbidden")

    # Normalize phone to digits (like in your reference project)
    clean = re.sub(r"\\D+", "", body.phone)
    if not clean:
        raise HTTPException(status_code=400, detail="invalid phone")

    row = db.execute(select(User).where(User.telegram_id == body.telegramId)).scalar_one_or_none()
    if row is None:
        row = User(telegram_id=body.telegramId, phone_number=clean)
        db.add(row)
    else:
        row.phone_number = clean
    db.commit()

    # Determine language for bot response
    preferred = getattr(row, "preferred_language", None) if row is not None else None
    base_lang = preferred or row.language_code if row is not None else None
    lang = "ru" if (base_lang or "").lower().startswith("ru") else "en"

    await hub.send(body.telegramId, {"type": "phone_updated", "phoneNumber": clean})
    return PhoneFromBotOut(success=True, phone=clean, language=lang)


