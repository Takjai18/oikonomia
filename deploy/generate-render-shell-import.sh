#!/bin/bash
# Generate a one-shot script to paste into Render Shell (imports migration tarball).
# Usage: bash deploy/generate-render-shell-import.sh [tarball]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCHIVE="${1:-$ROOT/deploy/artifacts/oikonomia-render-migrate-latest.tar.gz}"
OUT="${OUT:-$ROOT/deploy/artifacts/render-shell-paste.sh}"

if [ ! -f "$ARCHIVE" ]; then
    echo "ERROR: missing $ARCHIVE — run: bash deploy/render-pack-pa-export.sh"
    exit 1
fi

B64="$(base64 < "$ARCHIVE" | tr -d '\n')"

cat > "$OUT" <<SCRIPT
#!/bin/bash
# Auto-generated Render Shell import — paste entire file into Render Dashboard → Shell
set -euo pipefail
cd /opt/render/project/src
ARCHIVE="/tmp/oikonomia-render-migrate.tar.gz"
python3 - <<'PY'
import base64, pathlib
data = base64.b64decode("""${B64}""")
pathlib.Path("/tmp/oikonomia-render-migrate.tar.gz").write_bytes(data)
print("wrote", len(data), "bytes")
PY
bash deploy/render-import-data.sh "\$ARCHIVE"
bash deploy/render-print-env.sh /data || true
echo "Done. Trigger Manual Deploy in Dashboard."
SCRIPT

chmod +x "$OUT"
echo "Wrote $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes)"
echo "Open this file, copy ALL contents, paste into Render Shell, press Enter."