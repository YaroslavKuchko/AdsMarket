# Деплой AdMarketplace на сервер adsmarket.app

## Сервер
- IP: 77.110.118.221
- Домен: adsmarket.app, www.adsmarket.app

## Порты (не конфликтуют с другими проектами)
| Сервис      | Порт  | Описание                        |
|-------------|-------|---------------------------------|
| Backend     | 3100  | uvicorn (внутренний)           |
| PostgreSQL  | 5432  | стандартный, или 5434 если занят |
| Nginx       | 80,443| общие для всех сайтов          |

**Важно:** Перед установкой запустите `./check-ports.sh` на сервере и при необходимости измените порт 3100 в `admarketplace-backend.service` и `.env`.

## Быстрый деплой

### 1. Загрузить проект на сервер
```bash
# Локально (из корня проекта)
./deploy/upload.sh

# Или вручную:
rsync -avz --exclude node_modules --exclude .venv --exclude .git \
  ./ root@77.110.118.221:/opt/admarketplace/
```
**Совет:** для парольless-доступа добавьте SSH-ключ: `ssh-copy-id root@77.110.118.221`

### 2. Подключиться к серверу
```bash
ssh root@77.110.118.221
```

### 3. Проверить порты
```bash
cd /opt/admarketplace/deploy
chmod +x check-ports.sh
./check-ports.sh
```

### 4. Настроить .env
```bash
cp /opt/admarketplace/deploy/env.production.example /opt/admarketplace/backend_py/.env
nano /opt/admarketplace/backend_py/.env
# Заполнить: DATABASE_URL, TG_BOT_TOKEN, JWT_SECRET, USDT_*, WEBAPP_URL=https://adsmarket.app
```

### 5. Запустить установку
```bash
cd /opt/admarketplace/deploy
chmod +x install.sh
sudo bash install.sh
```

### 6. PostgreSQL: создать БД и пользователя (если install не сработал)
```bash
sudo -u postgres psql -c "CREATE DATABASE admarketplace;"
sudo -u postgres psql -c "CREATE USER admarket WITH PASSWORD 'ваш_пароль';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE admarketplace TO admarket;"
```

### 7. SSL сертификат
```bash
sudo certbot --nginx -d adsmarket.app -d www.adsmarket.app
```

После certbot заменить nginx конфиг на полный с SSL:
```bash
sudo cp /opt/admarketplace/deploy/nginx-adsmarket.conf /etc/nginx/sites-available/adsmarket
sudo nginx -t && sudo systemctl reload nginx
```

### 8. Запустить сервисы
```bash
sudo systemctl enable admarketplace-backend admarketplace-bot
sudo systemctl start admarketplace-backend admarketplace-bot
sudo systemctl status admarketplace-backend admarketplace-bot
```

### 9. Обновить @BotFather
В BotFather → Bot Settings → Menu Button → Configure menu button → URL: `https://adsmarket.app`

## Смена порта backend

Если 3100 занят:
1. Открыть `/etc/systemd/system/admarketplace-backend.service`
2. Заменить `3100` на свободный порт (например 3101)
3. В nginx config заменить `3100` на тот же порт
4. В `.env`: `APP_PORT=3101`, `API_BASE_URL=http://127.0.0.1:3101`
5. `sudo systemctl daemon-reload && sudo systemctl restart admarketplace-backend nginx`

## Логи
```bash
journalctl -u admarketplace-backend -f
journalctl -u admarketplace-bot -f
```

## Обновление: премиум-эмодзи из фото канала

После `./deploy/upload.sh` выполнить на сервере:

```bash
ssh root@77.110.118.221
cd /opt/admarketplace
chmod +x deploy/apply-custom-emoji.sh
sudo ./deploy/apply-custom-emoji.sh
```

Скрипт: Pillow, миграция (custom_emoji_id), перезапуск backend и bot.
