#!/bin/bash

# Script per aggiornare il frontend del Trading Agent
# Uso: ./update-frontend.sh

set -e  # Exit on error

echo "🔨 Building frontend..."
cd "$(dirname "$0")/frontend"
npm run build

echo "📦 Copying files to backend..."
cd ..
mkdir -p backend/static
cp -r static/* backend/static/

echo "✅ Frontend built successfully!"
echo ""
echo "📋 Next steps:"
echo "1. If running locally:"
echo "   - Refresh browser with Ctrl+Shift+R"
echo ""
echo "2. If running with Docker:"
echo "   - Run: docker-compose restart app"
echo "   - Or: docker-compose -f docker-compose.prod.yml restart app"
echo ""
echo "3. If on VPS:"
echo "   - The service will pick up changes automatically"
echo "   - Or restart with: docker-compose -f docker-compose.prod.yml restart app"
echo ""
echo "🌐 Access dashboard at: http://localhost:5611"
