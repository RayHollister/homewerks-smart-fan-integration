#!/usr/bin/env bash
# deploy.sh — Deploy integration to Home Assistant via SSH and restart
#
# Usage:
#   ./deploy.sh              # Deploy + restart HA
#   ./deploy.sh --no-restart # Deploy only
#   ./deploy.sh --logs       # Deploy, restart, and tail logs
#
# Requires: SSH config alias "ha" pointing to Home Assistant
#   (see ~/.ssh/config)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$REPO_DIR/custom_components/homewerks_smart_fan"
DEST="/config/custom_components/homewerks_smart_fan"
SSH_HOST="ha"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check source exists
if [[ ! -d "$SRC" ]]; then
    echo -e "${RED}Error:${NC} Source not found: $SRC"
    exit 1
fi

# Test SSH connection
if ! ssh -o ConnectTimeout=3 "$SSH_HOST" "true" 2>/dev/null; then
    echo -e "${RED}Error:${NC} Cannot connect to HA via SSH."
    echo "  Check that the Advanced SSH add-on is running"
    echo "  and ~/.ssh/config has a 'ha' host entry."
    exit 1
fi

# Deploy files via rsync over SSH
echo -e "${GREEN}Deploying${NC} integration files..."
rsync -az --delete --inplace --no-times \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='.gitignore' \
    --exclude='.DS_Store' \
    --rsync-path="sudo rsync" \
    -e ssh \
    "$SRC/" "$SSH_HOST:$DEST/"

echo -e "${GREEN}✓${NC} Files synced to HA"

# Handle flags
FLAG="${1:-}"

if [[ "$FLAG" == "--no-restart" ]]; then
    echo -e "${YELLOW}Skipping restart${NC} (--no-restart)"
    exit 0
fi

# Restart HA
echo -e "${GREEN}Restarting${NC} Home Assistant..."
ssh "$SSH_HOST" 'SUPERVISOR_TOKEN=$(cat /run/s6/container_environment/SUPERVISOR_TOKEN) ha core restart' 2>&1

echo -e "${GREEN}✓${NC} Restart triggered. HA will be back in ~60 seconds."

# Tail logs if requested
if [[ "$FLAG" == "--logs" ]]; then
    echo ""
    echo -e "${YELLOW}Waiting 30s for HA to start, then tailing logs...${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop.${NC}"
    sleep 30
    ssh "$SSH_HOST" 'SUPERVISOR_TOKEN=$(cat /run/s6/container_environment/SUPERVISOR_TOKEN) ha core logs -f' 2>&1 | grep --line-buffered -i "homewerks"
fi
