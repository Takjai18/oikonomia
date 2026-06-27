#!/bin/bash
# Run on PythonAnywhere Bash console after code is pushed to GitHub.
# Production: https://takjai.pythonanywhere.com
#
# IMPORTANT: Web tab → Reload only restarts the app worker.
# It does NOT download new code. You must run this script first.

set -e

REPO="${HOME}/oikonomia"

echo "=========================================="
echo " Oikonomia deploy update (PythonAnywhere)"
echo "=========================================="

if [ ! -d "$REPO" ]; then
    echo "ERROR: $REPO does not exist."
    echo "Clone first:"
    echo "  cd ~ && git clone https://github.com/Takjai18/oikonomia.git"
    exit 1
fi

cd "$REPO"

if [ ! -d .git ]; then
    echo "ERROR: $REPO is not a git repository."
    exit 1
fi

echo ""
echo "--- Before update ---"
echo "Path: $(pwd)"
echo "Commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
if grep -q "def resolve_player_phase" app.py 2>/dev/null; then
    echo "Code marker: COMBAT (resolve_player_phase found)"
elif grep -q "showOnlyProtagonistCard" app.py 2>/dev/null; then
    echo "Code marker: PARTIAL (no combat, has showOnlyProtagonistCard)"
else
    echo "Code marker: OLD"
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo ""
    echo "WARNING: Local changes detected on PythonAnywhere."
    echo "git pull may fail. Run: git status"
    echo "To discard local edits: git checkout -- . && git clean -fd"
fi

echo ""
echo "--- Pulling from GitHub ---"
git fetch origin main
git pull origin main

NEW_COMMIT=$(git rev-parse --short HEAD)
echo "$NEW_COMMIT" > .deploy-version

echo ""
echo "--- After update ---"
echo "Commit: $NEW_COMMIT"
if grep -q "showOnlyProtagonistCard" app.py; then
    echo "Code marker: NEW (showOnlyProtagonistCard found)"
else
    echo "Code marker: still OLD — check git pull output above"
fi

echo ""
echo "--- Upload folders ---"
mkdir -p uploads data/uploads
if [ -d data/uploads ]; then
    cp -n data/uploads/* uploads/ 2>/dev/null || true
    echo "Synced data/uploads -> uploads/ (if any legacy files)"
fi
echo "uploads count: $(ls -1 uploads 2>/dev/null | wc -l | tr -d ' ')"

echo ""
echo "--- Avatar images (static/avatars) ---"
AVATAR_COUNT=$(find static/avatars -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) ! -iname 'default.png' 2>/dev/null | wc -l | tr -d ' ')
echo "Selectable avatars: $AVATAR_COUNT"
ls -1 static/avatars 2>/dev/null | grep -viE '^default\.png$' | head -20 || true
if [ "$AVATAR_COUNT" = "0" ]; then
    echo "WARNING: No avatar images found. Add PNG/JPG to static/avatars/ and git push."
fi

echo ""
echo "Done. Now go to PythonAnywhere Web tab → Reload takjai.pythonanywhere.com"
echo "Then verify: curl https://takjai.pythonanywhere.com/api/version"
echo "Expected version: $NEW_COMMIT"
echo ""
echo "NOTE: Web tab → Static files 唔好 map /uploads/，交俾 Flask route 處理。"