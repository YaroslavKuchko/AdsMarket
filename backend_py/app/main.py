from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.config import router as config_router
from app.api.routes.channels import router as channels_router
from app.api.routes.internal import router as internal_router
from app.api.routes.media import router as media_router
from app.api.routes.orders import router as orders_router
from app.api.routes.telegram import router as telegram_router
from app.api.routes.ws import router as ws_router
from app.api.routes.user import router as user_router
from app.api.routes.referral import router as referral_router
from app.api.routes.wallet import router as wallet_router
from app.api.routes.stars import router as stars_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from sqlalchemy import text

# Media directory for uploaded files
MEDIA_DIR = Path(__file__).parent.parent / "media"


def create_app() -> FastAPI:
    app = FastAPI(title="AdMarketplace Backend (Python)")

    # For skeleton/dev: allow any origin. Tighten to your domain(s) in production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"ok": True}

    app.include_router(config_router)
    app.include_router(telegram_router)
    app.include_router(auth_router)
    app.include_router(user_router)
    app.include_router(internal_router)
    app.include_router(ws_router)
    app.include_router(referral_router)
    app.include_router(wallet_router)
    app.include_router(stars_router)
    app.include_router(orders_router)
    app.include_router(channels_router)
    app.include_router(media_router)
    
    # Mount static files for media (after API routes)
    # Note: /media is for static files, /api/media is for API endpoints
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    (MEDIA_DIR / "channels").mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

    @app.on_event("startup")
    async def _startup():
        # Skeleton bootstrap: create tables automatically (sync engine).
        # In production, use Alembic migrations.
        Base.metadata.create_all(bind=engine)
        # Lightweight dev migration for new nullable columns.
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(16)"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by BIGINT"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(32)"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_bonus_paid BOOLEAN DEFAULT FALSE"
                    )
                )
                # Referral settings new columns
                conn.execute(text("ALTER TABLE referral_settings ADD COLUMN IF NOT EXISTS bonus_stars INTEGER DEFAULT 50"))
                conn.execute(text("ALTER TABLE referral_settings ADD COLUMN IF NOT EXISTS min_purchase_stars INTEGER DEFAULT 1000"))
                conn.execute(text("ALTER TABLE referral_settings ADD COLUMN IF NOT EXISTS min_purchase_usdt NUMERIC(18,2) DEFAULT 25.00"))
                conn.execute(text("ALTER TABLE referral_settings ADD COLUMN IF NOT EXISTS ton_usd_price NUMERIC(18,8) DEFAULT 5.00"))
                conn.execute(text("ALTER TABLE referral_settings ADD COLUMN IF NOT EXISTS ton_price_updated_at TIMESTAMP WITH TIME ZONE"))
                # Referral payouts new column
                conn.execute(text("ALTER TABLE referral_payouts ADD COLUMN IF NOT EXISTS is_bonus BOOLEAN DEFAULT FALSE"))
                
                # Channel posts new columns
                conn.execute(text("ALTER TABLE channel_posts ADD COLUMN IF NOT EXISTS full_text TEXT"))
                conn.execute(text("ALTER TABLE channel_posts ADD COLUMN IF NOT EXISTS media_url VARCHAR(512)"))
                conn.execute(text("ALTER TABLE channel_posts ADD COLUMN IF NOT EXISTS is_album BOOLEAN DEFAULT FALSE"))
                conn.execute(text("ALTER TABLE channel_posts ADD COLUMN IF NOT EXISTS media_count INTEGER DEFAULT 1"))
                
                # AI insights columns
                conn.execute(text("ALTER TABLE channel_stats ADD COLUMN IF NOT EXISTS ai_insights_json TEXT"))
                conn.execute(text("ALTER TABLE channel_stats ADD COLUMN IF NOT EXISTS ai_insights_generated_at TIMESTAMP WITH TIME ZONE"))
                conn.execute(text("ALTER TABLE channel_stats ADD COLUMN IF NOT EXISTS ai_insights_error VARCHAR(256)"))
                # Order verification columns
                conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS published_channel_message_id INTEGER"))
                conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP WITH TIME ZONE"))
                # Stars transactions (for refund support)
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS usdt_transactions (
                        id SERIAL PRIMARY KEY,
                        event_id VARCHAR(128) UNIQUE NOT NULL,
                        telegram_id BIGINT NOT NULL,
                        amount NUMERIC(18,6) NOT NULL,
                        memo VARCHAR(256),
                        destination_memo VARCHAR(128),
                        tx_type VARCHAR(16) DEFAULT 'deposit',
                        status VARCHAR(16) DEFAULT 'completed',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """))
                conn.execute(text("ALTER TABLE usdt_transactions ALTER COLUMN memo TYPE VARCHAR(256)"))
                conn.execute(text("ALTER TABLE usdt_transactions ADD COLUMN IF NOT EXISTS destination_memo VARCHAR(128)"))
                conn.execute(text("ALTER TABLE usdt_transactions ADD COLUMN IF NOT EXISTS tx_hash VARCHAR(128)"))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS stars_transactions (
                        id SERIAL PRIMARY KEY,
                        telegram_id BIGINT NOT NULL,
                        amount INTEGER NOT NULL,
                        invoice_payload VARCHAR(256) NOT NULL,
                        telegram_payment_charge_id VARCHAR(256) UNIQUE NOT NULL,
                        provider_payment_charge_id VARCHAR(256) DEFAULT '',
                        status VARCHAR(16) DEFAULT 'completed',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """))
                # Migrate existing: Telegram charge IDs can exceed 128 chars
                conn.execute(text("ALTER TABLE stars_transactions ALTER COLUMN telegram_payment_charge_id TYPE VARCHAR(256)"))
                conn.execute(text("ALTER TABLE stars_transactions ALTER COLUMN provider_payment_charge_id TYPE VARCHAR(256)"))
                # Order payment tracking
                conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_currency VARCHAR(16)"))
                conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_amount NUMERIC(18,8)"))
                # TON withdrawals
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS ton_withdrawals (
                        id SERIAL PRIMARY KEY,
                        event_id VARCHAR(128) UNIQUE NOT NULL,
                        telegram_id BIGINT NOT NULL,
                        amount NUMERIC(18,9) NOT NULL,
                        memo VARCHAR(256),
                        tx_type VARCHAR(16) DEFAULT 'withdrawal',
                        status VARCHAR(16) DEFAULT 'pending',
                        tx_hash VARCHAR(128),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """))
        except Exception:
            # ignore in dev; schema migrations should be handled by Alembic in real prod
            pass

        # Start background scheduler for stats collection
        from app.services.scheduler import start_scheduler
        await start_scheduler()

    @app.on_event("shutdown")
    async def _shutdown():
        # Stop background scheduler
        from app.services.scheduler import stop_scheduler
        await stop_scheduler()

    return app


app = create_app()


