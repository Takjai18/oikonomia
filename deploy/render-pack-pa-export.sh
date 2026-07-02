#!/bin/bash
# Pack PythonAnywhere production data for Render migration.
# Run on PA Bash (or locally if you have a copy of data/ + uploads/).
#
# Usage:
#   bash deploy/render-pack-pa-export.sh
#   bash deploy/render-pack-pa-export.sh /path/to/oikonomia
#
# On PythonAnywhere (if script missing): cd ~/oikonomia && git pull origin main
#
# Output: /tmp/oikonomia-render-migrate.tar.gz (or $OUT)
set -euo pipefail

REPO="${1:-${HOME}/oikonomia}"
DATA_DIR="$REPO/data"
UPLOADS_DIR="$REPO/uploads"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${OUT:-/tmp/oikonomia-render-migrate-$STAMP.tar.gz}"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

mkdir -p "$WORKDIR/data" "$WORKDIR/uploads"

if [ ! -f "$DATA_DIR/oikonomia.db" ]; then
    echo "ERROR: missing $DATA_DIR/oikonomia.db"
    exit 1
fi

cp -a "$DATA_DIR/oikonomia.db" "$WORKDIR/data/"
for f in .secret_key .gm_pin .combat_v2; do
    if [ -f "$DATA_DIR/$f" ]; then
        cp -a "$DATA_DIR/$f" "$WORKDIR/data/"
    fi
done

if [ -d "$UPLOADS_DIR" ]; then
    cp -a "$UPLOADS_DIR/." "$WORKDIR/uploads/" 2>/dev/null || true
fi
if [ -d "$DATA_DIR/uploads" ]; then
    cp -an "$DATA_DIR/uploads/." "$WORKDIR/uploads/" 2>/dev/null || true
fi

tar -czf "$OUT" -C "$WORKDIR" data uploads
echo "Created $OUT"
echo "Contents:"
tar -tzf "$OUT" | head -30
echo "..."
echo ""
echo "Next: upload to Render Shell and run deploy/render-import-data.sh"