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
run_test scripts/test_combat_flow.py "Combat flow (API + HP sync + practice)"
run_test scripts/test_combat_audit.py "Combat audit (settlement + solo + protagonist)"
run_test scripts/test_combat_concurrency.py "Combat concurrency smoke"
run_test scripts/test_ending_flow.py "Ending orchestrator regression"

if ! grep -q "syncEnemyHpDisplay" templates/index.html 2>/dev/null; then
    echo "ERROR: templates/index.html missing syncEnemyHpDisplay (enemy HP sync)"
    exit 1
fi
if ! grep -q "enemy_hp_after" models/combat.py 2>/dev/null; then
    echo "ERROR: models/combat.py missing enemy_hp_after settlement field"
    exit 1
fi

echo ""
echo "=========================================="
echo " All pre-deploy checks passed"
echo "=========================================="