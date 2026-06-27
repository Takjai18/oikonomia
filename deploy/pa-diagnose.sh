#!/bin/bash
# Run on PythonAnywhere Bash to find why deploy is stuck.
# Usage: bash ~/oikonomia/deploy/pa-diagnose.sh

REPO="${HOME}/oikonomia"

echo "=========================================="
echo " Oikonomia deploy diagnose (PythonAnywhere)"
echo "=========================================="
echo "User: $(whoami)"
echo "Home: $HOME"
echo ""

if [ ! -d "$REPO" ]; then
    echo "FAIL: $REPO does not exist."
    echo "Fix: cd ~ && git clone https://github.com/Takjai18/oikonomia.git"
    exit 1
fi

cd "$REPO"

echo "--- Git ---"
echo "Path: $(pwd)"
if [ -d .git ]; then
    echo "Branch: $(git branch --show-current 2>/dev/null || echo unknown)"
    echo "HEAD: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
    echo "Remote:"
    git remote -v 2>/dev/null || true
    echo ""
    echo "Status:"
    git status -sb 2>/dev/null || true
    echo ""
    echo "Fetch origin/main (read-only):"
    git fetch origin main 2>&1 || true
    echo "origin/main: $(git rev-parse --short origin/main 2>/dev/null || echo unknown)"
else
    echo "FAIL: not a git repo"
fi

echo ""
echo "--- Code markers in app.py ---"
for marker in resolve_player_phase build_combat_round_preview combat-action-modal; do
    if grep -q "$marker" app.py 2>/dev/null; then
        echo "  OK  $marker"
    else
        echo "  NO  $marker"
    fi
done

echo ""
echo "--- .deploy-version ---"
if [ -f .deploy-version ]; then
    echo "  $(cat .deploy-version)"
else
    echo "  (missing)"
fi

echo ""
echo "--- WSGI hint ---"
if [ -f wsgi.py ]; then
    echo "  wsgi.py exists at $REPO/wsgi.py"
    echo "  Web tab WSGI should import: wsgi.application"
    echo "  Source code path should be: $REPO"
else
    echo "  wsgi.py missing"
fi

echo ""
echo "--- Live site (curl) ---"
curl -s https://takjai.pythonanywhere.com/api/version 2>/dev/null | head -c 600 || echo "curl failed"
echo ""
echo ""
echo "If HEAD != origin/main, run:"
echo "  FORCE=1 bash ~/oikonomia/deploy/pa-update.sh"
echo "Then Web tab -> Reload, and curl /api/version again."