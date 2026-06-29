#!/usr/bin/env python3
"""Concurrent combat submit / resolve smoke test (local temp DB)."""
import os
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from models import combat as combat_model
from models.settings import settings


def _bootstrap_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE squads (
            squad_id TEXT PRIMARY KEY,
            display_name TEXT,
            hp INTEGER DEFAULT 100,
            max_hp INTEGER DEFAULT 100,
            sanity INTEGER DEFAULT 50,
            power INTEGER DEFAULT 20,
            intellect INTEGER DEFAULT 20,
            resilience INTEGER DEFAULT 20,
            team_id TEXT,
            is_team_leader INTEGER DEFAULT 0,
            route TEXT,
            zoo_skills TEXT,
            near_death_until TEXT,
            current_combat_id INTEGER
        );
        CREATE TABLE combats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            squad_id TEXT,
            encounter_id TEXT,
            status TEXT,
            current_phase INTEGER DEFAULT 0,
            enemy_hp INTEGER,
            enemy_resilience INTEGER,
            enemy_sanity INTEGER,
            enemy_base_damage INTEGER,
            enemy_name TEXT,
            phase_actions TEXT,
            logs TEXT,
            phase_started_at TEXT,
            phase_deadline TEXT,
            started_at TEXT
        );
        CREATE TABLE combat_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            combat_id INTEGER,
            squad_id TEXT,
            phase INTEGER,
            action_type TEXT,
            dice_result INTEGER,
            item_id INTEGER,
            submitted_at TEXT,
            UNIQUE(combat_id, squad_id, phase)
        );
        """
    )
    for sid in ("p1", "p2", "p3", "p4"):
        conn.execute(
            "INSERT INTO squads (squad_id, display_name, team_id, hp, power, resilience) VALUES (?, ?, 'T1', 100, 30, 20)",
            (sid, sid),
        )
    conn.execute(
        """
        INSERT INTO combats (
            squad_id, encounter_id, status, current_phase, enemy_hp,
            enemy_resilience, enemy_sanity, enemy_base_damage, enemy_name,
            phase_actions, logs, phase_started_at, started_at
        ) VALUES ('p1', 'test-enc', 'player_phase', 0, 500, 10, 50, 5, 'Boss', '{}', '[]', datetime('now'), datetime('now'))
        """
    )
    combat_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute("UPDATE squads SET current_combat_id = ? WHERE squad_id = 'p1'", (combat_id,))
    conn.commit()
    conn.close()
    return combat_id


def main():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    original = settings.db_path
    settings.db_path = db_path
    combat_id = _bootstrap_db(db_path)

    errors = []
    resolve_results = []

    def worker(squad_id):
        try:
            combat_model.upsert_combat_action(
                combat_id, squad_id, 0, "attack", 6, None,
            )
            combat, winner = combat_model.resolve_player_phase(combat_id)
            resolve_results.append((squad_id, combat.get("status") if combat else None, winner))
        except Exception as exc:
            errors.append(f"{squad_id}: {exc}")

    threads = [threading.Thread(target=worker, args=(f"p{i}",)) for i in range(1, 5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    settings.db_path = original
    os.unlink(db_path)

    if errors:
        print("FAIL errors:", errors)
        return 1

    ended = [r for r in resolve_results if r[1] in ("enemy_phase", "ended", "player_phase")]
    resolving_only = [r for r in resolve_results if r[1] == combat_model.COMBAT_STATUS_RESOLVING]
    print("resolve_results:", resolve_results)
    if len(ended) < 1:
        print("FAIL: no successful resolve")
        return 1
    if len(ended) > 1:
        print("FAIL: double resolve detected")
        return 1
    print("OK: single resolve under concurrent workers")
    if resolving_only:
        print("note: some workers saw transient resolving state:", resolving_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())