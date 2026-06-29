#!/bin/bash
# Quick check on PythonAnywhere: error log tail + import test + live curl.
# Usage: bash ~/oikonomia/deploy/pa-check-error.sh

REPO="${HOME}/oikonomia"
LOG="/var/log/$(whoami).pythonanywhere.com.error.log"
VENV_DIR="$REPO/venv"

echo "=========================================="
echo " Oikonomia error check (PythonAnywhere)"
echo "=========================================="

echo ""
echo "--- Error log (last 40 lines) ---"
if [ -f "$LOG" ]; then
    tail -40 "$LOG"
else
    echo "Log not found at $LOG"
    echo "Try Web tab -> Log files -> error.log"
fi

echo ""
echo "--- Virtualenv ---"
if [ -d "$VENV_DIR" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    echo "Using venv: $VENV_DIR"
    echo "Python: $(which python3)"
else
    echo "WARNING: venv missing at $VENV_DIR"
    echo "Run: FORCE=1 bash ~/oikonomia/deploy/pa-update.sh"
fi

echo ""
echo "--- Pillow (PIL) ---"
if python3 -c "from PIL import Image; print('PIL ok')" 2>&1; then
    :
else
    echo ""
    echo "FIX: pip install -r requirements.txt inside venv, then set Web tab Virtualenv to:"
    echo "  $VENV_DIR"
fi

echo ""
echo "--- SECRET_KEY file ---"
SECRET_FILE="$REPO/data/.secret_key"
if [ -f "$SECRET_FILE" ]; then
    echo "  OK  $SECRET_FILE exists"
else
    echo "  NO  $SECRET_FILE — run: FORCE=1 bash ~/oikonomia/deploy/pa-update.sh"
fi

echo ""
echo "--- Python import test (wsgi, no shell SECRET_KEY) ---"
cd "$REPO" || exit 1
export DATA_DIR="$REPO/data"
export FLASK_ENV=production
unset SECRET_KEY
python3 -c "from wsgi import application; from utils.app_state import DB_INIT_ERROR; print('wsgi import ok'); print('db_init_error:', DB_INIT_ERROR)" 2>&1

echo ""
echo "--- Web tab checklist ---"
echo "1. Source code path: $REPO"
echo "2. Virtualenv path:  $VENV_DIR"
echo "3. WSGI file: copy deploy/pa-wsgi-web-tab.py into Web tab WSGI config"
echo "   (Do NOT use: from app import app as application)"
echo "4. SECRET_KEY: Web tab env var OR data/.secret_key (pa-update.sh creates it)"
echo "   NOTE: venv/bin/activate exports do NOT apply to Web workers"

echo ""
echo "--- Git HEAD ---"
git rev-parse --short HEAD 2>/dev/null || echo unknown

echo ""
echo "--- Live /api/version ---"
curl -s https://takjai.pythonanywhere.com/api/version | head -c 800
echo ""