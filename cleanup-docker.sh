#!/bin/bash

# Script per pulire risorse Docker e liberare spazio

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check disk space before
log_info "Spazio disco PRIMA della pulizia:"
df -h / | tail -1

# Stop all containers
log_info "Fermando tutti i container..."
docker compose -f docker-compose.prod.yml down 2>/dev/null || true
docker compose down 2>/dev/null || true

# Remove stopped containers
log_info "Rimuovendo container fermati..."
docker container prune -f

# Remove unused images
log_info "Rimuovendo immagini non utilizzate..."
docker image prune -a -f

# Remove unused volumes (ATTENZIONE: questo rimuove volumi non usati)
log_info "Rimuovendo volumi non utilizzati..."
docker volume prune -f

# Remove build cache
log_info "Pulendo build cache..."
docker builder prune -a -f

# Remove unused networks
log_info "Rimuovendo reti non utilizzate..."
docker network prune -f

# Clean system (tutto insieme)
log_info "Pulizia completa sistema Docker..."
docker system prune -a -f --volumes

# Check disk space after
log_info "Spazio disco DOPO la pulizia:"
df -h / | tail -1

# Check Docker disk usage
log_info "Uso disco Docker:"
docker system df

log_success "✅ Pulizia completata!"

