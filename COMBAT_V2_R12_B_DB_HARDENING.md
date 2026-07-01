# COMBAT_V2_R12_B_DB_HARDENING（局部審計 · SQLite 併發與資料 SSOT）

> **目的**：審計 **20 人西貢戶外** 資料層 — WAL 模式、orphan `combat_actions`、主角狀態單一真相源、斷線重連後端握手  
> **日期**：2026-07-01 · **commit**：`649526a`  
> **Baseline**：假設已讀 `COMBAT_V2_AUDIT_BUNDLE.md`  
> **生成**：`python3 scripts/build_combat_v2_partial_bundles.py`

---

## 0. 給 Gemini 的指令

**焦點問題**：
1. WAL + `busy_timeout` 是否覆蓋最熱寫入路徑（`immediate_transaction`）？殘留直連 `sqlite3.connect` 風險？
2. `purge_combat_actions` 是否在所有戰鬥結束路徑觸發（含 reconcile）？
3. `get_team_protagonists` 是否仍可能讀到 stale `squads.protagonist_stats`？
4. `/session/restore` 的 `current_combat_id` 與 `reconcile_finished_active_combat` 是否一致？

**輸出**：【Critical】→【High/Medium】→【Low】→ 健康度 X/10

---

## 1. SQLite WAL 工廠

"""SQLite transaction helpers (BEGIN IMMEDIATE + rollback)."""
import sqlite3
import time
from contextlib import contextmanager

from models.settings import settings

SQLITE_CONNECT_TIMEOUT = 30.0


def configure_sqlite_connection(conn):
    """
    High-concurrency defaults for camp-scale co-op (WAL + relaxed sync).
    Safe to call on every connection; journal_mode=WAL is idempotent.
    """
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=30000;")


def get_db_connection(db_path=None, *, row_factory=None):
    """Authoritative SQLite connection factory (30s timeout + WAL pragmas)."""
    path = db_path or settings.db_path
    conn = sqlite3.connect(path, timeout=SQLITE_CONNECT_TIMEOUT)
    if row_factory is not None:
        conn.row_factory = row_factory
    configure_sqlite_connection(conn)
    return conn


def ensure_wal_mode(db_path=None):
    """Persist WAL journal mode at bootstrap (called from init_db / migrate_db)."""
    conn = get_db_connection(db_path)
    try:
        mode = conn.execute("PRAGMA journal_mode;").fetchone()
        return (mode[0] if mode else "").lower() == "wal"
    finally:
        conn.close()


def with_db_retry(operation, max_attempts=5, base_delay=0.05):
    """Retry SQLite operations that fail with database is locked."""
    last_error = None
    for attempt in range(max_attempts):
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            last_error = exc
            if "locked" not in str(exc).lower() or attempt >= max_attempts - 1:
                raise
            time.sleep(base_delay * (attempt + 1))
    if last_error:
        raise last_error


@contextmanager
def immediate_transaction(db_path=None):
    """
    Open a connection, BEGIN IMMEDIATE, yield it, commit on success.
    Rolls back and re-raises on any exception.
    """
    conn = get_db_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

## 2. bootstrap 啟用 WAL

# database.py (L76–L85)


