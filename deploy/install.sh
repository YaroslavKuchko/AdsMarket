#!/bin/bash
# AdMarketplace — установка на сервер
# Запуск: sudo bash install.sh
# 
# Требования: Ubuntu/Debian, root
# Перед запуском: 1) Загрузите проект в /opt/admarketplace
#                 2) Запустите ./check-ports.sh и убедитесь, что 3100 свободен
#                 3) Настройте .env в backend_py

set -e

PROJECT_DIR="/opt/admarketplace"
BACKEND_PORT=3100

echo "=== AdMarketplace Install ==="

# 1. Проверка портов
echo "[1/8] Проверка порта $BACKEND_PORT..."
if ss -tlnp 2>/dev/null | grep -q ":${BACKEND_PORT} " || netstat -tlnp 2>/dev/null | grep -q ":${BACKEND_PORT} "; then
  echo "ОШИБКА: Порт $BACKEND_PORT занят! Запустите ./check-ports.sh для списка портов."
  exit 1
fi

# 2. Создание пользователя
echo "[2/8] Создание пользователя admarket..."
if ! id admarket &>/dev/null; then
  useradd -r -m -d /opt/admarketplace -s /bin/bash admarket
fi

# 3. Зависимости системы
echo "[3/8] Установка зависимостей..."
apt-get update -qq
apt-get install -y -qq curl nginx certbot python3-certbot-nginx python3-venv python3-pip postgresql postgresql-contrib

# 4. Node.js (если нет)
if ! command -v node &>/dev/null; then
  echo "Установка Node.js..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

# 5. PostgreSQL — база admarketplace
echo "[4/8] Настройка PostgreSQL..."
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='admarketplace'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE admarketplace;"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='admarket'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER admarket WITH PASSWORD 'CHANGE_ME_ADMARKET_DB_PASSWORD';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE admarketplace TO admarket;" 2>/dev/null || true

echo "ВАЖНО: Установите пароль БД в backend_py/.env:"
echo "  DATABASE_URL=postgresql+psycopg://admarket:YOUR_PASSWORD@localhost:5432/admarketplace"
echo "  (Порт 5432 — стандартный PostgreSQL. Если другой проект использует 5432, создайте БД на 5434)"
echo ""

# 6. Python backend
echo "[5/8] Python backend..."
cd "$PROJECT_DIR/backend_py"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
# Миграции/создание таблиц при первом запуске

# 7. Frontend
echo "[6/8] Frontend build..."
cd "$PROJECT_DIR"
npm ci 2>/dev/null || npm install
npm run build

# 8. Права
chown -R admarket:admarket "$PROJECT_DIR"
chmod +x "$PROJECT_DIR/deploy/check-ports.sh"

# 9. Systemd
echo "[7/8] Systemd units..."
cp "$PROJECT_DIR/deploy/admarketplace-backend.service" /etc/systemd/system/
cp "$PROJECT_DIR/deploy/admarketplace-bot.service" /etc/systemd/system/
# Порты и пути
sed -i "s|3100|$BACKEND_PORT|g" /etc/systemd/system/admarketplace-backend.service
sed -i "s|127.0.0.1:3100|127.0.0.1:$BACKEND_PORT|g" /etc/systemd/system/admarketplace-backend.service 2>/dev/null || true
systemctl daemon-reload

# 10. Nginx
echo "[8/8] Nginx..."
mkdir -p /var/www/certbot
sed "s|3100|$BACKEND_PORT|g" "$PROJECT_DIR/deploy/nginx-adsmarket-http-only.conf" > /etc/nginx/sites-available/adsmarket
ln -sf /etc/nginx/sites-available/adsmarket /etc/nginx/sites-enabled/ 2>/dev/null || true
nginx -t 2>/dev/null && systemctl reload nginx || echo "Nginx: проверьте конфиг вручную"

echo ""
echo "=== Установка завершена ==="
echo ""
echo "Дальнейшие шаги:"
echo "1. Отредактируйте $PROJECT_DIR/backend_py/.env (DATABASE_URL, TG_BOT_TOKEN, и др.)"
echo "2. API_BASE_URL=http://127.0.0.1:$BACKEND_PORT"
echo "3. WEBAPP_URL=https://adsmarket.app"
echo "4. Получите SSL: sudo certbot --nginx -d adsmarket.app -d www.adsmarket.app"
echo "5. После certbot замените nginx config на полный (с SSL)"
echo "6. Запуск: sudo systemctl enable admarketplace-backend admarketplace-bot"
echo "          sudo systemctl start admarketplace-backend admarketplace-bot"
echo ""
