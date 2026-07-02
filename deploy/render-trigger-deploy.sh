#!/bin/bash
# Trigger Render deploy via Deploy Hook (set RENDER_DEPLOY_HOOK in env or pass as arg).
# Dashboard → oikonomia → Settings → Deploy Hook → copy URL.
set -euo pipefail

HOOK="${1:-${RENDER_DEPLOY_HOOK:-}}"
if [ -z "$HOOK" ]; then
    echo "Usage: RENDER_DEPLOY_HOOK='https://api.render.com/...' bash deploy/render-trigger-deploy.sh"
    echo "Or: bash deploy/render-trigger-deploy.sh 'https://api.render.com/deploy/...'"
    exit 1
fi

curl -fsS -X POST "$HOOK"
echo ""
echo "Deploy triggered. Watch: https://dashboard.render.com"