def init_db():
    conn = get_db_connection(_db_path())
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS squads (
        squad_id TEXT PRIMARY KEY,
        sanity INTEGER DEFAULT 50,
        hp INTEGER DEFAULT 100,
        resources INTEGER DEFAULT 0,
# database.py (L196–L212)

    conn.close()
    migrate_db()
    ensure_wal_mode(_db_path())

def _add_column_if_missing(cursor, table, column, typedef, existing_cols):
    if column not in existing_cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {typedef}")


def migrate_db():
    conn = get_db_connection(_db_path())
    c = conn.cursor()

    c.execute("PRAGMA table_info(squads)")
    cols = {row[1] for row in c.fetchall()}
    squad_additions = {
        "power": "INTEGER DEFAULT 100",

## 3. combat_actions 清理

# models/combat.py (L155–L170)

def purge_combat_actions(combat_id, *, conn=None):
    """Remove orphaned phase submissions when a combat room closes."""
    if not combat_id:
        return 0
    if conn is not None:
        cur = conn.execute(
            "DELETE FROM combat_actions WHERE combat_id = ?", (int(combat_id),),
        )
        return cur.rowcount
    with immediate_transaction(settings.db_path) as tx:
        cur = tx.execute(
            "DELETE FROM combat_actions WHERE combat_id = ?", (int(combat_id),),
        )
        return cur.rowcount


# models/combat.py (L1316–L1355)

def _end_combat(combat_id, winner, encounter):
    combat = get_combat(combat_id)
    if not combat:
        return None

    squad = get_squad(combat["squad_id"])
    team_id = squad.get("team_id") if squad else None
    starter_id = combat.get("squad_id")
    now_str = datetime.now().isoformat()
    logs = list(combat.get("logs") or [])
    enemy_hp_val = 0 if winner == "squad" else combat.get("enemy_hp", 100)

    with immediate_transaction() as conn:
        row = conn.execute("SELECT 1 FROM combats WHERE id = ?", (combat_id,)).fetchone()
        if not row:
            return None
        conn.execute(
            """UPDATE combats SET status = 'ended', winner = ?, ended_at = ?, enemy_hp = ?
               WHERE id = ?""",
            (winner, now_str, enemy_hp_val, combat_id),
        )
        purge_combat_actions(combat_id, conn=conn)
        if team_id:
            conn.execute(
                "UPDATE squads SET current_combat_id = NULL WHERE team_id = ?",
                (team_id,),
            )
        else:
            conn.execute(
                "UPDATE squads SET current_combat_id = NULL WHERE squad_id = ?",
                (starter_id,),
            )

    outcome = resolve_combat_outcome(
        winner, team_id, encounter, starter_id, combat_id=combat_id,
    )
    log_messages = outcome.get("log_messages") or []
    if log_messages:
        for entry in log_messages:
            logs.append({

## 4. 主角 SSOT

# models/team.py (L162–L222)

def get_team_protagonists(team_id):
    """
    SSOT: protagonist HP/sanity/trauma from protagonist_states;
    static combat stats from PROTAGONIST_PROFILES (not squads.protagonist_stats JSON).
    """
    from models.protagonist import PROTAGONIST_PROFILES, get_protagonist_state

    clean_team_id = normalize_team_id(team_id)
    default = default_protagonist_template()
    if not clean_team_id:
        return {
            "iggy": default.copy(),
            "marah": default.copy(),
            "active_route": None,
        }

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    team_row = conn.execute(
        "SELECT route FROM teams WHERE team_id = ?", (clean_team_id,)
    ).fetchone()
    conn.close()

    if not team_row:
        return {
            "iggy": default.copy(),
            "marah": default.copy(),
            "active_route": None,
        }

    route = team_row["route"]
    result = {
        "iggy": default.copy(),
        "marah": default.copy(),
        "active_route": route,
    }

    for key in ("iggy", "marah"):
        profile = PROTAGONIST_PROFILES.get(key, {})
        state = get_protagonist_state(clean_team_id, key, create=True)
        entry = {
            **default.copy(),
            "name": profile.get("display_name", key.title()),
            "avatar": profile.get("avatar"),
            "power": int(profile.get("power", default.get("power", 100))),
            "intellect": int(profile.get("intellect", default.get("intellect", 100))),
            "resilience": int(profile.get("resilience", default.get("resilience", 100))),
        }
        if state:
            entry.update({
                "hp": int(state.get("hp", 100)),
                "max_hp": int(state.get("max_hp", 100)),
                "sanity": int(state.get("sanity", 100)),
                "trauma_count": int(state.get("trauma_count", 0)),
                "near_death_until": state.get("near_death_until"),
            })
        result[key] = entry

    return result



## 5. Session restore fast-forward

# routes/auth.py (L94–L122)

def session_restore():
    body = request.json if request.is_json else {}
    token = (body.get("restore_token") or request.form.get("restore_token") or "").strip()
    squad_id = verify_restore_token(token)
    if not squad_id:
        return jsonify({"success": False, "error": "無效或已過期的裝置憑證"}), 401

    squad = get_squad(squad_id)
    if not squad:
        return jsonify({"success": False, "error": "帳號不存在"}), 401

    establish_player_session(squad_id)
    status = build_player_status(squad)
    attach_restore_token(status, squad_id)

    team_id = squad.get("team_id")
    if team_id:
        active_combat = get_active_combat_for_team(team_id)
        if active_combat:
            is_live, combat_id, _enc_id = reconcile_finished_active_combat(
                active_combat, team_id=team_id,
            )
            if is_live and combat_id:
                status["current_combat_id"] = combat_id
                status["combat_status_interrupted"] = active_combat.get("status")

    return jsonify(status)



## 6. 測試

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


def test_reconcile_finished_combat_purges_actions():
    import sqlite3
    from datetime import datetime

    from models.combat import reconcile_finished_active_combat
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
            "INSERT INTO teams (team_id, team_name, route, created_at) VALUES (?, ?, ?, ?)",
            ("T-PURGE", "Purge Team", "iggy", now),
        )
        conn.execute(
            """INSERT INTO squads
               (squad_id, display_name, team_id, is_team_leader, last_update, current_combat_id)
               VALUES ('solo1', 'Solo', 'T-PURGE', 1, ?, 99)""",
            (now,),
        )
        cur = conn.execute(
            """INSERT INTO combats
               (squad_id, encounter_id, status, enemy_hp, current_phase, started_at)
               VALUES ('solo1', 'enc_test', 'player_phase', 0, 1, ?)""",
            (now,),
        )
        combat_id = cur.lastrowid
        conn.execute(
            "UPDATE squads SET current_combat_id = ? WHERE squad_id = 'solo1'",
            (combat_id,),
        )
        conn.execute(
            """INSERT INTO combat_actions
               (combat_id, squad_id, phase, action_type, dice_result, submitted_at)
               VALUES (?, 'solo1', 0, 'attack', 2, ?)""",
            (combat_id, now),
        )
        conn.commit()
        conn.close()

        combat = {
            "id": combat_id,
            "status": "player_phase",
            "enemy_hp": 0,
            "encounter_id": "enc_test",
        }
        is_live, live_id, _enc = reconcile_finished_active_combat(
            combat, team_id="T-PURGE",
        )
        conn = sqlite3.connect(path)
        remaining = conn.execute(
            "SELECT COUNT(*) FROM combat_actions WHERE combat_id = ?", (combat_id,),
        ).fetchone()[0]
        squad_combat = conn.execute(
            "SELECT current_combat_id FROM squads WHERE squad_id = 'solo1'",
        ).fetchone()[0]
        conn.close()

        if not is_live and live_id is None:
            ok("reconcile finished combat clears active marker")
        else:
            fail("reconcile finished combat clears active marker", str((is_live, live_id)))
        if remaining == 0:
            ok("reconcile finished combat purges stale combat_actions")
        else:
            fail("reconcile finished combat purges stale combat_actions", f"remaining={remaining}")
        if squad_combat is None:
            ok("reconcile finished combat clears squad current_combat_id")
        else:
            fail("reconcile finished combat clears squad current_combat_id", squad_combat)
    finally:
        settings.db_path = old_path
        os.unlink(path)


def main():
    print("=== DB hardening tests ===\n")
    test_wal_mode_enabled()
    test_protagonist_ssot_from_states_table()
    test_purge_combat_actions_on_end()
    test_reconcile_finished_combat_purges_actions()
    test_session_restore_includes_active_combat()
    print(f"\n=== 結果：{PASS} 通過 / {FAIL} 失敗 ===\n")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

---
*End of R12-B · 2026-07-01*
