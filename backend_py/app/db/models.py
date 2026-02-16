from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Preferred language selected in Mini App settings (ru/en). Used for bot messages.
    preferred_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional phone verification (from WebApp.requestContact via frontend -> backend)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Referral system: telegram_id of the user who referred this user
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    # Referral code (unique identifier for sharing)
    referral_code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)

    # Whether this user's referrer has received the signup bonus for them
    referral_bonus_paid: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TelegramAuthEvent(Base):
    __tablename__ = "telegram_auth_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    auth_date: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_param: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReferralSettings(Base):
    """
    Admin-configurable referral settings.
    Single row table - always use id=1.
    """
    __tablename__ = "referral_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # Payout percentages (0-100) for each currency - % from platform commission
    stars_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("10.00"))
    ton_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("10.00"))
    usdt_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("10.00"))

    # Bonus Stars for qualifying purchase (one-time)
    bonus_stars: Mapped[int] = mapped_column(Integer, default=50)

    # Minimum purchase thresholds for bonus eligibility (configurable from admin)
    min_purchase_stars: Mapped[int] = mapped_column(Integer, default=1000)
    min_purchase_usdt: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("25.00"))
    # min_purchase_ton is calculated: min_purchase_usdt / ton_usd_price

    # TON price in USD (updated daily from CoinGecko)
    ton_usd_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("5.00"))
    ton_price_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Minimum payout thresholds (for withdrawal)
    stars_min_payout: Mapped[int] = mapped_column(Integer, default=100)
    ton_min_payout: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0.5"))
    usdt_min_payout: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("5.00"))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @property
    def min_purchase_ton(self) -> Decimal:
        """Calculate minimum TON purchase based on USDT threshold and TON price."""
        if self.ton_usd_price <= 0:
            return Decimal("5.0")
        result = self.min_purchase_usdt / self.ton_usd_price
        # Round to 1 decimal place
        return Decimal(str(round(float(result), 1)))


