#!/usr/bin/env python3
"""
Refund Stars by telegram_payment_charge_id.
Usage:
  python -m scripts.refund_stars stx... stx...          # lookup in DB
  python -m scripts.refund_stars "stx...:USER_ID" ...    # charge not in DB, provide user_id
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal

from aiogram import Bot
from sqlalchemy import select

from app.core.config import settings
from app.db.models import StarsTransaction, UserBalance
from app.db.session import SessionLocal


CHARGE_IDS = [
    "stxmMC3XmM32VKSZUE2lZcevZFkttXEIoJXg6w2aFCTSk7QrDAb_ADnILUhKHqB4mX4nndfs4sL15NFdWnOj0-9pPJnNaIbD3-M_jNYv0HfV6Nrgy8QNtCMRl4ze2PtSo-x",
    "stx8Vh84EPRxK36ysHeCI9WpXcQ9Dn7QcDOHx4LbWJv4FIhxJZKeALxlwyvV8KSHCLfdLfJP03zk84AONfdKj1mGl3Ikavy5p2vV9o45jSqvnptJI7xKG4mfaU95_jlZHhJ",
    "stxKXSeBgaxZAg6e5wfLWIYDi4jh7obynP7PHvZnjsZrnfO1aZ-T3SPR22VoqJfgYvMSRHLlVdtoWrCvu1awttsEIMXZLIOFzhuuA9Ggn-2034qH_bgMjmQ7GyJXineluWc",
    "stxxR4AZXGc54XMQ91p4no5w5IhkXZPjUS8pXMWTbYUMm_9B20YIlr0BKzQJyi1QvTX6OrxLsxMy6lVJu7w9g7uHX2KC1aLg7lg-dORjksvzETZItGuwK1FZMAD_0bSOPju",
    "stxo5s3G5UZNLHR98_9lquqIC7Fa9f5S3Wjv9r5olaxG1t4gJlyfMZWG8t5A7LRda4UrkbU7qHFRnYPgbpy2eAa0P1YlxhZpnAK9zqB6GOwWpd7ibn4jEvbGM8VJ20WOLwU",
    "stxcLvR1o6oNR-RkawNFE3azxwJ_qovTqSvWkN3FA4ibujzpaoj8YTl7rJCeZ4asRJVhUwfrLowgxasaFXKhxlRzG3haNaBeUntLf_JnpwbdE4jpttqnlllwb3_CycqdQWi",
]


async def main() -> None:
    raw_args = sys.argv[1:] if len(sys.argv) > 1 else CHARGE_IDS
    bot = Bot(token=settings.tg_bot_token)
    db = SessionLocal()
    # Parse "charge_id" or "charge_id:user_id"
    items: list[tuple[str, int | None]] = []
    for s in raw_args:
        s = s.strip()
        if ":" in s and s.split(":")[1].isdigit():
            cid, uid = s.rsplit(":", 1)
            items.append((cid.strip(), int(uid)))
        else:
            items.append((s, None))
    try:
        for charge_id, forced_user_id in items:
            if not charge_id or not charge_id.startswith("stx"):
                continue
            tx = db.execute(
                select(StarsTransaction).where(
                    StarsTransaction.telegram_payment_charge_id == charge_id
                )
            ).scalar_one_or_none()
            user_id: int
            need_db_update = False
            if tx:
                user_id = tx.telegram_id
                need_db_update = True
                if tx.status == "refunded":
                    print(f"  SKIP {charge_id[:40]}... — already refunded")
                    continue
                # Always use tx.telegram_id for Telegram API and for DB balance deduction
            elif forced_user_id:
                user_id = forced_user_id
            else:
                print(f"  SKIP {charge_id[:40]}... — not in DB, need user_id (use charge_id:USER_ID)")
                continue
            if need_db_update:
                bal = db.execute(
                    select(UserBalance).where(
                        UserBalance.telegram_id == tx.telegram_id,
                        UserBalance.currency == "stars",
                    )
                ).scalar_one_or_none()
                if not bal or bal.available < Decimal(tx.amount):
                    print(f"  SKIP {charge_id[:40]}... — insufficient balance (user {tx.telegram_id})")
                    continue
            try:
                ok = await bot.refund_star_payment(
                    user_id=user_id,
                    telegram_payment_charge_id=charge_id,
                )
                if ok:
                    if need_db_update and tx:
                        bal = db.execute(
                            select(UserBalance).where(
                                UserBalance.telegram_id == tx.telegram_id,
                                UserBalance.currency == "stars",
                            )
                        ).scalar_one_or_none()
                        if bal:
                            bal.available -= Decimal(tx.amount)
                            bal.total_deposited -= Decimal(tx.amount)
                        tx.status = "refunded"
                        db.commit()
                    print(f"  OK   refunded Stars for user {user_id}")
                else:
                    print(f"  FAIL {charge_id[:40]}... — Telegram refused")
            except Exception as e:
                db.rollback()
                print(f"  FAIL {charge_id[:40]}... — {e}")
    finally:
        await bot.session.close()
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
