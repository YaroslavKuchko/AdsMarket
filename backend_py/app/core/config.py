from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_host: str = "0.0.0.0"
    app_port: int = 8081

    database_url: str

    tg_bot_token: str
    tg_auth_max_age_sec: int = 86400

    jwt_secret: str = "change_me"
    jwt_expires_sec: int = 60 * 60 * 24 * 30

    # Used by local bot process to push contact phone number into DB (dev/infrastructure).
    internal_secret: str = ""

    # API base URL for bot to call backend (channel-added, etc.). Default matches APP_PORT.
    api_base_url: str = "http://127.0.0.1:3001"

    # WebApp URL: HTTPS for opening (InlineKeyboard web_app=), or t.me/bot/app for sharing
    # Set WEBAPP_URL=https://adsmarket.app in production
    webapp_url: str = "t.me/ads_marketplacebot/admarket"

    # Order verification: channel ID where bot forwards posts to check they still exist (24h/48h).
    # Bot must be admin. Create a private channel, add bot, put its ID (e.g. -1001234567890) here.
    ad_verification_channel_id: int | None = None

    # Telegram userbot settings (for collecting channel stats)
    # Get these from https://my.telegram.org/apps
    pyrogram_api_id: int = 0
    pyrogram_api_hash: str = ""
    # Phone number for userbot authentication (with country code, e.g. +79991234567)
    pyrogram_phone: str = ""
    # Session directory
    pyrogram_session_dir: str = "sessions"
    # Enable stats collection
    stats_collection_enabled: bool = False
    # Collection interval in hours
    stats_collection_interval_hours: int = 4
    
    # OpenAI/OpenRouter API settings for AI insights
    # Use sk-or-... for OpenRouter, sk-... for OpenAI
    openai_api_key: str = ""
    # Approximate Stars per 1 USD for UI hints (Telegram rate varies by region; ~50 is typical)
    stars_per_usd: int = 50

    # USDT deposits (network TON, Jetton)
    # Our USDT Jetton wallet address - receives deposits. Get from Tonkeeper/wallet after first USDT receive.
    usdt_deposit_wallet: str = ""
    # USDT Jetton master (mainnet: EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs)
    usdt_jetton_master: str = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
    # TonAPI key for scanning deposits (get from https://tonapi.io)
    tonapi_key: str = ""

    # TON native (not Jetton): deposits and withdrawals
    # Our TON wallet that receives deposits. Users send from their connected wallet.
    ton_deposit_wallet: str = ""
    # For withdrawals we reuse usdt_withdraw_* (same TON wallet can send native TON)

    # USDT withdrawals: hot wallet for sending
    # Mnemonic phrase (24 words) ИЛИ приватный ключ (hex, 64 символа). Приоритет у private_key.
    usdt_withdraw_mnemonic: str = ""
    usdt_withdraw_private_key: str = ""  # hex: из MyTonWallet Settings → Security → View TON Private Key
    # Hot wallet address (optional, for verification).
    usdt_withdraw_wallet: str = ""

    # Parsing settings
    default_posts_limit: int = 100
    default_days_back: int = 30
    flood_wait_delay: float = 0.5


settings = Settings()


