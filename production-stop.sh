#!/bin/bash

# Stop the production Trading Agent stack (deployments started by production-deploy.sh)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

COMPOSE_FILE="docker-compose.prod.yml"
PROJECT_NAME="trading-agent-prod"
PRUNE_VOLUMES=false

usage() {
    cat <<EOF
Usage: $0 [--prune-volumes]

Stops the production stack launched via ${COMPOSE_FILE}.

Options:
  --prune-volumes   Remove named volumes as well (DB data will be deleted)
  -h, --help        Show this help
EOF
}

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --prune-volumes) PRUNE_VOLUMES=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) log_error "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# Checks
if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker is not installed."
    exit 1
fi

if ! command -v docker compose >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
    log_error "Docker Compose is not installed."
    exit 1
fi

if [ ! -f "${COMPOSE_FILE}" ]; then
    log_error "${COMPOSE_FILE} not found. Run this script from the repo root."
    exit 1
fi

# Stop stack
log_info "Stopping production stack (project: ${PROJECT_NAME})..."
DOWN_FLAGS="--remove-orphans"
if [ "${PRUNE_VOLUMES}" = true ]; then
    log_warning "Volumes will be removed (database data will be deleted)."
    DOWN_FLAGS="${DOWN_FLAGS} -v"
fi

docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" down ${DOWN_FLAGS}
log_success "Stack stopped."

# Optional network cleanup
log_info "Cleaning dangling networks (safe)..."
docker network prune -f >/dev/null 2>&1 || true

log_success "Done. To verify: docker compose -p ${PROJECT_NAME} -f ${COMPOSE_FILE} ps"

