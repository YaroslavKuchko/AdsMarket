"""
TON Wallet API routes.

Handles wallet connection, balance queries, and transaction verification.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_telegram_id
from app.db.models import TonTransaction, TonWallet, TonWithdrawal, UserBalance
from app.db.session import get_db

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


# ============================================================================
# Request/Response Models
# ============================================================================


class ConnectWalletRequest(BaseModel):
    """Request to connect a TON wallet."""
    address: str = Field(..., description="TON wallet address (raw format)")
    friendlyAddress: str | None = Field(None, description="User-friendly address format")
    walletName: str | None = Field(None, description="Wallet app name (e.g., Tonkeeper)")


class ConnectWalletResponse(BaseModel):
    """Response after connecting a wallet."""
    ok: bool
    walletId: int
    address: str
    isNew: bool


class DisconnectWalletResponse(BaseModel):
    """Response after disconnecting a wallet."""
    ok: bool


class WalletInfoResponse(BaseModel):
    """User's connected wallet info."""
    connected: bool
    address: str | None = None
    friendlyAddress: str | None = None
    walletName: str | None = None
    connectedAt: datetime | None = None


class BalanceResponse(BaseModel):
    """User's balance in all currencies."""
    stars: Decimal = Field(default=Decimal("0"), decimal_places=0)
    ton: Decimal = Field(default=Decimal("0"), decimal_places=8)
    usdt: Decimal = Field(default=Decimal("0"), decimal_places=2)


class VerifyTransactionRequest(BaseModel):
    """Request to verify a TON transaction."""
    txHash: str = Field(..., description="Transaction hash from blockchain")
    expectedAmount: Decimal = Field(..., description="Expected amount in TON")
    orderRef: str | None = Field(None, description="Order reference/comment")


class VerifyTransactionResponse(BaseModel):
    """Response after verifying a transaction."""
    ok: bool
    status: str  # 'confirmed', 'pending', 'failed', 'already_processed'
    message: str | None = None
    amount: Decimal | None = None


# ============================================================================
# Routes
# ============================================================================


