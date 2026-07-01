#!/usr/bin/env python3
"""P0 structural hardening: WAL, session restore combat hint, action purge, protagonist SSOT."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0


def ok(label):
    global PASS
    PASS += 1
    print(f"  ✓ {label}")


def fail(label, detail=""):
    global FAIL
    FAIL += 1
    print(f"  ✗ {label}" + (f" — {detail}" if detail else ""))


def _temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


def test_wal_mode_enabled():
    from database import configure_database, init_db
    from utils.db_tx import ensure_wal_mode, get_db_connection

    path = _temp_db()
    try:
        configure_database(
            db_path=path,
            data_dir=os.path.dirname(path),
            upload_folder=os.path.join(os.path.dirname(path), "uploads"),
            legacy_upload_folder=os.path.join(os.path.dirname(path), "legacy_uploads"),
            sample_items=[],
        )
        init_db()
        if ensure_wal_mode(path):
            ok("WAL journal_mode enabled after init_db")
        else:
            fail("WAL journal_mode enabled after init_db")

        conn = get_db_connection(path)
        try:
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            sync = conn.execute("PRAGMA synchronous;").fetchone()[0]
            if str(mode).lower() == "wal":
                ok("get_db_connection uses WAL")
            else:
                fail("get_db_connection uses WAL", mode)
            if int(sync) == 1:
                ok("get_db_connection synchronous=NORMAL")
            else:
                fail("get_db_connection synchronous=NORMAL", sync)
        finally:
            conn.close()
    finally:
        os.unlink(path)


def test_protagonist_ssot_from_states_table():
    import sqlite3
    from datetime import datetime

    from models.settings import settings
    from models.team import get_team_protagonists
    from utils.db_tx import configure_sqlite_connection

    path = _temp_db()
    old_path = settings.db_path
    settings.db_path = path
    try:
        from database import configure_database, init_db

        configure_database(
            db_path=path,
            data_dir=os.path.dirname(path),
            upload_folder=os.path.join(os.path.dirname(path), "uploads"),
            legacy_upload_folder=os.path.join(os.path.dirname(path), "legacy_uploads"),
            sample_items=[],
        )
        init_db()

        conn = sqlite3.connect(path)
        configure_sqlite_connection(conn)
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO teams (team_id, team_name, route, created_at) VALUES (?, ?, ?, ?)",
            ("T-SSOT", "SSOT Team", "iggy", now),
        )
        conn.execute(
            """INSERT INTO squads
               (squad_id, display_name, team_id, is_team_leader, protagonist_stats, last_update)
               VALUES (?, ?, ?, 1, ?, ?)""",
            (
                "leader1",
                "Leader",
                "T-SSOT",
                json.dumps({"hp": 99, "sanity": 99, "power": 50, "intellect": 50, "resilience": 50}),
                now,
            ),
        )
        conn.execute(
            """INSERT INTO protagonist_states
               (team_id, protagonist, hp, max_hp, sanity, trauma_count, is_active, last_updated)
               VALUES (?, 'iggy', 12, 100, 34, 2, 1, ?)""",
            ("T-SSOT", now),
        )
        conn.commit()
        conn.close()

        protagonists = get_team_protagonists("T-SSOT")
        iggy = protagonists.get("iggy") or {}
        if iggy.get("hp") == 12 and iggy.get("sanity") == 34:
            ok("protagonist SSOT reads hp/sanity from protagonist_states")
        else:
            fail("protagonist SSOT reads hp/sanity from protagonist_states", str(iggy))
        if iggy.get("power") == 100:
            ok("protagonist static stats from PROTAGONIST_PROFILES not stale JSON")
        else:
            fail("protagonist static stats from PROTAGONIST_PROFILES not stale JSON", iggy.get("power"))
    finally:
        settings.db_path = old_path
        os.unlink(path)


def test_purge_combat_actions_on_end():
    import sqlite3
    from datetime import datetime

    from models.combat import purge_combat_actions
    from models.settings import settings
    from utils.db_tx import configure_sqlite_connection

    path = _temp_db()
    old_path = settings.db_path
    settings.db_path = path
    try:
        from database import configure_database, init_db

        configure_database(
            db_path=path,
            data_dir=os.path.dirname(path),
            upload_folder=os.path.join(os.path.dirname(path), "uploads"),
            legacy_upload_folder=os.path.join(os.path.dirname(path), "legacy_uploads"),
            sample_items=[],
        )
        init_db()

        conn = sqlite3.connect(path)
        configure_sqlite_connection(conn)
        now = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO squads (squad_id, display_name, last_update)
               VALUES ('solo1', 'Solo', ?)""",
            (now,),
        )
        cur = conn.execute(
            """INSERT INTO combats
               (squad_id, encounter_id, status, enemy_hp, current_phase, started_at)
               VALUES ('solo1', 'enc_test', 'ended', 0, 1, ?)""",
            (now,),
        )
        combat_id = cur.lastrowid
        conn.execute(
            """INSERT INTO combat_actions
               (combat_id, squad_id, phase, action_type, dice_result, submitted_at)
               VALUES (?, 'solo1', 0, 'attack', 2, ?)""",
            (combat_id, now),
        )
        conn.commit()
        conn.close()

        deleted = purge_combat_actions(combat_id)
        conn = sqlite3.connect(path)
        remaining = conn.execute(
            "SELECT COUNT(*) FROM combat_actions WHERE combat_id = ?", (combat_id,),
        ).fetchone()[0]
        conn.close()
        if deleted >= 1 and remaining == 0:
            ok("purge_combat_actions clears orphaned rows")
        else:
            fail("purge_combat_actions clears orphaned rows", f"deleted={deleted} remaining={remaining}")
    finally:
        settings.db_path = old_path
        os.unlink(path)


