#!/usr/bin/env bash
# ==============================================================================
# Still Loading... — Hardware & Environment Verification Script
# ==============================================================================
# Verifies local Mac sensors, receiver reachability, token auth, and relay health.
#
# Usage:
#   ./scripts/verify_hardware.sh [BOARD_IP] [TOKEN]
# ==============================================================================

set -u

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

pass() { echo -e "  [ ${GREEN}PASS${NC} ] $1"; }
warn() { echo -e "  [ ${YELLOW}WARN${NC} ] $1"; }
fail() { echo -e "  [ ${RED}FAIL${NC} ] $1"; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${REPO_ROOT}/mac-agent/config.local.json"

BOARD_IP="${1:-}"
TOKEN="${2:-}"

# Try to extract from config.local.json or env if not passed
if [ -z "$BOARD_IP" ]; then
    if [ -f "$CONFIG_FILE" ]; then
        EXTRACTED_URL=$(grep -o '"board_url"[^,]*' "$CONFIG_FILE" | cut -d'"' -f4 || true)
        if [ -n "$EXTRACTED_URL" ]; then
            BOARD_IP=$(echo "$EXTRACTED_URL" | sed -E 's|https?://([^:/]+).*|\1|')
        fi
    fi
fi
BOARD_IP="${BOARD_IP:-192.168.1.5}"

if [ -z "$TOKEN" ]; then
    if [ -n "${STILL_LOADING_TOKEN:-}" ]; then
        TOKEN="$STILL_LOADING_TOKEN"
    elif [ -f "$CONFIG_FILE" ]; then
        TOKEN=$(grep -o '"token"[^,]*' "$CONFIG_FILE" | cut -d'"' -f4 || true)
    fi
fi

echo -e "${CYAN}========================================================${NC}"
echo -e "${CYAN} Still Loading... Hardware & Environment Verification   ${NC}"
echo -e "${CYAN}========================================================${NC}"
echo "Board IP Target : $BOARD_IP"
echo "Board Port      : 8090"
echo "Token Configured: $([ -n "$TOKEN" ] && echo "Yes (${#TOKEN} chars)" || echo "No (Unset)")"
echo ""

# 1. Local Mac Battery Sensor Test
echo "1. Checking macOS Battery Sensor (pmset)..."
if command -v pmset >/dev/null 2>&1; then
    BATT_OUTPUT=$(pmset -g batt 2>&1 || true)
    if echo "$BATT_OUTPUT" | grep -q "InternalBattery"; then
        PERCENT=$(echo "$BATT_OUTPUT" | grep -o '[0-9]\{1,3\}%' | head -n1)
        STATE=$(echo "$BATT_OUTPUT" | grep -o 'discharging\|charging\|charged\|finishing charge' | head -n1 || echo "unknown")
        pass "Mac battery sensor active: $PERCENT ($STATE)"
    else
        warn "No internal battery reported (Desktop Mac or AC only)"
    fi
else
    warn "pmset command not found (non-macOS environment)"
fi

# 2. Local Telemetry Relay Test (Port 8765)
echo ""
echo "2. Checking Local Telemetry Relay (port 8765)..."
RELAY_HEALTH=$(curl -s -m 2 http://127.0.0.1:8765/health 2>/dev/null || true)
if [ -n "$RELAY_HEALTH" ]; then
    pass "Local relay running at http://127.0.0.1:8765 ($RELAY_HEALTH)"
else
    warn "Local relay not responding on port 8765 (Optional: start via python3 relay/telemetry_relay.py)"
fi

# 3. Arduino UNO Q Network Reachability (Port 8090)
echo ""
echo "3. Checking Arduino UNO Q Connectivity ($BOARD_IP:8090)..."
if nc -z -w 3 "$BOARD_IP" 8090 2>/dev/null; then
    pass "Port 8090 is open and accepting TCP connections on $BOARD_IP"

    # Test /health endpoint
    HEALTH_RESP=$(curl -s -m 3 "http://${BOARD_IP}:8090/health" 2>/dev/null || true)
    if [ -n "$HEALTH_RESP" ]; then
        pass "Receiver /health responded: $HEALTH_RESP"
    else
        fail "Port open, but /health endpoint did not return expected response"
    fi

    # Test Authentication with /v1/lights
    if [ -n "$TOKEN" ]; then
        LIGHTS_RESP=$(curl -s -w "\n%{http_code}" -m 3 -H "Authorization: Bearer $TOKEN" "http://${BOARD_IP}:8090/v1/lights" 2>/dev/null || true)
        HTTP_CODE=$(echo "$LIGHTS_RESP" | tail -n1)
        BODY=$(echo "$LIGHTS_RESP" | head -n -1)

        if [ "$HTTP_CODE" = "200" ]; then
            pass "Authenticated GET /v1/lights succeeded (HTTP 200)"
            STATE_VAL=$(echo "$BODY" | grep -o '"state"[^,]*' | cut -d'"' -f4 || echo "unknown")
            echo "     Current Hardware Light State: $STATE_VAL"
        elif [ "$HTTP_CODE" = "401" ]; then
            fail "Authentication failed (HTTP 401 Unauthorized). Verify STILL_LOADING_TOKEN match."
        else
            warn "Unexpected response code: HTTP $HTTP_CODE ($BODY)"
        fi
    else
        warn "Token not provided; skipping authenticated /v1/lights test."
    fi
else
    fail "Cannot connect to $BOARD_IP on port 8090."
    echo "     Suggestions:"
    echo "       a. Verify the board is powered on and connected to the same Wi-Fi."
    echo "       b. Verify receiver is running: python3 uno-q/receiver.py --host 0.0.0.0 --port 8090"
    echo "       c. Verify board IP address: ping $BOARD_IP"
fi

# 4. Mac Unit Test Suite
echo ""
echo "4. Running Mac Test Suite Verification..."
if python3 -m unittest discover -s "${REPO_ROOT}/mac-agent/tests" -t "${REPO_ROOT}/mac-agent" >/dev/null 2>&1; then
    pass "All Mac agent & shared protocol unit tests passed successfully"
else
    fail "One or more Mac unit tests failed. Run: python3 -m unittest discover -s mac-agent/tests -t mac-agent -v"
fi

echo ""
echo -e "${CYAN}========================================================${NC}"
echo -e "${CYAN} Verification Complete                                  ${NC}"
echo -e "${CYAN}========================================================${NC}"
