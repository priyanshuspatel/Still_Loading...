#!/usr/bin/env bash
# ==============================================================================
# Still Loading... — Unified Monorepo Test Suite Runner
# ==============================================================================
# Runs all automated tests across Python backend, relay, and web frontend.
#
# Usage:
#   ./scripts/test_all.sh
# ==============================================================================

set -u

GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

pass() { echo -e "  [ ${GREEN}PASS${NC} ] $1"; }
fail() { echo -e "  [ ${RED}FAIL${NC} ] $1"; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAILED=0

echo -e "${CYAN}========================================================${NC}"
echo -e "${CYAN} Still Loading... Full Monorepo Test Suite             ${NC}"
echo -e "${CYAN}========================================================${NC}"
echo ""

# 1. Python Agent & Protocol Tests
echo "1. Running Mac Agent & Shared Protocol Unit Tests..."
if python3 -m unittest discover -s "${REPO_ROOT}/mac-agent/tests" -t "${REPO_ROOT}/mac-agent"; then
    pass "Mac Agent & Shared Protocol tests"
else
    fail "Mac Agent tests failed"
    FAILED=1
fi
echo ""

# 2. Telemetry Relay Tests (2 tests)
echo "2. Running Telemetry Relay Unit Tests..."
if python3 -m unittest "${REPO_ROOT}/relay/tests/test_relay.py"; then
    pass "Telemetry Relay tests (2 tests)"
else
    fail "Telemetry Relay tests failed"
    FAILED=1
fi
echo ""

# 3. Demonstration Suite Verification (headless fast run)
echo "3. Running Multi-Scenario Demo Suite (--all --fast)..."
if python3 "${REPO_ROOT}/mac-agent/demo.py" --all --fast >/dev/null 2>&1; then
    pass "Demo Suite (--all --fast completed with exit 0)"
else
    fail "Demo Suite run failed"
    FAILED=1
fi
echo ""

# 4. Web Frontend Tests
echo "4. Running Web Frontend Tests (matrixEngine)..."
if (cd "${REPO_ROOT}/web" && npm test >/dev/null 2>&1); then
    pass "Web frontend tests"
else
    fail "Web tests failed"
    FAILED=1
fi
echo ""

# 5. Web Frontend Production Build
echo "5. Running Web Production Bundle Build (tsc && vite build)..."
if (cd "${REPO_ROOT}/web" && npm run build >/dev/null 2>&1); then
    pass "Web Frontend build (Vite bundle compiled cleanly)"
else
    fail "Web Frontend build failed"
    FAILED=1
fi
echo ""

echo -e "${CYAN}========================================================${NC}"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN} ALL 5/5 TEST SUITES PASSED SUCCESSFULLY!${NC}"
    echo -e "${CYAN}========================================================${NC}"
    exit 0
else
    echo -e "${RED} ONE OR MORE SUITES FAILED. Check output above.${NC}"
    echo -e "${CYAN}========================================================${NC}"
    exit 1
fi
