#!/bin/bash
# Загрузка проекта на сервер
# Запуск локально: ./deploy/upload.sh
# Требует: rsync, ssh-доступ к серверу

SERVER="root@77.110.118.221"
DEST="/opt/admarketplace"

echo "Загрузка AdMarketplace на $SERVER..."
rsync -avz --progress \
  --exclude 'node_modules' \
  --exclude '.venv' \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude 'dist' \
  ./ "$SERVER:$DEST/"

echo ""
echo "Готово. Подключитесь: ssh $SERVER"
echo "Далее: cd $DEST/deploy && ./check-ports.sh && sudo bash install.sh"
