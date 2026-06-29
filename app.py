#!/usr/bin/env python3
"""
Oikonomia - Summer Camp 2026 Web App Prototype
Built by Grok Build
Priority: Beautiful Dashboard + GPS + Photo Upload
"""

from flask import Flask, jsonify, session
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import sqlite3
import json
import os
import shutil
import zipfile
import io
import re
from datetime import datetime, timedelta
import math
import time
import random
import hmac
import hashlib

from utils.env import is_production_env as _is_production_env

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or (
    None if _is_production_env() else "oikonomia-2026-prototype"
)
if _is_production_env() and not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable is required in production")
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get("RENDER") == "true" or os.environ.get("FLASK_ENV") == "production",
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_PATH="/",
    SESSION_COOKIE_NAME="oikonomia_session",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
)


@app.errorhandler(413)
def upload_too_large(_exc):
    return jsonify({"success": False, "error": "相片檔案太大（上限 8MB）"}), 413
RESTORE_TOKEN_MAX_AGE = int(timedelta(days=30).total_seconds())
_restore_serializer = None

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_data_dir():
    """每個部署環境用獨立 SQLite；PA 由 wsgi.py 設 DATA_DIR=data/。"""
    if os.environ.get("DATA_DIR"):
        return os.environ["DATA_DIR"]
    if os.environ.get("RENDER") == "true" and os.path.isdir("/data"):
        return "/data"
    return os.path.join(PROJECT_DIR, "local_data")

def migrate_legacy_db(target_dir):
    """首次改用 local_data/ 時，從舊路徑複製 oikonomia.db。"""
    target_db = os.path.join(target_dir, "oikonomia.db")
    if os.path.isfile(target_db):
        return
    for legacy_dir in (PROJECT_DIR, os.path.join(PROJECT_DIR, "data")):
        legacy_db = os.path.join(legacy_dir, "oikonomia.db")
        if os.path.isfile(legacy_db):
            shutil.copy2(legacy_db, target_db)
            break
app.static_folder = os.path.join(PROJECT_DIR, "static")
AVATAR_DIR = os.path.join(app.static_folder, "avatars")
PORTRAIT_DIR = os.path.join(app.static_folder, "portraits")
PORTRAIT_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".svg")
os.makedirs(PORTRAIT_DIR, exist_ok=True)

def portrait_static_path(filename):
    """非玩家角色頭像 URL（static/portraits/）。"""
    safe = os.path.basename((filename or "").strip())
    if not safe:
        return "/static/avatars/default.png"
    return f"/static/portraits/{safe}"
DATA_DIR = get_data_dir()
os.makedirs(DATA_DIR, exist_ok=True)
if not os.environ.get("DATA_DIR"):
    migrate_legacy_db(DATA_DIR)

# 上傳圖片固定放喺 project/uploads（PA 同 local 路徑一致，避免 data/uploads 分裂）
UPLOAD_FOLDER = os.path.join(PROJECT_DIR, "uploads")
LEGACY_UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "oikonomia.db")

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

migrate_upload_files()

# ==================== Utils Layer Imports ====================
from utils.uploads import save_task_submission_photo

DEFAULT_PROTAGONIST = {"hp": 100, "sanity": 100, "power": 100, "intellect": 100, "resilience": 100}
SQUAD_ATTRIBUTES = ["hp", "sanity", "power", "intellect", "resilience"]
MAX_INVENTORY_SLOTS = 5

SAMPLE_ITEMS = [
    {
        "name": "裂縫碎片",
        "description": "來自界線的微小碎片，似乎還有溫度。",
        "icon": "🧩",
        "item_type": "story",
        "qr_code_value": "item-001",
        "has_ability": 0,
        "effect_type": None,
        "effect_value": 0,
        "image_path": "/static/images/items/item-001.svg",
    },
    {
        "name": "Judas 的信箋",
        "description": "上面有模糊的字跡，閱讀時 Sanity 會微微波動。",
        "icon": "📜",
        "item_type": "story",
        "qr_code_value": "item-002",
        "has_ability": 1,
        "effect_type": "sanity_up",
        "effect_value": -5,
        "image_path": "/static/images/items/item-002.svg",
    },
    {
        "name": "守護者徽章",
        "description": "掃描營地 QR 後獲得的證物，能強化你的 Resilience。",
        "icon": "🛡️",
        "item_type": "qr",
        "qr_code_value": "item-003",
        "has_ability": 1,
        "effect_type": "resilience_up",
        "effect_value": 8,
        "image_path": "/static/images/items/item-003.svg",
    },
    {
        "name": "記憶之瓶",
        "description": "裝住一段未完成的對話，觸碰時 Sanity 會回復。",
        "icon": "🫙",
        "item_type": "qr",
        "qr_code_value": "item-004",
        "has_ability": 1,
        "effect_type": "sanity_up",
        "effect_value": 5,
        "image_path": "/static/images/items/item-004.svg",
    },
    {
        "name": "界線之鑰",
        "description": "據說可以打開某扇隱藏的門，蘊含強大 Power。",
        "icon": "🗝️",
        "item_type": "special",
        "qr_code_value": "item-005",
        "has_ability": 1,
        "effect_type": "power_up",
        "effect_value": 10,
        "image_path": "/static/images/items/item-005.svg",
    },
]

