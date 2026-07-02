#!/bin/bash
# Trigger Render deploy and wait until /api/version matches local git short hash.
# Requires RENDER_DEPLOY_HOOK in env (or pass as first arg).
# Optional: RENDER_URL (default https://oikonomia.onrender.com)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HOOK="${1:-${RENDER_DEPLOY_HOOK:-}}"
BASE_URL="${RENDER_URL:-https://oikonomia.onrender.com}"
EXPECTED="$(git rev-parse --short HEAD)"

if [ -z "$HOOK" ]; then
    echo "Usage: RENDER_DEPLOY_HOOK='https://api.render.com/...' bash deploy/render-sync.sh"
    echo "Or: bash deploy/render-sync.sh 'https://api.render.com/deploy/...'"
    exit 1
fi

echo "Local commit: $EXPECTED"
echo "Triggering Render deploy..."
curl -fsS -X POST "$HOOK"
echo ""

MAX_WAIT="${RENDER_SYNC_MAX_WAIT:-600}"
INTERVAL="${RENDER_SYNC_INTERVAL:-15}"
elapsed=0

while [ "$elapsed" -lt "$MAX_WAIT" ]; do
    REMOTE="$(curl -fsS "$BASE_URL/api/version" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('version',''))" 2>/dev/null || true)"
    if [ "$REMOTE" = "$EXPECTED" ]; then
        echo "Render synced: version=$REMOTE"
        bash deploy/render-check.sh "$BASE_URL"
        exit 0
    fi
    echo "Waiting… remote=${REMOTE:-<unavailable>} expected=$EXPECTED (${elapsed}s)"
    sleep "$INTERVAL"
    elapsed=$((elapsed + INTERVAL))
done

echo "Timeout: Render version still not $EXPECTED after ${MAX_WAIT}s"
curl -s "$BASE_URL/api/version" | python3 -m json.tool || true
exit 1