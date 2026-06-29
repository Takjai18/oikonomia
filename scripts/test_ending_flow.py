#!/usr/bin/env python3
"""Regression tests for services/ending.py (Phase 1 orchestrator)."""
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime

TEST_DIR = tempfile.mkdtemp(prefix="oikonomia_ending_test_")
os.environ["DATA_DIR"] = TEST_DIR

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as oikonomia  # noqa: E402
from models.protagonist import (
    TRAUMA_BAD_ENDING_LIMIT,
    initialize_protagonist_for_team,
    update_protagonist_state,
)
from services.ending import (
    apply_ending,
    build_trauma_summary,
    is_ending_orchestrator_enabled,
    judge_ending,
    preview_ending_for_players,
)

oikonomia.init_db()
oikonomia.migrate_db()

PASS = 0
FAIL = 0
TEAM = "TEAM-98"


def _ensure_team_row(team_id, route="iggy"):
    conn = sqlite3.connect(os.path.join(TEST_DIR, "oikonomia.db"))
    conn.execute(
        "INSERT OR IGNORE INTO teams (team_id, team_name, route, created_at) VALUES (?, ?, ?, ?)",
        (team_id, "Ending Test Team", route, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def ok(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}" + (f" — {detail}" if detail else ""))


def test_trauma_bands():
    _ensure_team_row(TEAM)
    initialize_protagonist_for_team(TEAM, "iggy")
    update_protagonist_state(TEAM, "iggy", trauma_count=0, is_active=1)
    ending = judge_ending(TEAM)
    ok("0 trauma → safe", ending.get("trauma_level") == "safe")
    ok("0 trauma → neutral label", ending.get("ending_type_label") == "neutral")
    ok("trauma_summary total", ending.get("trauma_summary", {}).get("total") == 0)

    update_protagonist_state(TEAM, "iggy", trauma_count=2)
    ending = judge_ending(TEAM)
    ok("2 trauma → caution", ending.get("trauma_level") == "caution")
    ok("narrative_key caution", ending.get("narrative_key") == "trauma_caution")

    update_protagonist_state(TEAM, "iggy", trauma_count=TRAUMA_BAD_ENDING_LIMIT)
    ending = judge_ending(TEAM)
    ok("3 trauma still neutral ending", ending.get("ending_type_label") == "neutral")
    ok("3 trauma critical band", ending.get("trauma_level") == "critical")

    update_protagonist_state(TEAM, "iggy", trauma_count=TRAUMA_BAD_ENDING_LIMIT + 1)
    ending = judge_ending(TEAM)
    ok("4 trauma bad label", ending.get("ending_type_label") == "bad")
    ok("should_apply_bad_ending_victory", ending.get("should_apply_bad_ending_victory") is True)


def test_apply_ending():
    result = apply_ending(TEAM, "bad_ending", source="test_enc")
    ok("apply_ending applied", result.get("applied") is True)
    ending = judge_ending(TEAM)
    ok("locked after apply", ending.get("trauma_level") == "locked")
    ok("is_ending_locked", ending.get("is_ending_locked") is True)
    ok("should_apply false when locked", ending.get("should_apply_bad_ending_victory") is False)


def test_preview_helpers():
    summary = build_trauma_summary(TEAM)
    ok("summary has theology_note", bool(summary.get("theology_note")))
    preview = preview_ending_for_players(TEAM)
    ok("preview has message", bool(preview.get("message")))
    ok("preview locked level", preview.get("level") == "locked")


def test_orchestrator_flag():
    ok("orchestrator default on", is_ending_orchestrator_enabled() is True)
    os.environ["OIKONOMIA_ENDING_ENABLED"] = "0"
    ok("orchestrator env off", is_ending_orchestrator_enabled() is False)
    result = apply_ending(TEAM, "bad_ending")
    ok("apply skipped when disabled", result.get("applied") is False)
    os.environ.pop("OIKONOMIA_ENDING_ENABLED", None)


def test_status_api():
    client = oikonomia.app.test_client()
    client.post("/login", data={"squad_id": "EndingTestPlayer"})
    team_data = client.post("/team/create", data={"team_name": "EndingTest"}).get_json() or {}
    team_id = team_data.get("team_id")
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    if team_id:
        initialize_protagonist_for_team(team_id, "iggy")
        update_protagonist_state(team_id, "iggy", trauma_count=1, is_active=1)

    data = client.get("/status").get_json() or {}
    ok("/status success", data.get("success"))
    ok("/status trauma_summary", isinstance(data.get("trauma_summary"), dict))
    ok("/status ending_preview", isinstance(data.get("ending_preview"), dict))
    ok("/status protagonist_control_status", isinstance(data.get("protagonist_control_status"), dict))


def main():
    print(f"\n=== Ending orchestrator tests (DATA_DIR={TEST_DIR}) ===\n")
    test_trauma_bands()
    test_apply_ending()
    test_preview_helpers()
    test_orchestrator_flag()
    test_status_api()
    print(f"\n=== 結果：{PASS} 通過 / {FAIL} 失敗 ===\n")
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())