#!/bin/bash
# Render preDeployCommand: secrets + one-shot DB bootstrap (fcntl lock).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export DATA_DIR="${DATA_DIR:-/data}"
export RENDER="${RENDER:-true}"
export FLASK_ENV="${FLASK_ENV:-production}"

echo "=== Render pre-deploy (DATA_DIR=$DATA_DIR) ==="
bash "$ROOT/deploy/render-ensure-secrets.sh"

echo "--- Database bootstrap ---"
python3 -c "
from wsgi import application
from app import bootstrap_app_data
bootstrap_app_data()
print('DB bootstrap ok')
"

echo "--- Import smoke test ---"
unset SECRET_KEY
unset GM_PIN
python3 -c "from wsgi import application; print('wsgi import ok')"

echo "=== Render pre-deploy done ==="