ITEM_EFFECT_STAT_MAP = {
    "power_up": "power",
    "sanity_up": "sanity",
    "resilience_up": "resilience",
    "hp_up": "hp",
    "intellect_up": "intellect",
}

ITEM_EFFECT_LABELS = {
    "power_up": "力量",
    "sanity_up": "神智",
    "resilience_up": "韌性",
    "hp_up": "生命值",
    "intellect_up": "智力",
}

# ==================== Encounter / Combat ====================
ENCOUNTERS_DIR = os.path.join(PROJECT_DIR, "encounters")
NEAR_DEATH_MINUTES = 15
COMBAT_ACTION_TYPES = (
    "attack", "attack_physical", "attack_nonphysical",
    "defend", "use_item", "use_zoo", "pass",
)
COMBAT_ATTACK_BASE_DAMAGE = 10
ATTACK_ACTION_TYPES = frozenset({
    "attack", "attack_physical", "attack_nonphysical", "use_zoo",
})
DICE_MULTIPLIERS = {0: 0.0, 1: 1.0, 2: 1.5, 3: 2.0}
_encounter_cache = {}

from data.locations import LOCATIONS
from data.story_config import STORY_STAGE_THRESHOLDS, STORY_STAGE_REQUIRED_TASKS
from data.narrative_stories import NARRATIVE_PORTRAITS, NARRATIVE_STORIES

from models import configure as configure_models

configure_models(
    db_path=DB_PATH,
    upload_folder=UPLOAD_FOLDER,
    legacy_upload_folder=LEGACY_UPLOAD_FOLDER,
    default_protagonist=DEFAULT_PROTAGONIST,
    squad_attributes=SQUAD_ATTRIBUTES,
    max_inventory_slots=MAX_INVENTORY_SLOTS,
    encounters_dir=ENCOUNTERS_DIR,
    item_effect_stat_map=ITEM_EFFECT_STAT_MAP,
    item_effect_labels=ITEM_EFFECT_LABELS,
    encounter_cache=_encounter_cache,
    near_death_minutes=NEAR_DEATH_MINUTES,
    combat_action_types=COMBAT_ACTION_TYPES,
    attack_action_types=ATTACK_ACTION_TYPES,
    dice_multipliers=DICE_MULTIPLIERS,
    combat_attack_base_damage=COMBAT_ATTACK_BASE_DAMAGE,
    locations=LOCATIONS,
    story_stage_thresholds=STORY_STAGE_THRESHOLDS,
    story_stage_required_tasks=STORY_STAGE_REQUIRED_TASKS,
    narrative_stories=NARRATIVE_STORIES,
    avatar_dir=AVATAR_DIR,
    portrait_dir=PORTRAIT_DIR,
)

