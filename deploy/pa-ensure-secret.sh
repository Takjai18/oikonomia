#!/bin/bash
# Create data/.secret_key and data/.gm_pin for PythonAnywhere Web workers (idempotent).
# Web tab workers do NOT inherit shell exports from pa-update.sh — they read these files via wsgi.py.
# Usage: bash ~/oikonomia/deploy/pa-ensure-secret.sh

set -e
REPO="${HOME}/oikonomia"
SECRET_FILE="$REPO/data/.secret_key"
GM_PIN_FILE="$REPO/data/.gm_pin"

mkdir -p "$REPO/data"

if [ -f "$SECRET_FILE" ] && [ -s "$SECRET_FILE" ]; then
    echo "OK: $SECRET_FILE already exists"
else
    python3 -c "import secrets; print(secrets.token_hex(32))" > "$SECRET_FILE"
    chmod 600 "$SECRET_FILE"
    echo "Created $SECRET_FILE"
fi

if [ -f "$GM_PIN_FILE" ] && [ -s "$GM_PIN_FILE" ]; then
    echo "OK: $GM_PIN_FILE already exists"
else
    echo "${GM_PIN:-gm2026}" > "$GM_PIN_FILE"
    chmod 600 "$GM_PIN_FILE"
    echo "Created $GM_PIN_FILE (override with Web tab GM_PIN env or edit file)"
fi

cd "$REPO"
# shellcheck disable=SC1091
[ -d "$REPO/venv" ] && source "$REPO/venv/bin/activate"
export DATA_DIR="$REPO/data"
export FLASK_ENV=production
unset SECRET_KEY
unset GM_PIN
python3 -c "from wsgi import application; print('wsgi import ok (via data/.secret_key + data/.gm_pin)')"