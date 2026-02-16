#!/bin/bash

# AdMarketplace - Start All Services
# Usage: ./start-all.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "🚀 Starting AdMarketplace services..."

# Kill existing processes (avoid Telegram Conflict: only one bot instance)
echo "🔄 Stopping existing services..."
pkill -9 -f "uvicorn app.main:app" 2>/dev/null || true
pkill -9 -f "app.telegram_bot" 2>/dev/null || true
pkill -9 -f "telegram_bot" 2>/dev/null || true
pkill -9 -f "vite" 2>/dev/null || true
pkill -9 -f "cloudflared tunnel" 2>/dev/null || true

# Free ports
lsof -ti:3001 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
sleep 4

# 1. Start Python Backend (port 3001)
echo "📦 Starting Python Backend..."
cd "$PROJECT_DIR/backend_py"
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload > /tmp/backend_py.log 2>&1 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# 2. Start Telegram Bot (handles /start, post flow, channel add/remove, etc.)
echo "🤖 Starting Telegram Bot..."
cd "$PROJECT_DIR/backend_py"
source .venv/bin/activate
nohup python -m app.telegram_bot > /tmp/telegram_bot.log 2>&1 &
BOT_PID=$!
echo "   Bot PID: $BOT_PID"

# 3. Start Frontend (port 5173)
echo "🎨 Starting Frontend..."
cd "$PROJECT_DIR"
nohup npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   Frontend PID: $FRONTEND_PID"

# 4. Start Cloudflare Tunnel
echo "🌐 Starting Cloudflare Tunnel..."
nohup cloudflared tunnel run teamwb > /tmp/tunnel.log 2>&1 &
TUNNEL_PID=$!
echo "   Tunnel PID: $TUNNEL_PID"

# Wait for services to start
sleep 5

echo ""
echo "✅ All services started!"
echo ""
echo "📊 Service URLs:"
echo "   Frontend:  http://localhost:5173"
echo "   Backend:   http://localhost:3001"
echo "   Public:    https://teamwb.top"
echo ""
echo "📝 Log files:"
echo "   Backend:   /tmp/backend_py.log"
echo "   Bot:       /tmp/telegram_bot.log"
echo "   Frontend:  /tmp/frontend.log"
echo "   Tunnel:    /tmp/tunnel.log"
echo ""
echo "🛑 To stop all: pkill -f 'uvicorn|app.telegram_bot|vite|cloudflared'"

