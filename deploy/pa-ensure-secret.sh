#!/bin/bash
# Create data/.secret_key for PythonAnywhere Web workers (idempotent).
# Usage: bash ~/oikonomia/deploy/pa-ensure-secret.sh

set -e
REPO="${HOME}/oikonomia"
SECRET_FILE="$REPO/data/.secret_key"

mkdir -p "$REPO/data"
if [ -f "$SECRET_FILE" ] && [ -s "$SECRET_FILE" ]; then
    echo "OK: $SECRET_FILE already exists"
else
    python3 -c "import secrets; print(secrets.token_hex(32))" > "$SECRET_FILE"
    chmod 600 "$SECRET_FILE"
    echo "Created $SECRET_FILE"
fi

cd "$REPO"
# shellcheck disable=SC1091
[ -d "$REPO/venv" ] && source "$REPO/venv/bin/activate"
export DATA_DIR="$REPO/data"
export FLASK_ENV=production
export GM_PIN="${GM_PIN:-gm2026}"
unset SECRET_KEY
python3 -c "from wsgi import application; print('wsgi import ok (via .secret_key)')"