#!/bin/bash
# Post-deploy smoke check for Render (or any URL).
# Usage: bash deploy/render-check.sh https://oikonomia.onrender.com
set -euo pipefail

BASE="${1:-}"
if [ -z "$BASE" ]; then
    echo "Usage: bash deploy/render-check.sh https://YOUR-SERVICE.onrender.com"
    exit 1
fi

BASE="${BASE%/}"
echo "Checking $BASE/api/version ..."
BODY="$(curl -sf --max-time 30 "$BASE/api/version")"
echo "$BODY" | python3 -m json.tool

echo "$BODY" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d.get('success') is True, d
v = d.get('version') or d.get('git_commit') or ''
assert v, 'missing version/git_commit'
print('OK: success=true version=', v)
if 'combat_v2' in d:
    print('combat_v2:', d['combat_v2'])
"

echo ""
echo "TTFB probe:"
curl -s -o /dev/null -w "connect:%{time_connect}s ttfb:%{time_starttransfer}s total:%{time_total}s\n" "$BASE/api/version"