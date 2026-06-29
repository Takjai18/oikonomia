#!/usr/bin/env python3
"""Encounter JSON cache: mtime invalidation smoke test."""
import json
import os
import sys
import tempfile
import time

TEST_DIR = tempfile.mkdtemp(prefix="oikonomia_encounter_cache_")
os.environ["DATA_DIR"] = TEST_DIR

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as oikonomia  # noqa: E402
from models.encounter import load_encounter  # noqa: E402
from models.settings import settings  # noqa: E402

oikonomia.init_db()
oikonomia.migrate_db()

PASS = FAIL = 0


def ok(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}" + (f" — {detail}" if detail else ""))


def main():
    enc_dir = settings.encounters_dir
    os.makedirs(enc_dir, exist_ok=True)
    path = os.path.join(enc_dir, "cache_test.json")
    cache = {}

    from models import configure as configure_models

    configure_models(encounter_cache=cache)

    with open(path, "w", encoding="utf-8") as f:
        json.dump({"encounter_id": "cache_test", "enemy": {"hp": 10}}, f)
    first = load_encounter("cache_test")
    ok("loads encounter", first and first["enemy"]["hp"] == 10)

    with open(path, "w", encoding="utf-8") as f:
        json.dump({"encounter_id": "cache_test", "enemy": {"hp": 99}}, f)
    time.sleep(0.05)
    second = load_encounter("cache_test")
    ok("mtime invalidates cache", second and second["enemy"]["hp"] == 99, str(second))

    os.environ["SKIP_ENCOUNTER_CACHE"] = "1"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"encounter_id": "cache_test", "enemy": {"hp": 42}}, f)
    third = load_encounter("cache_test")
    ok("skip cache reads disk", third and third["enemy"]["hp"] == 42)

    print(f"\n=== 結果：{PASS} 通過 / {FAIL} 失敗 ===\n")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())