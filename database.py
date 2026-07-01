"""Database bootstrap, schema creation, and migrations."""
import json
import os
import shutil
import sqlite3
from datetime import datetime

from models.settings import settings
from models.team import backfill_team_routes_from_members
from utils.db_tx import ensure_wal_mode, get_db_connection
from utils.env import is_production_env as _is_production_env

# Populated by configure_database() from app.py before bootstrap.
DB_PATH = None
DATA_DIR = None
UPLOAD_FOLDER = None
LEGACY_UPLOAD_FOLDER = None
SAMPLE_ITEMS = []


def configure_database(*, db_path, data_dir, upload_folder, legacy_upload_folder, sample_items):
    global DB_PATH, DATA_DIR, UPLOAD_FOLDER, LEGACY_UPLOAD_FOLDER, SAMPLE_ITEMS
    DB_PATH = db_path
    DATA_DIR = data_dir
    UPLOAD_FOLDER = upload_folder
    LEGACY_UPLOAD_FOLDER = legacy_upload_folder
    SAMPLE_ITEMS = sample_items


def _db_path():
    return DB_PATH or settings.db_path


def migrate_upload_files():
    """把舊版 data/uploads 的檔案搬到 project/uploads"""
    if not os.path.isdir(LEGACY_UPLOAD_FOLDER):
        return 0
    if os.path.abspath(LEGACY_UPLOAD_FOLDER) == os.path.abspath(UPLOAD_FOLDER):
        return 0
    moved = 0
    for name in os.listdir(LEGACY_UPLOAD_FOLDER):
        src = os.path.join(LEGACY_UPLOAD_FOLDER, name)
        dst = os.path.join(UPLOAD_FOLDER, name)
        if not os.path.isfile(src):
            continue
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
            moved += 1
    return moved


def should_auto_bootstrap_db():
    """Production workers skip DB/file migration; deploy script runs bootstrap once."""
    if os.environ.get("OIKONOMIA_SKIP_DB_BOOTSTRAP", "").lower() in ("1", "true", "yes"):
        return False
    if _is_production_env():
        return False
    return True


