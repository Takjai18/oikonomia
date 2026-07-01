#!/bin/bash
# Regression gate before PythonAnywhere deploy or CI merge.
# Uses isolated temp DBs inside each test script — never touches production data/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="python3"
if [ -x "$ROOT/venv/bin/python3" ]; then
    PYTHON="$ROOT/venv/bin/python3"
fi

export FLASK_ENV=development
export SECRET_KEY="${SECRET_KEY:-test-secret-pre-deploy}"

run_test() {
    local script="$1"
    local label="$2"
    echo ""
    echo "=========================================="
    echo " $label"
    echo "=========================================="
    "$PYTHON" "$script"
}

echo "Pre-deploy checks (Python: $PYTHON)"
echo "Repo: $ROOT"

run_test scripts/test_combat_engine.py "Combat engine (pure calculation unit)"
run_test scripts/test_combat_flow_orchestrator.py "Combat flow orchestrator (INV-E)"
run_test scripts/test_combat_flow.py "Combat flow (API + HP sync + practice)"
run_test scripts/test_combat_audit.py "Combat audit (settlement + solo + protagonist)"
run_test scripts/test_combat_concurrency.py "Combat concurrency smoke"
run_test scripts/test_ending_flow.py "Ending orchestrator regression"

if ! test -f static/js/combat/index.js; then
    echo "ERROR: static/js/combat/index.js missing (Combat V2 module)"
    exit 1
fi
if ! grep -q "combat-root-v2" templates/combat_screen.html 2>/dev/null; then
    echo "ERROR: templates/combat_screen.html missing combat-root-v2 mount"
    exit 1
fi
if ! grep -q "enemy_hp_after" models/combat.py 2>/dev/null; then
    echo "ERROR: models/combat.py missing enemy_hp_after settlement field"
    exit 1
fi

if [ -d "$ROOT/node_modules/@playwright/test" ] && command -v npx >/dev/null 2>&1; then
    echo ""
    echo "=========================================="
    echo " Combat V2 Playwright E2E (T8–T14 Phase 2)"
    echo "=========================================="
    if ! npx playwright test -c playwright.config.cjs tests/combat_v2.spec.js --reporter=line; then
        echo "ERROR: Combat V2 Playwright E2E failed"
        exit 1
    fi
else
    echo ""
    echo "SKIP: Playwright not installed — run: npm install && npx playwright install chromium"
fi

echo ""
echo "=========================================="
echo " All pre-deploy checks passed"
echo "=========================================="