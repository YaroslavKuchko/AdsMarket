from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import TelegramValidateIn, TelegramValidateOut
from app.core.config import settings
from app.db.models import TelegramAuthEvent, User
from app.db.session import get_db
from app.telegram.verify_init_data import verify_webapp_init_data

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/validate", response_model=TelegramValidateOut)
def validate_init_data(body: TelegramValidateIn, db: Session = Depends(get_db)):
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

    telegram_id = int(verified.user["id"])

    # Upsert user
    existing = db.execute(select(User).where(User.telegram_id == telegram_id))
    user_row = existing.scalar_one_or_none()

    username = verified.user.get("username")
    first_name = verified.user.get("first_name")
    last_name = verified.user.get("last_name")
    language_code = verified.user.get("language_code")
    photo_url = verified.user.get("photo_url")

    if user_row is None:
        user_row = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
            photo_url=photo_url,
        )
        db.add(user_row)
    else:
        user_row.username = username
        user_row.first_name = first_name
        user_row.last_name = last_name
        user_row.language_code = language_code
        user_row.photo_url = photo_url

    # Save auth event (for future attribution / referral)
    db.add(
        TelegramAuthEvent(
            telegram_id=telegram_id,
            auth_date=verified.auth_date,
            start_param=verified.start_param,
        )
    )

    db.commit()

    return TelegramValidateOut(
        ok=True,
        user=verified.user,
        startParam=verified.start_param,
        authDate=verified.auth_date,
    )


