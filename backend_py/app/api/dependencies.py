"""
Shared FastAPI dependencies for authentication and common operations.
"""
from __future__ import annotations

import jwt
from fastapi import Depends, Header, HTTPException

from app.core.config import settings


def get_current_user_telegram_id(
    authorization: str | None = Header(None),
) -> int:
    """
    Extract and validate telegram_id from JWT token in Authorization header.
    
    Usage:
        @router.get("/endpoint")
        async def endpoint(telegram_id: int = Depends(get_current_user_telegram_id)):
            ...
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="missing authorization")
    
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="invalid authorization")
    
    token = authorization.split(" ", 1)[1].strip()
    
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")
    
    telegram_id = payload.get("telegram_id")
    if telegram_id is None:
        raise HTTPException(status_code=401, detail="invalid token payload")

    return int(telegram_id)


def get_optional_telegram_id(
    authorization: str | None = Header(None),
) -> int | None:
    """
    Return telegram_id from JWT if Authorization header is present and valid; else None.
    Use for endpoints that work both with and without auth (e.g. market channel details).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        tid = payload.get("telegram_id")
        return int(tid) if tid is not None else None
    except Exception:
        return None

