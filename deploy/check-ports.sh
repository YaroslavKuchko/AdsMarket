#!/bin/bash
# Run on server: ./check-ports.sh
# Shows which ports are in use so we can pick free ones for AdMarketplace

echo "=== Порты в использовании (LISTEN) ==="
ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null

echo ""
echo "=== Рекомендуемые порты для AdMarketplace (если свободны) ==="
echo "Backend:  3100  (uvicorn)"
echo "PostgreSQL: 5434 (если 5432, 5433 заняты)"
echo "Nginx: 80, 443 (общие для всех сайтов)"
echo ""
echo "Проверка конкретных портов:"
for p in 80 443 3000 3001 3100 5173 5432 5433 5434 8000 8080; do
  if ss -tlnp 2>/dev/null | grep -q ":${p} " || netstat -tlnp 2>/dev/null | grep -q ":${p} "; then
    echo "  $p: ЗАНЯТ"
  else
    echo "  $p: свободен"
  fi
done
