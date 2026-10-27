#!/usr/bin/env bash
# ==============================================================================
# Still Loading... — Sync Code to Arduino UNO Q
# ==============================================================================
# Copies shared/ and uno-q/ to the board over SSH/rsync.
#
# Usage:
#   ./scripts/sync_to_board.sh [HOST_OR_IP] [--restart]
#
# Examples:
#   ./scripts/sync_to_board.sh
#   ./scripts/sync_to_board.sh 192.168.1.5
#   ./scripts/sync_to_board.sh arduino@192.168.1.5 --restart
# ==============================================================================

set -euo pipefail

DEFAULT_HOST="192.168.1.5"
DEFAULT_USER="arduino"
REMOTE_PATH="~/still-loading"
RESTART_SERVICE=false

TARGET="${1:-$DEFAULT_HOST}"
if [[ "$TARGET" =~ ^-- ]]; then
    if [[ "$TARGET" == "--restart" ]]; then
        RESTART_SERVICE=true
    fi
    TARGET="$DEFAULT_HOST"
fi

if [[ $# -ge 2 && "$2" == "--restart" ]]; then
    RESTART_SERVICE=true
fi

# Ensure user is prefixed
if [[ "$TARGET" != *"@"* ]]; then
    SSH_TARGET="${DEFAULT_USER}@${TARGET}"
else
    SSH_TARGET="$TARGET"
fi

echo "========================================================"
echo " Still Loading... UNO Q Board Sync Tool"
echo " Target: ${SSH_TARGET}:${REMOTE_PATH}"
echo "========================================================"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Check SSH connectivity
echo -n "Checking SSH reachability... "
if ! ssh -o ConnectTimeout=4 -o BatchMode=no "${SSH_TARGET}" "echo OK" >/dev/null 2>&1; then
    echo "FAILED"
    echo "Error: Cannot connect to ${SSH_TARGET}. Please check IP, Wi-Fi, and credentials."
    exit 1
fi
echo "CONNECTED"

# Create remote directory structure if missing
echo "Ensuring remote directory structure..."
ssh "${SSH_TARGET}" "mkdir -p ${REMOTE_PATH}/shared ${REMOTE_PATH}/uno-q"

# Sync shared and uno-q folders
echo "Syncing shared/ and uno-q/..."
if command -v rsync >/dev/null 2>&1; then
    rsync -avz --delete \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.DS_Store' \
        "${REPO_ROOT}/shared/" "${SSH_TARGET}:${REMOTE_PATH}/shared/"

    rsync -avz --delete \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.DS_Store' \
        "${REPO_ROOT}/uno-q/" "${SSH_TARGET}:${REMOTE_PATH}/uno-q/"
else
    echo "rsync not found locally, falling back to scp..."
    scp -r "${REPO_ROOT}/shared" "${SSH_TARGET}:${REMOTE_PATH}/"
    scp -r "${REPO_ROOT}/uno-q" "${SSH_TARGET}:${REMOTE_PATH}/"
fi

echo "✓ Code successfully synced."

if [ "$RESTART_SERVICE" = true ]; then
    echo "Restarting still-loading-receiver.service on board..."
    ssh "${SSH_TARGET}" "sudo systemctl restart still-loading-receiver.service || true"
    echo "✓ Service restart triggered."
fi

echo "========================================================"
echo " Done! Ready to run on UNO Q."
echo "========================================================"
