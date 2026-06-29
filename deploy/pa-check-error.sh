#!/bin/bash
# Quick check on PythonAnywhere: error log tail + import test + live curl.
# Usage: bash ~/oikonomia/deploy/pa-check-error.sh

REPO="${HOME}/oikonomia"
LOG="/var/log/$(whoami).pythonanywhere.com.error.log"

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
echo "--- Python import test ---"
cd "$REPO" || exit 1
export DATA_DIR="$REPO/data"
export FLASK_ENV=production
python3.10 -c "from wsgi import application; from utils.app_state import DB_INIT_ERROR; print('wsgi import ok'); print('db_init_error:', DB_INIT_ERROR)" 2>&1 \
    || python3 -c "from wsgi import application; from utils.app_state import DB_INIT_ERROR; print('wsgi import ok'); print('db_init_error:', DB_INIT_ERROR)" 2>&1

echo ""
echo "--- Git HEAD ---"
git rev-parse --short HEAD 2>/dev/null || echo unknown

echo ""
echo "--- Live /api/version ---"
curl -s https://takjai.pythonanywhere.com/api/version | head -c 800
echo ""