def test_session_restore_includes_active_combat():
    import sqlite3
    from datetime import datetime

    from models.combat import get_active_combat_for_team, reconcile_finished_active_combat
    from models.settings import settings
    from models.squad import get_squad
    from utils.db_tx import configure_sqlite_connection

    path = _temp_db()
    old_path = settings.db_path
    settings.db_path = path
    try:
        from database import configure_database, init_db

        configure_database(
            db_path=path,
            data_dir=os.path.dirname(path),
            upload_folder=os.path.join(os.path.dirname(path), "uploads"),
            legacy_upload_folder=os.path.join(os.path.dirname(path), "legacy_uploads"),
            sample_items=[],
        )
        init_db()

        conn = sqlite3.connect(path)
        configure_sqlite_connection(conn)
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO teams (team_id, team_name, route, created_at) VALUES (?, ?, ?, ?)",
            ("T-REST", "Restore Team", "iggy", now),
        )
        conn.execute(
            """INSERT INTO squads
               (squad_id, display_name, team_id, is_team_leader, last_update)
               VALUES ('p1', 'Player', 'T-REST', 1, ?)""",
            (now,),
        )
        cur = conn.execute(
            """INSERT INTO combats
               (squad_id, encounter_id, status, enemy_hp, current_phase, started_at)
               VALUES ('p1', 'enc_test', 'player_phase', 50, 0, ?)""",
            (now,),
        )
        combat_id = cur.lastrowid
        conn.execute(
            "UPDATE squads SET current_combat_id = ? WHERE squad_id = 'p1'", (combat_id,),
        )
        conn.commit()
        conn.close()

        squad = get_squad("p1")
        team_id = squad.get("team_id")
        active = get_active_combat_for_team(team_id)
        is_live, live_id, _enc = reconcile_finished_active_combat(active, team_id=team_id)
        hint = {}
        if is_live and live_id:
            hint["current_combat_id"] = live_id
            hint["combat_status_interrupted"] = active.get("status")

        if hint.get("current_combat_id") == combat_id:
            ok("session restore fast-forward resolves current_combat_id")
        else:
            fail("session restore fast-forward resolves current_combat_id", str(hint))
        if hint.get("combat_status_interrupted") == "player_phase":
            ok("session restore fast-forward resolves combat_status_interrupted")
        else:
            fail("session restore fast-forward resolves combat_status_interrupted", hint)
    finally:
        settings.db_path = old_path
        os.unlink(path)


def main():
    print("=== DB hardening tests ===\n")
    test_wal_mode_enabled()
    test_protagonist_ssot_from_states_table()
    test_purge_combat_actions_on_end()
    test_session_restore_includes_active_combat()
    print(f"\n=== 結果：{PASS} 通過 / {FAIL} 失敗 ===\n")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())