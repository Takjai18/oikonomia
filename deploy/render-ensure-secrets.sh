#!/bin/bash
# Idempotent secrets on Render persistent disk (/data).
# Called by render-predeploy.sh before each deploy.
set -euo pipefail

DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"

SECRET_FILE="$DATA_DIR/.secret_key"
GM_PIN_FILE="$DATA_DIR/.gm_pin"
COMBAT_V2_FILE="$DATA_DIR/.combat_v2"

if [ -f "$SECRET_FILE" ] && [ -s "$SECRET_FILE" ]; then
    echo "OK: $SECRET_FILE exists"
elif [ -n "${SECRET_KEY:-}" ]; then
    printf '%s\n' "$SECRET_KEY" > "$SECRET_FILE"
    chmod 600 "$SECRET_FILE"
    echo "Created $SECRET_FILE from SECRET_KEY env"
else
    python3 -c "import secrets; print(secrets.token_hex(32))" > "$SECRET_FILE"
    chmod 600 "$SECRET_FILE"
    echo "Created $SECRET_FILE (new random key — set Dashboard SECRET_KEY to match for multi-worker consistency)"
fi

if [ -f "$GM_PIN_FILE" ] && [ -s "$GM_PIN_FILE" ]; then
    echo "OK: $GM_PIN_FILE exists"
elif [ -n "${GM_PIN:-}" ]; then
    printf '%s\n' "$GM_PIN" > "$GM_PIN_FILE"
    chmod 600 "$GM_PIN_FILE"
    echo "Created $GM_PIN_FILE from GM_PIN env"
else
    echo "ERROR: GM_PIN is required. Set it in Render Dashboard env vars, or import PA data/.gm_pin to /data/.gm_pin"
    exit 1
fi

if [ -f "$COMBAT_V2_FILE" ] && grep -qE '^(1|true|yes|on)$' "$COMBAT_V2_FILE" 2>/dev/null; then
    echo "OK: $COMBAT_V2_FILE enables COMBAT_V2"
else
    echo "1" > "$COMBAT_V2_FILE"
    chmod 644 "$COMBAT_V2_FILE"
    echo "Created $COMBAT_V2_FILE (COMBAT_V2=1)"
fi