def bootstrap_app_data():
    """Legacy upload migration + DB schema (file-locked). Deploy script calls this in production."""
    import fcntl

    lock_path = os.path.join(DATA_DIR, ".db_bootstrap.lock")
    with open(lock_path, "a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            moved = migrate_upload_files()
            if moved:
                print(f"[oikonomia] migrated {moved} upload file(s) to {UPLOAD_FOLDER}", flush=True)
            init_db()
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def init_db():
    conn = get_db_connection(_db_path())
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS squads (
        squad_id TEXT PRIMARY KEY,
        sanity INTEGER DEFAULT 50,
        hp INTEGER DEFAULT 100,
        resources INTEGER DEFAULT 0,
        zoo_skills TEXT DEFAULT '[]',
        last_update TEXT,
        power INTEGER DEFAULT 100,
        intellect INTEGER DEFAULT 100,
        resilience INTEGER DEFAULT 100,
        route TEXT,
        protagonist_stats TEXT,
        team_id TEXT,
        is_team_leader INTEGER DEFAULT 0,
        display_name TEXT,
        pin TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        squad_id TEXT,
        task_id TEXT,
        content TEXT,
        photo_path TEXT,
        timestamp TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS teams (
        team_id TEXT PRIMARY KEY,
        team_name TEXT NOT NULL,
        route TEXT,
        created_at TEXT,
        leader_squad_id TEXT,
        gm_notes TEXT DEFAULT ''
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS global_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        effect_type TEXT,
        effect_value INTEGER DEFAULT 0,
        created_by TEXT DEFAULT 'GM',
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        icon TEXT,
        qr_code_value TEXT UNIQUE,
        item_type TEXT DEFAULT 'normal',
        is_active INTEGER DEFAULT 1,
        is_one_time_use INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS qr_code_uses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL UNIQUE,
        squad_id TEXT NOT NULL,
        team_id TEXT,
        used_at TEXT DEFAULT CURRENT_TIMESTAMP,
        source TEXT,
        FOREIGN KEY (item_id) REFERENCES items(id),
        FOREIGN KEY (squad_id) REFERENCES squads(squad_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS player_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        squad_id TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        obtained_at TEXT DEFAULT CURRENT_TIMESTAMP,
        source TEXT,
        FOREIGN KEY (squad_id) REFERENCES squads(squad_id),
        FOREIGN KEY (item_id) REFERENCES items(id),
        UNIQUE(squad_id, item_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS encounter_completions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id TEXT NOT NULL,
        encounter_id TEXT NOT NULL,
        outcome TEXT NOT NULL,
        unlocks TEXT DEFAULT '[]',
        narrative TEXT,
        rewards TEXT,
        completed_at TEXT,
        UNIQUE(team_id, encounter_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS combats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        squad_id TEXT NOT NULL,
        encounter_id TEXT NOT NULL,
        status TEXT DEFAULT 'precheck',
        current_phase INTEGER DEFAULT 0,
        enemy_name TEXT,
        enemy_hp INTEGER,
        enemy_max_hp INTEGER,
        enemy_resilience INTEGER,
        enemy_sanity INTEGER,
        enemy_base_damage INTEGER,
        phase_actions TEXT DEFAULT '{}',
        logs TEXT DEFAULT '[]',
        phase_started_at TEXT,
        phase_deadline TEXT,
        started_at TEXT,
        ended_at TEXT,
        winner TEXT,
        FOREIGN KEY (squad_id) REFERENCES squads(squad_id)
    )''')

    conn.commit()
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
        "intellect": "INTEGER DEFAULT 100",
        "resilience": "INTEGER DEFAULT 100",
        "route": "TEXT",
        "protagonist_stats": "TEXT",
        "team_id": "TEXT",
        "is_team_leader": "INTEGER DEFAULT 0",
    }
    for col, typedef in squad_additions.items():
        _add_column_if_missing(c, "squads", col, typedef, cols)
    _add_column_if_missing(c, "squads", "display_name", "TEXT", cols)
    _add_column_if_missing(c, "squads", "pin", "TEXT", cols)
    _add_column_if_missing(c, "squads", "avatar", "TEXT", cols)
    _add_column_if_missing(c, "squads", "insight_fragments", "INTEGER DEFAULT 0", cols)
    _add_column_if_missing(c, "squads", "status_effects", "TEXT DEFAULT '{}'", cols)
    squad_trauma_cols = {
        "trauma_resilience": "INTEGER DEFAULT 0",
        "trauma_power": "INTEGER DEFAULT 0",
        "trauma_intellect": "INTEGER DEFAULT 0",
        "near_death_until": "TEXT",
        "current_combat_id": "INTEGER",
    }
    for col, typedef in squad_trauma_cols.items():
        _add_column_if_missing(c, "squads", col, typedef, cols)
    if "max_hp" not in cols:
        c.execute("ALTER TABLE squads ADD COLUMN max_hp INTEGER DEFAULT 100")
        c.execute(
            "UPDATE squads SET max_hp = MAX(COALESCE(hp, 100), 100) "
            "WHERE max_hp IS NULL OR max_hp < 100"
        )
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='protagonist_states'")
    if not c.fetchone():
        c.execute('''CREATE TABLE protagonist_states (
            team_id TEXT NOT NULL,
            protagonist TEXT NOT NULL,
            hp INTEGER NOT NULL DEFAULT 100,
            max_hp INTEGER NOT NULL DEFAULT 100,
            sanity INTEGER NOT NULL DEFAULT 100,
            trauma_count INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            near_death_until TEXT,
            last_updated TEXT,
            PRIMARY KEY (team_id, protagonist)
        )''')
    else:
        c.execute("PRAGMA table_info(protagonist_states)")
        ps_cols = {row[1] for row in c.fetchall()}
        _add_column_if_missing(
            c, "protagonist_states", "is_active", "INTEGER NOT NULL DEFAULT 1", ps_cols
        )
    if "stats_allocated" not in cols:
        c.execute("ALTER TABLE squads ADD COLUMN stats_allocated INTEGER DEFAULT 0")
        c.execute(
            "UPDATE squads SET stats_allocated = 1 "
            "WHERE COALESCE(stats_allocated, 0) = 0 "
            "AND (COALESCE(power, 100) != 10 OR COALESCE(intellect, 100) != 10 "
            "OR COALESCE(resilience, 100) != 10 OR pin IS NOT NULL)"
        )
    default_protagonist = settings.default_protagonist or {
        "hp": 100,
        "sanity": 100,
        "power": 100,
        "intellect": 100,
        "resilience": 100,
    }
    c.execute(
        "UPDATE squads SET protagonist_stats = ? WHERE protagonist_stats IS NULL",
        (json.dumps(default_protagonist),),
    )

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='teams'")
    if not c.fetchone():
        c.execute('''CREATE TABLE teams (
            team_id TEXT PRIMARY KEY,
            team_name TEXT NOT NULL,
            route TEXT,
            created_at TEXT,
            leader_squad_id TEXT,
            gm_notes TEXT DEFAULT ''
        )''')

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='global_events'")
    if not c.fetchone():
        c.execute('''CREATE TABLE global_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            effect_type TEXT,
            effect_value INTEGER DEFAULT 0,
            created_by TEXT DEFAULT 'GM',
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
    else:
        c.execute("PRAGMA table_info(global_events)")
        ge_cols = {row[1] for row in c.fetchall()}
        if "title" not in ge_cols:
            c.execute('''CREATE TABLE global_events_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                effect_type TEXT,
                effect_value INTEGER DEFAULT 0,
                created_by TEXT,
                timestamp TEXT
            )''')
            if "message" in ge_cols:
                c.execute("""
                    INSERT INTO global_events_new
                        (title, description, effect_type, effect_value, created_by, timestamp)
                    SELECT message, message, event_type, 0, 'GM', timestamp
                    FROM global_events
                """)
            c.execute("DROP TABLE global_events")
            c.execute("ALTER TABLE global_events_new RENAME TO global_events")

    c.execute("PRAGMA table_info(teams)")
    team_cols = {row[1] for row in c.fetchall()}
    team_additions = {
        "leader_squad_id": "TEXT",
        "gm_notes": "TEXT DEFAULT ''",
        "ending_type": "TEXT",
        "ending_locked_at": "TEXT",
    }
    for col, typedef in team_additions.items():
        _add_column_if_missing(c, "teams", col, typedef, team_cols)

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
    if not c.fetchone():
        c.execute('''CREATE TABLE items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            icon TEXT,
            qr_code_value TEXT UNIQUE,
            item_type TEXT DEFAULT 'normal',
            is_active INTEGER DEFAULT 1,
            is_one_time_use INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

    c.execute("PRAGMA table_info(items)")
    item_cols = {row[1] for row in c.fetchall()}
    item_additions = {
        "qr_code_value": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "is_one_time_use": "INTEGER DEFAULT 1",
        "effect_type": "TEXT",
        "effect_value": "INTEGER DEFAULT 0",
        "has_ability": "INTEGER DEFAULT 0",
        "image_path": "TEXT",
    }
    for col, typedef in item_additions.items():
        _add_column_if_missing(c, "items", col, typedef, item_cols)

    missing_qr_rows = c.execute("""
        SELECT id FROM items
        WHERE qr_code_value IS NULL OR TRIM(qr_code_value) = ''
    """).fetchall()
    for row in missing_qr_rows:
        c.execute(
            "UPDATE items SET qr_code_value = ? WHERE id = ?",
            (f"item-{row[0]:03d}", row[0]),
        )

    c.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_items_qr_code_value
        ON items(qr_code_value)
        WHERE qr_code_value IS NOT NULL AND TRIM(qr_code_value) != ''
    """)

    c.execute("UPDATE items SET is_active = 1 WHERE is_active IS NULL")
    c.execute("UPDATE items SET is_one_time_use = 1 WHERE is_one_time_use IS NULL")
    c.execute("UPDATE items SET is_one_time_use = 0 WHERE item_type = 'story'")

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='qr_code_uses'")
    if not c.fetchone():
        c.execute('''CREATE TABLE qr_code_uses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL UNIQUE,
            squad_id TEXT NOT NULL,
            team_id TEXT,
            used_at TEXT DEFAULT CURRENT_TIMESTAMP,
            source TEXT,
            FOREIGN KEY (item_id) REFERENCES items(id),
            FOREIGN KEY (squad_id) REFERENCES squads(squad_id)
        )''')

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='player_items'")
    if not c.fetchone():
        c.execute('''CREATE TABLE player_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            squad_id TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            obtained_at TEXT DEFAULT CURRENT_TIMESTAMP,
            source TEXT,
            FOREIGN KEY (squad_id) REFERENCES squads(squad_id),
            FOREIGN KEY (item_id) REFERENCES items(id),
            UNIQUE(squad_id, item_id)
        )''')

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='encounter_completions'")
    if not c.fetchone():
        c.execute('''CREATE TABLE encounter_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT NOT NULL,
            encounter_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            unlocks TEXT DEFAULT '[]',
            narrative TEXT,
            rewards TEXT,
            completed_at TEXT,
            UNIQUE(team_id, encounter_id)
        )''')
    else:
        c.execute("PRAGMA table_info(encounter_completions)")
        ec_cols = {row[1] for row in c.fetchall()}
        _add_column_if_missing(c, "encounter_completions", "rewards", "TEXT", ec_cols)

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='combats'")
    if not c.fetchone():
        c.execute('''CREATE TABLE combats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            squad_id TEXT NOT NULL,
            encounter_id TEXT NOT NULL,
            status TEXT DEFAULT 'precheck',
            current_phase INTEGER DEFAULT 0,
            enemy_name TEXT,
            enemy_hp INTEGER,
            enemy_max_hp INTEGER,
            enemy_resilience INTEGER,
            enemy_sanity INTEGER,
            enemy_base_damage INTEGER,
            phase_actions TEXT DEFAULT '{}',
            logs TEXT DEFAULT '[]',
            phase_started_at TEXT,
            phase_deadline TEXT,
            started_at TEXT,
            ended_at TEXT,
            winner TEXT,
            FOREIGN KEY (squad_id) REFERENCES squads(squad_id)
        )''')

    c.execute("PRAGMA table_info(combats)")
    combat_cols = {row[1] for row in c.fetchall()}
    for col, typedef in {
        "enemy_power": "INTEGER",
        "enemy_intellect": "INTEGER",
    }.items():
        _add_column_if_missing(c, "combats", col, typedef, combat_cols)

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='story_views'")
    if not c.fetchone():
        c.execute('''CREATE TABLE story_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            squad_id TEXT NOT NULL,
            story_id TEXT NOT NULL,
            viewed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(squad_id, story_id),
            FOREIGN KEY (squad_id) REFERENCES squads(squad_id)
        )''')

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='combat_actions'")
    if not c.fetchone():
        c.execute('''CREATE TABLE combat_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            combat_id INTEGER NOT NULL,
            squad_id TEXT NOT NULL,
            phase INTEGER NOT NULL,
            action_type TEXT,
            dice_result INTEGER,
            item_id INTEGER,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(combat_id, squad_id, phase),
            FOREIGN KEY (combat_id) REFERENCES combats(id)
        )''')
        try:
            active_rows = c.execute(
                "SELECT id, current_phase, phase_actions FROM combats WHERE status = 'player_phase'"
            ).fetchall()
            for crow in active_rows:
                try:
                    actions = json.loads(crow["phase_actions"] or "{}")
                except (json.JSONDecodeError, TypeError):
                    actions = {}
                for squad_id, ad in actions.items():
                    if not isinstance(ad, dict):
                        continue
                    c.execute(
                        """INSERT OR IGNORE INTO combat_actions
                           (combat_id, squad_id, phase, action_type, dice_result, item_id, submitted_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            crow["id"],
                            squad_id,
                            crow["current_phase"] or 0,
                            ad.get("action_type"),
                            ad.get("dice_result"),
                            ad.get("item_id"),
                            datetime.now().isoformat(),
                        ),
                    )
        except sqlite3.Error:
            pass

    item_count = c.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    if item_count == 0:
        now = datetime.now().isoformat()
        for entry in SAMPLE_ITEMS:
            is_one_time = 0 if entry["item_type"] == "story" else 1
            c.execute(
                """INSERT INTO items
                   (name, description, icon, item_type, qr_code_value, is_active,
                    is_one_time_use, has_ability, effect_type, effect_value,
                    image_path, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)""",
                (
                    entry["name"],
                    entry["description"],
                    entry["icon"],
                    entry["item_type"],
                    entry["qr_code_value"],
                    is_one_time,
                    entry.get("has_ability", 0),
                    entry.get("effect_type"),
                    entry.get("effect_value", 0),
                    entry.get("image_path"),
                    now,
                ),
            )
    else:
        for entry in SAMPLE_ITEMS:
            c.execute(
                """UPDATE items
                   SET has_ability = ?, effect_type = ?, effect_value = ?,
                       image_path = COALESCE(NULLIF(image_path, ''), ?),
                       description = ?
                   WHERE qr_code_value = ?""",
                (
                    entry.get("has_ability", 0),
                    entry.get("effect_type"),
                    entry.get("effect_value", 0),
                    entry.get("image_path"),
                    entry["description"],
                    entry["qr_code_value"],
                ),
            )

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='protagonist_trauma_log'")
    if not c.fetchone():
        c.execute('''CREATE TABLE protagonist_trauma_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT NOT NULL,
            protagonist TEXT NOT NULL,
            delta INTEGER NOT NULL,
            reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

    conn.commit()
    conn.close()
    try:
        backfill_team_routes_from_members()
    except Exception as e:
        print(f"[oikonomia] backfill_team_routes_from_members failed: {e}", flush=True)


def safe_init_db():
    import utils.app_state as app_state
    if not should_auto_bootstrap_db():
        return
    try:
        bootstrap_app_data()
    except Exception as e:
        app_state.DB_INIT_ERROR = str(e)
        print(f"[oikonomia] init_db failed: {e}", flush=True)
