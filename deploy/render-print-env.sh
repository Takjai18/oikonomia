#!/bin/bash
# Print Render Dashboard env vars from local/PA data files (for copy-paste).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${1:-$ROOT/data}"

if [ ! -d "$DATA_DIR" ]; then
    echo "ERROR: missing $DATA_DIR"
    exit 1
fi

echo "=== Render Environment (copy to Dashboard) ==="
if [ -f "$DATA_DIR/.secret_key" ]; then
    echo "SECRET_KEY=$(tr -d '\n' < "$DATA_DIR/.secret_key")"
else
    echo "# SECRET_KEY: (missing $DATA_DIR/.secret_key)"
fi
if [ -f "$DATA_DIR/.gm_pin" ]; then
    echo "GM_PIN=$(tr -d '\n' < "$DATA_DIR/.gm_pin")"
else
    echo "# GM_PIN: (missing $DATA_DIR/.gm_pin)"
fi
echo "DATA_DIR=/data"
echo "RENDER=true"
echo "FLASK_ENV=production"
echo "PYTHON_VERSION=3.12.8"
echo ""
echo "=== Verify after deploy ==="
echo "db_path should be: /data/oikonomia.db"
echo "bash deploy/render-check.sh https://oikonomia.onrender.com"