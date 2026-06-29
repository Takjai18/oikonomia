#!/bin/bash
# Run on PythonAnywhere Bash console after code is pushed to GitHub.
# Production: https://takjai.pythonanywhere.com
#
# IMPORTANT: Web tab -> Reload only restarts the app worker.
# It does NOT download new code. You must run this script first.
#
# If git pull keeps failing, use force update:
#   FORCE=1 bash ~/oikonomia/deploy/pa-update.sh

set -e

REPO="${HOME}/oikonomia"
FORCE="${FORCE:-0}"

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
echo "Branch: $(git branch --show-current 2>/dev/null || echo unknown)"
echo "Commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "Remote:"
git remote -v 2>/dev/null || true

has_combat_modal() {
    grep -q "combat-action-modal" templates/index.html 2>/dev/null \
        || grep -q "combat-action-modal" app.py 2>/dev/null
}

code_marker() {
    if has_combat_modal; then
        echo "COMBAT_MODAL"
    elif grep -q "build_combat_round_preview" models/combat.py 2>/dev/null; then
        echo "COMBAT_PREVIEW"
    elif grep -q "def resolve_player_phase" models/combat.py 2>/dev/null; then
        echo "COMBAT"
    elif grep -q "showOnlyProtagonistCard" templates/index.html 2>/dev/null; then
        echo "PARTIAL"
    else
        echo "OLD"
    fi
}
echo "Code marker: $(code_marker)"

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo ""
    echo "WARNING: Local changes on PythonAnywhere (git pull may fail)."
    git status -sb || true
    if [ "$FORCE" != "1" ]; then
        echo ""
        echo "To discard local edits and match GitHub exactly:"
        echo "  FORCE=1 bash ~/oikonomia/deploy/pa-update.sh"
    fi
fi

echo ""
echo "--- Fetching from GitHub ---"
git fetch origin main

if [ "$FORCE" = "1" ]; then
    echo "FORCE=1: resetting to origin/main (discards local changes)"
    git reset --hard origin/main
else
    echo "Pulling origin/main..."
    if ! git pull origin main; then
        echo ""
        echo "ERROR: git pull failed."
        echo "Common fixes:"
        echo "  1) FORCE=1 bash ~/oikonomia/deploy/pa-update.sh"
        echo "  2) bash ~/oikonomia/deploy/pa-diagnose.sh"
        exit 1
    fi
fi

NEW_COMMIT=$(git rev-parse --short HEAD)
echo "$NEW_COMMIT" > .deploy-version

echo ""
echo "--- After update ---"
echo "Commit: $NEW_COMMIT"
echo "origin/main: $(git rev-parse --short origin/main 2>/dev/null || echo unknown)"
echo "Code marker: $(code_marker)"

if ! has_combat_modal; then
    echo ""
    echo "WARNING: combat-action-modal NOT found in templates/index.html."
    echo "Check: git remote -v  (should point to github.com/Takjai18/oikonomia)"
    echo "       Web tab source code path should be: $REPO"
fi

echo ""
echo "--- Python virtualenv ---"
VENV_DIR="$REPO/venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "Created venv at $VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install -q -r requirements.txt
echo "venv pip install -r requirements.txt (ok)"
if ! python3 -c "from PIL import Image; print('Pillow OK')" 2>&1; then
    echo "ERROR: Pillow (PIL) not installed in venv."
    exit 1
fi
echo "NOTE: PythonAnywhere Web tab -> Virtualenv path MUST be: $VENV_DIR"
echo "NOTE: WSGI file must use: from wsgi import application (NOT from app import app)"

echo ""
echo "--- SECRET_KEY (data/.secret_key) ---"
SECRET_FILE="$REPO/data/.secret_key"
mkdir -p "$REPO/data"
if [ ! -f "$SECRET_FILE" ]; then
    python3 -c "import secrets; print(secrets.token_hex(32))" > "$SECRET_FILE"
    chmod 600 "$SECRET_FILE"
    echo "Created $SECRET_FILE (Web worker reads this if Web tab has no SECRET_KEY env)"
else
    echo "Using existing $SECRET_FILE"
fi

echo ""
echo "--- Import smoke test ---"
export DATA_DIR="$REPO/data"
export FLASK_ENV=production
unset SECRET_KEY
if ! python3 -c "from wsgi import application; print('wsgi import ok')" 2>&1; then
    echo ""
    echo "ERROR: wsgi import failed. Fix before Web Reload."
    echo "Check Web tab -> Virtualenv: $VENV_DIR"
    echo "Check Web tab -> Environment: SECRET_KEY, GM_PIN, DATA_DIR=data"
    exit 1
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

echo ""
echo "Done. Now: Web tab -> Reload takjai.pythonanywhere.com"
echo ""
echo "Verify:"
echo "  curl -s https://takjai.pythonanywhere.com/api/version"
echo "Expected:"
echo "  version: $NEW_COMMIT"
echo "  markers.combat_preview: true"
echo "  markers.combat_modal: true"
echo ""
echo "NOTE: Do NOT map /uploads/ in Static files (Flask serves uploads)."