@router.post("/connect", response_model=ConnectWalletResponse)
async def connect_wallet(
    request: ConnectWalletRequest,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> ConnectWalletResponse:
    """
    Connect a TON wallet to user's account.
    
    If the wallet was previously connected to this user, it will be reactivated.
    If it's a new wallet, it will be added and set as primary.
    """
    print(f"[Wallet] Connect request: telegram_id={telegram_id}")
    print(f"[Wallet]   address={request.address}")
    print(f"[Wallet]   friendlyAddress={request.friendlyAddress}")
    print(f"[Wallet]   walletName={request.walletName}")
    
    # Check if this wallet was already connected to this user
    existing = db.execute(
        select(TonWallet).where(
            TonWallet.telegram_id == telegram_id,
            TonWallet.address == request.address,
        )
    ).scalar_one_or_none()

    if existing:
        # Reactivate the wallet
        existing.is_active = True
        existing.is_primary = True
        existing.disconnected_at = None
        existing.wallet_name = request.walletName or existing.wallet_name
        existing.friendly_address = request.friendlyAddress or existing.friendly_address
        db.commit()

        return ConnectWalletResponse(
            ok=True,
            walletId=existing.id,
            address=existing.address,
            isNew=False,
        )

    # Deactivate other primary wallets for this user
    db.execute(
        update(TonWallet)
        .where(TonWallet.telegram_id == telegram_id, TonWallet.is_primary == True)
        .values(is_primary=False)
    )

    # Create new wallet connection
    wallet = TonWallet(
        telegram_id=telegram_id,
        address=request.address,
        friendly_address=request.friendlyAddress,
        wallet_name=request.walletName,
        is_primary=True,
        is_active=True,
    )
    db.add(wallet)
    db.commit()
    db.refresh(wallet)

    return ConnectWalletResponse(
        ok=True,
        walletId=wallet.id,
        address=wallet.address,
        isNew=True,
    )


@router.post("/disconnect", response_model=DisconnectWalletResponse)
async def disconnect_wallet(
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> DisconnectWalletResponse:
    """
    Disconnect the user's current primary wallet.
    """
    result = db.execute(
        update(TonWallet)
        .where(
            TonWallet.telegram_id == telegram_id,
            TonWallet.is_primary == True,
            TonWallet.is_active == True,
        )
        .values(is_active=False, is_primary=False, disconnected_at=datetime.utcnow())
    )
    db.commit()

    return DisconnectWalletResponse(ok=True)


@router.get("/info", response_model=WalletInfoResponse)
async def get_wallet_info(
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> WalletInfoResponse:
    """
    Get user's connected wallet information.
    """
    wallet = db.execute(
        select(TonWallet).where(
            TonWallet.telegram_id == telegram_id,
            TonWallet.is_primary == True,
            TonWallet.is_active == True,
        )
    ).scalar_one_or_none()

    if not wallet:
        return WalletInfoResponse(connected=False)

    return WalletInfoResponse(
        connected=True,
        address=wallet.address,
        friendlyAddress=wallet.friendly_address,
        walletName=wallet.wallet_name,
        connectedAt=wallet.connected_at,
    )


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> BalanceResponse:
    """
    Get user's balance in all currencies.
    """
    balances = db.execute(
        select(UserBalance).where(UserBalance.telegram_id == telegram_id)
    ).scalars().all()

    result = BalanceResponse()
    for balance in balances:
        if balance.currency == "stars":
            result.stars = balance.available
        elif balance.currency == "ton":
            result.ton = balance.available
        elif balance.currency == "usdt":
            result.usdt = balance.available

    return result


@router.post("/verify-transaction", response_model=VerifyTransactionResponse)
async def verify_transaction(
    request: VerifyTransactionRequest,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> VerifyTransactionResponse:
    """
    Verify a TON transaction and credit user's balance if valid.
    
    Security checks:
    1. Transaction hash uniqueness (prevent replay attacks)
    2. Amount verification
    3. Destination address verification
    4. Transaction confirmation on blockchain
    """
    # Check if transaction was already processed
    existing = db.execute(
        select(TonTransaction).where(TonTransaction.tx_hash == request.txHash)
    ).scalar_one_or_none()

    if existing:
        if existing.status == "processed":
            return VerifyTransactionResponse(
                ok=False,
                status="already_processed",
                message="This transaction has already been processed",
            )
        elif existing.status == "failed":
            return VerifyTransactionResponse(
                ok=False,
                status="failed",
                message=existing.error_message or "Transaction verification failed",
            )

    # TODO: Implement actual blockchain verification via TON Center API
    # For now, we'll create a pending transaction record
    # In production, this should:
    # 1. Call TON Center API to get transaction details
    # 2. Verify destination address matches our wallet
    # 3. Verify amount matches expected
    # 4. Verify comment/memo if provided
    # 5. Only then credit the user's balance

    return VerifyTransactionResponse(
        ok=False,
        status="pending",
        message="Transaction verification is pending. This feature requires TON Center API integration.",
    )


# ============================================================================
# USDT (TON network, Jetton)
# ============================================================================


@router.get("/usdt-deposit-info")
async def get_usdt_deposit_info(
    telegram_id: int = Depends(get_current_user_telegram_id),
) -> dict:
    """
    Get deposit address and memo for USDT top-up.
    User sends USDT to our wallet with memo = telegram_id.
    """
    from app.core.config import settings

    wallet = (settings.usdt_deposit_wallet or "").strip()
    if not wallet:
        raise HTTPException(
            status_code=503,
            detail="USDT deposits are not configured",
        )
    return {
        "depositAddress": wallet,
        "memo": str(telegram_id),
        "network": "TON",
        "instruction": "Send USDT to the address above. In the comment/memo field, enter your ID (shown below).",
    }


USDT_WITHDRAW_FEE = Decimal("0.3")
USDT_WITHDRAW_MIN = Decimal("10")


class UsdtWithdrawRequest(BaseModel):
    amount: Decimal = Field(..., ge=USDT_WITHDRAW_MIN, description="Amount in USDT (min 10)")
    address: str = Field(..., min_length=40, max_length=256, description="TON wallet address")
    memo: str | None = Field(None, max_length=128, description="Optional Tag/Memo for exchange")


@router.get("/usdt-withdraw-info")
async def get_usdt_withdraw_info(
    telegram_id: int = Depends(get_current_user_telegram_id),
) -> dict:
    """Return withdraw fee and min amount for UI."""
    return {
        "feeUsdt": float(USDT_WITHDRAW_FEE),
        "minUsdt": float(USDT_WITHDRAW_MIN),
    }


@router.post("/usdt-withdraw")
async def usdt_withdraw(
    body: UsdtWithdrawRequest,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> dict:
    """
    Request USDT withdrawal to any TON wallet.
    Fee 0.3 USDT; user receives amount - fee.
    """
    total_deduct = body.amount  # User pays full amount; we send amount - fee
    net_amount = body.amount - USDT_WITHDRAW_FEE

    # Lock row to prevent race: two concurrent withdrawals with same balance
    stmt = (
        select(UserBalance)
        .where(
            UserBalance.telegram_id == telegram_id,
            UserBalance.currency == "usdt",
        )
        .with_for_update()
    )
    usdt_bal = db.execute(stmt).scalar_one_or_none()

    if not usdt_bal:
        raise HTTPException(status_code=400, detail="Insufficient USDT balance")

    if usdt_bal.available < total_deduct:
        raise HTTPException(status_code=400, detail="Insufficient USDT balance")

    from app.db.models import UsdtTransaction
    import uuid

    # Deduct full amount; net_amount goes to user
    usdt_bal.available -= total_deduct
    usdt_bal.total_withdrawn += total_deduct

    tx = UsdtTransaction(
        event_id=f"wd_{uuid.uuid4().hex}",
        telegram_id=telegram_id,
        amount=net_amount,
        tx_type="withdrawal",
        status="pending",
        memo=body.address[:256] if body.address else None,
        destination_memo=body.memo[:128] if body.memo else None,
    )
    db.add(tx)
    db.commit()

    return {
        "ok": True,
        "amount": float(net_amount),
        "fee": float(USDT_WITHDRAW_FEE),
        "address": body.address,
        "status": "pending",
    }


# ============================================================================
# TON native (deposits by connected wallet, withdrawals)
# ============================================================================

TON_WITHDRAW_FEE = Decimal("0.15")
TON_WITHDRAW_MIN = Decimal("0.1")


@router.get("/ton-deposit-info")
async def get_ton_deposit_info(
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get TON deposit address. User must send from their CONNECTED wallet.
    No memo - we match by sender address (TonWallet).
    """
    from app.core.config import settings
    wallet = (settings.ton_deposit_wallet or "").strip()
    if not wallet:
        raise HTTPException(status_code=503, detail="TON deposits are not configured")
    # Check user has connected wallet (must send from connected wallet)
    conn = db.execute(
        select(TonWallet).where(
            TonWallet.telegram_id == telegram_id,
            TonWallet.is_active == True,
        )
    ).scalars().first()
    if not conn:
        raise HTTPException(
            status_code=400,
            detail="Подключите кошелёк для пополнения TON. Отправляйте TON только с подключённого кошелька.",
        )
    return {
        "depositAddress": wallet,
        "network": "TON",
        "instruction": "Отправьте TON с вашего подключённого кошелька на указанный адрес. Сумма будет зачислена автоматически.",
        "connectedWallet": conn.address,
    }


class TonWithdrawRequest(BaseModel):
    amount: Decimal = Field(..., ge=TON_WITHDRAW_MIN, description="Amount in TON (min 0.1)")


@router.get("/ton-withdraw-info")
async def get_ton_withdraw_info() -> dict:
    return {"feeTon": float(TON_WITHDRAW_FEE), "minTon": float(TON_WITHDRAW_MIN)}


@router.post("/ton-withdraw")
async def ton_withdraw(
    body: TonWithdrawRequest,
    telegram_id: int = Depends(get_current_user_telegram_id),
    db: Session = Depends(get_db),
) -> dict:
    """Request TON withdrawal to connected primary wallet. Fee 0.15 TON."""
    import uuid
    # Get primary (or any active) connected wallet address
    conn = db.execute(
        select(TonWallet).where(
            TonWallet.telegram_id == telegram_id,
            TonWallet.is_active == True,
        ).order_by(TonWallet.is_primary.desc())  # primary first
    ).scalars().first()
    if not conn or not conn.address:
        raise HTTPException(
            status_code=400,
            detail="Подключите кошелёк TON для вывода. Вывод только на подключённый кошелёк.",
        )

    total_deduct = body.amount + TON_WITHDRAW_FEE
    net_amount = body.amount

    stmt = (
        select(UserBalance)
        .where(
            UserBalance.telegram_id == telegram_id,
            UserBalance.currency == "ton",
        )
        .with_for_update()
    )
    ton_bal = db.execute(stmt).scalar_one_or_none()
    if not ton_bal:
        raise HTTPException(status_code=400, detail="Insufficient TON balance")
    if ton_bal.available < total_deduct:
        raise HTTPException(status_code=400, detail="Insufficient TON balance")

    ton_bal.available -= total_deduct
    ton_bal.total_withdrawn += total_deduct

    address = conn.address
    tx = TonWithdrawal(
        event_id=f"ton_wd_{uuid.uuid4().hex}",
        telegram_id=telegram_id,
        amount=net_amount,
        memo=address[:256],
        status="pending",
    )
    db.add(tx)
    db.commit()

    return {
        "ok": True,
        "amount": float(net_amount),
        "fee": float(TON_WITHDRAW_FEE),
        "address": address,
        "status": "pending",
    }