# ==================== Model Layer Imports ====================
from utils.helpers import (
    hkt_timestamp,
    list_image_files,
    normalize_team_id,
    normalize_photo_url,
    photo_public_url,
    safe_zip_arcname,
    resolve_upload_disk_path,
)
from utils.deploy import read_deploy_version
from utils.qr import (
    build_item_qr_payload,
    resolve_item_from_qr_payload,
    sign_qr_token,
)
from utils.validators import parse_status_effects, serialize_status_effects
from models.encounter import (
    load_encounter,
    list_encounter_ids,
    load_all_encounters,
    encounter_route_matches,
    evaluate_precheck_condition,
)
from models.squad import (
    row_to_squad,
    get_squad,
    update_squad,
    get_all_squads,
    fetch_squads_by_ids,
    get_team_members,
    get_team_average_stat,
)
from models.team import (
    resolve_team_display_route,
    official_team_route,
    is_team_leader_session,
    sync_team_route,
    backfill_team_routes_from_members,
    get_next_team_id,
    get_team_by_id,
    get_team_protagonists,
)
from models.item import (
    get_item_by_id,
    get_item_by_qr_code_value,
    format_item_effect_text,
    serialize_item_for_client,
    apply_item_effect_to_squad,
    team_has_item,
    team_has_item_by_name,
    grant_item_to_squad,
)
from models.encounter_outcomes import (
    apply_status_debuff,
    add_insight_fragments,
    encounter_already_completed,
    record_encounter_completion,
    apply_precheck_skip,
    apply_failure_side_effects,
    apply_trauma_on_failure,
    apply_encounter_success,
    apply_encounter_failure,
    apply_encounter_success_solo,
    apply_encounter_failure_solo,
)
from models.combat import (
    row_to_combat,
    get_combat,
    get_combat_by_squad,
    get_active_combat_for_team,
    save_combat,
    set_team_combat_id,
    clear_team_combat_id,
    get_effective_stat,
    get_effective_attack_stat,
    describe_attack_stat,
    calculate_attack_damage,
    calculate_damage_simple,
    calculate_damage,
    calculate_incoming_damage,
    dice_multiplier,
    roll_combat_dice,
    get_combat_phase_actions,
    combat_action_already_submitted,
    upsert_combat_action,
    zoo_bonus_multiplier,
    berserk_probability,
    is_berserk,
    combat_phase_deadline,
    combat_phase_expired,
    get_combat_participants,
    get_active_combat_member_ids,
    get_active_combat_members,
    all_phase_actions_submitted,
    append_combat_log,
    apply_damage_to_player,
    get_lowest_resilience_player,
    resolve_player_phase,
    build_enemy_combat_stats,
    build_combat_status_response,
    build_combat_round_preview,
    build_single_player_preview,
    _combat_outcome_json,
    _build_full_preview_from_status,
    _build_round_resolved_response,
    COMBAT_ACTION_TYPES,
    ATTACK_ACTION_TYPES,
    DICE_MULTIPLIERS,
    COMBAT_ATTACK_BASE_DAMAGE,
    create_combat_record,
)

# ==================== Service Layer Imports ====================
from services.announcements import list_announcements
from services.global_events import apply_global_effect, create_global_event
from services.player_status import build_player_status
from services.story import (
    count_team_distinct_tasks,
    get_pending_story_id,
    is_story_viewed,
    mark_story_viewed,
    narrative_story_id_for_stage,
    resolve_story_stage,
)
from services.teams_overview import (
    build_active_combats_overview,
    build_teams_overview,
    get_all_teams_with_stats,
    query_teams_list,
)
from utils.tasks import task_display_name
from services.narrative import (
    enrich_story_lines,
    get_available_narrative_stories,
    get_story_for_route,
    next_stage_threshold,
)

# ==================== 向後兼容層（逐步移除） ====================
_enrich_story_lines = enrich_story_lines
_create_combat_record = create_combat_record


def register_blueprints():
    """Register route blueprints after app module is fully initialized."""
    from routes.auth import auth_bp
    from routes.player import player_bp
    from routes.combat import combat_bp
    from routes.gm import gm_bp
    from routes.team import team_bp
    from routes.misc import misc_bp
    from routes.story import story_bp
    from routes.encounters import encounters_bp
    from routes.items import items_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(player_bp)
    app.register_blueprint(combat_bp)
    app.register_blueprint(gm_bp)
    app.register_blueprint(team_bp)
    app.register_blueprint(misc_bp)
    app.register_blueprint(story_bp)
    app.register_blueprint(encounters_bp)
    app.register_blueprint(items_bp)


def init_db():
    conn = sqlite3.connect(DB_PATH)
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

