## Backend (Python) — Telegram Mini App + PostgreSQL

This service validates Telegram Mini App `initData` and stores user data in PostgreSQL using **SQLAlchemy**.

### Why frontend must send initData to backend
Telegram provides `window.Telegram.WebApp.initData` **inside the Mini App**.  
Your backend must verify it (HMAC) using the bot token before trusting the user identity.

### Setup
1) Start PostgreSQL:

```bash
cd backend_py
docker compose up -d
```

2) Create `backend_py/.env` from `backend_py/env.example`.

3) Install deps and run API:

```bash
cd backend_py
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload
```

4) (Optional) Run the **Ad Post Telegram Bot** in a separate terminal (same token as Mini App; handles `?start=post_{order_id}` for writing ad posts):

```bash
cd backend_py
source .venv/bin/activate
python -m app.telegram_bot
```

Use the same `.env` (e.g. `TG_BOT_TOKEN`, `DATABASE_URL`). The bot must run alongside the API so that orders created in the app can be continued in the bot.

### API
- `GET /health`
- `POST /api/telegram/validate`

Body:

```json
{ "initData": "<window.Telegram.WebApp.initData>" }
```

Response (skeleton):
```json
{ "ok": true, "user": { ... }, "startParam": "....", "authDate": 123 }
```

### DB tables (auto-created in dev)
- `users` (upsert by `telegram_id`)
- `telegram_auth_events` (stores `start_param` and `auth_date` for attribution)


