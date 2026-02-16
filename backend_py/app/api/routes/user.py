from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/api/user", tags=["user"])


class UserOut(BaseModel):
    telegramId: int
    username: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    languageCode: str | None = None
    preferredLanguage: str | None = None
    photoUrl: str | None = None
    phoneNumber: str | None = None


class SetLanguageIn(BaseModel):
    language: str


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


@router.get("/profile", response_model=UserOut)
def get_profile(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    telegram_id = _get_telegram_id_from_auth(authorization)
    row = db.execute(select(User).where(User.telegram_id == telegram_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")
    return UserOut(
        telegramId=int(row.telegram_id),
        username=row.username,
        firstName=row.first_name,
        lastName=row.last_name,
        languageCode=row.language_code,
        preferredLanguage=getattr(row, "preferred_language", None),
        photoUrl=row.photo_url,
        phoneNumber=row.phone_number,
    )


@router.post("/language")
def set_language(
    body: SetLanguageIn,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    telegram_id = _get_telegram_id_from_auth(authorization)
    lang = (body.language or "").strip().lower()
    if lang not in ("ru", "en"):
        raise HTTPException(status_code=400, detail="unsupported language")
    row = db.execute(select(User).where(User.telegram_id == telegram_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")
    # store preference without affecting Telegram language_code
    setattr(row, "preferred_language", lang)
    db.commit()
    return {"ok": True, "preferredLanguage": lang}


