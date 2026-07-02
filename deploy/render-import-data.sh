#!/bin/bash
# Import PA export tarball into Render persistent disk (/data).
# Run inside Render Dashboard → oikonomia → Shell.
#
# 1. Upload oikonomia-render-migrate-*.tar.gz (Dashboard file upload or scp workaround).
# 2. bash deploy/render-import-data.sh /path/to/oikonomia-render-migrate.tar.gz
set -euo pipefail

ARCHIVE="${1:-}"
DATA_DIR="${DATA_DIR:-/data}"

if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
    echo "Usage: bash deploy/render-import-data.sh /path/to/oikonomia-render-migrate.tar.gz"
    exit 1
fi

if [ ! -d "$DATA_DIR" ]; then
    echo "ERROR: $DATA_DIR not mounted — enable Persistent Disk in Render service settings."
    exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
tar -xzf "$ARCHIVE" -C "$WORKDIR"

if [ -f "$WORKDIR/data/oikonomia.db" ]; then
    cp -a "$WORKDIR/data/oikonomia.db" "$DATA_DIR/"
    echo "Imported oikonomia.db"
fi
for f in .secret_key .gm_pin .combat_v2; do
    if [ -f "$WORKDIR/data/$f" ]; then
        cp -a "$WORKDIR/data/$f" "$DATA_DIR/"
        chmod 600 "$DATA_DIR/$f" 2>/dev/null || chmod 644 "$DATA_DIR/$f"
        echo "Imported data/$f"
    fi
done

mkdir -p "$DATA_DIR/uploads"
if [ -d "$WORKDIR/uploads" ]; then
    cp -an "$WORKDIR/uploads/." "$DATA_DIR/uploads/" 2>/dev/null || true
    echo "Imported uploads/ -> $DATA_DIR/uploads/"
fi

echo ""
echo "Done. Sync Dashboard env vars from imported secrets:"
if [ -f "$DATA_DIR/.secret_key" ]; then
    echo "  SECRET_KEY=$(tr -d '\n' < "$DATA_DIR/.secret_key")"
fi
if [ -f "$DATA_DIR/.gm_pin" ]; then
    echo "  GM_PIN=$(tr -d '\n' < "$DATA_DIR/.gm_pin")"
fi
echo "Then trigger Manual Deploy (or push to main)."