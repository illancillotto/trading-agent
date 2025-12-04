#!/bin/bash

# Script per aggiornare il frontend del Trading Agent su VPS
# Uso: ./update-frontend-vps.sh

set -e  # Exit on error

# Determina la directory del progetto
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "📍 Project directory: $PROJECT_DIR"
echo ""
echo "🔨 Building frontend..."
cd "$PROJECT_DIR/frontend"
npm run build

echo ""
echo "📦 Copying files to backend..."
cd "$PROJECT_DIR"
mkdir -p backend/static
cp -r static/* backend/static/

echo ""
echo "🔄 Restarting Docker service..."
if [ -f "docker-compose.prod.yml" ]; then
    docker-compose -f docker-compose.prod.yml restart app
    echo "✅ Service restarted (docker-compose.prod.yml)"
elif [ -f "docker-compose.yml" ]; then
    docker-compose restart app
    echo "✅ Service restarted (docker-compose.yml)"
else
    echo "⚠️ No docker-compose file found. Please restart manually."
fi

echo ""
echo "✅ Frontend updated successfully!"
echo "🌐 Access dashboard at: http://$(curl -s ifconfig.me 2>/dev/null || echo 'your-ip'):5611"
echo ""
echo "💡 Tip: Clear browser cache with Ctrl+Shift+R"
