from __future__ import annotations

from pydantic import BaseModel, Field


class TelegramValidateIn(BaseModel):
    initData: str = Field(min_length=1)


class TelegramValidateOut(BaseModel):
    ok: bool
    user: dict | None = None
    startParam: str | None = None
    authDate: int | None = None


