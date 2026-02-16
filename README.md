# AdsMarket

**Telegram-бот для тестирования:** [@ads_marketplacebot](https://t.me/ads_marketplacebot)

Маркетплейс рекламы в Telegram-каналах. Владельцы каналов публикуют форматы (посты, сторис), покупатели оплачивают Stars, TON или USDT и размещают рекламу.

## Стек

- **Frontend:** React 19, Vite, MUI, TonConnect (TON кошельки), i18n
- **Backend:** FastAPI, PostgreSQL, SQLAlchemy, Uvicorn
- **Bot:** aiogram
- **Платежи:** Telegram Stars, TON, USDT (Jetton на TON)
- **AI:** OpenAI/OpenRouter для аналитики каналов

## Структура проекта

```
├── src/                 # Frontend (React + Vite)
├── backend_py/          # Backend (FastAPI)
│   ├── app/
│   │   ├── api/         # API routes
│   │   ├── db/          # Модели, сессии
│   │   ├── services/    # Бизнес-логика (депозиты, выводы, ордера)
│   │   └── telegram_bot/
│   └── scripts/         # Утилиты
├── deploy/              # Деплой, nginx, systemd
└── dist/                # Собранный frontend (генерируется)
```

## Быстрый старт

### Backend

```bash
cd backend_py
python -m venv .venv
source .venv/bin/activate  # или .venv\Scripts\activate на Windows
pip install -r requirements.txt
cp env.example .env
# Заполнить .env: DATABASE_URL, TG_BOT_TOKEN, JWT_SECRET и т.д.
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 3100
```

### Frontend

```bash
npm install
npm run dev
```

### Переменные окружения (backend_py/.env)

См. `backend_py/env.example`. Важные переменные:

- `DATABASE_URL` — PostgreSQL
- `TG_BOT_TOKEN` — токен бота
- `JWT_SECRET` — секрет JWT
- `TONAPI_KEY` — для сканирования депозитов
- `USDT_DEPOSIT_WALLET`, `TON_DEPOSIT_WALLET` — адреса для пополнения
- `USDT_WITHDRAW_MNEMONIC` или `USDT_WITHDRAW_PRIVATE_KEY` — для выводов

**Важно:** Никогда не коммитьте `.env` и реальные мнемоники/ключи.

## Функционал

- **Маркет:** каталог каналов с фильтрами, карточки каналов, AI-аналитика
- **Мои каналы:** добавление бота, управление форматами, цены (Stars/USDT)
- **Профиль:** балансы (Stars, TON, USDT), пополнение, вывод, TON Connect
- **Заказы:** создание, оплата с баланса, верификация постов (24h/48h)
- **Реферальная программа**

## Деплой

Подробнее см. `deploy/README.md`.

---

## Будущие этапы развития

### Этап 1 — Стабилизация и UX
- [ ] Улучшенная модерация каналов (ручная проверка перед публикацией)
- [ ] Расширенные уведомления (Email / Telegram)
- [ ] Мобильная оптимизация, PWA
- [ ] A/B тесты для конверсии

### Этап 2 — Монетизация и масштаб
- [ ] Комиссия платформы с каждой сделки (например 5–10%)
- [ ] Рекламные пакеты и скидки
- [ ] API для партнёров (агрегаторы)
- [ ] Мультиязычность (EN, UA и др.)

### Этап 3 — Интеграции
- [ ] Интеграция с другими соцсетями (как альтернативные площадки)
- [ ] Автоматическая выгрузка отчётов
- [ ] Webhook для CRM/аналитики
- [ ] Партнёрские программы с биржами/агентствами

### Этап 4 — Продвинутая аналитика
- [ ] Детальная аналитика по постам (охват, вовлечённость)
- [ ] Прогноз эффективности рекламы (ML)
- [ ] Рекомендации каналов по нише
- [ ] Дашборды для рекламодателей

### Этап 5 — Юридическая и инфраструктура
- [ ] KYC для крупных сделок
- [ ] Юридические договоры (оферта, соглашения)
- [ ] Масштабирование (Kubernetes, CDN)
- [ ] Аудит безопасности

---

## Лицензия

MIT