def migrate_db():
    conn = sqlite3.connect(DB_PATH)
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
        if col not in cols:
            try:
                c.execute(f"ALTER TABLE squads ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass
    if "display_name" not in cols:
        try:
            c.execute("ALTER TABLE squads ADD COLUMN display_name TEXT")
        except sqlite3.OperationalError:
            pass
    # === 新增 PIN 欄位 ===
    if "pin" not in cols:
        try:
            c.execute("ALTER TABLE squads ADD COLUMN pin TEXT")
        except sqlite3.OperationalError:
            pass
    if "avatar" not in cols:
        try:
            c.execute("ALTER TABLE squads ADD COLUMN avatar TEXT")
        except sqlite3.OperationalError:
            pass
    if "insight_fragments" not in cols:
        try:
            c.execute("ALTER TABLE squads ADD COLUMN insight_fragments INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
    if "status_effects" not in cols:
        try:
            c.execute("ALTER TABLE squads ADD COLUMN status_effects TEXT DEFAULT '{}'")
        except sqlite3.OperationalError:
            pass
    squad_trauma_cols = {
        "trauma_resilience": "INTEGER DEFAULT 0",
        "trauma_power": "INTEGER DEFAULT 0",
        "trauma_intellect": "INTEGER DEFAULT 0",
        "near_death_until": "TEXT",
        "current_combat_id": "INTEGER",
    }
    for col, typedef in squad_trauma_cols.items():
        if col not in cols:
            try:
                c.execute(f"ALTER TABLE squads ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass
    if "max_hp" not in cols:
        try:
            c.execute("ALTER TABLE squads ADD COLUMN max_hp INTEGER DEFAULT 100")
            c.execute(
                "UPDATE squads SET max_hp = MAX(COALESCE(hp, 100), 100) "
                "WHERE max_hp IS NULL OR max_hp < 100"
            )
        except sqlite3.OperationalError:
            pass
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='protagonist_states'")
    if not c.fetchone():
        c.execute('''CREATE TABLE protagonist_states (
            team_id TEXT NOT NULL,
            protagonist TEXT NOT NULL,
            hp INTEGER DEFAULT 100,
            max_hp INTEGER DEFAULT 100,
            sanity INTEGER DEFAULT 100,
            trauma_count INTEGER DEFAULT 0,
            near_death_until TEXT,
            last_updated TEXT,
            PRIMARY KEY (team_id, protagonist)
        )''')
    if "stats_allocated" not in cols:
        try:
            c.execute("ALTER TABLE squads ADD COLUMN stats_allocated INTEGER DEFAULT 0")
            c.execute(
                "UPDATE squads SET stats_allocated = 1 "
                "WHERE COALESCE(stats_allocated, 0) = 0 "
                "AND (COALESCE(power, 100) != 10 OR COALESCE(intellect, 100) != 10 "
                "OR COALESCE(resilience, 100) != 10 OR pin IS NOT NULL)"
            )
        except sqlite3.OperationalError:
            pass
    c.execute(
        "UPDATE squads SET protagonist_stats = ? WHERE protagonist_stats IS NULL",
        (json.dumps(DEFAULT_PROTAGONIST),),
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
    }
    for col, typedef in team_additions.items():
        if col not in team_cols:
            try:
                c.execute(f"ALTER TABLE teams ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass

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
        if col not in item_cols:
            try:
                c.execute(f"ALTER TABLE items ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass

    missing_qr_rows = c.execute("""
        SELECT id FROM items
        WHERE qr_code_value IS NULL OR TRIM(qr_code_value) = ''
    """).fetchall()
    for row in missing_qr_rows:
        c.execute(
            "UPDATE items SET qr_code_value = ? WHERE id = ?",
            (f"item-{row[0]:03d}", row[0]),
        )

    try:
        c.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_items_qr_code_value
            ON items(qr_code_value)
            WHERE qr_code_value IS NOT NULL AND TRIM(qr_code_value) != ''
        """)
    except sqlite3.OperationalError:
        pass

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
            completed_at TEXT,
            UNIQUE(team_id, encounter_id)
        )''')

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
        if col not in combat_cols:
            try:
                c.execute(f"ALTER TABLE combats ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass

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

    conn.commit()
    conn.close()
    try:
        backfill_team_routes_from_members()
    except Exception as e:
        print(f"[oikonomia] backfill_team_routes_from_members failed: {e}", flush=True)


def _safe_init_db():
    import utils.app_state as app_state
    try:
        init_db()
    except Exception as e:
        app_state.DB_INIT_ERROR = str(e)
        print(f"[oikonomia] init_db failed: {e}", flush=True)


_safe_init_db()

from services.session_auth import (
    attach_restore_token,
    establish_player_session,
    make_restore_token,
    verify_restore_token,
)

# ==================== Routes ====================
@app.before_request
def refresh_player_session():
    if "squad_id" in session or session.get("is_gm"):
        session.permanent = True


@app.after_request
def prevent_html_cache(response):
    """避免手機瀏覽器快取舊版內嵌 HTML/JS。"""
    if response.content_type and "text/html" in response.content_type:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response



register_blueprints()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "1").lower() in ("1", "true", "yes")
    print(f"\n  Oikonomia 本地伺服器")
    print(f"  ➜  http://localhost:{port}")
    print(f"  （注意：macOS 嘅 5000 port 通常被系統佔用，請用 {port}）\n")
    try:
        app.run(host="0.0.0.0", port=port, debug=debug)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"\n  ❌ Port {port} 已被佔用。請執行：")
            print(f"     lsof -ti:{port} | xargs kill -9")
            print(f"  或者用其他 port：PORT=5002 python3 app.py\n")
        raise