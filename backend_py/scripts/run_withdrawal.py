#!/usr/bin/env python3
"""
One-off script to create and process a USDT withdrawal.
Usage: python scripts/run_withdrawal.py <telegram_id> <amount> <address>
Example: python scripts/run_withdrawal.py 650355091 10 UQDkqVwe1BEab_skHDhtAVvJJ3CuMHltq-3Il3QxQN4YeXge
"""
import asyncio
import sys
import uuid
from decimal import Decimal

# Setup path
sys.path.insert(0, ".")

from sqlalchemy import select
from app.db.models import UsdtTransaction, UserBalance
from app.db.session import SessionLocal
from app.services.usdt_withdraw_sender import (
    USDT_WITHDRAW_FEE,
    process_pending_withdrawals,
)


def main():
    if len(sys.argv) < 4:
        print("Usage: python scripts/run_withdrawal.py <telegram_id> <amount> <address>")
        sys.exit(1)
    telegram_id = int(sys.argv[1])
    amount = Decimal(sys.argv[2])
    address = sys.argv[3].strip()
    total = amount  # user pays full, receives amount - fee
    net = amount - USDT_WITHDRAW_FEE

    db = SessionLocal()
    try:
        bal = db.execute(
            select(UserBalance).where(
                UserBalance.telegram_id == telegram_id,
                UserBalance.currency == "usdt",
            )
        ).scalar_one_or_none()
        if not bal:
            bal = UserBalance(telegram_id=telegram_id, currency="usdt", available=Decimal("0"), total_withdrawn=Decimal("0"))
            db.add(bal)
            db.flush()
        if bal.available < total:
            need = total - bal.available
            print(f"Adding {need} USDT to balance for test")
            bal.available += need
        bal.available -= total
        bal.total_withdrawn += total
        tx = UsdtTransaction(
            event_id=f"wd_{uuid.uuid4().hex}",
            telegram_id=telegram_id,
            amount=net,
            tx_type="withdrawal",
            status="pending",
            memo=address[:256],
            destination_memo=None,
        )
        db.add(tx)
        db.commit()
        print(f"Created withdrawal {tx.event_id}: {net} USDT -> {address[:40]}...")
    finally:
        db.close()

    print("Running process_pending_withdrawals...")
    n = asyncio.run(process_pending_withdrawals())
    print(f"Processed {n} withdrawal(s)")


if __name__ == "__main__":
    main()
