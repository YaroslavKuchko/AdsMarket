from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl


@dataclass(frozen=True)
class VerifiedInitData:
    raw: str
    auth_date: int | None
    user: dict[str, Any] | None
    start_param: str | None


def _build_data_check_string(init_data_raw: str) -> tuple[str, str | None]:
    """
    Return (data_check_string, hash_value).
    """
    pairs = parse_qsl(init_data_raw, keep_blank_values=True)
    hash_value = None

    items: list[tuple[str, str]] = []
    for k, v in pairs:
        if k == "hash":
            hash_value = v
            continue
        items.append((k, v))

    items.sort(key=lambda kv: kv[0])
    data_check_string = "\n".join([f"{k}={v}" for k, v in items])
    return data_check_string, hash_value


def verify_webapp_init_data(
    init_data_raw: str,
    bot_token: str,
    max_age_sec: int = 86400,
) -> tuple[bool, str | VerifiedInitData]:
    """
    Validates initData received from Telegram WebApp.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data_raw:
        return False, "initData is empty"
    if not bot_token:
        return False, "bot token is missing"

    data_check_string, hash_value = _build_data_check_string(init_data_raw)
    if not hash_value:
        return False, "hash missing"

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    # timing-safe compare
    if not hmac.compare_digest(computed_hash, hash_value):
        return False, "hash mismatch"

    params = dict(parse_qsl(init_data_raw, keep_blank_values=True))
    auth_date_raw = params.get("auth_date")
    auth_date: int | None = None
    if auth_date_raw is not None:
        try:
            auth_date = int(auth_date_raw)
        except ValueError:
            return False, "auth_date invalid"

    if auth_date is not None:
        now = int(time.time())
        if auth_date > now + 60:
            return False, "auth_date is in the future"
        if now - auth_date > max_age_sec:
            return False, "initData expired"

    user_json = params.get("user")
    user: dict[str, Any] | None = None
    if user_json:
        try:
            parsed = json.loads(user_json)
            if isinstance(parsed, dict):
                user = parsed
        except Exception:
            user = None

    start_param = params.get("start_param")

    return True, VerifiedInitData(
        raw=init_data_raw,
        auth_date=auth_date,
        user=user,
        start_param=start_param,
    )


