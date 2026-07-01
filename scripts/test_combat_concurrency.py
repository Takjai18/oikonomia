#!/usr/bin/env python3
"""Concurrent combat submit / resolve smoke test (local temp DB)."""
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

TEST_DIR = tempfile.mkdtemp(prefix="oikonomia_combat_concurrency_")
os.environ["DATA_DIR"] = TEST_DIR

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import app as oikonomia  # noqa: E402
from models import combat as combat_model

oikonomia.init_db()
oikonomia.migrate_db()


def _seed_combat():
    """Insert a player_phase combat with four squad members on one team."""
    db_path = oikonomia.DB_PATH
    now = datetime.now().isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO teams (team_id, team_name, route, created_at, leader_squad_id) "
        "VALUES ('T1', 'ConcurrencyTest', 'iggy', ?, 'p1')",
        (now,),
    )
    for sid in ("p1", "p2", "p3", "p4"):
        conn.execute(
            """INSERT INTO squads
               (squad_id, display_name, team_id, hp, max_hp, sanity, power, intellect,
                resilience, is_team_leader, route, zoo_skills, last_update)
               VALUES (?, ?, 'T1', 100, 100, 50, 30, 20, 20, ?, 'iggy', '[]', ?)""",
            (sid, sid, 1 if sid == "p1" else 0, now),
        )
    conn.execute(
        """
        INSERT INTO combats (
            squad_id, encounter_id, status, current_phase, enemy_hp,
            enemy_resilience, enemy_sanity, enemy_base_damage, enemy_name,
            phase_actions, logs, phase_started_at, started_at
        ) VALUES ('p1', 'test_combat_01', 'player_phase', 0, 60, 10, 50, 5, 'Boss', '{}', '[]', ?, ?)
        """,
        (now, now),
    )
    combat_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute("UPDATE squads SET current_combat_id = ? WHERE squad_id = 'p1'", (combat_id,))
    conn.commit()
    conn.close()
    return combat_id


def main():
    combat_id = _seed_combat()
    errors = []
    resolve_results = []

    for i in range(1, 5):
        combat_model.upsert_combat_action(
            combat_id, f"p{i}", 0, "attack", 6, None,
        )

    def resolve_worker(squad_id):
        try:
            combat, winner = combat_model.resolve_player_phase(combat_id)
            resolve_results.append((squad_id, combat.get("status") if combat else None, winner))
        except Exception as exc:
            errors.append(f"{squad_id}: {exc}")

    threads = [threading.Thread(target=resolve_worker, args=(f"p{i}",)) for i in range(1, 5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    if errors:
        print("FAIL errors:", errors)
        shutil.rmtree(TEST_DIR, ignore_errors=True)
        return 1

    print("resolve_results:", resolve_results)
    final = combat_model.get_combat(combat_id) or {}
    winners = {winner for _sid, _status, winner in resolve_results if winner}
    if final.get("status") != "ended":
        print("FAIL: combat did not end", final.get("status"))
        shutil.rmtree(TEST_DIR, ignore_errors=True)
        return 1
    if winners != {"squad"}:
        print("FAIL: inconsistent winners", winners)
        shutil.rmtree(TEST_DIR, ignore_errors=True)
        return 1
    summary_logs = [
        entry for entry in (final.get("logs") or [])
        if isinstance(entry, dict) and entry.get("type") == "summary"
    ]
    if len(summary_logs) > 1:
        print("FAIL: duplicate resolve logs detected", len(summary_logs))
        shutil.rmtree(TEST_DIR, ignore_errors=True)
        return 1
    print("OK: single resolve under concurrent workers")
    resolving_only = [r for r in resolve_results if r[1] == combat_model.COMBAT_STATUS_RESOLVING]
    if resolving_only:
        print("note: some workers saw transient resolving state:", resolving_only)
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    return 0


def _seed_team_for_start():
    """Team with route set, no active combat."""
    db_path = oikonomia.DB_PATH
    now = datetime.now().isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO teams (team_id, team_name, route, created_at, leader_squad_id) "
        "VALUES ('T2', 'StartRace', 'iggy', ?, 'sA')",
        (now,),
    )
    conn.execute(
        """INSERT INTO squads
           (squad_id, display_name, team_id, hp, max_hp, sanity, power, intellect,
            resilience, is_team_leader, route, zoo_skills, last_update)
           VALUES ('sA', 'Leader', 'T2', 100, 100, 50, 30, 20, 20, 1, 'iggy', '[]', ?)""",
        (now,),
    )
    conn.commit()
    conn.close()


def test_concurrent_combat_start():
    """Parallel POST /combat/start must create at most one active combat per team."""
    _seed_team_for_start()
    client = oikonomia.app.test_client()
    with client.session_transaction() as sess:
        sess["squad_id"] = "sA"

    results = []
    errors = []

    def start_worker():
        try:
            r = client.post(
                "/combat/start",
                json={"encounter_id": "practice_iggy_01_quick"},
                content_type="application/json",
            )
            results.append((r.status_code, (r.get_json() or {}).get("combat_id")))
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=start_worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    if errors:
        print("FAIL start race errors:", errors)
        return 1

    server_errors = [code for code, _ in results if code >= 500]
    if server_errors:
        print("FAIL: combat/start returned 5xx (e.g. protagonist_states race):", results)
        return 1

    success_ids = [cid for code, cid in results if code == 200 and cid]
    conflict_codes = [code for code, _ in results if code in (400, 409)]
    if len(success_ids) != 1:
        print("FAIL: expected exactly one successful start", results)
        return 1
    if len(set(success_ids)) != 1:
        print("FAIL: multiple distinct combat_ids", success_ids)
        return 1
    if not conflict_codes and len(results) > 1:
        print("note: no explicit conflicts returned;", results)

    db_path = oikonomia.DB_PATH
    conn = sqlite3.connect(db_path)
    active_rows = conn.execute(
        """
        SELECT COUNT(*) FROM combats c
        INNER JOIN squads s ON c.squad_id = s.squad_id
        WHERE UPPER(TRIM(s.team_id)) = 'T2' AND c.status NOT IN ('ended')
        """
    ).fetchone()[0]
    conn.close()
    if active_rows != 1:
        print("FAIL: DB has", active_rows, "active combats for team T2")
        return 1
    print("OK: concurrent combat/start produced single active combat")
    return 0


if __name__ == "__main__":
    raise SystemExit(test_concurrent_combat_start() or main())