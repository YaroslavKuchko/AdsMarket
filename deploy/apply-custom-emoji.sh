#!/bin/bash
# Применить изменения: custom_emoji_id в channels, Pillow, перезапуск
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend_py"

cd "$BACKEND_DIR"
source .venv/bin/activate

echo "1. Установка Pillow..."
pip install -q Pillow>=10.0.0 || echo "   (Pillow: пропуск, возможно уже установлен)"

echo "2. Миграция БД: добавить custom_emoji_id в channels..."
python -c "
from app.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text('ALTER TABLE channels ADD COLUMN custom_emoji_id VARCHAR(32) NULL'))
        conn.commit()
        print('   Колонка custom_emoji_id добавлена')
    except Exception as e:
        if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
            print('   Колонка custom_emoji_id уже есть')
        else:
            raise
"

echo "3. Перезапуск сервисов..."
if command -v systemctl &>/dev/null && systemctl is-active --quiet admarketplace-backend 2>/dev/null; then
    sudo systemctl restart admarketplace-backend admarketplace-bot
    echo "   systemd: backend и bot перезапущены"
else
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    pkill -f "app.telegram_bot" 2>/dev/null || true
    sleep 2
    nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload > /tmp/backend_py.log 2>&1 &
    nohup .venv/bin/python -m app.telegram_bot > /tmp/telegram_bot.log 2>&1 &
    echo "   Backend и bot запущены (nohup)"
fi

echo ""
echo "✅ Готово. Премиум-эмодзи из фото канала включены."