class ReferralPayout(Base):
    """
    Tracks referral payouts to users.
    """
    __tablename__ = "referral_payouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Who receives the payout (referrer)
    referrer_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # Who made the purchase (referred user)
    referred_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # Currency: 'stars', 'ton', 'usdt'
    currency: Mapped[str] = mapped_column(String(16))

    # Original transaction amount
    transaction_amount: Mapped[Decimal] = mapped_column(Numeric(18, 8))

    # Payout amount (transaction_amount * percent / 100)
    payout_amount: Mapped[Decimal] = mapped_column(Numeric(18, 8))

    # Percent applied at the time of payout
    percent_applied: Mapped[Decimal] = mapped_column(Numeric(5, 2))

    # Is this a bonus payout (50 stars for qualifying purchase)?
    is_bonus: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status: 'pending', 'paid', 'cancelled'
    status: Mapped[str] = mapped_column(String(16), default="pending")

    # Reference to original transaction (order_id or similar)
    transaction_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReferralBalance(Base):
    """
    Accumulated referral earnings per user per currency.
    """
    __tablename__ = "referral_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    currency: Mapped[str] = mapped_column(String(16))  # 'stars', 'ton', 'usdt'

    # Total earned from referrals
    total_earned: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))

    # Total withdrawn
    total_withdrawn: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))

    # Available balance (total_earned - total_withdrawn)
    # Computed but stored for quick access
    available: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TonWallet(Base):
    """
    Stores connected TON wallets for users.
    One user can have multiple wallets, but only one is primary.
    """
    __tablename__ = "ton_wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # TON wallet address (raw format)
    address: Mapped[str] = mapped_column(String(128), index=True)

    # Friendly address (user-friendly format)
    friendly_address: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Is this the primary wallet for the user?
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)

    # Is the wallet active (not disconnected)?
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Wallet name (from TON Connect, e.g., "Tonkeeper", "MyTonWallet")
    wallet_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Connection timestamp
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Disconnection timestamp (if disconnected)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TonTransaction(Base):
    """
    Tracks TON transactions for payment verification and history.
    Used to prevent replay attacks and for auditing.
    """
    __tablename__ = "ton_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Transaction hash (unique identifier from blockchain)
    tx_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)

    # Logical time (lt) from blockchain
    lt: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # User who made the payment
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # Wallet address that sent the transaction
    from_address: Mapped[str] = mapped_column(String(128))

    # Our wallet address that received the payment
    to_address: Mapped[str] = mapped_column(String(128))

    # Amount in nanoTON
    amount_nano: Mapped[int] = mapped_column(BigInteger)

    # Amount in TON (for convenience)
    amount_ton: Mapped[Decimal] = mapped_column(Numeric(18, 9))

    # Comment/memo from the transaction
    comment: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Order ID or reference (from comment)
    order_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Transaction type: 'top_up', 'payment', 'withdrawal'
    tx_type: Mapped[str] = mapped_column(String(32), default="top_up")

    # Status: 'pending', 'confirmed', 'failed', 'processed'
    status: Mapped[str] = mapped_column(String(16), default="pending")

    # Error message if failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # When the transaction was created on blockchain
    blockchain_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # When we first saw this transaction
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # When we processed this transaction
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TonWithdrawal(Base):
    """
    Pending TON withdrawals. User requests withdrawal to their connected wallet.
    """
    __tablename__ = "ton_withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 9))  # TON amount
    memo: Mapped[str | None] = mapped_column(String(256), nullable=True)  # destination address
    tx_type: Mapped[str] = mapped_column(String(16), default="withdrawal")
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending, completed, failed
    tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StarsTransaction(Base):
    """
    Stars payments (top-ups). Required for refunds via refundStarPayment.
    """
    __tablename__ = "stars_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[int] = mapped_column(Integer)  # Stars amount
    invoice_payload: Mapped[str] = mapped_column(String(256))

    # Required for refund via Bot API refundStarPayment (Telegram charge IDs can be 120+ chars)
    telegram_payment_charge_id: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    provider_payment_charge_id: Mapped[str] = mapped_column(String(256), default="")

    # Status: 'completed', 'refunded'
    status: Mapped[str] = mapped_column(String(16), default="completed")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UsdtTransaction(Base):
    """
    USDT deposits (and withdrawals) on TON. Tracks Jetton transfers.
    Deposits: memo = telegram_id. Withdrawals: memo = destination address, destination_memo = optional tag.
    """
    __tablename__ = "usdt_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Unique identifier (event_id from API or tx_hash:lt)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)

    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))  # USDT has 6 decimals
    memo: Mapped[str | None] = mapped_column(String(256), nullable=True)  # deposit: telegram_id; withdrawal: address
    destination_memo: Mapped[str | None] = mapped_column(String(128), nullable=True)  # withdrawal: optional Tag/Memo

    # deposit | withdrawal
    tx_type: Mapped[str] = mapped_column(String(16), default="deposit")
    status: Mapped[str] = mapped_column(String(16), default="completed")  # pending, completed, failed

    # Blockchain tx hash for Tonscan link (withdrawals)
    tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserBalance(Base):
    """
    User balances in different currencies.
    """
    __tablename__ = "user_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    currency: Mapped[str] = mapped_column(String(16))  # 'stars', 'ton', 'usdt'

    # Available balance
    available: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))

    # Frozen balance (in pending orders, withdrawals, etc.)
    frozen: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))

    # Total deposited
    total_deposited: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))

    # Total withdrawn
    total_withdrawn: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Channel(Base):
    """
    Telegram channels/groups added by users for selling ads.
    """
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Telegram chat ID (negative for groups/channels)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)

    # Owner - user who added the channel
    owner_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # Chat type: 'channel', 'group', 'supergroup'
    chat_type: Mapped[str] = mapped_column(String(32))

    # Channel info
    title: Mapped[str] = mapped_column(String(256))
    username: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stats
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)

    # Custom emoji ID created from channel photo (for premium emoji in bot messages)
    custom_emoji_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    
    # Invite link for private channels
    invite_link: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Status: 'pending', 'active', 'paused', 'removed'
    # pending - bot was just added, waiting for verification
    # active - channel is live on marketplace
    # paused - owner temporarily disabled the channel
    # removed - bot was removed or channel deleted
    status: Mapped[str] = mapped_column(String(16), default="pending")

    # Is the channel visible on marketplace?
    is_visible: Mapped[bool] = mapped_column(Boolean, default=False)

    # Category: 'news', 'tech', 'lifestyle', 'crypto', 'entertainment', 'education', 'other'
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Language of the channel content
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # When the bot was added to this channel
    bot_added_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # When the bot was removed from this channel
    bot_removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ChannelStats(Base):
    """
    Current statistics snapshot for a channel.
    Updated periodically by the bot.
    """
    __tablename__ = "channel_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    channel_id: Mapped[int] = mapped_column(Integer, index=True, unique=True)

    # Subscribers
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
    subscriber_growth_24h: Mapped[int] = mapped_column(Integer, default=0)
    subscriber_growth_7d: Mapped[int] = mapped_column(Integer, default=0)
    subscriber_growth_30d: Mapped[int] = mapped_column(Integer, default=0)

    # Views / Reach
    avg_post_views: Mapped[int] = mapped_column(Integer, default=0)
    avg_reach_24h: Mapped[int] = mapped_column(Integer, default=0)
    total_views_24h: Mapped[int] = mapped_column(Integer, default=0)
    total_views_7d: Mapped[int] = mapped_column(Integer, default=0)

    # Engagement
    engagement_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    avg_reactions: Mapped[int] = mapped_column(Integer, default=0)
    avg_comments: Mapped[int] = mapped_column(Integer, default=0)
    avg_shares: Mapped[int] = mapped_column(Integer, default=0)

    # Posting frequency
    posts_24h: Mapped[int] = mapped_column(Integer, default=0)
    posts_7d: Mapped[int] = mapped_column(Integer, default=0)
    posts_30d: Mapped[int] = mapped_column(Integer, default=0)
    posts_90d: Mapped[int] = mapped_column(Integer, default=0)
    avg_posts_per_day: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))

    # Totals (for display)
    total_reactions: Mapped[int] = mapped_column(Integer, default=0)
    total_comments: Mapped[int] = mapped_column(Integer, default=0)
    total_shares: Mapped[int] = mapped_column(Integer, default=0)

    # Best post
    best_post_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_post_views: Mapped[int] = mapped_column(Integer, default=0)
    best_post_text: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Quality metrics
    # Dynamics: 'growing', 'stable', 'declining'
    dynamics: Mapped[str] = mapped_column(String(16), default="stable")
    dynamics_score: Mapped[int] = mapped_column(Integer, default=0)  # -100 to +100

    # Last post timestamp
    last_post_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Collection status
    is_collecting: Mapped[bool] = mapped_column(Boolean, default=False)
    collection_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collection_error: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # AI Insights (stored as JSON, regenerated weekly)
    ai_insights_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_insights_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_insights_error: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # When stats were last updated
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ChannelStatsHistory(Base):
    """
    Historical statistics for channels (for graphs).
    One row per channel per day.
    """
    __tablename__ = "channel_stats_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    channel_id: Mapped[int] = mapped_column(Integer, index=True)

    # Date of this snapshot (YYYY-MM-DD)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # Stats for this day
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
    total_views: Mapped[int] = mapped_column(Integer, default=0)
    total_posts: Mapped[int] = mapped_column(Integer, default=0)
    avg_post_views: Mapped[int] = mapped_column(Integer, default=0)
    engagement_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    reactions: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChannelPost(Base):
    """
    Individual posts in a channel for tracking views and engagement.
    """
    __tablename__ = "channel_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    channel_id: Mapped[int] = mapped_column(Integer, index=True)

    # Telegram message ID
    message_id: Mapped[int] = mapped_column(Integer)

    # Post content preview (first 200 chars)
    text_preview: Mapped[str | None] = mapped_column(String(256), nullable=True)
    
    # Full post text
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Has media (photo/video)
    has_media: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Media URL (photo thumbnail)
    media_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    
    # Album support
    is_album: Mapped[bool] = mapped_column(Boolean, default=False)
    media_count: Mapped[int] = mapped_column(Integer, default=1)

    # Stats
    views: Mapped[int] = mapped_column(Integer, default=0)
    reactions: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)

    # When the post was published
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Last time we updated the stats for this post
    stats_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChannelAdFormat(Base):
    """
    Ad formats and pricing for a channel.
    Each channel can have multiple ad formats (post, story, pin, etc.)
    """
    __tablename__ = "channel_ad_formats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    channel_id: Mapped[int] = mapped_column(Integer, index=True)

    # Format type: 'post', 'story', 'pin', 'repost'
    format_type: Mapped[str] = mapped_column(String(32))

    # Is this format enabled?
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Pricing in Stars (primary currency)
    price_stars: Mapped[int] = mapped_column(Integer, default=0)

    # Alternative pricing
    price_ton: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    price_usdt: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)

    # Duration settings
    duration_hours: Mapped[int] = mapped_column(Integer, default=24)  # How long the ad stays
    
    # Estimated time to publish after approval
    eta_hours: Mapped[int] = mapped_column(Integer, default=24)

    # Format-specific settings (JSON)
    # e.g., max_text_length, allow_media, allow_links, etc.
    settings: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Order(Base):
    """
    Ad order: buyer purchases an ad slot; after "payment" (skipped) they write the post in the bot.
    """
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    channel_id: Mapped[int] = mapped_column(Integer, index=True)
    format_id: Mapped[int] = mapped_column(Integer, index=True)

    buyer_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    seller_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # writing_post -> pending_seller -> done | cancelled
    status: Mapped[str] = mapped_column(String(32), default="writing_post")

    # Payment: currency and amount (frozen until done/cancelled)
    payment_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)  # 'stars','ton','usdt'
    payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)

    # Post content (filled by bot)
    post_text_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_button_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    post_button_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    post_media_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Secret token for /start post_{token} (alphanumeric, not order_id)
    post_token: Mapped[str | None] = mapped_column(String(16), nullable=True, unique=True, index=True)

    # Seller flow: comment when sending back to buyer for revision
    seller_revision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # When seller approved (status -> done)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Link to published post in channel (t.me/channel_username/msg_id)
    published_post_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Telegram message_id in channel (for verification)
    published_channel_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # When post was verified (not deleted, not edited) after duration_hours
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
