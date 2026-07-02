#!/bin/bash
# Generate Render Shell paste script to write oikonomia.db directly to /data.
# Usage: bash deploy/generate-render-shell-db-import.sh [path/to/oikonomia.db]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="${1:-$ROOT/data/oikonomia.db}"
OUT="${OUT:-$ROOT/deploy/artifacts/render-shell-import-db.sh}"

if [ ! -f "$DB" ]; then
    echo "ERROR: missing $DB"
    exit 1
fi

DATA_DIR="$(dirname "$DB")"
B64="$(base64 < "$DB" | tr -d '\n')"
SIZE="$(wc -c < "$DB" | tr -d ' ')"
SECRET_B64=""
GM_B64=""
[ -f "$DATA_DIR/.secret_key" ] && SECRET_B64="$(base64 < "$DATA_DIR/.secret_key" | tr -d '\n')"
[ -f "$DATA_DIR/.gm_pin" ] && GM_B64="$(base64 < "$DATA_DIR/.gm_pin" | tr -d '\n')"

cat > "$OUT" <<SCRIPT
#!/bin/bash
# Paste this ENTIRE script into Render Dashboard → oikonomia → Shell
set -euo pipefail
mkdir -p /data
python3 - <<'PY'
import base64, pathlib, os
db = base64.b64decode("""${B64}""")
pathlib.Path("/data/oikonomia.db").write_bytes(db)
print(f"wrote /data/oikonomia.db ({len(db)} bytes)")
secret_b64 = """${SECRET_B64}"""
gm_b64 = """${GM_B64}"""
if secret_b64:
    pathlib.Path("/data/.secret_key").write_bytes(base64.b64decode(secret_b64))
    os.chmod("/data/.secret_key", 0o600)
    print("wrote /data/.secret_key")
if gm_b64:
    pathlib.Path("/data/.gm_pin").write_bytes(base64.b64decode(gm_b64))
    os.chmod("/data/.gm_pin", 0o600)
    print("wrote /data/.gm_pin")
pathlib.Path("/data/.combat_v2").write_text("1\\n")
print("wrote /data/.combat_v2")
PY
ls -la /data
echo "DB size: \$(du -h /data/oikonomia.db | cut -f1)"
echo "Done. Set Dashboard SECRET_KEY/GM_PIN to match /data files, then Manual Deploy."
SCRIPT

chmod +x "$OUT"
echo "Wrote $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes, db=${SIZE} bytes)"
echo "Copy ALL contents → Render Shell → Enter"