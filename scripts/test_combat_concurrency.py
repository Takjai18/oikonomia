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
        ) VALUES ('p1', 'test_combat_01', 'player_phase', 0, 500, 10, 50, 5, 'Boss', '{}', '[]', ?, ?)
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


if __name__ == "__main__":
    raise SystemExit(main())