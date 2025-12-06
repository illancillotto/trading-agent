#!/bin/bash

# Script per risolvere i problemi in produzione sulla VPS
# Esegui questo script sulla VPS per applicare tutti i fix

set -e

echo "========================================"
echo "🔧 FIX TRADING AGENT PRODUCTION"
echo "========================================"
echo ""

# 1. Pull delle ultime modifiche
echo "📥 Step 1: Pulling latest code from Git..."
git pull origin main
echo "✅ Code updated"
echo ""

# 2. Stop dei container
echo "🛑 Step 2: Stopping containers..."
docker compose -f docker-compose.prod.yml down
echo "✅ Containers stopped"
echo ""

# 3. Rebuild con --no-cache per forzare l'uso del nuovo Dockerfile
echo "🔨 Step 3: Rebuilding app container (this may take a few minutes)..."
docker compose -f docker-compose.prod.yml build --no-cache app
echo "✅ Container rebuilt"
echo ""

# 4. Restart
echo "🚀 Step 4: Starting containers..."
docker compose -f docker-compose.prod.yml up -d
echo "✅ Containers started"
echo ""

# 5. Wait for health check
echo "⏳ Step 5: Waiting for health check (30s)..."
sleep 30
echo ""

# 6. Verifica workers
echo "🔍 Step 6: Verifying uvicorn workers..."
echo "Expected: 1 worker process"
echo "Actual:"
docker compose -f docker-compose.prod.yml exec app ps aux | grep -E "uvicorn|python" | grep -v grep || echo "No processes found"
echo ""

# 7. Check logs per errori
echo "📋 Step 7: Checking for errors in logs..."
echo "Checking for 429 errors (rate limiting):"
docker compose -f docker-compose.prod.yml logs --tail=100 app | grep -i "429" || echo "✅ No 429 errors found"
echo ""

echo "Checking for NaN errors (forecast):"
docker compose -f docker-compose.prod.yml logs --tail=100 app | grep -i "nan" || echo "✅ No NaN errors found"
echo ""

echo "Checking for deadlock errors (database):"
docker compose -f docker-compose.prod.yml logs --tail=100 app | grep -i "deadlock" || echo "✅ No deadlock errors found"
echo ""

# 8. Final summary
echo "========================================"
echo "✅ FIX COMPLETED"
echo "========================================"
echo ""
echo "Prossimi passi:"
echo "1. Monitora i log per 5-10 minuti con:"
echo "   docker compose -f docker-compose.prod.yml logs -f app"
echo ""
echo "2. Verifica che non ci siano più:"
echo "   - ❌ HTTP 429 errors (rate limiting)"
echo "   - ❌ NaN forecast errors"
echo "   - ❌ Database deadlocks"
echo ""
echo "3. Se continui a vedere errori 429, esegui:"
echo "   docker compose -f docker-compose.prod.yml exec app ps aux"
echo "   e verifica che ci sia UN SOLO processo uvicorn"
echo ""
