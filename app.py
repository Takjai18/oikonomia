#!/usr/bin/env python3
"""
Oikonomia - Summer Camp 2026 Web App Prototype
Built by Grok Build
Priority: Beautiful Dashboard + GPS + Photo Upload
"""

from flask import Flask, render_template_string, request, jsonify, session, redirect, send_from_directory, send_file, abort
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

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "oikonomia-2026-prototype")
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get("RENDER") == "true" or os.environ.get("FLASK_ENV") == "production",
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
    PERMANENT_SESSION_LIFETIME=timedelta(days=14),
)

_default_data_dir = "."
if os.environ.get("RENDER") == "true" and os.path.isdir("/data"):
    _default_data_dir = "/data"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
app.static_folder = os.path.join(PROJECT_DIR, "static")
AVATAR_DIR = os.path.join(app.static_folder, "avatars")
DATA_DIR = os.environ.get("DATA_DIR", _default_data_dir)
os.makedirs(DATA_DIR, exist_ok=True)

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

def read_deploy_version():
    version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".deploy-version")
    if os.path.isfile(version_file):
        with open(version_file, encoding="utf-8") as f:
            return f.read().strip()
    return "unknown"

def normalize_photo_url(photo_path):
    """Convert stored path to browser URL segment, e.g. uploads/foo.jpg"""
    if not photo_path:
        return None
    path = str(photo_path).replace("\\", "/")
    if path.startswith("uploads/"):
        return path
    return f"uploads/{os.path.basename(path)}"

def photo_public_url(photo_path):
    normalized = normalize_photo_url(photo_path)
    return f"/{normalized}" if normalized else None

def task_display_name(task_id):
    if not task_id:
        return "未知任務"
    return LOCATIONS.get(task_id, {}).get("name", task_id)

def safe_zip_arcname(*parts):
    name = "_".join(str(p or "unknown") for p in parts)
    return re.sub(r"[^\w\-.]", "_", name)

def resolve_upload_disk_path(filename):
    basename = os.path.basename(str(filename).replace("\\", "/"))
    if not basename:
        return None
    for folder in (UPLOAD_FOLDER, LEGACY_UPLOAD_FOLDER):
        if not folder or not os.path.isdir(folder):
            continue
        path = os.path.join(folder, basename)
        if os.path.isfile(path):
            return path
    return None

DEFAULT_PROTAGONIST = {"hp": 100, "sanity": 100, "power": 100, "intellect": 100, "resilience": 100}
SQUAD_ATTRIBUTES = ["hp", "sanity", "power", "intellect", "resilience"]
MAX_INVENTORY_SLOTS = 5

SAMPLE_ITEMS = [
    ("裂縫碎片", "來自界線的微小碎片，似乎還有溫度。", "🧩", "story"),
    ("Judas 的信箋", "上面有模糊的字跡，閱讀時 Sanity 會微微波動。", "📜", "story"),
    ("守護者徽章", "掃描營地 QR 後獲得的證物。", "🛡️", "qr"),
    ("記憶之瓶", "裝住一段未完成的對話。", "🫙", "qr"),
    ("界線之鑰", "據說可以打開某扇隱藏的門。", "🗝️", "special"),
]

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
        item_type TEXT DEFAULT 'normal',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
            item_type TEXT DEFAULT 'normal',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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

    item_count = c.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    if item_count == 0:
        now = datetime.now().isoformat()
        for name, description, icon, item_type in SAMPLE_ITEMS:
            c.execute(
                "INSERT INTO items (name, description, icon, item_type, created_at) VALUES (?, ?, ?, ?, ?)",
                (name, description, icon, item_type, now),
            )

    conn.commit()
    conn.close()

init_db()

# ==================== 樣本資料（之後容易改） ====================
LOCATIONS = {
    "loc1": {
        "name": "裂縫起點",
        "hint": "籃球場旁邊嘅大樹下",
        "lat": 22.3850,
        "lng": 114.2700,
        "radius": 40,
        "task_type": "gps",
        "description": "Iggy 嘅第一段記憶似乎喺呢度。"
    },
    "loc2": {
        "name": "Judas 嘅低語",
        "hint": "室內活動室角落",
        "lat": 22.3845,
        "lng": 114.2695,
        "radius": 30,
        "task_type": "puzzle",
        "description": "Judas 留低嘅謎題。"
    },
    "loc3": {
        "name": "痛楚回音",
        "hint": "營地邊緣安靜位置",
        "lat": 22.3830,
        "lng": 114.2720,
        "radius": 50,
        "task_type": "photo",
        "description": "影一張代表「界線」嘅相。"
    }
}

# ==================== 故事階段設定（之後容易改） ====================
# 每個 Stage 解鎖所需「獨特已完成任務」最低數量（Stage 0 = 未達 Stage 1 門檻）
STORY_STAGE_THRESHOLDS = {
    1: 2,   # Stage 1：至少 N 個任務 — 可改
    2: 4,   # Stage 2：至少 N 個任務 — 可改
    3: 6,   # Stage 3（最終）：至少 N 個任務 — 可改
}

# 可選：特定任務 ID 解鎖階段（留空 = 只用上面數量門檻）
# 完成 listed 任務之一即可達到該 stage（與數量門檻取較高）
STORY_STAGE_REQUIRED_TASKS = {
    # 1: ["loc1"],
    # 2: ["loc2"],
    # 3: ["loc3"],
}

STORY_CONTENT = {
    "iggy": {
        0: {"title": "🔥 第一階段：裂縫的開端", "content": "你踏入了 Oikonomia 的世界，Iggy 的第一段記憶正喺度等待被找回。"},
        1: {"title": "🔥 第二階段：痛楚的回音", "content": "你開始感受到 Iggy 曾經承受過嘅界線與痛楚。Judas 的低語開始出現。"},
        2: {"title": "🔥 第三階段：界線的崩壞", "content": "Iggy 嘅世界開始出現裂痕。你必須決定係咪繼續陪佢走落去。"},
        3: {"title": "🔥 最終階段：救贖或崩壞", "content": "你已經深入 Iggy 嘅核心。最後嘅選擇將會決定一切。"},
    },
    "marah": {
        0: {"title": "🌊 第一階段：智慧的開端", "content": "你選擇了 Marah 路線，開始以智慧同韌性去面對界線。"},
        1: {"title": "🌊 第二階段：低語的解析", "content": "Judas 嘅謎題開始出現。你正試圖理解 Marah 背後嘅意義。"},
        2: {"title": "🌊 第三階段：韌性的考驗", "content": "你開始面對更深層嘅情緒勒索同界線問題。"},
        3: {"title": "🌊 最終階段：覺醒", "content": "你已經掌握足夠嘅資訊，準備迎接最後嘅真相。"},
    },
}

def count_team_distinct_tasks(squad_id, team_id):
    conn = sqlite3.connect(DB_PATH)
    if team_id:
        clean_team_id = normalize_team_id(team_id)
        count = conn.execute("""
            SELECT COUNT(DISTINCT task_id)
            FROM submissions
            WHERE squad_id IN (
                SELECT squad_id FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))
            )
        """, (clean_team_id,)).fetchone()[0]
        rows = conn.execute("""
            SELECT DISTINCT task_id
            FROM submissions
            WHERE squad_id IN (
                SELECT squad_id FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))
            )
        """, (clean_team_id,)).fetchall()
    else:
        count = conn.execute(
            "SELECT COUNT(DISTINCT task_id) FROM submissions WHERE squad_id = ?",
            (squad_id,),
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT DISTINCT task_id FROM submissions WHERE squad_id = ?",
            (squad_id,),
        ).fetchall()
    conn.close()
    return count, {row[0] for row in rows}

def resolve_story_stage(completed_count, completed_task_ids):
    stage = 0
    for target_stage, min_tasks in STORY_STAGE_THRESHOLDS.items():
        if completed_count >= min_tasks:
            stage = max(stage, target_stage)
    for target_stage, required_tasks in STORY_STAGE_REQUIRED_TASKS.items():
        if required_tasks and any(t in completed_task_ids for t in required_tasks):
            stage = max(stage, target_stage)
    return min(stage, max(STORY_STAGE_THRESHOLDS.keys(), default=0))

def get_story_for_route(route, stage):
    if not route:
        return {
            "title": "故事尚未開始",
            "content": "你尚未選擇路線。請先完成路線選擇，故事將會展開。",
        }
    route_stories = STORY_CONTENT.get(route, {})
    return route_stories.get(stage, route_stories.get(0, {"title": "故事進行中", "content": ""}))

def next_stage_threshold(current_stage):
    next_stage = current_stage + 1
    return STORY_STAGE_THRESHOLDS.get(next_stage)

def get_item_by_id(item_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def team_has_item(team_id, item_id):
    if not team_id:
        return False
    clean_team_id = normalize_team_id(team_id)
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("""
        SELECT COUNT(*) FROM player_items pi
        JOIN squads s ON pi.squad_id = s.squad_id
        WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?)) AND pi.item_id = ?
    """, (clean_team_id, item_id)).fetchone()[0]
    conn.close()
    return count > 0

def grant_item_to_squad(squad_id, item_id, source="story"):
    squad = get_squad(squad_id)
    if not squad:
        return False, "找不到玩家"

    item = get_item_by_id(item_id)
    if not item:
        return False, "物品不存在"

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    existing = c.execute(
        "SELECT id FROM player_items WHERE squad_id = ? AND item_id = ?",
        (squad_id, item_id),
    ).fetchone()
    if existing:
        conn.close()
        return False, "你已經擁有此物品"

    team_id = squad.get("team_id")
    if team_id and team_has_item(team_id, item_id):
        conn.close()
        return False, "同一隊內已經有人擁有此物品"

    owned_count = c.execute(
        "SELECT COUNT(*) FROM player_items WHERE squad_id = ?",
        (squad_id,),
    ).fetchone()[0]
    if owned_count >= MAX_INVENTORY_SLOTS:
        conn.close()
        return False, f"你已經持有 {MAX_INVENTORY_SLOTS} 樣物品，請先丟棄"

    c.execute(
        "INSERT INTO player_items (squad_id, item_id, source, obtained_at) VALUES (?, ?, ?, ?)",
        (squad_id, item_id, source, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return True, "成功獲得物品"

def hkt_timestamp():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")

def apply_global_effect(effect_type, effect_value=0):
    if not effect_type or effect_type in ("announcement", "global_debuff"):
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if effect_type in ("adjust_sanity", "sanity_adjust"):
        c.execute(
            "UPDATE squads SET sanity = MAX(0, MIN(100, sanity + ?))",
            (effect_value,),
        )
    elif effect_type == "sanity_down":
        c.execute(
            "UPDATE squads SET sanity = MAX(0, MIN(100, sanity - ?))",
            (abs(effect_value),),
        )
    elif effect_type == "sanity_up":
        c.execute(
            "UPDATE squads SET sanity = MAX(0, MIN(100, sanity + ?))",
            (abs(effect_value),),
        )
    elif effect_type == "power_up":
        c.execute(
            "UPDATE squads SET power = MAX(0, MIN(100, power + ?))",
            (abs(effect_value),),
        )
    elif effect_type == "intellect_up":
        c.execute(
            "UPDATE squads SET intellect = MAX(0, MIN(100, intellect + ?))",
            (abs(effect_value),),
        )
    elif effect_type == "resilience_up":
        c.execute(
            "UPDATE squads SET resilience = MAX(0, MIN(100, resilience + ?))",
            (abs(effect_value),),
        )
    elif effect_type == "judas_strengthen":
        c.execute("UPDATE squads SET sanity = MAX(0, sanity - 8)")
    elif effect_type == "iggy_collapse":
        c.execute("UPDATE squads SET sanity = MAX(0, sanity - 12)")
    conn.commit()
    conn.close()

def create_global_event(title, description="", effect_type=None, effect_value=0, created_by="GM"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO global_events
           (title, description, effect_type, effect_value, created_by, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, description, effect_type, effect_value, created_by, hkt_timestamp()),
    )
    conn.commit()
    conn.close()

# ==================== 輔助函數 ====================
def normalize_team_id(team_id):
    if not team_id:
        return None
    return str(team_id).strip().upper()

def build_player_status(squad):
    if not squad:
        return None

    if not squad.get("team_id"):
        return {
            "success": True,
            **squad,
            "team": None,
            "protagonists": {},
            "route": squad.get("route"),
            "is_team_leader": 0,
        }

    team = get_team_by_id(squad["team_id"])
    protagonists = get_team_protagonists(squad["team_id"])
    route = (team or {}).get("route") or squad.get("route")

    return {
        "success": True,
        **squad,
        "route": route,
        "team": team,
        "protagonists": protagonists,
        "is_team_leader": squad.get("is_team_leader", 0),
    }

def row_to_squad(row):
    d = dict(row)
    protagonist = DEFAULT_PROTAGONIST.copy()
    if d.get("protagonist_stats"):
        try:
            protagonist = json.loads(d["protagonist_stats"])
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "squad_id": d["squad_id"],
        "display_name": d.get("display_name") or d["squad_id"],
        "sanity": d.get("sanity", 50),
        "hp": d.get("hp", 100),
        "power": d.get("power", 100),
        "intellect": d.get("intellect", 100),
        "resilience": d.get("resilience", 100),
        "resources": d.get("resources", 0),
        "zoo_skills": json.loads(d["zoo_skills"]) if d.get("zoo_skills") else [],
        "route": d.get("route"),
        "team_id": d.get("team_id"),
        "is_team_leader": 1 if d.get("is_team_leader") else 0,
        "has_pin": bool(d.get("pin")),
        "avatar": d.get("avatar"),
        "protagonist": protagonist,
    }

def get_squad(squad_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM squads WHERE squad_id = ?", (squad_id,)).fetchone()
    conn.close()

    if not row:
        return None

    squad = row_to_squad(row)

    if squad.get("team_id"):
        clean_team_id = normalize_team_id(squad["team_id"])
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        team_row = conn.execute(
            "SELECT route, leader_squad_id FROM teams WHERE team_id = ?",
            (clean_team_id,),
        ).fetchone()
        conn.close()

        if team_row:
            if team_row["route"]:
                squad["route"] = team_row["route"]
            if team_row["leader_squad_id"] == squad["squad_id"]:
                squad["is_team_leader"] = 1
            squad["protagonists"] = get_team_protagonists(clean_team_id)

    return squad

def get_team_protagonists(team_id):
    clean_team_id = normalize_team_id(team_id)
    if not clean_team_id:
        return {
            "iggy": DEFAULT_PROTAGONIST.copy(),
            "marah": DEFAULT_PROTAGONIST.copy(),
            "active_route": None,
        }

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    team_row = conn.execute(
        "SELECT route, leader_squad_id FROM teams WHERE team_id = ?", (clean_team_id,)
    ).fetchone()
    if not team_row:
        conn.close()
        return {
            "iggy": DEFAULT_PROTAGONIST.copy(),
            "marah": DEFAULT_PROTAGONIST.copy(),
            "active_route": None,
        }

    route = team_row["route"]
    leader_id = team_row["leader_squad_id"]
    if leader_id:
        squad_row = conn.execute(
            "SELECT protagonist_stats FROM squads WHERE squad_id = ?", (leader_id,)
        ).fetchone()
    else:
        squad_row = conn.execute(
            "SELECT protagonist_stats FROM squads WHERE team_id = ? LIMIT 1", (clean_team_id,)
        ).fetchone()
    conn.close()

    protagonist = DEFAULT_PROTAGONIST.copy()
    if squad_row and squad_row["protagonist_stats"]:
        try:
            protagonist = json.loads(squad_row["protagonist_stats"])
        except (json.JSONDecodeError, TypeError):
            pass

    iggy = DEFAULT_PROTAGONIST.copy()
    marah = DEFAULT_PROTAGONIST.copy()
    if route == "iggy":
        iggy = protagonist
    elif route == "marah":
        marah = protagonist

    return {"iggy": iggy, "marah": marah, "active_route": route}

def get_all_squads():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM squads ORDER BY squad_id").fetchall()
    conn.close()
    return [row_to_squad(r) for r in rows]

def update_squad(squad_id, **kwargs):
    allowed = {"sanity", "hp", "power", "intellect", "resilience", "resources", "route", "protagonist_stats", "team_id", "is_team_leader", "display_name", "pin", "avatar"}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    updates = []
    params = []
    for key, val in kwargs.items():
        if key not in allowed:
            continue
        if key == "pin" and val is None:
            updates.append("pin = NULL")
        elif val is not None:
            updates.append(f"{key} = ?")
            params.append(val)
    if updates:
        updates.append("last_update = ?")
        params.append(datetime.now().isoformat())
        params.append(squad_id)
        c.execute(f"UPDATE squads SET {', '.join(updates)} WHERE squad_id = ?", params)
        conn.commit()
    conn.close()

def get_next_team_id():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT team_id FROM teams ORDER BY team_id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if not row:
        return "TEAM-01"
    num = int(row[0].split("-")[1]) + 1
    return f"TEAM-{num:02d}"

def get_team_by_id(team_id):
    if not team_id:
        return None

    clean_id = team_id.strip().upper()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM teams WHERE team_id = ?", (clean_id,)
    ).fetchone()

    if not row:
        conn.close()
        return None

    member_count = conn.execute(
        "SELECT COUNT(*) FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))", (clean_id,)
    ).fetchone()[0]
    conn.close()

    return {
        "team_id": row["team_id"],
        "team_name": row["team_name"],
        "route": row["route"],
        "created_at": row["created_at"],
        "member_count": member_count,
    }

def query_teams_list(current_team_id=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM teams ORDER BY created_at DESC").fetchall()

    teams = []
    for row in rows:
        member_count = conn.execute(
            "SELECT COUNT(*) FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))", (row["team_id"],)
        ).fetchone()[0]

        teams.append({
            "team_id": row["team_id"],
            "team_name": row["team_name"],
            "route": row["route"],
            "created_at": row["created_at"],
            "member_count": member_count,
            "is_joined": row["team_id"] == current_team_id,
        })

    conn.close()
    return teams

def get_all_teams_with_stats():
    return query_teams_list()

def build_teams_overview():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    team_rows = conn.execute("SELECT * FROM teams ORDER BY created_at DESC").fetchall()

    teams = []
    for team_row in team_rows:
        team_id = team_row["team_id"]
        clean_id = normalize_team_id(team_id)
        members = conn.execute(
            "SELECT * FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))",
            (clean_id,),
        ).fetchall()

        member_count = len(members)
        stat_fields = ["hp", "sanity", "power", "intellect", "resilience", "resources"]

        def team_avg(field):
            if not members:
                return 0
            return round(sum((m[field] or 0) for m in members) / member_count)

        leader_name = None
        leader_id = team_row["leader_squad_id"]
        if leader_id:
            leader = get_squad(leader_id)
            if leader:
                leader_name = leader.get("display_name") or leader["squad_id"]

        distinct_tasks, task_ids = count_team_distinct_tasks(None, clean_id)
        story_stage = resolve_story_stage(distinct_tasks, task_ids)

        sub_row = conn.execute("""
            SELECT COUNT(*) AS total, MAX(timestamp) AS last_ts
            FROM submissions
            WHERE squad_id IN (
                SELECT squad_id FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))
            )
        """, (clean_id,)).fetchone()

        route = team_row["route"]
        teams.append({
            "team_id": team_id,
            "team_name": team_row["team_name"],
            "route": route,
            "route_label": {"iggy": "🔥 Iggy", "marah": "🌊 Marah"}.get(route, "未選路線"),
            "leader_squad_id": leader_id,
            "leader_name": leader_name or "未設定",
            "member_count": member_count,
            "avg_hp": team_avg("hp"),
            "avg_sanity": team_avg("sanity"),
            "avg_power": team_avg("power"),
            "avg_intellect": team_avg("intellect"),
            "avg_resilience": team_avg("resilience"),
            "avg_resources": team_avg("resources"),
            "distinct_tasks": distinct_tasks,
            "story_stage": story_stage,
            "submission_count": sub_row["total"] if sub_row else 0,
            "last_submission": sub_row["last_ts"] if sub_row else None,
            "members": [
                {
                    "squad_id": m["squad_id"],
                    "display_name": m["display_name"] or m["squad_id"],
                    "hp": m["hp"],
                    "sanity": m["sanity"],
                    "power": m["power"],
                    "intellect": m["intellect"],
                    "resilience": m["resilience"],
                    "is_leader": 1 if leader_id and m["squad_id"] == leader_id else 0,
                }
                for m in members
            ],
        })

    solo_players = []
    unassigned_rows = conn.execute("""
        SELECT * FROM squads
        WHERE team_id IS NULL OR TRIM(team_id) = ''
        ORDER BY COALESCE(display_name, squad_id)
    """).fetchall()
    for row in unassigned_rows:
        distinct_tasks, task_ids = count_team_distinct_tasks(row["squad_id"], None)
        sub_row = conn.execute(
            "SELECT COUNT(*) AS total, MAX(timestamp) AS last_ts FROM submissions WHERE squad_id = ?",
            (row["squad_id"],),
        ).fetchone()
        solo_players.append({
            "squad_id": row["squad_id"],
            "display_name": row["display_name"] or row["squad_id"],
            "route": row["route"],
            "route_label": {"iggy": "🔥 Iggy", "marah": "🌊 Marah"}.get(row["route"], "未選路線"),
            "hp": row["hp"],
            "sanity": row["sanity"],
            "power": row["power"],
            "intellect": row["intellect"],
            "resilience": row["resilience"],
            "resources": row["resources"],
            "distinct_tasks": distinct_tasks,
            "story_stage": resolve_story_stage(distinct_tasks, task_ids),
            "submission_count": sub_row["total"] if sub_row else 0,
            "last_submission": sub_row["last_ts"] if sub_row else None,
        })

    conn.close()
    return {"teams": teams, "solo_players": solo_players}

# ==================== Routes ====================
@app.before_request
def refresh_player_session():
    if "squad_id" in session or session.get("is_gm"):
        session.permanent = True

@app.route("/api/version")
def api_version():
    upload_count = len([
        name for name in os.listdir(UPLOAD_FOLDER)
        if os.path.isfile(os.path.join(UPLOAD_FOLDER, name))
    ]) if os.path.isdir(UPLOAD_FOLDER) else 0
    avatar_count = 0
    if os.path.isdir(AVATAR_DIR):
        avatar_count = len([
            name for name in os.listdir(AVATAR_DIR)
            if name.lower().endswith((".png", ".jpg", ".jpeg")) and name != "default.png"
        ])
    return jsonify({
        "success": True,
        "version": read_deploy_version(),
        "markers": {
            "iggy_card": "iggy-card",
            "show_only_protagonist": "showOnlyProtagonistCard",
        },
        "upload_folder": UPLOAD_FOLDER,
        "legacy_upload_folder": LEGACY_UPLOAD_FOLDER,
        "upload_file_count": upload_count,
        "avatar_dir": AVATAR_DIR,
        "avatar_count": avatar_count,
    })

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/login", methods=["POST"])
def login():
    name = request.form.get("squad_id", "").strip()
    input_pin = request.form.get("pin", "").strip()

    if not name:
        return jsonify({"error": "請輸入名稱"}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        "SELECT * FROM squads WHERE display_name = ? OR squad_id = ?",
        (name, name),
    ).fetchone()

    if not row:
        internal_id = f"PLAYER-{int(time.time() * 1000) % 100000}"
        while get_squad(internal_id):
            internal_id = f"PLAYER-{(int(time.time() * 1000) + int(time.time() * 1000000) % 9999) % 100000}"
        c = conn.cursor()
        c.execute(
            "INSERT INTO squads (squad_id, display_name) VALUES (?, ?)",
            (internal_id, name),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM squads WHERE squad_id = ?", (internal_id,)).fetchone()

    has_pin = bool(row["pin"])

    if has_pin:
        if not input_pin:
            conn.close()
            return jsonify({
                "success": False,
                "require_pin": True,
                "message": "請輸入 PIN",
            })
        if input_pin != row["pin"]:
            conn.close()
            return jsonify({
                "success": False,
                "error": "PIN 錯誤",
            })

    session.permanent = True
    session["squad_id"] = row["squad_id"]
    conn.close()

    squad = get_squad(row["squad_id"])
    status = build_player_status(squad)
    status["require_set_pin"] = not has_pin
    return jsonify(status)

@app.route("/set_pin", methods=["POST"])
def set_pin():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    new_pin = request.form.get("pin", "").strip()

    if not new_pin or len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({"success": False, "error": "請輸入 4 位數字 PIN"}), 400

    update_squad(session["squad_id"], pin=new_pin)

    return jsonify({"success": True, "message": "PIN 設定成功"})

@app.route("/my_submissions")
def my_submissions():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT task_id, content, photo_path, timestamp
        FROM submissions
        WHERE squad_id = ?
        ORDER BY timestamp DESC
    """, (session["squad_id"],)).fetchall()
    conn.close()

    submissions = []
    for row in rows:
        submissions.append({
            "task_id": row["task_id"],
            "content": row["content"],
            "photo_path": normalize_photo_url(row["photo_path"]),
            "photo_url": photo_public_url(row["photo_path"]),
            "timestamp": row["timestamp"],
        })

    return jsonify({"submissions": submissions})

@app.route("/team_task_logs")
def team_task_logs():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    team_id = squad.get("team_id") if squad else None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if team_id:
        rows = conn.execute("""
            SELECT
                s.id,
                s.task_id AS task_name,
                s.content AS description,
                s.photo_path,
                s.timestamp,
                sq.display_name,
                sq.squad_id
            FROM submissions s
            JOIN squads sq ON s.squad_id = sq.squad_id
            WHERE sq.team_id = ?
            ORDER BY s.timestamp DESC
        """, (team_id,)).fetchall()
        has_team = True
    else:
        rows = conn.execute("""
            SELECT
                s.id,
                s.task_id AS task_name,
                s.content AS description,
                s.photo_path,
                s.timestamp,
                sq.display_name,
                sq.squad_id
            FROM submissions s
            JOIN squads sq ON s.squad_id = sq.squad_id
            WHERE s.squad_id = ?
            ORDER BY s.timestamp DESC
        """, (session["squad_id"],)).fetchall()
        has_team = False
    conn.close()

    logs = []
    for row in rows:
        entry = dict(row)
        entry["status"] = "已完成"
        entry["display_name"] = entry.get("display_name") or entry.get("squad_id")
        entry["photo_path"] = normalize_photo_url(entry.get("photo_path"))
        entry["photo_url"] = photo_public_url(entry.get("photo_path"))
        logs.append(entry)

    return jsonify({"success": True, "logs": logs, "has_team": has_team})

@app.route("/global_events")
def get_global_events():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, title, description, effect_type, effect_value, created_by, timestamp
        FROM global_events
        ORDER BY timestamp DESC
        LIMIT 30
    """).fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "events": [dict(row) for row in rows],
    })

@app.route("/story_progress")
def story_progress():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"error": "玩家不存在"}), 404

    completed_count, completed_task_ids = count_team_distinct_tasks(
        session["squad_id"], squad.get("team_id")
    )
    stage = resolve_story_stage(completed_count, completed_task_ids)
    route = squad.get("route")
    story = get_story_for_route(route, stage)

    return jsonify({
        "stage": stage,
        "completed_tasks": completed_count,
        "route": route,
        "next_stage_at": next_stage_threshold(stage),
        "stage_thresholds": STORY_STAGE_THRESHOLDS,
        "story": story,
    })

@app.route("/status")
def get_status():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if not squad:
        session.clear()
        return jsonify({"success": False, "error": "未登入"}), 401

    return jsonify(build_player_status(squad))

@app.route("/team")
def get_team():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401
    return jsonify({"members": get_all_squads()})

@app.route("/my_team")
def my_team():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401
    squad = get_squad(session["squad_id"])
    if not squad or not squad.get("team_id"):
        return jsonify({
            "has_team": False,
            "route": squad.get("route") if squad else None,
        })
    clean_team_id = normalize_team_id(squad["team_id"])
    team = get_team_by_id(clean_team_id)
    if not team:
        return jsonify({
            "has_team": False,
            "route": squad.get("route"),
        })
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM squads
        WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))
        ORDER BY is_team_leader DESC, COALESCE(display_name, squad_id), squad_id
    """, (clean_team_id,)).fetchall()
    conn.close()
    members = []
    for row in rows:
        member = get_squad(row["squad_id"])
        if member:
            member["is_leader"] = member.get("is_team_leader") == 1
            members.append(member)
    protagonists = get_team_protagonists(squad["team_id"])
    return jsonify({
        "success": True,
        "has_team": True,
        "team": team,
        "route": team.get("route"),
        "members": members,
        "is_team_leader": squad.get("is_team_leader", 0),
        "current_squad_id": session["squad_id"],
        "protagonists": protagonists,
    })

@app.route("/available_teams")
def available_teams():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    current_team_id = squad.get("team_id") if squad else None
    has_team = bool(current_team_id and str(current_team_id).strip())
    clean_current_id = normalize_team_id(current_team_id) if has_team else None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM teams ORDER BY created_at DESC").fetchall()

    teams = []
    for row in rows:
        member_count = conn.execute(
            "SELECT COUNT(*) FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))", (row["team_id"],)
        ).fetchone()[0]

        is_joined = bool(
            clean_current_id
            and normalize_team_id(row["team_id"]) == clean_current_id
        )

        teams.append({
            "team_id": row["team_id"],
            "team_name": row["team_name"],
            "route": row["route"],
            "member_count": member_count,
            "is_joined": is_joined,
        })

    conn.close()
    return jsonify({
        "success": True,
        "has_team": has_team,
        "current_team_id": clean_current_id,
        "teams": teams,
    })

@app.route("/team/join", methods=["POST"])
def join_team():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    team_id = request.form.get("team_id", "").strip()
    if not team_id:
        return jsonify({"success": False, "error": "請輸入 Team Code"}), 400

    team = get_team_by_id(team_id)
    if not team:
        print(f"[DEBUG] Join failed - team_id input: '{team_id}' not found in DB")
        return jsonify({"success": False, "error": "Team 不存在"}), 400

    squad = get_squad(session["squad_id"])
    if squad.get("team_id"):
        return jsonify({"success": False, "error": "你已加入 Team，無法重複加入"}), 400

    update_squad(session["squad_id"], team_id=normalize_team_id(team["team_id"]), is_team_leader=0)
    return jsonify({"success": True, "team": team})

@app.route("/team/create", methods=["POST"])
def create_player_team():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if squad.get("team_id"):
        return jsonify({"success": False, "error": "你已加入 Team，請先離開現有隊伍"}), 400

    team_name = request.form.get("team_name", "").strip() or "新小隊"
    team_id = get_next_team_id()
    created_at = datetime.now().isoformat()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO teams (team_id, team_name, route, created_at, leader_squad_id) VALUES (?, ?, ?, ?, ?)",
        (team_id, team_name, None, created_at, session["squad_id"]),
    )
    conn.commit()
    conn.close()

    update_squad(session["squad_id"], team_id=team_id, is_team_leader=1)
    return jsonify({"success": True, "team_id": team_id, "team_name": team_name})

@app.route("/team/update_name", methods=["POST"])
def team_update_name():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    new_name = request.form.get("team_name", "").strip()
    if not new_name:
        return jsonify({"success": False, "error": "隊名不能為空"}), 400
    if len(new_name) > 30:
        return jsonify({"success": False, "error": "隊名最長 30 個字"}), 400

    squad = get_squad(session["squad_id"])
    if not squad or squad.get("is_team_leader") != 1:
        return jsonify({"success": False, "error": "只有隊長可以改隊名"}), 403

    team_id = squad.get("team_id")
    if not team_id:
        return jsonify({"success": False, "error": "你未有隊伍"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE teams SET team_name = ? WHERE team_id = ?", (new_name, team_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "team_name": new_name})

@app.route("/team/transfer_leadership", methods=["POST"])
def transfer_leadership():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    data = request.get_json(silent=True) or {}
    target_squad_id = (data.get("target_squad_id") or "").strip()
    if not target_squad_id:
        return jsonify({"success": False, "error": "請選擇目標隊員"}), 400

    if target_squad_id == session["squad_id"]:
        return jsonify({"success": False, "error": "不能轉讓畀自己"}), 400

    current_squad = get_squad(session["squad_id"])
    if not current_squad or current_squad.get("is_team_leader") != 1:
        return jsonify({"success": False, "error": "只有隊長可以轉讓"}), 403

    team_id = normalize_team_id(current_squad.get("team_id"))
    if not team_id:
        return jsonify({"success": False, "error": "你未有隊伍"}), 400

    target_squad = get_squad(target_squad_id)
    if not target_squad:
        return jsonify({"success": False, "error": "找不到目標隊員"}), 404

    if normalize_team_id(target_squad.get("team_id")) != team_id:
        return jsonify({"success": False, "error": "目標隊員唔係同一個隊"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE squads SET is_team_leader = 0 WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))",
        (team_id,),
    )
    c.execute("UPDATE squads SET is_team_leader = 1 WHERE squad_id = ?", (target_squad_id,))
    c.execute("UPDATE teams SET leader_squad_id = ? WHERE team_id = ?", (target_squad_id, team_id))
    conn.commit()
    conn.close()

    updated = get_squad(session["squad_id"])
    return jsonify({
        "success": True,
        "message": "隊長已成功轉讓",
        "is_team_leader": updated.get("is_team_leader", 0),
    })

@app.route("/set_team_route_by_leader", methods=["POST"])
def set_team_route_by_leader():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if not squad or squad.get("is_team_leader") != 1:
        return jsonify({"success": False, "error": "只有隊長可以設定路線"}), 403

    route = request.form.get("route", "").lower()
    if route not in ("iggy", "marah"):
        return jsonify({"success": False, "error": "無效路線"}), 400

    team_id = normalize_team_id(squad.get("team_id"))
    if not team_id:
        return jsonify({"success": False, "error": "你未加入任何 Team"}), 400

    team = get_team_by_id(team_id)
    if team and team.get("route"):
        return jsonify({"success": False, "error": "Team 已設定路線，無法更改"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE teams SET route = ? WHERE team_id = ?", (route, team_id))
    conn.commit()
    conn.close()

    updated = get_squad(session["squad_id"])
    status = build_player_status(updated)
    status["squad"] = updated
    return jsonify(status)

@app.route("/set_route", methods=["POST"])
def set_route():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    route = request.form.get("route", "").lower()
    if route not in ("iggy", "marah"):
        return jsonify({"error": "請選擇 Iggy 或 Marah 路線"}), 400

    squad = get_squad(session["squad_id"])
    if squad.get("route"):
        return jsonify({"error": "你已選擇路線，無法更改"}), 400

    update_squad(session["squad_id"], route=route)
    return jsonify(build_player_status(get_squad(session["squad_id"])))

@app.route("/locations")
def get_locations():
    return jsonify(LOCATIONS)

@app.route("/verify_gps", methods=["POST"])
def verify_gps():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    data = request.get_json()
    loc_id = data.get("loc_id")
    lat = float(data.get("lat"))
    lng = float(data.get("lng"))

    if loc_id not in LOCATIONS:
        return jsonify({"error": "無效地點"}), 400

    loc = LOCATIONS[loc_id]
    distance = math.sqrt((lat - loc["lat"])**2 + (lng - loc["lng"])**2) * 111000

    if distance <= loc["radius"]:
        return jsonify({
            "success": True,
            "message": "位置正確！",
            "task_type": loc["task_type"],
            "loc_name": loc["name"]
        })
    else:
        return jsonify({
            "success": False,
            "message": f"距離太遠（相差約 {int(distance)} 米）"
        })

@app.route("/submit_task", methods=["POST"])
def submit_task():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    task_id = request.form.get("task_id", "unknown")
    content = request.form.get("content", "")

    squad = get_squad(session["squad_id"])
    team_id = squad.get("team_id")

    if not team_id:
        return jsonify({"error": "你未加入任何 Team，無法提交任務"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id FROM submissions
        WHERE task_id = ? AND squad_id IN (
            SELECT squad_id FROM squads WHERE team_id = ?
        )
    """, (task_id, team_id))
    already_submitted = c.fetchone()

    photo_path = None
    if "photo" in request.files:
        photo = request.files["photo"]
        if photo.filename:
            filename = f"{session['squad_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            photo.save(os.path.join(UPLOAD_FOLDER, filename))
            photo_path = f"uploads/{filename}"

    c.execute("""INSERT INTO submissions (squad_id, task_id, content, photo_path, timestamp)
                 VALUES (?, ?, ?, ?, ?)""",
              (session["squad_id"], task_id, content, photo_path, datetime.now().isoformat()))
    conn.commit()

    if not already_submitted:
        new_sanity = min(100, squad["sanity"] + 6)
        new_resources = squad["resources"] + 1
        update_squad(session["squad_id"], sanity=new_sanity, resources=new_resources)
        conn.close()
        return jsonify({
            "success": True,
            "message": "任務提交成功！+6 Sanity +1 Resource（第一次提交）"
        })
    else:
        conn.close()
        return jsonify({
            "success": True,
            "message": "提交已記錄，但呢個任務已經計過分（只計一次）"
        })

@app.route("/update_display_name", methods=["POST"])
def update_display_name():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    new_name = request.form.get("display_name", "").strip()
    if not new_name:
        return jsonify({"success": False, "error": "名稱不能為空"}), 400
    if len(new_name) > 20:
        return jsonify({"success": False, "error": "名稱最長 20 個字"}), 400

    update_squad(session["squad_id"], display_name=new_name)
    return jsonify({"success": True, "display_name": new_name})

@app.route("/available_avatars")
def available_avatars():
    if not os.path.isdir(AVATAR_DIR):
        return jsonify({"avatars": [], "avatar_dir": AVATAR_DIR})
    files = [
        filename for filename in os.listdir(AVATAR_DIR)
        if filename.lower().endswith((".png", ".jpg", ".jpeg")) and filename != "default.png"
    ]
    return jsonify({"avatars": sorted(files)})

@app.route("/set_avatar", methods=["POST"])
def set_avatar():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    avatar_filename = os.path.basename(request.form.get("avatar", "").strip())
    if not avatar_filename:
        return jsonify({"success": False, "error": "請選擇頭像"}), 400

    avatar_path = os.path.join(AVATAR_DIR, avatar_filename)
    if not os.path.exists(avatar_path):
        return jsonify({"success": False, "error": "頭像不存在"}), 400

    update_squad(session["squad_id"], avatar=avatar_filename)
    return jsonify({"success": True, "avatar": avatar_filename})

@app.route("/my_items")
def my_items():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad_id = session["squad_id"]
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT pi.id, pi.item_id, i.name, i.description, i.icon, i.item_type,
               pi.source, pi.obtained_at
        FROM player_items pi
        JOIN items i ON pi.item_id = i.id
        WHERE pi.squad_id = ?
        ORDER BY pi.obtained_at DESC
    """, (squad_id,)).fetchall()
    conn.close()

    items = [dict(row) for row in rows]
    return jsonify({
        "success": True,
        "items": items,
        "max_slots": MAX_INVENTORY_SLOTS,
        "current_count": len(items),
    })

@app.route("/add_item", methods=["POST"])
def add_item():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    data = request.get_json(silent=True) or {}
    item_id = data.get("item_id")
    source = (data.get("source") or "story").strip() or "story"

    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "無效物品 ID"}), 400

    success, message = grant_item_to_squad(session["squad_id"], item_id, source)
    if not success:
        return jsonify({"success": False, "error": message}), 400

    return jsonify({"success": True, "message": message, "item_id": item_id})

@app.route("/discard_item", methods=["POST"])
def discard_item():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    data = request.get_json(silent=True) or {}
    player_item_id = data.get("player_item_id")
    try:
        player_item_id = int(player_item_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "無效物品記錄"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "DELETE FROM player_items WHERE id = ? AND squad_id = ?",
        (player_item_id, session["squad_id"]),
    )
    deleted = c.rowcount
    conn.commit()
    conn.close()

    if deleted == 0:
        return jsonify({"success": False, "error": "找不到物品或無權限丟棄"}), 404

    return jsonify({"success": True, "message": "物品已丟棄"})

@app.route("/claim_item/<int:item_id>")
def claim_item_page(item_id):
    if "squad_id" not in session:
        return redirect(f"/?next=/claim_item/{item_id}")

    item = get_item_by_id(item_id)
    if not item:
        return "找不到此物品", 404

    return render_template_string(CLAIM_ITEM_HTML, item=item, item_id=item_id)

# ==================== GM Routes ====================

GM_PIN = "gm2026"  # GM 登入 PIN，你可以之後改

@app.route("/gm")
def gm_login_page():
    return render_template_string(GM_LOGIN_HTML)

@app.route("/gm/login", methods=["POST"])
def gm_login():
    pin = request.form.get("pin", "")
    if pin == GM_PIN:
        session.permanent = True
        session["is_gm"] = True
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "PIN 錯誤"})

@app.route("/gm/dashboard")
def gm_dashboard():
    if not session.get("is_gm"):
        return redirect("/gm")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    squad_list = []
    for s in get_all_squads():
        c.execute("SELECT COUNT(*) FROM submissions WHERE squad_id = ?", (s["squad_id"],))
        submission_count = c.fetchone()[0]
        squad_list.append({
            **s,
            "zoo_count": len(s["zoo_skills"]),
            "submission_count": submission_count,
            "route_label": {"iggy": "Iggy", "marah": "Marah"}.get(s.get("route"), "未選"),
        })
    
    last_update = datetime.now().strftime("%H:%M:%S")
    conn.close()
    
    return render_template_string(GM_DASHBOARD_HTML, squads=squad_list, last_update=last_update)

@app.route("/gm/squad/<squad_id>")
def gm_squad_detail(squad_id):
    if not session.get("is_gm"):
        return redirect("/gm")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    squad = get_squad(squad_id)
    if not squad:
        conn.close()
        return "找不到該小隊", 404
    squad["zoo_count"] = len(squad["zoo_skills"])
    squad["route_label"] = {"iggy": "Iggy 路線", "marah": "Marah 路線"}.get(squad.get("route"), "未選路線")
    
    # 取得提交記錄
    c.execute("""SELECT task_id, content, photo_path, timestamp 
                 FROM submissions 
                 WHERE squad_id = ? 
                 ORDER BY timestamp DESC""", (squad_id,))
    submissions_raw = c.fetchall()
    conn.close()
    
    submissions = []
    for sub in submissions_raw:
        submissions.append({
            "task_id": sub[0],
            "content": sub[1],
            "photo_path": normalize_photo_url(sub[2]),
            "photo_url": photo_public_url(sub[2]),
            "timestamp": sub[3]
        })
    
    return render_template_string(GM_SQUAD_DETAIL_HTML, squad=squad, submissions=submissions)

@app.route("/gm/adjust", methods=["POST"])
def gm_adjust():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未登入"}), 403

    squad_id = request.form.get("squad_id")
    field = request.form.get("field")          # hp, sanity, resources
    value = int(request.form.get("value", 0))

    if field not in ["hp", "sanity", "power", "intellect", "resilience", "resources"]:
        return jsonify({"success": False, "error": "無效欄位"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f"UPDATE squads SET {field} = ? WHERE squad_id = ?", (value, squad_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route("/gm/reset_pin", methods=["POST"])
def gm_reset_pin():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未登入 GM"}), 403

    squad_id = request.form.get("squad_id", "").strip()
    new_pin = request.form.get("new_pin", "").strip()

    if not squad_id:
        return jsonify({"success": False, "error": "請提供 Player ID"}), 400

    if not get_squad(squad_id):
        return jsonify({"success": False, "error": "玩家不存在"}), 404

    if not new_pin:
        new_pin = str(random.randint(1000, 9999))

    if len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({"success": False, "error": "PIN 必須係 4 位數字"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE squads SET pin = ? WHERE squad_id = ?", (new_pin, squad_id))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"已重置 {squad_id} 的 PIN",
        "new_pin": new_pin,
    })

@app.route("/gm/global_event", methods=["POST"])
def gm_global_event():
    if not session.get("is_gm"):
        return jsonify({"success": False}), 403

    event_type = request.form.get("event_type")
    value = int(request.form.get("value", 0))

    if event_type == "adjust_sanity":
        title = f"全營 Sanity {'+' if value > 0 else ''}{value}"
        description = f"GM 調整全營 Sanity {'+' if value > 0 else ''}{value}"
        effect_type = "adjust_sanity"
        effect_value = value
    elif event_type == "judas_strengthen":
        title = "Judas 加強"
        description = "Judas 加強！全營 Sanity -8"
        effect_type = "judas_strengthen"
        effect_value = -8
    elif event_type == "iggy_collapse":
        title = "Iggy 崩潰"
        description = "Iggy 開始崩潰！全營 Sanity -12"
        effect_type = "iggy_collapse"
        effect_value = -12
    else:
        return jsonify({"success": False, "error": "未知事件類型"})

    apply_global_effect(effect_type, effect_value)
    create_global_event(title, description, effect_type, effect_value, "GM")
    return jsonify({"success": True, "message": description})

@app.route("/gm/create_global_event", methods=["POST"])
def gm_create_global_event():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    data = request.get_json(silent=True) or request.form
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"success": False, "error": "標題不能為空"}), 400

    description = (data.get("description") or "").strip()
    effect_type = (data.get("effect_type") or "").strip() or None
    effect_value = int(data.get("effect_value", 0) or 0)

    apply_global_effect(effect_type, effect_value)
    create_global_event(title, description, effect_type, effect_value, "GM")
    return jsonify({"success": True, "message": "全球事件已建立"})

RESET_PASSWORD = "reset2026"  # 重置遊戲專用密碼

@app.route("/gm/reset_game", methods=["POST"])
def gm_reset_game():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未登入"}), 403

    password = request.form.get("password", "")
    if password != RESET_PASSWORD:
        return jsonify({"success": False, "error": "密碼錯誤"})

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. 清空提交記錄
    c.execute("DELETE FROM submissions")

    # 1b. 清空玩家物品
    c.execute("DELETE FROM player_items")

    # 2. 清空所有 Team
    c.execute("DELETE FROM teams")

    # 3. 刪除所有玩家記錄（Squad = 獨立玩家ID）
    c.execute("DELETE FROM squads")

    # 4. 清空全球事件記錄
    c.execute("DELETE FROM global_events")

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "遊戲已完全重置（所有玩家ID、Team、提交記錄已清空）",
    })

@app.route("/gm/clear_all_images", methods=["POST"])
def gm_clear_all_images():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未登入"}), 403

    data = request.get_json(silent=True) or {}
    confirm = data.get("confirm", "")
    if confirm != "CLEAR_IMAGES":
        return jsonify({"success": False, "error": "確認碼錯誤"}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, photo_path FROM submissions
        WHERE photo_path IS NOT NULL AND TRIM(photo_path) != ''
    """)
    submissions = c.fetchall()

    deleted_count = 0
    cleared_count = 0
    for row in submissions:
        photo_path = row["photo_path"]
        disk_path = resolve_upload_disk_path(photo_path)
        if disk_path and os.path.isfile(disk_path):
            try:
                os.remove(disk_path)
                deleted_count += 1
            except OSError as e:
                print(f"刪除圖片失敗: {disk_path}, {e}")

        c.execute("UPDATE submissions SET photo_path = NULL WHERE id = ?", (row["id"],))
        cleared_count += 1

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"已成功刪除 {deleted_count} 張圖片（清空 {cleared_count} 筆提交記錄中的圖片欄位）",
        "deleted_files": deleted_count,
        "cleared_records": cleared_count,
    })

@app.route("/gm/teams_overview")
def gm_teams_overview():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    overview = build_teams_overview()
    return jsonify({"success": True, **overview})

@app.route("/gm/download_team_images/<team_id>")
def gm_download_team_images(team_id):
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    clean_id = normalize_team_id(team_id)
    team = get_team_by_id(clean_id)
    if not team:
        return jsonify({"success": False, "error": "找不到該隊伍"}), 404

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT s.id, s.photo_path, s.task_id, sq.display_name, sq.squad_id
        FROM submissions s
        JOIN squads sq ON s.squad_id = sq.squad_id
        WHERE UPPER(TRIM(sq.team_id)) = UPPER(TRIM(?))
          AND s.photo_path IS NOT NULL AND TRIM(s.photo_path) != ''
        ORDER BY s.timestamp
    """, (clean_id,)).fetchall()
    conn.close()

    if not rows:
        return jsonify({"success": False, "error": "該隊伍冇上傳過圖片"}), 404

    memory_file = io.BytesIO()
    added = 0
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            disk_path = resolve_upload_disk_path(row["photo_path"])
            if not disk_path or not os.path.isfile(disk_path):
                continue
            display_name = row["display_name"] or row["squad_id"]
            task_name = task_display_name(row["task_id"])
            filename = os.path.basename(disk_path)
            arcname = safe_zip_arcname(display_name, task_name, row["id"], filename)
            zf.write(disk_path, arcname=arcname)
            added += 1

    if added == 0:
        return jsonify({"success": False, "error": "圖片檔案已不存在於伺服器"}), 404

    memory_file.seek(0)
    zip_name = safe_zip_arcname(team.get("team_name") or clean_id, "images") + ".zip"
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_name,
    )

@app.route("/gm/player_logs/<squad_id>")
def gm_player_logs(squad_id):
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    squad = get_squad(squad_id)
    if not squad:
        return jsonify({"success": False, "error": "找不到玩家"}), 404

    team_info = get_team_by_id(squad.get("team_id")) if squad.get("team_id") else None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT s.id, s.task_id, s.content, s.photo_path, s.timestamp,
               sq.display_name, sq.squad_id, sq.team_id,
               t.team_name
        FROM submissions s
        JOIN squads sq ON s.squad_id = sq.squad_id
        LEFT JOIN teams t ON UPPER(TRIM(t.team_id)) = UPPER(TRIM(sq.team_id))
        WHERE s.squad_id = ?
        ORDER BY s.timestamp DESC
    """, (squad_id,)).fetchall()
    conn.close()

    logs = []
    for row in rows:
        task_id = row["task_id"]
        logs.append({
            "id": row["id"],
            "task_id": task_id,
            "task_name": task_display_name(task_id),
            "description": row["content"],
            "photo_path": normalize_photo_url(row["photo_path"]),
            "photo_url": photo_public_url(row["photo_path"]),
            "timestamp": row["timestamp"],
            "status": "已完成",
            "display_name": row["display_name"] or row["squad_id"],
            "team_name": row["team_name"],
        })

    return jsonify({
        "success": True,
        "player": {
            "squad_id": squad_id,
            "display_name": squad.get("display_name") or squad_id,
            "team_id": squad.get("team_id"),
            "team_name": team_info["team_name"] if team_info else None,
        },
        "logs": logs,
    })

# 公告歷史記錄（每條包含訊息 + 時間）
ANNOUNCEMENTS = []   # 格式: [{"message": "...", "timestamp": "..."}]

@app.route("/gm/announcement", methods=["POST"])
def gm_send_announcement():
    if not session.get("is_gm"):
        return jsonify({"success": False}), 403

    message = request.form.get("message", "").strip()
    if not message:
        return jsonify({"success": False, "error": "訊息不能為空"})

    timestamp = hkt_timestamp()

    ANNOUNCEMENTS.append({
        "message": message,
        "timestamp": timestamp
    })
    create_global_event("公告", message, "announcement", 0, "GM")

    return jsonify({"success": True, "message": "公告已發送"})

@app.route("/gm/teams")
def gm_teams():
    if not session.get("is_gm"):
        return jsonify({"error": "未授權"}), 403
    return jsonify({"teams": get_all_teams_with_stats()})

@app.route("/gm/team_members/<team_id>")
def gm_team_members(team_id):
    if not session.get("is_gm"):
        return jsonify({"error": "未授權"}), 403

    team = get_team_by_id(team_id)
    if not team:
        return jsonify({"error": "Team 不存在"}), 404

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM squads WHERE team_id = ? ORDER BY display_name, squad_id",
        (team_id,),
    ).fetchall()
    conn.close()

    members = [get_squad(row["squad_id"]) for row in rows]
    return jsonify({"team": team, "members": members})

@app.route("/gm/assignable_players")
def gm_assignable_players():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權", "players": []}), 403

    target_team_id = normalize_team_id(request.args.get("team_id", ""))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT squad_id, display_name, team_id
        FROM squads
        ORDER BY COALESCE(display_name, squad_id), squad_id
    """).fetchall()
    conn.close()

    players = []
    for row in rows:
        current_team_id = normalize_team_id(row["team_id"]) if row["team_id"] else None
        on_target_team = bool(target_team_id and current_team_id == target_team_id)

        label = row["display_name"] or row["squad_id"]
        if current_team_id:
            team_info = get_team_by_id(current_team_id)
            team_label = team_info["team_name"] if team_info else current_team_id
            label += f"（現於 {team_label}）"
        else:
            label += "（未入隊）"
        if on_target_team:
            label += "（已在目標隊）"

        players.append({
            "squad_id": row["squad_id"],
            "display_name": row["display_name"] or row["squad_id"],
            "current_team_id": current_team_id,
            "label": label,
            "on_target_team": on_target_team,
            "eligible": not on_target_team,
        })

    eligible = [player for player in players if player["eligible"]]
    return jsonify({
        "success": True,
        "players": eligible,
        "all_players": players,
        "count": len(eligible),
    })

@app.route("/gm/create_team", methods=["POST"])
def gm_create_team():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    team_name = request.form.get("team_name", "").strip() or "新小隊"
    team_id = get_next_team_id()
    created_at = datetime.now().isoformat()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO teams (team_id, team_name, route, created_at, leader_squad_id) VALUES (?, ?, ?, ?, ?)",
        (team_id, team_name, None, created_at, None),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "team_id": team_id, "team_name": team_name})

@app.route("/gm/assign_squad", methods=["POST"])
def gm_assign_squad():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    squad_id = request.form.get("squad_id", "").strip()
    new_team_id = request.form.get("team_id", "").strip().upper()

    if not squad_id:
        return jsonify({"success": False, "error": "請選擇玩家"}), 400

    squad = get_squad(squad_id)
    if not squad:
        if not squad_id.upper().startswith("FRAG-"):
            squad_id = squad_id.upper().replace(" ", "_")[:15]
        else:
            squad_id = squad_id.upper()
        squad = get_squad(squad_id)
    if not squad:
        return jsonify({"success": False, "error": "玩家不存在"}), 400

    new_team = get_team_by_id(new_team_id)
    if not new_team:
        return jsonify({"success": False, "error": "目標 Team 不存在"}), 400

    old_team_id = squad.get("team_id")
    old_team_name = None
    if old_team_id:
        old_team = get_team_by_id(old_team_id)
        if old_team:
            old_team_name = old_team["team_name"]

    is_leader = 0
    update_squad(squad_id, team_id=normalize_team_id(new_team_id), is_team_leader=is_leader)

    label = squad.get("display_name") or squad_id
    message = f"已將 {label} 分配到 {new_team['team_name']}"
    if old_team_name:
        message = f"已將 {label} 從「{old_team_name}」轉到「{new_team['team_name']}」"

    return jsonify({
        "success": True,
        "message": message,
        "old_team": old_team_name,
        "new_team": new_team["team_name"],
    })

@app.route("/gm/set_team_route", methods=["POST"])
def gm_set_team_route():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    team_id = request.form.get("team_id", "").strip().upper()
    route = request.form.get("route", "").strip().lower()

    if route not in ("iggy", "marah"):
        return jsonify({"success": False, "error": "路線必須是 iggy 或 marah"}), 400
    if not get_team_by_id(team_id):
        return jsonify({"success": False, "error": "Team 不存在"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE teams SET route = ? WHERE team_id = ?", (route, team_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/gm/update_team_name", methods=["POST"])
def gm_update_team_name():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未登入 GM"}), 403

    team_id = request.form.get("team_id", "").strip().upper()
    new_name = request.form.get("new_name", "").strip()

    if not team_id or not new_name:
        return jsonify({"success": False, "error": "參數不完整"}), 400
    if not get_team_by_id(team_id):
        return jsonify({"success": False, "error": "Team 不存在"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE teams SET team_name = ? WHERE team_id = ?", (new_name, team_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "隊名已更新"})

@app.route("/debug/teams")
def debug_teams():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='teams'")
    exists = c.fetchone() is not None
    count = 0
    if exists:
        count = c.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    conn.close()
    return jsonify({"teams_table_exists": exists, "team_count": count})

@app.route("/announcements")
def get_announcements():
    return jsonify({"announcements": ANNOUNCEMENTS})

@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    disk_path = resolve_upload_disk_path(filename)
    if not disk_path:
        abort(404)
    return send_from_directory(os.path.dirname(disk_path), os.path.basename(disk_path))

# ==================== 漂亮嘅 HTML ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-HK">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oikonomia • 原型</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        :root {
            --bg-main: #0D0D0D;
            --bg-color: #0D0D0D;
            --bg-gradient-start: #0D0D0D;
            --bg-gradient-mid: #141414;
            --bg-gradient-end: #141414;
            --bg-glow: transparent;
            --card-bg: #1F1F1F;
            --card-border: #555555;
            --text-primary: #FFFFFF;
            --text-secondary: #AAAAAA;
            --text-color: #FFFFFF;
            --text-muted: #AAAAAA;
            --accent-gold: #FFFFFF;
            --accent-orange: #888888;
            --accent-color: #FFFFFF;
            --accent-contrast: #0D0D0D;
            --accent-soft: rgba(255, 255, 255, 0.12);
            --progress-bg: #333333;
            --progress-track: #333333;
            --progress-color: #888888;
            --header-border: rgba(63, 63, 70, 0.8);
            --shadow-color: rgba(44, 62, 80, 0.6);
            --card-glow: none;
        }
        .theme-iggy {
            --bg-main: #0D0D0D;
            --bg-color: #0D0D0D;
            --bg-gradient-start: #3D1A2E;
            --bg-gradient-mid: #1a0f14;
            --bg-gradient-end: #0D0D0D;
            --bg-glow: rgba(212, 160, 23, 0.1);
            --card-bg: #4A1C2E;
            --card-border: #D4A017;
            --text-primary: #F5E8C7;
            --text-secondary: #C9A36A;
            --text-color: #F5E8C7;
            --text-muted: #C9A36A;
            --accent-gold: #D4A017;
            --accent-orange: #E07A5F;
            --accent-color: #D4A017;
            --accent-contrast: #1a0f14;
            --accent-soft: rgba(212, 160, 23, 0.22);
            --progress-bg: #3D1A2E;
            --progress-track: #3D1A2E;
            --progress-color: #E07A5F;
            --header-border: rgba(212, 160, 23, 0.45);
            --shadow-color: rgba(61, 26, 46, 0.85);
            --card-glow: 0 0 24px rgba(212, 160, 23, 0.18), inset 0 1px 0 rgba(212, 160, 23, 0.15);
        }
        .theme-marah {
            --bg-main: #0D0D0D;
            --bg-color: #0D0D0D;
            --bg-gradient-start: #152033;
            --bg-gradient-mid: #0f1a2e;
            --bg-gradient-end: #0D0D0D;
            --bg-glow: rgba(74, 144, 164, 0.08);
            --card-bg: #1E2A44;
            --card-border: #4A90A4;
            --text-primary: #E8E8E8;
            --text-secondary: #9ca8b8;
            --text-color: #E8E8E8;
            --text-muted: #9ca8b8;
            --accent-gold: #C0C0C0;
            --accent-orange: #4A90A4;
            --accent-color: #C0C0C0;
            --accent-contrast: #0f1520;
            --accent-soft: rgba(74, 144, 164, 0.28);
            --progress-bg: #152033;
            --progress-track: #152033;
            --progress-color: #4A90A4;
            --header-border: rgba(74, 144, 164, 0.38);
            --shadow-color: rgba(30, 42, 68, 0.75);
            --card-glow: 0 0 20px rgba(74, 144, 164, 0.12), inset 0 1px 0 rgba(192, 192, 192, 0.08);
        }
        body { font-family: 'Noto Sans TC', system-ui, sans-serif; }
        body.theme-body {
            background:
                radial-gradient(ellipse 110% 75% at 50% -8%, var(--bg-glow) 0%, transparent 52%),
                radial-gradient(ellipse 85% 55% at 8% 18%, color-mix(in srgb, var(--bg-gradient-start) 55%, transparent) 0%, transparent 48%),
                linear-gradient(165deg, var(--bg-gradient-start) 0%, var(--bg-gradient-mid) 38%, var(--bg-main) 100%);
            background-attachment: fixed;
            color: var(--text-color);
            min-height: 100vh;
        }
        .title-font { font-family: 'Playfair Display', Georgia, serif; }
        .theme-accent-bg { background-color: var(--accent-color); }
        .theme-accent-text { color: var(--accent-color); }
        .theme-muted-text { color: var(--text-muted); }
        .section-card {
            background: var(--card-bg);
            border: 1px solid var(--header-border);
        }
        .status-bar { transition: width 0.4s ease; }
        .stat-track { background-color: var(--progress-track); }
        .nav-active {
            background-color: var(--accent-soft);
            color: var(--accent-color);
            border-radius: 9999px;
        }
        .nav-btn {
            color: var(--text-muted);
            transition: all 0.2s;
        }
        .nav-btn:hover {
            color: var(--text-color);
            background-color: var(--accent-soft);
            border-radius: 9999px;
        }
        .app-header { border-color: var(--header-border) !important; }
        .cartoon-box {
            border: 2px solid var(--card-border);
            border-radius: 12px;
            background: var(--card-bg);
            box-shadow: var(--card-glow), 6px 6px 0px var(--shadow-color);
            color: var(--text-color);
        }
        body.theme-iggy .cartoon-box {
            border-width: 2px;
        }
        .theme-card-title {
            color: var(--accent-gold);
        }
        .ring-active-route {
            box-shadow: var(--card-glow), 0 0 0 2px var(--accent-gold), 6px 6px 0px var(--shadow-color);
        }
        .route-card {
            border: 3px solid #2C3E50;
            border-radius: 12px;
            padding: 1.25rem;
            cursor: pointer;
            transition: transform 0.1s ease, box-shadow 0.1s ease;
            box-shadow: 4px 4px 0px rgba(44, 62, 80, 0.5);
        }
        .route-card:hover { transform: translate(-2px, -2px); box-shadow: 6px 6px 0px rgba(44, 62, 80, 0.5); }
        .route-iggy { background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%); }
        .route-marah { background: linear-gradient(135deg, #1e3a5f 0%, #1e40af 100%); }
        /* Fallback（Tailwind CDN 載入失敗時仍可用） */
        .hidden { display: none; }
        .fixed { position: fixed; }
        .inset-0 { top: 0; right: 0; bottom: 0; left: 0; }
        /* 導航：桌面橫向 / 手機漢堡（唔用全局 .flex !important，避免蓋過響應式） */
        #nav-desktop { display: none; }
        @media (min-width: 768px) {
            #nav-desktop.nav-visible {
                display: flex !important;
                align-items: center;
                gap: 0.25rem;
            }
        }
        #hamburger-btn { display: none; }
        @media (max-width: 767px) {
            #hamburger-btn.nav-visible { display: block; }
        }
        #mobile-menu { display: none !important; }
        @media (max-width: 767px) {
            #mobile-menu.menu-open {
                display: flex !important;
                flex-direction: column;
            }
        }
        .location-card {
            cursor: pointer; padding: 1.25rem; border-radius: 1.5rem; margin-bottom: 1rem;
            background: var(--card-bg); border: 1px solid var(--header-border);
            color: var(--text-color);
        }
        .location-card:active { opacity: 0.85; }
        .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 50;
            display: flex; align-items: flex-end; justify-content: center; }
        .modal-box {
            background: var(--card-bg); color: var(--text-color);
            width: 100%; max-width: 480px; padding: 1.5rem;
            border-radius: 1.5rem 1.5rem 0 0; border-top: 1px solid var(--card-border);
        }
        #game-content .text-zinc-400 { color: var(--text-muted); }
        #game-content .border-zinc-700,
        #game-content .border-zinc-800 { border-color: var(--card-border); }
        .theme-btn-primary {
            background-color: var(--accent-color);
            color: var(--accent-contrast);
        }
        .theme-btn-primary:hover { filter: brightness(1.08); }
        @media (min-width: 768px) {
            .modal-overlay { align-items: center; }
            .modal-box { border-radius: 1.5rem; }
        }
    </style>
</head>
<body class="theme-body">
    <div class="max-w-4xl mx-auto">
        <!-- ==================== Header ==================== -->
        <div class="app-header flex items-center justify-between px-6 py-5 border-b border-zinc-800">
            <div class="flex items-center gap-x-3">
                <div class="w-9 h-9 theme-accent-bg rounded-2xl flex items-center justify-center">
                    <i class="fa-solid fa-link" style="color: var(--accent-contrast)"></i>
                </div>
                <span class="title-font text-3xl font-bold">Oikonomia</span>
            </div>

            <!-- 桌面版導航（≥768px 先顯示） -->
            <div id="nav-desktop" class="items-center gap-x-1 text-sm">
                <button onclick="showSection('dashboard')" class="px-5 py-2 nav-btn">Dashboard</button>
                <button onclick="showSection('explore')" class="px-5 py-2 nav-btn">探索</button>
                <button onclick="showSection('team')" class="px-5 py-2 nav-btn">Team</button>
                <button onclick="showSection('log')" class="px-5 py-2 nav-btn">日誌</button>
            </div>

            <!-- 手機版漢堡按鈕（<768px 先顯示） -->
            <button id="hamburger-btn" onclick="toggleMobileMenu()"
                    class="text-2xl text-zinc-300 hover:text-white px-2">
                <i class="fa-solid fa-bars"></i>
            </button>
        </div>

        <!-- 手機版彈出選單 -->
        <div id="mobile-menu" onclick="toggleMobileMenu()"
             class="fixed inset-0 bg-black/90 z-[60] pt-20 px-6">
            <div class="flex flex-col text-lg" onclick="event.stopPropagation()">
                <button onclick="showSection('dashboard'); toggleMobileMenu()" class="py-4 text-left border-b border-zinc-800">Dashboard</button>
                <button onclick="showSection('explore'); toggleMobileMenu()" class="py-4 text-left border-b border-zinc-800">探索</button>
                <button onclick="showSection('team'); toggleMobileMenu()" class="py-4 text-left border-b border-zinc-800">Team</button>
                <button onclick="showSection('log'); toggleMobileMenu()" class="py-4 text-left">日誌</button>
            </div>
        </div>

        <!-- 恢復登入中 -->
        <div id="session-loading" class="max-w-md mx-auto px-6 py-24 text-center">
            <i class="fa-solid fa-circle-notch fa-spin text-4xl theme-accent-text mb-4"></i>
            <p class="text-zinc-400">正在恢復登入狀態...</p>
        </div>

        <!-- Login -->
        <div id="login-screen" class="hidden max-w-md mx-auto px-6 py-16">
            <div class="text-center mb-8">
                <i class="fa-solid fa-user-secret text-6xl theme-accent-text mb-4"></i>
                <h1 class="text-3xl font-bold">歡迎進入Oikonomia的世界</h1>
                <p class="text-zinc-400 mt-2">輸入名稱登入（首次無需 PIN）</p>
            </div>
            <form onsubmit="login(event)" class="section-card rounded-3xl p-8 space-y-4">
                <input type="text" id="squad_id" placeholder="輸入你的名稱" 
                       class="w-full bg-zinc-900 border border-zinc-700 focus:border-amber-500 rounded-2xl px-6 py-4 text-xl mb-3">
                <input type="password" id="login_pin" placeholder="輸入 PIN（第一次登入可留空）" maxlength="4"
                       inputmode="numeric" pattern="[0-9]*"
                       class="w-full bg-zinc-900 border border-zinc-700 focus:border-amber-500 rounded-2xl px-6 py-4 text-xl tracking-widest text-center font-mono">
                <button type="submit" 
                        class="w-full theme-btn-primary font-semibold py-4 rounded-2xl">
                    進入 Oikonomia
                </button>
            </form>
        </div>

        <!-- Game Content -->
        <div id="game-content" class="hidden px-6 pb-12">
            <!-- Dashboard -->
            <div id="dashboard" class="section">
                <!-- Announcement History -->
                <div id="announcement-box" class="hidden mt-4 mb-10 bg-blue-900/30 border border-blue-500/30 rounded-3xl p-5">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-x-2">
                            <i class="fa-solid fa-bullhorn text-blue-400"></i>
                            <span class="font-medium text-blue-400">最新公告</span>
                        </div>
                        
                        <!-- 展開/收起按鈕 -->
                        <button id="toggle-announcement-btn" 
                                onclick="toggleAllAnnouncements()"
                                class="text-xs px-3 py-1 bg-blue-800 hover:bg-blue-700 rounded-full text-blue-200">
                            查看所有公告
                        </button>
                    </div>
                    
                    <!-- 最新一條公告 -->
                    <div id="latest-announcement"></div>
                    
                    <!-- 全部歷史公告（預設隱藏） -->
                    <div id="all-announcements" class="hidden mt-4 pt-4 border-t border-blue-700/50 space-y-3 text-sm"></div>
                </div>

                <div class="flex items-center gap-x-3 mb-6">
                    <img id="player-avatar"
                         src="/static/avatars/default.png"
                         class="w-16 h-16 rounded-full object-cover border-2 border-zinc-600 cursor-pointer"
                         onclick="showAvatarModal()">

                    <div>
                        <div class="flex items-center gap-x-2">
                            <div id="squad-name" class="text-4xl font-semibold"></div>
                            <button onclick="editDisplayName()"
                                    class="text-xs px-3 py-1 bg-zinc-700 hover:bg-zinc-600 rounded-xl flex items-center gap-x-1">
                                <i class="fa-solid fa-edit text-xs"></i>
                                <span>改名</span>
                            </button>
                        </div>
                        <div id="route-badge" class="hidden mt-2 text-sm"></div>
                        <div class="text-sm text-zinc-400 mt-1">點擊頭像更換角色頭像</div>
                    </div>
                </div>

                <!-- 路線選擇 -->
                <div id="route-picker" class="hidden mb-8 cartoon-box p-6">
                    <h3 class="text-lg font-bold mb-2">🔗 選擇你的路線</h3>
                    <p class="text-sm text-zinc-400 mb-4">A/B Line Unified Protocol — 選擇後無法更改</p>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div class="route-card route-iggy" onclick="selectRoute('iggy')">
                            <div class="text-xl font-bold">🔥 Iggy 路線</div>
                            <div class="text-sm mt-1 opacity-90">界線、力量、面對 Judas</div>
                        </div>
                        <div class="route-card route-marah" onclick="selectRoute('marah')">
                            <div class="text-xl font-bold">🌊 Marah 路線</div>
                            <div class="text-sm mt-1 opacity-90">智慧、韌性、深度連結</div>
                        </div>
                    </div>
                </div>

                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                    <!-- Squad 五維 -->
                    <div class="cartoon-box p-5">
                        <h3 class="font-bold mb-4 flex items-center gap-2 theme-card-title"><i class="fa-solid fa-shield-halved theme-accent-text"></i> Player Status</h3>
                        <div class="space-y-3">
                            <div class="stat-row" data-stat="hp"><div class="flex justify-between text-sm mb-1"><span>❤️ HP</span><span id="hp-value" class="font-mono">100</span></div><div class="h-2.5 stat-track rounded-full"><div id="hp-bar" class="h-2.5 rounded-full status-bar" style="width:100%;background:var(--progress-color)"></div></div></div>
                            <div class="stat-row" data-stat="sanity"><div class="flex justify-between text-sm mb-1"><span>🧠 Sanity</span><span id="sanity-value" class="font-mono">50</span></div><div class="h-2.5 stat-track rounded-full"><div id="sanity-bar" class="h-2.5 bg-purple-500 rounded-full status-bar" style="width:50%"></div></div></div>
                            <div class="stat-row" data-stat="power"><div class="flex justify-between text-sm mb-1"><span>⚡ Power</span><span id="power-value" class="font-mono">100</span></div><div class="h-2.5 stat-track rounded-full"><div id="power-bar" class="h-2.5 bg-orange-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div class="stat-row" data-stat="intellect"><div class="flex justify-between text-sm mb-1"><span>📖 Intellect</span><span id="intellect-value" class="font-mono">100</span></div><div class="h-2.5 stat-track rounded-full"><div id="intellect-bar" class="h-2.5 bg-blue-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div class="stat-row" data-stat="resilience"><div class="flex justify-between text-sm mb-1"><span>🛡️ Resilience</span><span id="resilience-value" class="font-mono">100</span></div><div class="h-2.5 stat-track rounded-full"><div id="resilience-bar" class="h-2.5 bg-emerald-500 rounded-full status-bar" style="width:100%"></div></div></div>
                        </div>
                        <div class="mt-4 pt-3 border-t border-zinc-700 flex justify-between text-sm">
                            <span><i class="fa-solid fa-gem text-purple-400 mr-1"></i>Resource</span>
                            <span id="resource-value" class="font-mono text-purple-400">0</span>
                        </div>
                    </div>

                    <!-- Iggy 五維（已選 Iggy 路線時顯示） -->
                    <div id="iggy-card" class="cartoon-box p-5" style="display:none">
                        <h3 class="font-bold mb-4">🔥 Iggy</h3>
                        <div class="space-y-3">
                            <div><div class="flex justify-between text-sm mb-1"><span>❤️ HP</span><span id="iggy-hp-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="iggy-hp-bar" class="h-2.5 bg-red-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>🧠 Sanity</span><span id="iggy-sanity-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="iggy-sanity-bar" class="h-2.5 bg-purple-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>⚡ Power</span><span id="iggy-power-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="iggy-power-bar" class="h-2.5 bg-orange-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>📖 Intellect</span><span id="iggy-intellect-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="iggy-intellect-bar" class="h-2.5 bg-blue-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>🛡️ Resilience</span><span id="iggy-resilience-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="iggy-resilience-bar" class="h-2.5 bg-emerald-500 rounded-full status-bar" style="width:100%"></div></div></div>
                        </div>
                    </div>

                    <!-- Marah 五維（已選 Marah 路線時顯示） -->
                    <div id="marah-card" class="cartoon-box p-5" style="display:none">
                        <h3 class="font-bold mb-4">🌊 Marah</h3>
                        <div class="space-y-3">
                            <div><div class="flex justify-between text-sm mb-1"><span>❤️ HP</span><span id="marah-hp-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="marah-hp-bar" class="h-2.5 bg-red-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>🧠 Sanity</span><span id="marah-sanity-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="marah-sanity-bar" class="h-2.5 bg-purple-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>⚡ Power</span><span id="marah-power-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="marah-power-bar" class="h-2.5 bg-orange-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>📖 Intellect</span><span id="marah-intellect-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="marah-intellect-bar" class="h-2.5 bg-blue-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>🛡️ Resilience</span><span id="marah-resilience-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="marah-resilience-bar" class="h-2.5 bg-emerald-500 rounded-full status-bar" style="width:100%"></div></div></div>
                        </div>
                    </div>
                </div>

                <!-- 持有物品 -->
                <div class="cartoon-box p-5 mb-8">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="font-bold text-lg flex items-center gap-x-2 theme-card-title">
                            <i class="fa-solid fa-box-open theme-accent-text"></i>
                            <span>持有物品</span>
                            <span id="items-slot-label" class="text-xs font-normal theme-muted-text">(0/5)</span>
                        </h3>
                        <div class="flex items-center gap-2">
                            <button onclick="startQRScanner()"
                                    class="text-xs px-3 py-1.5 theme-btn-primary rounded-xl flex items-center gap-x-1 font-medium">
                                <i class="fa-solid fa-qrcode"></i>
                                <span>掃描 QR</span>
                            </button>
                            <button onclick="loadMyItems()"
                                    class="text-xs px-3 py-1 bg-zinc-700 hover:bg-zinc-600 rounded-xl">刷新</button>
                        </div>
                    </div>
                    <div id="my-items-list" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div class="text-sm text-zinc-400 col-span-full text-center py-4">載入中...</div>
                    </div>
                </div>

                <!-- Zoo Skills -->
                <div>
                    <div class="font-medium mb-3 flex items-center gap-x-2">
                        <i class="fa-solid fa-magic theme-accent-text"></i>
                        <span>Zoo 能力</span>
                    </div>
                    <div class="grid grid-cols-2 gap-3" id="zoo-list">
                        <div class="bg-zinc-800 border border-zinc-700 rounded-2xl p-4 text-sm">
                            <div class="text-amber-400 font-medium">溫柔之焰</div>
                            <div class="text-xs text-zinc-400 mt-1">幫助 Iggy 冷靜</div>
                        </div>
                        <div class="bg-zinc-800 border border-zinc-700 rounded-2xl p-4 text-sm">
                            <div class="text-amber-400 font-medium">界線共鳴</div>
                            <div class="text-xs text-zinc-400 mt-1">感受他人痛楚</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ==================== 日誌頁面 ==================== -->
            <div id="log" class="section hidden">
                <div class="mb-8 flex items-center gap-x-4">
                    <img id="log-player-avatar"
                         src="/static/avatars/default.png"
                         class="w-12 h-12 rounded-full object-cover border border-zinc-600">
                    <div>
                        <div class="text-sm theme-accent-text">LOG</div>
                        <div class="text-3xl font-semibold">故事與任務記錄</div>
                    </div>
                </div>

                <div class="cartoon-box p-6 mb-8">
                    <h3 class="font-bold text-xl mb-4 flex items-center gap-x-2">
                        <i class="fa-solid fa-book text-amber-400"></i>
                        <span>故事進度</span>
                    </h3>
                    <div id="story-log-content"></div>
                </div>

                <div class="cartoon-box p-6 mb-8">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="font-bold text-xl flex items-center gap-x-2">
                            <i class="fa-solid fa-tasks text-amber-400"></i>
                            <span id="team-task-logs-title">任務記錄</span>
                        </h3>
                        <button onclick="loadTeamTaskLogs()"
                                class="text-xs px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-2xl">
                            刷新記錄
                        </button>
                    </div>
                    <div id="team-task-logs" class="space-y-3"></div>
                </div>

                <!-- 全球事件記錄（日誌頁最底部） -->
                <div class="cartoon-box p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="font-bold text-xl flex items-center gap-x-2">
                            <i class="fa-solid fa-globe text-amber-400"></i>
                            <span>全球事件記錄</span>
                        </h3>
                        <button onclick="loadGlobalEvents()"
                                class="text-xs px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-2xl">
                            刷新
                        </button>
                    </div>
                    <div id="global-events-list" class="space-y-3"></div>
                </div>
            </div>

            <!-- Explore -->
            <div id="explore" class="section hidden">
                <h2 class="text-2xl font-semibold mb-4">探索地點</h2>
                <div id="location-list" class="space-y-4"></div>
            </div>

            <!-- Team 區塊 -->
            <div id="team" class="section hidden">
                <div class="mb-6">
                    <div class="text-sm theme-accent-text">TEAM</div>
                    <div class="text-3xl font-semibold">你的小隊</div>
                </div>

                <!-- 未有 Team 時顯示（改為列表模式） -->
                <div id="no-team-box" class="hidden cartoon-box p-8">
                    <div class="text-center mb-6">
                        <i class="fa-solid fa-users text-5xl text-zinc-600 mb-4"></i>
                        <h3 class="text-xl font-bold mb-2">你尚未加入任何 Team</h3>
                        <p class="text-zinc-400">請選擇一個 Team 加入，或建立新隊</p>
                    </div>

                    <!-- 建立新隊 -->
                    <div class="border-t border-zinc-700 pt-5">
                        <div class="text-sm text-zinc-400 mb-2 px-1">或者建立新隊</div>
                        <div class="flex gap-x-2">
                            <input type="text" id="create-team-name" placeholder="輸入隊名（例如：界線守護者）" 
                                   class="flex-1 bg-zinc-900 border border-zinc-700 rounded-2xl px-5 py-3 text-sm">
                            <button onclick="createMyTeam()" 
                                    class="px-6 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-2xl whitespace-nowrap">
                                建立新隊
                            </button>
                        </div>
                    </div>
                </div>

                <!-- 已有 Team 時顯示 -->
                <div id="has-team-box" class="hidden">
                    <div class="cartoon-box p-6 mb-6">
                        <div class="flex justify-between items-center">
                            <div>
                                <div class="text-xs text-emerald-400">TEAM NAME</div>
                                <div id="my-team-name" class="text-2xl font-bold"></div>
                                <div id="my-team-id" class="font-mono text-xs text-zinc-500"></div>
                            </div>
                            <div id="my-team-route-badge"></div>
                        </div>
                    </div>

                    <div class="mb-4 flex items-center justify-between">
                        <div class="font-semibold">隊友列表</div>
                        <button onclick="loadMyTeam()" class="text-xs px-3 py-1 bg-zinc-700 rounded-xl">刷新</button>
                    </div>
                    <div id="team-protagonists-section" class="hidden grid grid-cols-1 md:grid-cols-2 gap-4 mb-6"></div>

                    <div id="team-members-list" class="grid grid-cols-1 md:grid-cols-2 gap-4"></div>

                    <div class="cartoon-box p-5 mt-6">
                        <div class="flex items-center justify-between mb-4">
                            <h3 class="font-bold flex items-center gap-x-2">
                                <i class="fa-solid fa-clipboard-list text-amber-400"></i>
                                <span>全隊任務日誌</span>
                            </h3>
                            <button onclick="loadTeamTaskLogs()"
                                    class="text-xs px-3 py-1 bg-zinc-700 hover:bg-zinc-600 rounded-xl">
                                刷新
                            </button>
                        </div>
                        <div id="team-task-logs-list" class="space-y-3 max-h-[400px] overflow-auto pr-1"></div>
                    </div>
                </div>

                <!-- 所有 Team 列表（同 GM 一致，永遠顯示） -->
                <div class="cartoon-box p-5 mt-6">
                    <div class="flex items-center justify-between mb-3">
                        <div class="font-semibold text-sm">所有 Team</div>
                        <button onclick="loadAvailableTeams()" 
                                class="text-xs px-3 py-1 bg-zinc-700 hover:bg-zinc-600 rounded-xl flex items-center gap-x-1">
                            <i class="fa-solid fa-sync text-xs"></i>
                            <span>刷新列表</span>
                        </button>
                    </div>
                    <div id="available-teams-list" class="space-y-2 max-h-[280px] overflow-auto pr-1"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentSquad = null;

        function setVisible(el, visible) {
            if (!el) return;
            el.classList.toggle('hidden', !visible);
            el.style.display = visible ? '' : 'none';
        }

        function toggleMobileMenu() {
            const menu = document.getElementById('mobile-menu');
            if (menu) menu.classList.toggle('menu-open');
        }

        function showNavAfterLogin() {
            document.getElementById('nav-desktop')?.classList.add('nav-visible');
            document.getElementById('hamburger-btn')?.classList.add('nav-visible');
        }

        function showSection(id) {
            document.querySelectorAll('.section').forEach(s => setVisible(s, false));
            setVisible(document.getElementById(id), true);
            if (id === 'explore') loadLocations();
            if (id === 'dashboard') loadMyItems();
            if (id === 'team') loadMyTeam();
            if (id === 'log') {
                loadStoryLog();
                loadTeamTaskLogs();
                loadGlobalEvents();
            }
        }

        async function loadStoryLog() {
            const container = document.getElementById('story-log-content');
            container.innerHTML = '<div class="text-zinc-400">載入故事中...</div>';

            try {
                const res = await fetch('/story_progress', { credentials: 'same-origin' });
                const data = await res.json();

                const stage = data.stage || 0;
                const completed = data.completed_tasks || 0;
                const story = data.story || {};
                const title = story.title || '故事進行中';
                const content = story.content || '';

                let progressHint = '';
                if (data.next_stage_at != null) {
                    const remaining = Math.max(0, data.next_stage_at - completed);
                    progressHint = `<div class="text-xs text-zinc-500 mt-3">距離下一階段還需 ${remaining} 個新任務（門檻：${data.next_stage_at} 個）</div>`;
                } else if (stage >= 3) {
                    progressHint = `<div class="text-xs text-amber-400/80 mt-3">你已達最終故事階段</div>`;
                }

                container.innerHTML = `
                    <div class="mb-3 flex flex-wrap gap-2">
                        <div class="inline-block px-3 py-1 bg-zinc-700 rounded-full text-xs">
                            已完成任務：${completed} 個
                        </div>
                        <div class="inline-block px-3 py-1 bg-zinc-800 border border-zinc-600 rounded-full text-xs">
                            故事階段：Stage ${stage}
                        </div>
                    </div>
                    <div class="text-xl font-bold mb-2">${title}</div>
                    <div class="text-zinc-300 leading-relaxed">${content}</div>
                    ${progressHint}
                `;

            } catch (e) {
                container.innerHTML = '<div class="text-red-400">載入故事失敗</div>';
            }
        }

        function renderTeamTaskLogEntries(container, logs, options = {}) {
            const { showPlayer = false, emptyText = '暫無任務記錄' } = options;

            if (!logs || logs.length === 0) {
                container.innerHTML = `<div class="text-zinc-400 py-6 text-center">${emptyText}</div>`;
                return;
            }

            container.innerHTML = '';
            logs.forEach(log => {
                const taskName = log.task_name || log.task_id || '未知任務';
                const description = log.description || log.content || '';
                const status = log.status || '已完成';
                const el = document.createElement('div');
                el.className = 'log-item bg-zinc-800 border border-zinc-700 rounded-2xl p-4';
                el.innerHTML = `
                    <div class="flex justify-between items-start gap-x-3 mb-2">
                        <div>
                            ${showPlayer ? `<strong class="text-zinc-100">${log.display_name}</strong>` : ''}
                            <span class="text-xs px-2 py-0.5 bg-emerald-900/50 text-emerald-400 rounded-full ml-1">${status}</span>
                        </div>
                        <div class="text-xs text-zinc-500 whitespace-nowrap">${log.timestamp}</div>
                    </div>
                    <div class="text-sm">
                        <strong class="text-zinc-300">任務：</strong>
                        <span class="font-mono text-amber-400">${taskName}</span>
                    </div>
                    ${description ? `<div class="text-zinc-400 text-sm mt-1">${description}</div>` : ''}
                    ${(log.photo_url || log.photo_path) ? `
                        <div class="mt-2">
                            <img src="${log.photo_url || '/' + log.photo_path}" class="max-h-48 rounded-xl border border-zinc-700">
                        </div>
                    ` : ''}
                `;
                container.appendChild(el);
            });
        }

        async function loadTeamTaskLogs() {
            const logPageContainer = document.getElementById('team-task-logs');
            const teamPageContainer = document.getElementById('team-task-logs-list');
            const titleEl = document.getElementById('team-task-logs-title');

            if (!logPageContainer && !teamPageContainer) return;

            if (logPageContainer) logPageContainer.innerHTML = '<div class="text-zinc-400">載入中...</div>';
            if (teamPageContainer) teamPageContainer.innerHTML = '<div class="text-zinc-400">載入中...</div>';

            try {
                const res = await fetch('/team_task_logs', { credentials: 'same-origin' });
                const data = await res.json();

                if (logPageContainer) {
                    if (titleEl) {
                        titleEl.textContent = data.has_team ? '👥 全隊任務日誌' : '📋 個人任務日誌';
                    }
                    renderTeamTaskLogEntries(logPageContainer, data.logs, {
                        showPlayer: !!data.has_team,
                        emptyText: data.has_team ? '全隊尚未有任務記錄' : '暫無任務記錄',
                    });
                }

                if (teamPageContainer) {
                    if (!data.has_team) {
                        teamPageContainer.innerHTML = '<div class="text-zinc-400 py-4 text-center">你尚未加入 Team</div>';
                    } else {
                        renderTeamTaskLogEntries(teamPageContainer, data.logs, {
                            showPlayer: true,
                            emptyText: '全隊尚未有任務記錄',
                        });
                    }
                }
            } catch (e) {
                console.error('載入任務日誌失敗', e);
                if (logPageContainer) logPageContainer.innerHTML = '<div class="text-red-400">載入失敗</div>';
                if (teamPageContainer) teamPageContainer.innerHTML = '<div class="text-red-400">載入失敗</div>';
            }
        }

        function formatGlobalEffect(ev) {
            if (!ev.effect_type || ev.effect_type === 'announcement') return '';
            const labels = {
                adjust_sanity: 'Sanity 調整',
                sanity_adjust: 'Sanity 調整',
                sanity_down: 'Sanity 下降',
                sanity_up: 'Sanity 上升',
                power_up: 'Power 上升',
                intellect_up: 'Intellect 上升',
                resilience_up: 'Resilience 上升',
                judas_strengthen: 'Judas 加強',
                iggy_collapse: 'Iggy 崩潰',
                global_debuff: '全球減益',
            };
            const label = labels[ev.effect_type] || ev.effect_type;
            if (ev.effect_value) {
                const sign = ev.effect_value > 0 ? '+' : '';
                return `${label} ${sign}${ev.effect_value}`;
            }
            return label;
        }

        async function loadGlobalEvents() {
            const container = document.getElementById('global-events-list');
            if (!container) return;
            container.innerHTML = '<div class="text-zinc-400">載入中...</div>';

            const eventIcons = {
                adjust_sanity: '🧠',
                sanity_adjust: '🧠',
                sanity_down: '🧠',
                sanity_up: '🧠',
                power_up: '⚡',
                intellect_up: '📚',
                resilience_up: '🛡️',
                judas_strengthen: '⚔️',
                iggy_collapse: '🔥',
                announcement: '📢',
                global_debuff: '💀',
            };

            try {
                const res = await fetch('/global_events', { credentials: 'same-origin' });
                const data = await res.json();

                if (!data.events || data.events.length === 0) {
                    container.innerHTML = '<div class="text-zinc-400 py-4 text-center">暫無全球事件</div>';
                    return;
                }

                container.innerHTML = '';
                data.events.forEach(event => {
                    const icon = eventIcons[event.effect_type] || '🌍';
                    const effectText = formatGlobalEffect(event);
                    const el = document.createElement('div');
                    el.className = 'global-event-item bg-zinc-800 border border-zinc-700 rounded-2xl p-4';
                    el.innerHTML = `
                        <div class="flex justify-between items-start gap-x-3">
                            <div class="flex gap-x-2 min-w-0">
                                <span class="text-lg shrink-0">${icon}</span>
                                <div class="min-w-0">
                                    <div class="font-semibold text-red-400">${event.title}</div>
                                    ${event.description ? `<div class="text-zinc-300 text-sm mt-1 leading-relaxed">${event.description}</div>` : ''}
                                    ${event.effect_type ? `
                                        <div class="mt-2 flex flex-wrap items-center gap-2 text-xs">
                                            <span class="px-2 py-0.5 bg-zinc-700 rounded-full text-zinc-300">${event.effect_type}</span>
                                            <span class="text-zinc-400">數值: ${event.effect_value ?? 0}</span>
                                            ${effectText ? `<span class="text-amber-400">${effectText}</span>` : ''}
                                        </div>
                                    ` : ''}
                                    ${event.created_by ? `<div class="text-xs text-zinc-500 mt-1">由 ${event.created_by} 觸發</div>` : ''}
                                </div>
                            </div>
                            <div class="text-xs text-zinc-500 whitespace-nowrap shrink-0">${event.timestamp}</div>
                        </div>
                    `;
                    container.appendChild(el);
                });
            } catch (e) {
                container.innerHTML = '<div class="text-red-400">載入失敗</div>';
            }
        }

        function closeModal(el) {
            const modal = el?.closest?.('.modal-overlay') || el?.closest?.('.fixed');
            if (modal) modal.remove();
        }

        function setStatBar(prefix, stat, value) {
            const el = document.getElementById(prefix + stat + '-value');
            const bar = document.getElementById(prefix + stat + '-bar');
            if (el) el.textContent = value;
            if (bar) bar.style.width = value + '%';
        }

        function setText(id, value) {
            const el = document.getElementById(id);
            if (el) el.textContent = value ?? 0;
        }

        async function editDisplayName() {
            const current = currentSquad.display_name || currentSquad.squad_id;
            const newName = prompt('輸入新顯示名稱（最多 20 字）', current);
            if (!newName || newName.trim() === current) return;

            const res = await fetch('/update_display_name', {
                method: 'POST',
                credentials: 'same-origin',
                body: new URLSearchParams({display_name: newName.trim()})
            });
            const data = await res.json();

            if (data.success) {
                currentSquad.display_name = data.display_name;
                document.getElementById('squad-name').textContent = data.display_name;
                alert('名稱已更新！');
            } else {
                alert(data.error || '更新失敗');
            }
        }

        async function editTeamName(teamId, currentName) {
            const newName = prompt('輸入新隊名（最多 30 字）', currentName);
            if (!newName || newName.trim() === currentName) return;

            const res = await fetch('/team/update_name', {
                method: 'POST',
                credentials: 'same-origin',
                body: new URLSearchParams({ team_name: newName.trim() })
            });

            const data = await res.json();

            if (data.success) {
                document.getElementById('my-team-name').textContent = data.team_name;
                loadAvailableTeams();
                alert('隊名已更新！');
            } else {
                alert(data.error || '更新失敗');
            }
        }

        function renderProtagonistStats(prefix, stats) {
            ['hp', 'sanity', 'power', 'intellect', 'resilience'].forEach(s => {
                setStatBar(prefix, s, stats?.[s] ?? 100);
            });
        }

        function showOnlyProtagonistCard(route, protagonists) {
            const iggyCard = document.getElementById('iggy-card');
            const marahCard = document.getElementById('marah-card');
            if (!iggyCard || !marahCard) return;

            iggyCard.style.display = 'none';
            marahCard.style.display = 'none';
            iggyCard.classList.remove('ring-2', 'ring-amber-500/50');
            marahCard.classList.remove('ring-2', 'ring-amber-500/50');

            const iggy = protagonists?.iggy || {};
            const marah = protagonists?.marah || {};

            if (route === 'iggy') {
                iggyCard.style.display = 'block';
                iggyCard.classList.add('ring-2', 'ring-amber-500/50');
                renderProtagonistStats('iggy-', iggy);
            } else if (route === 'marah') {
                marahCard.style.display = 'block';
                marahCard.classList.add('ring-2', 'ring-amber-500/50');
                renderProtagonistStats('marah-', marah);
            }
        }

        function buildProtagonistCardHtml(title, prefix, stats, isActive) {
            const ring = isActive ? 'ring-active-route' : '';
            const statsList = ['hp', 'sanity', 'power', 'intellect', 'resilience'];
            const labels = {hp: '❤️ HP', sanity: '🧠 San', power: '⚡ Pow', intellect: '📖 Int', resilience: '🛡️ Res'};
            const colors = {hp: 'text-red-400', sanity: 'text-purple-400', power: 'text-orange-400', intellect: 'text-blue-400', resilience: 'text-emerald-400'};
            const barColors = {hp: 'bg-red-500', sanity: 'bg-purple-500', power: 'bg-orange-500', intellect: 'bg-blue-500', resilience: 'bg-emerald-500'};
            const rows = statsList.map(s => `
                <div>
                    <div class="flex justify-between text-xs mb-1"><span>${labels[s]}</span><span class="font-mono ${colors[s]}">${stats?.[s] ?? 100}</span></div>
                    <div class="h-2 stat-track rounded-full"><div class="h-2 rounded-full status-bar ${barColors[s]}" style="width:${stats?.[s] ?? 100}%"></div></div>
                </div>
            `).join('');
            return `
                <div class="cartoon-box p-5 ${ring}">
                    <h3 class="font-bold mb-4 theme-card-title">${title}${isActive ? ' <span class="text-xs theme-accent-text">(使用中)</span>' : ''}</h3>
                    <div class="space-y-2">${rows}</div>
                </div>
            `;
        }

        function renderTeamProtagonists(protagonists) {
            const section = document.getElementById('team-protagonists-section');
            if (!section) return;
            const route = protagonists?.active_route;
            if (!protagonists || !route) {
                section.classList.add('hidden');
                section.innerHTML = '';
                return;
            }
            section.classList.remove('hidden');
            if (route === 'iggy') {
                section.innerHTML = buildProtagonistCardHtml('🔥 Iggy', 'iggy', protagonists.iggy, true);
            } else if (route === 'marah') {
                section.innerHTML = buildProtagonistCardHtml('🌊 Marah', 'marah', protagonists.marah, true);
            } else {
                section.classList.add('hidden');
                section.innerHTML = '';
            }
        }

        const THEME_VARS = {
            default: {
                '--bg-main': '#0D0D0D',
                '--bg-color': '#0D0D0D',
                '--bg-gradient-start': '#0D0D0D',
                '--bg-gradient-mid': '#141414',
                '--bg-gradient-end': '#141414',
                '--bg-glow': 'transparent',
                '--card-bg': '#1F1F1F',
                '--card-border': '#555555',
                '--text-primary': '#FFFFFF',
                '--text-secondary': '#AAAAAA',
                '--text-color': '#FFFFFF',
                '--text-muted': '#AAAAAA',
                '--accent-gold': '#FFFFFF',
                '--accent-orange': '#888888',
                '--accent-color': '#FFFFFF',
                '--accent-contrast': '#0D0D0D',
                '--accent-soft': 'rgba(255, 255, 255, 0.12)',
                '--progress-bg': '#333333',
                '--progress-track': '#333333',
                '--progress-color': '#888888',
                '--header-border': 'rgba(63, 63, 70, 0.8)',
                '--shadow-color': 'rgba(44, 62, 80, 0.6)',
                '--card-glow': 'none',
            },
            iggy: {
                '--bg-main': '#0D0D0D',
                '--bg-color': '#0D0D0D',
                '--bg-gradient-start': '#3D1A2E',
                '--bg-gradient-mid': '#1a0f14',
                '--bg-gradient-end': '#0D0D0D',
                '--bg-glow': 'rgba(212, 160, 23, 0.1)',
                '--card-bg': '#4A1C2E',
                '--card-border': '#D4A017',
                '--text-primary': '#F5E8C7',
                '--text-secondary': '#C9A36A',
                '--text-color': '#F5E8C7',
                '--text-muted': '#C9A36A',
                '--accent-gold': '#D4A017',
                '--accent-orange': '#E07A5F',
                '--accent-color': '#D4A017',
                '--accent-contrast': '#1a0f14',
                '--accent-soft': 'rgba(212, 160, 23, 0.22)',
                '--progress-bg': '#3D1A2E',
                '--progress-track': '#3D1A2E',
                '--progress-color': '#E07A5F',
                '--header-border': 'rgba(212, 160, 23, 0.45)',
                '--shadow-color': 'rgba(61, 26, 46, 0.85)',
                '--card-glow': '0 0 24px rgba(212, 160, 23, 0.18), inset 0 1px 0 rgba(212, 160, 23, 0.15)',
            },
            marah: {
                '--bg-main': '#0D0D0D',
                '--bg-color': '#0D0D0D',
                '--bg-gradient-start': '#152033',
                '--bg-gradient-mid': '#0f1a2e',
                '--bg-gradient-end': '#0D0D0D',
                '--bg-glow': 'rgba(74, 144, 164, 0.08)',
                '--card-bg': '#1E2A44',
                '--card-border': '#4A90A4',
                '--text-primary': '#E8E8E8',
                '--text-secondary': '#9ca8b8',
                '--text-color': '#E8E8E8',
                '--text-muted': '#9ca8b8',
                '--accent-gold': '#C0C0C0',
                '--accent-orange': '#4A90A4',
                '--accent-color': '#C0C0C0',
                '--accent-contrast': '#0f1520',
                '--accent-soft': 'rgba(74, 144, 164, 0.28)',
                '--progress-bg': '#152033',
                '--progress-track': '#152033',
                '--progress-color': '#4A90A4',
                '--header-border': 'rgba(74, 144, 164, 0.38)',
                '--shadow-color': 'rgba(30, 42, 68, 0.75)',
                '--card-glow': '0 0 20px rgba(74, 144, 164, 0.12), inset 0 1px 0 rgba(192, 192, 192, 0.08)',
            },
        };

        function applyThemeVars(themeName) {
            const root = document.documentElement;
            const vars = THEME_VARS[themeName] || THEME_VARS.default;
            Object.entries(vars).forEach(([key, value]) => {
                root.style.setProperty(key, value);
            });
        }

        function applyDefaultTheme() {
            applyThemeVars('default');
        }

        function applyIggyTheme() {
            applyThemeVars('iggy');
        }

        function applyMarahTheme() {
            applyThemeVars('marah');
        }

        function applyRouteTheme(route) {
            const body = document.body;
            body.classList.remove('theme-iggy', 'theme-marah');
            if (route === 'iggy') {
                body.classList.add('theme-iggy');
                applyIggyTheme();
            } else if (route === 'marah') {
                body.classList.add('theme-marah');
                applyMarahTheme();
            } else {
                applyDefaultTheme();
            }
        }

        function updateDashboard(data) {
            const squad = data.squad_id ? data : (data.squad || data);
            const protagonists = data.protagonists || squad.protagonists;
            const route = data.route || data.team?.route || squad.route;

            applyRouteTheme(route);

            ['hp','sanity','power','intellect','resilience'].forEach(s => setStatBar('', s, squad[s] ?? 100));
            document.getElementById('resource-value').textContent = squad.resources || 0;
            document.getElementById('squad-name').textContent = squad.display_name || squad.squad_id;

            const routePicker = document.getElementById('route-picker');
            const routeBadge = document.getElementById('route-badge');
            const isLeader = squad.is_team_leader === 1;
            const inTeam = !!(squad.team_id || data.team);

            showOnlyProtagonistCard(route, protagonists || {});

            if (routePicker) setVisible(routePicker, !route && (!inTeam || isLeader));

            if (routeBadge) {
                if (route === 'iggy') {
                    setVisible(routeBadge, true);
                    routeBadge.innerHTML = `<span class="inline-flex items-center gap-x-1 px-3 py-1 bg-red-900/60 text-red-400 rounded-full text-xs font-medium">🔥 Iggy 路線</span>`;
                } else if (route === 'marah') {
                    setVisible(routeBadge, true);
                    routeBadge.innerHTML = `<span class="inline-flex items-center gap-x-1 px-3 py-1 bg-blue-900/60 text-blue-400 rounded-full text-xs font-medium">🌊 Marah 路線</span>`;
                } else if (inTeam && !isLeader) {
                    setVisible(routeBadge, true);
                    routeBadge.innerHTML = `<span class="text-xs text-zinc-400">等待隊長選擇路線...</span>`;
                } else {
                    setVisible(routeBadge, true);
                    routeBadge.innerHTML = `<span class="text-xs text-zinc-500">未選擇路線</span>`;
                }
            }

            if (currentSquad) {
                Object.assign(currentSquad, squad);
                if (protagonists) currentSquad.protagonists = protagonists;
                if (route) currentSquad.route = route;
                if (data.team) currentSquad.team = data.team;
            }
            initPlayerAvatar();
        }

        async function selectRoute(route) {
            if (!confirm(route === 'iggy' ? '確認選擇 Iggy 路線？' : '確認選擇 Marah 路線？')) return;

            const useTeamRoute = currentSquad && currentSquad.is_team_leader === 1 && currentSquad.team_id;
            const endpoint = useTeamRoute ? '/set_team_route_by_leader' : '/set_route';

            const res = await fetch(endpoint, {
                method: 'POST',
                credentials: 'same-origin',
                body: new URLSearchParams({route})
            });
            const data = await res.json();

            if (!data.success) {
                alert(data.error || '選擇失敗');
                return;
            }

            if (data.squad_id) {
                currentSquad = data;
            } else if (data.squad) {
                currentSquad = { ...data.squad, route: data.route, team: data.team, protagonists: data.protagonists };
            } else {
                const statusRes = await fetch('/status', { credentials: 'same-origin' });
                currentSquad = await statusRes.json();
            }
            updateDashboard(currentSquad);

            const picker = document.getElementById('route-picker');
            if (picker) setVisible(picker, false);
        }

        async function loadMyTeam() {
            const noBox = document.getElementById('no-team-box');
            const hasBox = document.getElementById('has-team-box');
            try {
                const res = await fetch('/my_team', { credentials: 'same-origin' });
                const data = await res.json();

                if (!data.has_team) {
                    setVisible(noBox, true);
                    setVisible(hasBox, false);
                    applyRouteTheme(data.route || (currentSquad && currentSquad.route));
                } else {
                    setVisible(noBox, false);
                    setVisible(hasBox, true);
                    applyRouteTheme(data.route || data.team?.route);
                    if (currentSquad && data.route) currentSquad.route = data.route;
                }

                if (!data.has_team) {
                    loadAvailableTeams();
                    return;
                }

                const team = data.team;
                const isLeader = data.is_team_leader === 1;
                if (currentSquad) currentSquad.is_team_leader = data.is_team_leader;
                const safeTeamName = (team.team_name || '').replace(/'/g, "\\'");
                const currentSquadId = data.current_squad_id;

                let teamNameHTML = `
                    <div class="flex items-center gap-x-2">
                        <div id="my-team-name" class="text-2xl font-bold">${team.team_name}</div>
                `;

                if (isLeader) {
                    teamNameHTML += `
                        <button onclick="editTeamName('${team.team_id}', '${safeTeamName}')"
                                class="text-xs px-3 py-1 bg-zinc-700 hover:bg-zinc-600 rounded-xl flex items-center gap-x-1">
                            <i class="fa-solid fa-edit"></i>
                            <span>改名</span>
                        </button>
                    `;
                }

                teamNameHTML += `</div>`;

                document.querySelector('#has-team-box .cartoon-box').innerHTML = `
                    <div class="flex justify-between items-center">
                        <div>
                            <div class="text-xs text-emerald-400">TEAM NAME</div>
                            ${teamNameHTML}
                            <div id="my-team-id" class="font-mono text-xs text-zinc-500">${team.team_id}</div>
                        </div>
                        <div id="my-team-route-badge"></div>
                    </div>
                `;

                const routeBadge = document.getElementById('my-team-route-badge');
                if (team.route === 'iggy') {
                    routeBadge.innerHTML = '<div class="text-xs px-3 py-1 rounded-full bg-red-900/50 text-red-300">🔥 Iggy 線</div>';
                } else if (team.route === 'marah') {
                    routeBadge.innerHTML = '<div class="text-xs px-3 py-1 rounded-full bg-blue-900/50 text-blue-300">🌊 Marah 線</div>';
                } else {
                    routeBadge.innerHTML = '<div class="text-xs px-3 py-1 rounded-full bg-zinc-700 text-zinc-400">未設定路線</div>';
                }

                renderTeamProtagonists(data.protagonists);

                const list = document.getElementById('team-members-list');
                list.innerHTML = '';
                const members = data.members || [];
                if (members.length === 0) {
                    list.innerHTML = '<div class="text-zinc-400 col-span-2 text-center py-6">暫無隊友</div>';
                } else {
                members.forEach(m => {
                    const isYou = currentSquadId && m.squad_id === currentSquadId;
                    const isMemberLeader = m.is_leader || m.is_team_leader === 1;
                    const el = document.createElement('div');
                    el.className = 'cartoon-box p-4' + (isYou ? ' ring-2 ring-amber-500/50' : '');

                    const displayName = m.display_name || m.squad_id;
                    const leaderBadge = isMemberLeader
                        ? '<span class="ml-2 text-xs px-2 py-0.5 bg-amber-500 text-zinc-950 rounded-full font-medium">👑 隊長</span>'
                        : '';
                    const transferBtn = (isYou && isMemberLeader && isLeader)
                        ? `<button onclick="showTransferModal()"
                                   class="text-xs px-3 py-1 bg-amber-600 hover:bg-amber-700 text-zinc-950 rounded-xl font-medium shrink-0">
                               轉讓隊長
                           </button>`
                        : '';

                    el.innerHTML = `
                        <div class="flex items-center gap-x-3">
                            <img src="${avatarSrc(m.avatar)}"
                                 class="w-12 h-12 rounded-full object-cover border border-zinc-600 shrink-0">
                            <div class="flex-1 min-w-0">
                                <div class="font-semibold text-lg flex flex-wrap items-center gap-x-1">
                                    <span>${displayName}</span>
                                    ${leaderBadge}
                                    ${isYou ? '<span class="text-xs text-amber-400">(你)</span>' : ''}
                                </div>
                            </div>
                            ${transferBtn}
                        </div>

                        <div class="grid grid-cols-5 gap-1 mt-3 text-center text-xs">
                            <div>
                                <div class="text-red-400 font-mono">${m.hp}</div>
                                <div class="text-zinc-500">HP</div>
                            </div>
                            <div>
                                <div class="text-purple-400 font-mono">${m.sanity}</div>
                                <div class="text-zinc-500">San</div>
                            </div>
                            <div>
                                <div class="text-orange-400 font-mono">${m.power}</div>
                                <div class="text-zinc-500">Pow</div>
                            </div>
                            <div>
                                <div class="text-blue-400 font-mono">${m.intellect}</div>
                                <div class="text-zinc-500">Int</div>
                            </div>
                            <div>
                                <div class="text-emerald-400 font-mono">${m.resilience}</div>
                                <div class="text-zinc-500">Res</div>
                            </div>
                        </div>
                    `;
                    list.appendChild(el);
                });
                }
                loadTeamTaskLogs();
                loadAvailableTeams();
            } catch (e) {
                console.error('loadMyTeam failed', e);
                setVisible(noBox, true);
                setVisible(hasBox, false);
                loadAvailableTeams();
            }
        }

        async function showTransferModal() {
            const modal = document.getElementById('transfer-modal');
            const select = document.getElementById('transfer-target');
            if (!modal || !select) return;

            select.innerHTML = '<option value="">載入中...</option>';
            modal.classList.remove('hidden');
            modal.classList.add('flex');

            try {
                const res = await fetch('/my_team', { credentials: 'same-origin' });
                const data = await res.json();
                select.innerHTML = '';

                const currentId = data.current_squad_id;
                const others = (data.members || []).filter(m => m.squad_id !== currentId);

                if (others.length === 0) {
                    select.innerHTML = '<option value="">（隊內無其他隊員）</option>';
                    return;
                }

                others.forEach(member => {
                    const option = document.createElement('option');
                    option.value = member.squad_id;
                    option.textContent = member.display_name || member.squad_id;
                    select.appendChild(option);
                });
            } catch (e) {
                select.innerHTML = '<option value="">載入失敗</option>';
            }
        }

        function hideTransferModal() {
            const modal = document.getElementById('transfer-modal');
            if (!modal) return;
            modal.classList.remove('flex');
            modal.classList.add('hidden');
            const select = document.getElementById('transfer-target');
            if (select) select.innerHTML = '';
        }

        async function transferLeadership() {
            const select = document.getElementById('transfer-target');
            const targetSquadId = select ? select.value : '';
            if (!targetSquadId) {
                alert('請選擇要轉讓的隊員');
                return;
            }

            if (!confirm('確定要將隊長轉讓畀呢位隊員嗎？')) return;

            try {
                const res = await fetch('/team/transfer_leadership', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ target_squad_id: targetSquadId })
                });
                const result = await res.json();

                if (result.success) {
                    alert(result.message || '隊長已成功轉讓！');
                    hideTransferModal();
                    const statusRes = await fetch('/status', { credentials: 'same-origin' });
                    if (statusRes.ok) {
                        currentSquad = await statusRes.json();
                        updateDashboard(currentSquad);
                    }
                    loadMyTeam();
                } else {
                    alert(result.error || '轉讓失敗');
                }
            } catch (e) {
                alert('轉讓失敗，請重試');
            }
        }

        async function loadAvailableTeams() {
            const container = document.getElementById('available-teams-list');
            container.innerHTML = '<div class="text-zinc-400 text-sm py-4 text-center">載入中...</div>';

            try {
                const res = await fetch('/available_teams', { credentials: 'same-origin' });
                const data = await res.json();

                if (!data.teams || data.teams.length === 0) {
                    container.innerHTML = '<div class="text-zinc-400 text-sm py-6 text-center">暫時冇 Team</div>';
                    return;
                }

                container.innerHTML = '';
                const hasTeam = Boolean(data.has_team);
                data.teams.forEach(team => {
                    const el = document.createElement('div');
                    el.className = 'flex items-center justify-between bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-2xl px-4 py-3';

                    let actionBtn = '';
                    if (team.is_joined) {
                        actionBtn = `<span class="px-4 py-1 text-xs bg-emerald-900/50 text-emerald-300 rounded-xl">已加入</span>`;
                    } else if (hasTeam) {
                        actionBtn = `<span class="px-4 py-1 text-xs bg-zinc-600 text-zinc-400 rounded-xl">已加入其他隊</span>`;
                    } else {
                        actionBtn = `<button class="px-4 py-1 text-xs bg-amber-500 hover:bg-amber-600 text-zinc-950 font-medium rounded-xl">加入</button>`;
                    }

                    el.innerHTML = `
                        <div class="flex-1">
                            <div class="font-mono text-emerald-400 text-sm">${team.team_id}</div>
                            <div class="font-semibold">${team.team_name}</div>
                            <div class="text-xs text-zinc-400 mt-0.5">${team.member_count} 人</div>
                        </div>
                        <div>${actionBtn}</div>
                    `;

                    const btn = el.querySelector('button');
                    if (btn) {
                        btn.onclick = () => joinTeamDirectly(team.team_id);
                    }
                    container.appendChild(el);
                });
            } catch (e) {
                container.innerHTML = '<div class="text-red-400 text-sm py-4 text-center">載入失敗</div>';
            }
        }

        async function joinTeamDirectly(teamId) {
            const res = await fetch('/team/join', {
                method: 'POST',
                credentials: 'same-origin',
                body: new URLSearchParams({team_id: teamId})
            });
            const data = await res.json();
            if (data.success) {
                alert('成功加入 Team！');
                if (currentSquad) {
                    currentSquad.team_id = data.team.team_id;
                    const statusRes = await fetch('/status', { credentials: 'same-origin' });
                    currentSquad = await statusRes.json();
                    updateDashboard(currentSquad);
                }
                loadMyTeam();
            } else {
                alert(data.error || '加入失敗');
            }
        }

        async function createMyTeam() {
            const name = document.getElementById('create-team-name').value.trim() || '新小隊';
            const res = await fetch('/team/create', {
                method: 'POST',
                credentials: 'same-origin',
                body: new URLSearchParams({team_name: name})
            });
            const data = await res.json();
            if (data.success) {
                alert(`Team ${data.team_id} 已建立！`);
                document.getElementById('create-team-name').value = '';
                loadMyTeam();
            } else {
                alert(data.error || '建立失敗');
            }
        }

        async function restoreSession() {
            const loading = document.getElementById('session-loading');
            const loginScreen = document.getElementById('login-screen');

            for (let attempt = 0; attempt < 3; attempt++) {
                try {
                    const res = await fetch('/status', { credentials: 'same-origin' });
                    if (res.ok) {
                        const squad = await res.json();
                        if (squad && squad.squad_id && squad.success !== false && !squad.error) {
                            if (loading) setVisible(loading, false);
                            await completeLogin({ ...squad, require_set_pin: false, skip_team_prompt: true });
                            return;
                        }
                    }
                } catch (e) {
                    console.log('session restore attempt failed', attempt + 1);
                }
                if (attempt < 2) {
                    await new Promise(r => setTimeout(r, 1200));
                }
            }

            if (loading) setVisible(loading, false);
            if (loginScreen) setVisible(loginScreen, true);
        }

        async function completeLogin(data) {
            currentSquad = data.squad_id ? data : (data.squad || data);
            setVisible(document.getElementById('login-screen'), false);
            setVisible(document.getElementById('game-content'), true);
            showNavAfterLogin();

            document.getElementById('squad-name').textContent =
                currentSquad.display_name || currentSquad.squad_id;

            if (data.require_set_pin) {
                setTimeout(() => {
                    const pin = prompt('請設定你的 4 位數 PIN（之後登入要用）');
                    if (pin && pin.length === 4 && /^\\d+$/.test(pin)) {
                        fetch('/set_pin', {
                            method: 'POST',
                            credentials: 'same-origin',
                            body: new URLSearchParams({pin: pin})
                        }).then(r => r.json()).then(res => {
                            if (res.success) {
                                alert('PIN 設定成功！請記住。');
                                currentSquad.has_pin = true;
                            } else {
                                alert(res.error || 'PIN 設定失敗');
                            }
                        });
                    } else if (pin) {
                        alert('PIN 設定失敗，請之後再設定。');
                    }
                }, 800);
            }

            showSection('dashboard');
            updateDashboard(currentSquad);
            initPlayerAvatar();
            loadMyItems();
            loadAnnouncements();

            setTimeout(() => {
                const picker = document.getElementById('route-picker');
                if (!picker) return;
                if (currentSquad.route) {
                    setVisible(picker, false);
                } else if (currentSquad.is_team_leader !== 1) {
                    setVisible(picker, false);
                }
            }, 400);

            if (!data.skip_team_prompt) {
                try {
                    const teamRes = await fetch('/my_team', { credentials: 'same-origin' });
                    const teamData = await teamRes.json();
                    if (!teamData.has_team) {
                        setTimeout(() => {
                            if (confirm('你尚未加入任何 Team。\\n是否立即建立或加入一個 Team？')) {
                                showSection('team');
                            }
                        }, 1200);
                    }
                } catch (teamErr) {
                    console.error('team check failed', teamErr);
                }
            }
        }

        async function loginWithPin(name, pin) {
            const res = await fetch('/login', {
                method: 'POST',
                credentials: 'same-origin',
                body: new URLSearchParams({squad_id: name, pin: pin})
            });
            const data = await res.json();
            if (data.success) {
                await completeLogin(data);
            } else {
                alert(data.error || 'PIN 錯誤');
            }
        }

        async function login(e) {
            e.preventDefault();
            try {
                const name = document.getElementById('squad_id').value.trim();
                const pin = document.getElementById('login_pin').value.trim();
                const res = await fetch('/login', {
                    method: 'POST',
                    credentials: 'same-origin',
                    body: new URLSearchParams({squad_id: name, pin: pin})
                });
                const data = await res.json();

                if (data.success) {
                    await completeLogin(data);
                } else {
                    if (data.require_pin) {
                        const inputPin = prompt('請輸入你的 4 位數 PIN');
                        if (inputPin) {
                            await loginWithPin(name, inputPin);
                        }
                    } else {
                        alert(data.error || data.message || '登入失敗');
                    }
                }
            } catch (err) {
                console.error('login failed', err);
                alert('登入失敗，請重試或檢查網絡連線');
            }
        }

        let showAllAnnouncements = false;

        async function loadAnnouncements() {
            try {
                const res = await fetch('/announcements');
                const data = await res.json();
                
                if (!data.announcements || data.announcements.length === 0) {
                    document.getElementById('announcement-box').classList.add('hidden');
                    return;
                }

                const reversed = [...data.announcements].reverse(); // 由新到舊
                
                // 顯示最新一條
                const latest = reversed[0];
                document.getElementById('latest-announcement').innerHTML = `
                    <div class="bg-blue-950/50 rounded-2xl p-3">
                        <div class="flex justify-between text-xs mb-1">
                            <span class="text-blue-300">${latest.timestamp}</span>
                        </div>
                        <div class="text-blue-100">${latest.message}</div>
                    </div>
                `;
                
                // 顯示全部歷史（如果已展開）
                const allContainer = document.getElementById('all-announcements');
                allContainer.innerHTML = '';
                
                reversed.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'bg-blue-950/50 rounded-2xl p-3';
                    div.innerHTML = `
                        <div class="flex justify-between text-xs mb-1">
                            <span class="text-blue-300">${item.timestamp}</span>
                        </div>
                        <div class="text-blue-100">${item.message}</div>
                    `;
                    allContainer.appendChild(div);
                });
                
                document.getElementById('announcement-box').classList.remove('hidden');
                
            } catch(e) {
                console.log("載入公告失敗");
            }
        }

        // 切換顯示全部公告
        function toggleAllAnnouncements() {
            const allContainer = document.getElementById('all-announcements');
            const btn = document.getElementById('toggle-announcement-btn');
            
            showAllAnnouncements = !showAllAnnouncements;
            
            if (showAllAnnouncements) {
                allContainer.classList.remove('hidden');
                btn.textContent = '收起';
            } else {
                allContainer.classList.add('hidden');
                btn.textContent = '查看所有公告';
            }
        }

        const fetchOpts = { credentials: 'same-origin' };

        async function loadLocations() {
            const container = document.getElementById('location-list');
            container.innerHTML = '<div class="text-zinc-400 text-sm py-4">載入地點中…</div>';
            try {
                const res = await fetch('/locations', fetchOpts);
                if (!res.ok) throw new Error('HTTP ' + res.status);
                const locs = await res.json();
                container.innerHTML = '';
                const keys = Object.keys(locs);
                if (keys.length === 0) {
                    container.innerHTML = '<div class="text-zinc-400 text-sm py-4">暫無地點</div>';
                    return;
                }
                keys.forEach(key => {
                    const loc = locs[key];
                    const el = document.createElement('div');
                    el.className = 'section-card rounded-3xl p-5 location-card';
                    el.innerHTML = `<div class="font-semibold">${loc.name}</div><div class="text-xs text-amber-400">${loc.hint}</div>`;
                    el.addEventListener('click', () => openLocation(key, loc));
                    container.appendChild(el);
                });
            } catch (e) {
                console.error('loadLocations failed', e);
                container.innerHTML = '<div class="text-red-400 text-sm py-4">載入失敗，<button onclick="loadLocations()" class="underline">按此重試</button></div>';
            }
        }

        function openLocation(id, loc) {
            currentLocation = { id: id, ...loc };

            // 建立簡單 Modal
            const modal = document.createElement('div');
            modal.className = 'modal-overlay fixed inset-0 bg-black/70 flex items-end md:items-center justify-center z-50';
            modal.innerHTML = `
                <div class="modal-box bg-zinc-900 w-full md:w-[480px] md:rounded-t-3xl md:rounded-b-3xl rounded-t-3xl p-6 border-t border-zinc-700">
                    <div class="flex justify-between items-start mb-4">
                        <div>
                            <div class="font-semibold text-2xl">${loc.name}</div>
                            <div class="text-sm text-amber-400 mt-0.5">${loc.hint}</div>
                        </div>
                        <button type="button" class="text-3xl leading-none text-zinc-400 hover:text-white" onclick="closeModal(this)">×</button>
                    </div>

                    <div class="text-zinc-300 mb-6">${loc.description}</div>

                    <div id="action-area">
                        ${loc.task_type === 'gps' ? `
                            <button onclick="verifyCurrentLocation('${id}')" 
                                    class="w-full py-4 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl flex items-center justify-center gap-x-3">
                                <i class="fa-solid fa-location-arrow"></i>
                                <span>驗證目前位置</span>
                            </button>
                        ` : ''}

                        ${loc.task_type === 'photo' ? `
                            <div class="space-y-3">
                                <input type="file" id="photo-input" accept="image/*" capture="environment" class="hidden">
                                <button onclick="document.getElementById('photo-input').click()" 
                                        class="w-full py-4 bg-zinc-700 hover:bg-zinc-600 rounded-2xl font-medium flex items-center justify-center gap-x-3">
                                    <i class="fa-solid fa-camera"></i>
                                    <span>影相上傳</span>
                                </button>
                                <button onclick="submitPhotoTask('${id}', this)" 
                                        class="w-full py-3.5 text-sm border border-zinc-700 rounded-2xl hover:bg-zinc-800">
                                    直接提交任務（唔影相）
                                </button>
                            </div>
                        ` : ''}

                        ${loc.task_type === 'puzzle' ? `
                            <button onclick="startPuzzle('${id}', this)" 
                                    class="w-full py-4 bg-zinc-700 hover:bg-zinc-600 rounded-2xl font-medium flex items-center justify-center gap-x-3">
                                <i class="fa-solid fa-question-circle"></i>
                                <span>開始解謎</span>
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
            document.body.appendChild(modal);

            // 處理影相選擇
            setTimeout(() => {
                const input = document.getElementById('photo-input');
                if (input) {
                    input.onchange = () => {
                        if (input.files.length > 0) {
                            submitPhotoWithFile(id, input.files[0], modal);
                        }
                    };
                }
            }, 100);
        }

        let currentLocation = null;

        async function verifyCurrentLocation(locId) {
            if (!navigator.geolocation) {
                showLocationError("你的手機唔支援定位功能");
                return;
            }

            navigator.geolocation.getCurrentPosition(
                async (position) => {
                    const res = await fetch('/verify_gps', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            loc_id: locId,
                            lat: position.coords.latitude,
                            lng: position.coords.longitude
                        })
                    });
                    const data = await res.json();
                    alert(data.message || (data.error ? '錯誤：' + data.error : '驗證失敗'));
                    if (data.success) closeModal(document.querySelector('.modal-overlay'));
                },
                (error) => {
                    let message = "無法取得定位";
                    if (error.code === error.PERMISSION_DENIED) {
                        message = "你已拒絕定位權限";
                        showLocationPermissionGuide();
                    } else if (error.code === error.POSITION_UNAVAILABLE) {
                        message = "暫時無法取得定位";
                    } else if (error.code === error.TIMEOUT) {
                        message = "定位超時";
                    }
                    showLocationError(message);
                }
            );
        }

        function showLocationError(msg) {
            alert(msg);
        }

        function detectBrowser() {
            const ua = navigator.userAgent;
            const isIOS = /iPad|iPhone|iPod/.test(ua)
                || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
            const isAndroid = /Android/.test(ua);

            let browser = 'other';
            if (/CriOS/.test(ua)) browser = 'chrome-ios';
            else if (/FxiOS/.test(ua)) browser = 'firefox-ios';
            else if (/EdgiOS/.test(ua)) browser = 'edge-ios';
            else if (/OPiOS/.test(ua)) browser = 'opera-ios';
            else if (isIOS && /Safari/.test(ua)) browser = 'safari-ios';
            else if (/SamsungBrowser/.test(ua)) browser = 'samsung';
            else if (/EdgA/.test(ua)) browser = 'edge-android';
            else if (/Firefox/.test(ua)) browser = 'firefox';
            else if (/Chrome/.test(ua)) browser = 'chrome';
            else if (isIOS) browser = 'safari-ios';

            const names = {
                'safari-ios': 'Safari',
                'chrome-ios': 'Chrome',
                'firefox-ios': 'Firefox',
                'edge-ios': 'Edge',
                'opera-ios': 'Opera',
                'chrome': 'Chrome',
                'firefox': 'Firefox',
                'edge-android': 'Edge',
                'samsung': 'Samsung 瀏覽器',
                'other': '你的瀏覽器',
            };

            return { isIOS, isAndroid, browser, browserName: names[browser] || names.other };
        }

        function getLocationPermissionGuide() {
            const { isIOS, isAndroid, browser, browserName } = detectBrowser();

            const guides = {
                'safari-ios': `
                    <strong>Safari（iPhone / iPad）：</strong><br>
                    1. 喺 Safari 網址列左邊點 <strong>aA</strong> →「網站設定」→ 位置 → <strong>允許</strong><br>
                    2. 或者：設定 → Safari → 進階 → 網站資料 → 搵 oikonomia → 位置 → 允許<br>
                    3. 確保：設定 → 私隱與保安 → 定位服務 → <strong>開啟</strong>
                `,
                'chrome-ios': `
                    <strong>Chrome（iPhone / iPad）：</strong><br>
                    1. 設定 → Chrome → 位置 → <strong>使用 App 期間</strong><br>
                    2. 返回 Chrome，點網址列左邊圖示 → 網站設定 → 位置 → <strong>允許</strong><br>
                    3. 確保：設定 → 私隱與保安 → 定位服務 → <strong>開啟</strong>
                `,
                'firefox-ios': `
                    <strong>Firefox（iPhone / iPad）：</strong><br>
                    1. 設定 → Firefox → 位置 → <strong>使用 App 期間</strong><br>
                    2. 返回 Firefox，重新整理頁面，彈出提示時選 <strong>允許</strong><br>
                    3. 確保：設定 → 私隱與保安 → 定位服務 → <strong>開啟</strong>
                `,
                'edge-ios': `
                    <strong>Edge（iPhone / iPad）：</strong><br>
                    1. 設定 → Edge → 位置 → <strong>使用 App 期間</strong><br>
                    2. 返回 Edge，點網址列圖示 → 網站權限 → 位置 → <strong>允許</strong>
                `,
                'chrome': `
                    <strong>Chrome（Android）：</strong><br>
                    1. 點網址列左邊 <strong>鎖頭／圖示</strong> → 權限 → 位置 → <strong>允許</strong><br>
                    2. 或者：設定 → 應用程式 → Chrome → 權限 → 位置 → <strong>允許</strong>
                `,
                'samsung': `
                    <strong>Samsung 瀏覽器（Android）：</strong><br>
                    1. 點網址列左邊圖示 → 權限 → 位置 → <strong>允許</strong><br>
                    2. 或者：設定 → 應用程式 → Samsung 瀏覽器 → 權限 → 位置 → <strong>允許</strong>
                `,
                'firefox': `
                    <strong>Firefox（Android）：</strong><br>
                    1. 點網址列左邊圖示 → 權限 → 位置 → <strong>允許</strong><br>
                    2. 或者：設定 → 應用程式 → Firefox → 權限 → 位置 → <strong>允許</strong>
                `,
                'edge-android': `
                    <strong>Edge（Android）：</strong><br>
                    1. 點網址列左邊圖示 → 權限 → 位置 → <strong>允許</strong><br>
                    2. 或者：設定 → 應用程式 → Edge → 權限 → 位置 → <strong>允許</strong>
                `,
            };

            if (isIOS) {
                return {
                    intro: `Oikonomia 係網頁，定位權限要畀 <strong>${browserName}</strong>，唔係 Oikonomia 本身。`,
                    steps: guides[browser] || guides['safari-ios'],
                };
            }
            if (isAndroid) {
                return {
                    intro: `Oikonomia 係網頁，定位權限要畀 <strong>${browserName}</strong>，唔係 Oikonomia 本身。`,
                    steps: guides[browser] || guides['chrome'],
                };
            }
            return {
                intro: '請喺瀏覽器允許此網站使用定位，先至可以用到探索功能。',
                steps: `
                    <strong>桌面瀏覽器：</strong><br>
                    點網址列左邊嘅鎖頭／圖示 → 網站設定 → 位置 → <strong>允許</strong>，然後重新整理頁面。
                `,
            };
        }

        function showLocationPermissionGuide() {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100] px-4';

            const guide = getLocationPermissionGuide();

            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-md rounded-3xl p-6 border border-zinc-700 max-h-[90vh] overflow-auto">
                    <div class="text-xl font-bold mb-4">需要開啟定位權限</div>

                    <div class="text-zinc-300 mb-4 leading-relaxed text-sm">
                        ${guide.intro}
                    </div>

                    <div class="space-y-3">
                        <div class="bg-zinc-800 p-4 rounded-2xl text-sm leading-relaxed">
                            ${guide.steps}
                        </div>

                        <button onclick="this.closest('.fixed').remove()"
                                class="w-full py-3 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl">
                            我已開啟，重新嘗試
                        </button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);
        }

        async function submitPhotoWithFile(locId, file, modal) {
            const formData = new FormData();
            formData.append('task_id', locId);
            formData.append('photo', file);

            const res = await fetch('/submit_task', { method: 'POST', credentials: 'same-origin', body: formData });
            const data = await res.json();
            alert(data.message || (data.error ? '錯誤：' + data.error : '提交失敗'));
            if (modal) modal.remove();
        }

        async function submitPhotoTask(locId, btn) {
            btn.disabled = true;
            btn.textContent = '提交中...';

            const formData = new FormData();
            formData.append('task_id', locId);

            const res = await fetch('/submit_task', { method: 'POST', credentials: 'same-origin', body: formData });
            const data = await res.json();
            alert(data.message);
            closeModal(btn);
        }

        async function startPuzzle(locId, btn) {
            const answer = prompt('請輸入答案：');
            if (!answer) return;

            // 簡單示範，之後可以改做真實後端驗證
            if (answer.toLowerCase() === 'iggy') {
                alert('正確！獲得 Sanity +8');
                closeModal(btn);
            } else {
                alert('唔正確');
            }
        }

        // 自動更新公告
        setInterval(() => {
            loadAnnouncements();
        }, 10000);

        // 每 12 秒自動更新狀態
        setInterval(() => {
            if (currentSquad) {
                fetch('/status', { credentials: 'same-origin' })
                    .then(r => r.ok ? r.json() : null)
                    .then(d => {
                        if (d && d.squad_id && d.success !== false) {
                            currentSquad = d;
                            updateDashboard(d);
                        }
                    });
            }
        }, 12000);

        let currentAvatar = null;

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text ?? '';
            return div.innerHTML;
        }

        const ITEM_SOURCE_LABELS = { story: '劇情', qr: 'QR', event: '事件', special: '特殊' };

        async function loadMyItems() {
            const container = document.getElementById('my-items-list');
            const slotLabel = document.getElementById('items-slot-label');
            if (!container) return;

            try {
                const res = await fetch('/my_items', { credentials: 'same-origin' });
                const data = await res.json();

                if (!res.ok || !data.success) {
                    container.innerHTML = '<div class="text-red-400 text-sm col-span-full text-center py-4">載入失敗</div>';
                    return;
                }

                if (slotLabel) {
                    slotLabel.textContent = `(${data.current_count || 0}/${data.max_slots || 5})`;
                }

                const items = data.items || [];
                if (items.length === 0) {
                    container.innerHTML = '<div class="text-sm text-zinc-400 col-span-full text-center py-6">暫無物品 — 完成劇情或掃描 QR 可獲得</div>';
                    return;
                }

                container.innerHTML = '';
                items.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'bg-zinc-800/80 border border-zinc-700 rounded-2xl p-4';
                    const sourceLabel = ITEM_SOURCE_LABELS[item.source] || item.source || '未知';
                    const icon = item.icon
                        ? (item.icon.includes('/') ? `<img src="${escapeHtml(item.icon)}" class="w-10 h-10 object-contain" alt="">` : `<span class="text-3xl">${escapeHtml(item.icon)}</span>`)
                        : '<span class="text-3xl">📦</span>';
                    div.innerHTML = `
                        <div class="flex gap-3">
                            <div class="shrink-0 w-10 flex items-center justify-center">${icon}</div>
                            <div class="flex-1 min-w-0">
                                <div class="font-semibold">${escapeHtml(item.name)}</div>
                                <div class="text-xs text-zinc-400 mt-0.5 line-clamp-2">${escapeHtml(item.description || '')}</div>
                                <div class="text-xs text-zinc-500 mt-1">${escapeHtml(sourceLabel)}</div>
                            </div>
                            <button onclick="discardItem(${item.id})"
                                    class="text-xs px-2 py-1 h-fit bg-red-900/50 hover:bg-red-800 text-red-300 rounded-lg shrink-0">
                                丟棄
                            </button>
                        </div>
                    `;
                    container.appendChild(div);
                });
            } catch (e) {
                container.innerHTML = '<div class="text-red-400 text-sm col-span-full text-center py-4">載入失敗</div>';
            }
        }

        async function discardItem(playerItemId) {
            if (!confirm('確定要丟棄此物品嗎？')) return;

            const res = await fetch('/discard_item', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ player_item_id: playerItemId })
            });
            const result = await res.json();

            if (result.success) {
                loadMyItems();
            } else {
                alert(result.error || '丟棄失敗');
            }
        }

        async function claimItemFromQR(itemId, source = 'qr') {
            try {
                const res = await fetch('/add_item', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ item_id: itemId, source })
                });
                const result = await res.json();
                if (result.success) {
                    alert(result.message || '成功獲得物品！');
                    loadMyItems();
                    return true;
                }
                alert(result.error || '獲取失敗');
                return false;
            } catch (err) {
                alert('網絡錯誤，請稍後再試');
                return false;
            }
        }

        let html5QrCode = null;
        let qrScannerRunning = false;
        let qrClaimInProgress = false;

        function parseQrItemId(decodedText) {
            const text = (decodedText || '').trim();
            if (!text) return null;

            const claimMatch = text.match(/\/claim_item\/(\d+)/i);
            if (claimMatch) return parseInt(claimMatch[1], 10);

            const queryMatch = text.match(/[?&]item_id=(\d+)/i);
            if (queryMatch) return parseInt(queryMatch[1], 10);

            const prefixMatch = text.match(/^oiko-item-(\d+)$/i);
            if (prefixMatch) return parseInt(prefixMatch[1], 10);

            if (text.startsWith('{')) {
                try {
                    const obj = JSON.parse(text);
                    if (obj.type === 'item' && obj.id != null) return parseInt(obj.id, 10);
                    if (obj.item_id != null) return parseInt(obj.item_id, 10);
                } catch (e) {}
            }

            if (/^\d+$/.test(text)) return parseInt(text, 10);
            return null;
        }

        async function stopQRScanner() {
            const modal = document.getElementById('qr-scanner-modal');
            if (modal) {
                modal.classList.remove('flex');
                modal.classList.add('hidden');
            }
            if (html5QrCode && qrScannerRunning) {
                try {
                    await html5QrCode.stop();
                    html5QrCode.clear();
                } catch (e) {
                    console.error(e);
                }
            }
            html5QrCode = null;
            qrScannerRunning = false;
        }

        async function startQRScanner() {
            if (typeof Html5Qrcode === 'undefined') {
                alert('QR 掃描庫載入失敗，請重新整理頁面');
                return;
            }

            const modal = document.getElementById('qr-scanner-modal');
            const status = document.getElementById('qr-status');
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            if (status) status.textContent = '正在啟動相機...';

            await stopQRScanner();
            html5QrCode = new Html5Qrcode('qr-reader');
            const config = { fps: 10, qrbox: { width: 250, height: 250 } };

            const onScanFailure = () => {};

            async function tryStartCamera(facingMode, label) {
                await html5QrCode.start(
                    { facingMode },
                    config,
                    onScanSuccess,
                    onScanFailure
                );
                qrScannerRunning = true;
                if (status) status.textContent = label;
            }

            try {
                await tryStartCamera('environment', '請對準 QR Code');
            } catch (err) {
                console.error('後置相機失敗:', err);
                try {
                    html5QrCode = new Html5Qrcode('qr-reader');
                    await tryStartCamera('user', '請對準 QR Code（前鏡頭）');
                } catch (err2) {
                    console.error('前鏡頭失敗:', err2);
                    if (status) status.textContent = '無法啟動相機，請檢查瀏覽器權限';
                }
            }
        }

        async function onScanSuccess(decodedText) {
            if (qrClaimInProgress) return;

            const itemId = parseQrItemId(decodedText);
            if (!itemId || Number.isNaN(itemId)) {
                const status = document.getElementById('qr-status');
                if (status) status.textContent = 'QR Code 格式不正確';
                return;
            }

            qrClaimInProgress = true;
            const status = document.getElementById('qr-status');
            if (status) status.textContent = '掃描成功，正在領取物品...';

            await stopQRScanner();
            await claimItemFromQR(itemId);
            qrClaimInProgress = false;
        }

        function avatarSrc(filename) {
            return `/static/avatars/${filename || 'default.png'}`;
        }

        function showAvatarModal() {
            const modal = document.getElementById('avatar-modal');
            const grid = document.getElementById('avatar-grid');
            grid.innerHTML = '<div class="col-span-full text-center py-8 text-zinc-400">載入中...</div>';
            modal.classList.remove('hidden');
            modal.classList.add('flex');

            fetch('/available_avatars', { credentials: 'same-origin' })
                .then(res => res.json())
                .then(data => {
                    grid.innerHTML = '';

                    if (!data.avatars || data.avatars.length === 0) {
                        grid.innerHTML = '<div class="col-span-full text-center text-zinc-400 py-8">暫無可用頭像</div>';
                        return;
                    }

                    data.avatars.forEach(filename => {
                        const div = document.createElement('div');
                        div.className = `cursor-pointer rounded-2xl overflow-hidden border-2 transition-all hover:scale-105 ${currentAvatar === filename ? 'border-amber-500' : 'border-zinc-700'}`;

                        div.innerHTML = `
                            <img src="/static/avatars/${filename}"
                                 class="w-full aspect-square object-cover">
                        `;

                        div.onclick = () => selectAvatar(filename, div);
                        grid.appendChild(div);
                    });
                })
                .catch(() => {
                    grid.innerHTML = '<div class="col-span-full text-center text-red-400 py-8">載入失敗</div>';
                });
        }

        function hideAvatarModal() {
            const modal = document.getElementById('avatar-modal');
            modal.classList.remove('flex');
            modal.classList.add('hidden');
        }

        function selectAvatar(filename, element) {
            document.querySelectorAll('#avatar-grid > div').forEach(el => {
                el.classList.remove('border-amber-500');
                el.classList.add('border-zinc-700');
            });

            element.classList.remove('border-zinc-700');
            element.classList.add('border-amber-500');

            fetch('/set_avatar', {
                method: 'POST',
                credentials: 'same-origin',
                body: new URLSearchParams({ avatar: filename })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    currentAvatar = filename;
                    if (currentSquad) currentSquad.avatar = filename;
                    initPlayerAvatar();

                    setTimeout(() => {
                        hideAvatarModal();
                        alert('頭像已更新！');
                    }, 300);
                } else {
                    alert(data.error || '更新失敗');
                }
            });
        }

        function initPlayerAvatar() {
            const filename = currentSquad?.avatar || null;
            currentAvatar = filename;
            ['player-avatar', 'log-player-avatar'].forEach(id => {
                const img = document.getElementById(id);
                if (img) img.src = avatarSrc(filename);
            });
        }

        // 頁面載入時還原登入狀態（Render 冷啟動會重試）
        restoreSession();
    </script>

    <!-- 轉讓隊長 Modal -->
    <div id="transfer-modal" onclick="if (event.target.id === 'transfer-modal') hideTransferModal()"
         class="hidden fixed inset-0 bg-black/80 items-center justify-center z-[100]">
        <div onclick="event.stopImmediatePropagation()"
             class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-zinc-700">
            <div class="text-xl font-bold mb-1">轉讓隊長</div>
            <div class="text-sm text-zinc-400 mb-4">選擇隊內另一位隊員成為新隊長</div>
            <select id="transfer-target"
                    class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-3 text-sm mb-4">
            </select>
            <div class="flex gap-x-3">
                <button onclick="hideTransferModal()"
                        class="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm">取消</button>
                <button onclick="transferLeadership()"
                        class="flex-1 py-3 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl text-sm">
                    確認轉讓
                </button>
            </div>
        </div>
    </div>

    <!-- 掃描 QR Code Modal -->
    <div id="qr-scanner-modal" onclick="if (event.target.id === 'qr-scanner-modal') stopQRScanner()"
         class="hidden fixed inset-0 bg-black/80 items-center justify-center z-[100]">
        <div onclick="event.stopImmediatePropagation()"
             class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl overflow-hidden border border-zinc-700">
            <div class="flex justify-between items-center p-4 border-b border-zinc-700">
                <h3 class="text-lg font-bold">掃描 QR Code 獲得物品</h3>
                <button onclick="stopQRScanner()" class="text-2xl leading-none text-zinc-400 hover:text-white px-2">×</button>
            </div>
            <div class="p-4">
                <div id="qr-reader" class="w-full rounded-xl overflow-hidden border border-zinc-700"></div>
                <p id="qr-status" class="text-center text-sm mt-3 text-zinc-400">請對準 QR Code</p>
            </div>
            <div class="p-4 border-t border-zinc-700">
                <button onclick="stopQRScanner()"
                        class="w-full py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm">取消</button>
            </div>
        </div>
    </div>

    <!-- 選擇頭像 Modal -->
    <div id="avatar-modal" class="hidden fixed inset-0 bg-black/80 items-center justify-center z-[100]">
        <div class="bg-zinc-900 w-full max-w-2xl mx-4 rounded-3xl p-6 border border-zinc-700">
            <div class="flex justify-between items-center mb-6">
                <div class="text-2xl font-bold">選擇角色頭像</div>
                <button onclick="hideAvatarModal()" class="text-3xl text-zinc-400 hover:text-white">×</button>
            </div>

            <div id="avatar-grid" class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-4 max-h-[400px] overflow-auto p-1">
            </div>

            <div class="mt-6 text-center text-xs text-zinc-400">
                頭像只會喺呢個營會顯示
            </div>
        </div>
    </div>
</body>
</html>
"""

CLAIM_ITEM_HTML = """
<!DOCTYPE html>
<html lang="zh-HK">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>獲得物品 • Oikonomia</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-zinc-100 min-h-screen flex items-center justify-center p-6">
    <div class="max-w-md w-full bg-zinc-900 border border-zinc-700 rounded-3xl p-8 text-center">
        <div class="text-5xl mb-4">{{ item.icon or '📦' }}</div>
        <h1 class="text-2xl font-bold mb-2">{{ item.name }}</h1>
        <p class="text-zinc-400 text-sm mb-6">{{ item.description or '' }}</p>
        <div id="claim-status" class="text-sm text-zinc-400 mb-4">正在領取物品...</div>
        <button id="claim-btn" onclick="claimNow()"
                class="w-full py-3 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl mb-3">
            領取物品
        </button>
        <a href="/" class="text-sm text-amber-400 hover:underline">返回 Dashboard</a>
    </div>
    <script>
        const itemId = {{ item_id }};

        async function claimNow() {
            const status = document.getElementById('claim-status');
            const btn = document.getElementById('claim-btn');
            btn.disabled = true;
            status.textContent = '領取中...';

            const res = await fetch('/add_item', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ item_id: itemId, source: 'qr' })
            });
            const data = await res.json();

            if (data.success) {
                status.textContent = data.message || '成功獲得物品！';
                status.className = 'text-sm text-emerald-400 mb-4';
                btn.classList.add('hidden');
            } else {
                status.textContent = data.error || '領取失敗';
                status.className = 'text-sm text-red-400 mb-4';
                btn.disabled = false;
            }
        }

        claimNow();
    </script>
</body>
</html>
"""

# ==================== GM HTML Templates ====================

GM_LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>GM Login • Oikonomia</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-white flex items-center justify-center min-h-screen">
    <div class="w-full max-w-sm">
        <div class="text-center mb-8">
            <h1 class="text-3xl font-bold">GM 後台</h1>
            <p class="text-zinc-400 mt-2">請輸入管理員 PIN</p>
        </div>
        
        <form id="gm-login-form" class="space-y-4">
            <input type="password" id="pin" placeholder="輸入 GM PIN" 
                   class="w-full bg-zinc-900 border border-zinc-700 focus:border-amber-500 rounded-2xl px-6 py-4 text-xl text-center">
            <button type="submit" 
                    class="w-full bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold py-4 rounded-2xl">
                登入 GM 後台
            </button>
        </form>
    </div>

    <script>
        document.getElementById('gm-login-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            const pin = document.getElementById('pin').value;
            
            const res = await fetch('/gm/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({pin: pin})
            });
            
            const data = await res.json();
            if (data.success) {
                window.location.href = '/gm/dashboard';
            } else {
                alert(data.error || '登入失敗');
            }
        });
    </script>
</body>
</html>
"""

GM_DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>GM Dashboard • Oikonomia</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        .hidden { display: none !important; }
        .gm-tab { background: #27272a; color: #a1a1aa; }
        .gm-tab.active { background: #f59e0b; color: #09090b; }
        .route-card {
            border: 3px solid #2C3E50;
            border-radius: 12px;
            cursor: pointer;
            transition: transform 0.1s ease, box-shadow 0.1s ease;
            box-shadow: 4px 4px 0px rgba(44, 62, 80, 0.5);
        }
        .route-card:hover { transform: translate(-2px, -2px); box-shadow: 6px 6px 0px rgba(44, 62, 80, 0.5); }
        .route-iggy { background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%); }
        .route-marah { background: linear-gradient(135deg, #1e3a5f 0%, #1e40af 100%); }
    </style>
</head>
<body class="bg-zinc-950 text-white p-8">
    <div class="max-w-6xl mx-auto">
        <div class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-3xl font-bold">GM Dashboard</h1>
                <p class="text-zinc-400 text-sm mt-1">即時監控所有玩家狀態</p>
            </div>
            <div class="flex items-center gap-x-3">
                <div class="text-xs px-3 py-1.5 bg-zinc-800 rounded-2xl text-zinc-400 flex items-center gap-x-2">
                    <i class="fa-solid fa-sync"></i>
                    <span>手動刷新</span>
                </div>
                <button onclick="location.reload()" 
                        class="px-5 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-2xl text-sm flex items-center gap-x-2">
                    <i class="fa-solid fa-redo"></i>
                    <span>手動刷新</span>
                </button>
                <a href="/" class="px-5 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-2xl text-sm">返回玩家端</a>
            </div>
        </div>

        <!-- Tab 切換 -->
        <div class="flex gap-x-2 mb-6 px-1">
            <button onclick="switchGMTab('squads')" id="tab-squads"
                    class="gm-tab active px-6 py-2 rounded-2xl text-sm font-medium">玩家狀態</button>
            <button onclick="switchGMTab('teams')" id="tab-teams"
                    class="gm-tab px-6 py-2 rounded-2xl text-sm font-medium">Team 管理</button>
            <button onclick="switchGMTab('overview')" id="tab-overview"
                    class="gm-tab px-6 py-2 rounded-2xl text-sm font-medium">進度總覽</button>
        </div>

        <div id="gm-squads-tab">
        <div class="bg-zinc-900 rounded-3xl p-6">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-semibold">所有玩家即時狀態</h2>
                <div class="text-xs text-zinc-500">最後更新：{{ last_update }}</div>
            </div>
            
            <table class="w-full">
                <thead>
                    <tr class="border-b border-zinc-700 text-left text-sm text-zinc-400">
                        <th class="py-3 pl-2 w-12"></th>
                        <th class="py-3">玩家名稱</th>
                        <th class="py-3">路線</th>
                        <th class="py-3">HP</th>
                        <th class="py-3">Sanity</th>
                        <th class="py-3">Pow/Int/Res</th>
                        <th class="py-3">提交次數</th>
                        <th class="py-3">操作</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-zinc-800">
                    {% for squad in squads %}
                    <tr class="hover:bg-zinc-800/60">
                        <td class="py-4 pl-2">
                            <img src="/static/avatars/{{ squad.avatar or 'default.png' }}"
                                 class="w-10 h-10 rounded-full object-cover border border-zinc-600">
                        </td>
                        <td class="py-4 font-mono font-semibold text-amber-400">
                            <a href="/gm/squad/{{ squad.squad_id }}" class="hover:underline">
                                {{ squad.display_name or squad.squad_id }}
                            </a>
                        </td>
                        <td class="py-4 text-sm">{{ squad.route_label }}</td>
                        <td class="py-4">
                            <div class="flex items-center gap-x-3">
                                <span class="font-mono w-8">{{ squad.hp }}</span>
                                <div class="w-28 h-2 bg-zinc-700 rounded-full">
                                    <div class="h-2 bg-red-500 rounded-full" style="width: {{ squad.hp }}%"></div>
                                </div>
                            </div>
                        </td>
                        <td class="py-4">
                            <div class="flex items-center gap-x-3">
                                <span class="font-mono w-8">{{ squad.sanity }}</span>
                                <div class="w-28 h-2 bg-zinc-700 rounded-full">
                                    <div class="h-2 bg-amber-500 rounded-full" style="width: {{ squad.sanity }}%"></div>
                                </div>
                            </div>
                        </td>
                        <td class="py-4 font-mono text-xs">{{ squad.power }}/{{ squad.intellect }}/{{ squad.resilience }}</td>
                        <td class="py-4">
                            <span class="px-3 py-1 bg-zinc-700 rounded-full text-xs">{{ squad.submission_count }} 次</span>
                            
                        </td>
                        <td class="py-4">
                            {% if squad.submission_count > 0 %}
                            <button onclick="viewPlayerLogs('{{ squad.squad_id }}')"
                                    class="px-3 py-1 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-full mr-2">
                                任務 Log
                            </button>
                            <a href="/gm/squad/{{ squad.squad_id }}" 
                               class="px-3 py-1 text-xs bg-amber-500 hover:bg-amber-600 text-zinc-950 rounded-full">
                                詳情
                            </a>
                            {% else %}
                            <span class="text-xs text-zinc-500">—</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Global Event -->
        <div class="bg-zinc-900 rounded-3xl p-6 mt-6">
            <h2 class="text-xl font-semibold mb-4">觸發 Global Event</h2>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                
                <!-- 全營 Sanity 調整 -->
                <div class="bg-zinc-800 rounded-2xl p-5">
                    <div class="font-medium mb-3">全營 Sanity 調整</div>
                    <div class="flex gap-x-2">
                        <input type="number" id="sanity-value" value="-5" 
                               class="flex-1 bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button onclick="triggerGlobalEvent('adjust_sanity')" 
                                class="px-6 py-2 bg-amber-600 hover:bg-amber-700 rounded-2xl text-sm">
                            執行
                        </button>
                    </div>
                    <div class="text-xs text-zinc-400 mt-2">正數 = 增加，負數 = 減少</div>
                </div>

                <!-- 劇情事件 -->
                <div class="bg-zinc-800 rounded-2xl p-5">
                    <div class="font-medium mb-3">劇情事件</div>
                    <div class="flex flex-wrap gap-2">
                        <button onclick="triggerGlobalEvent('judas_strengthen')" 
                                class="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm">
                            Judas 加強
                        </button>
                        <button onclick="triggerGlobalEvent('iggy_collapse')" 
                                class="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm">
                            Iggy 崩潰
                        </button>
                    </div>
                </div>

                <!-- 自訂全球事件 -->
                <div class="bg-zinc-800 rounded-2xl p-5 md:col-span-2">
                    <div class="font-medium mb-3">自訂全球事件</div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                        <input type="text" id="custom-event-title" placeholder="事件標題（例如：裂縫擴大）"
                               class="bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <select id="custom-event-effect-type"
                                class="bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                            <option value="">只記錄，不套用效果</option>
                            <option value="sanity_down">全營 Sanity 下降</option>
                            <option value="sanity_up">全營 Sanity 上升</option>
                            <option value="power_up">全營 Power 上升</option>
                            <option value="intellect_up">全營 Intellect 上升</option>
                            <option value="resilience_up">全營 Resilience 上升</option>
                            <option value="global_debuff">全球減益（只記錄）</option>
                        </select>
                    </div>
                    <textarea id="custom-event-description" rows="2" placeholder="事件描述（可選）"
                              class="w-full bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm mb-3"></textarea>
                    <div class="flex gap-x-3 items-center">
                        <input type="number" id="custom-event-effect-value" value="5" placeholder="效果數值"
                               class="w-32 bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button onclick="createCustomGlobalEvent()"
                                class="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-2xl text-sm">
                            建立全球事件
                        </button>
                    </div>
                    <div class="text-xs text-zinc-400 mt-2">事件會顯示喺玩家日誌頁最底部嘅「全球事件記錄」</div>
                </div>

            </div>
        </div>

        <!-- Global Announcement -->
        <div class="bg-zinc-900 rounded-3xl p-6 mt-6">
            <h2 class="text-xl font-semibold mb-4">發送 Global Announcement</h2>
            
            <div class="flex gap-x-3">
                <input type="text" id="announcement-input" placeholder="輸入要發送嘅訊息..." 
                       class="flex-1 bg-zinc-800 border border-zinc-700 rounded-2xl px-5 py-3">
                <button onclick="sendAnnouncement()" 
                        class="px-8 py-3 bg-blue-600 hover:bg-blue-700 rounded-2xl font-medium">
                    發送
                </button>
            </div>
        </div>

        <!-- Danger Zone -->
        <div class="mt-8 border border-red-500/30 rounded-3xl p-6">
            <div class="flex items-center gap-x-2 mb-4">
                <i class="fa-solid fa-exclamation-triangle text-red-400"></i>
                <h2 class="text-lg font-semibold text-red-400">Danger Zone</h2>
            </div>
            
            <div class="flex items-center justify-between mb-4 pb-4 border-b border-red-500/20">
                <div>
                    <div class="font-medium">清空所有玩家上傳圖片</div>
                    <div class="text-xs text-zinc-400">刪除 uploads 資料夾內嘅圖片檔案，並清空提交記錄中的圖片欄位（可減少 Storage）</div>
                </div>
                <button onclick="showClearImagesModal()"
                        class="px-6 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm font-medium">
                    清空圖片
                </button>
            </div>

            <div class="flex items-center justify-between">
                <div>
                    <div class="font-medium">重置整個遊戲</div>
                    <div class="text-xs text-zinc-400">會刪除所有玩家ID（FRAG-XX）、Team 同提交記錄，一切由零開始</div>
                </div>
                <button onclick="showResetModal()" 
                        class="px-6 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm font-medium">
                    重置遊戲
                </button>
            </div>
        </div>
        </div>

        <div id="gm-teams-tab" class="hidden">
        <!-- Team 管理 (加強版) -->
        <div class="bg-zinc-900 rounded-3xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-xl font-semibold">Team 管理</h2>
                <button onclick="loadGMTeams()" 
                        class="px-4 py-1.5 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm flex items-center gap-x-2">
                    <i class="fa-solid fa-sync"></i>
                    <span>刷新</span>
                </button>
            </div>

            <!-- 建立新 Team -->
            <div class="bg-zinc-800 rounded-2xl p-5 mb-4">
                <div class="font-medium mb-3">建立新 Team</div>
                <div class="flex gap-x-3">
                    <input type="text" id="new-team-name" placeholder="輸入隊名（例如：界線守護者）" 
                           class="flex-1 bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                    <button onclick="gmCreateTeam()" 
                            class="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-2xl text-sm font-medium">
                        建立新隊
                    </button>
                </div>
            </div>

            <!-- Teams 列表 -->
            <div id="gm-teams-list" class="space-y-4"></div>
        </div>
        </div>

        <div id="gm-overview-tab" class="hidden">
        <div class="bg-zinc-900 rounded-3xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-xl font-semibold">隊伍 / 玩家進度總覽</h2>
                <button onclick="loadTeamsOverview()"
                        class="px-4 py-1.5 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm flex items-center gap-x-2">
                    <i class="fa-solid fa-sync"></i>
                    <span>刷新</span>
                </button>
            </div>
            <div id="gm-overview-content" class="text-zinc-400 text-center py-8">載入中...</div>
        </div>
        </div>

        <script>
        function sendAnnouncement() {
            const message = document.getElementById('announcement-input').value.trim();
            if (!message) {
                alert('請輸入訊息');
                return;
            }

            fetch('/gm/announcement', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({message: message})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert('公告已發送');
                    document.getElementById('announcement-input').value = '';
                }
            });
        }
        </script>

        <script>
        function triggerGlobalEvent(eventType) {
            let value = 0;
            if (eventType === 'adjust_sanity') {
                value = parseInt(document.getElementById('sanity-value').value) || 0;
            }

            fetch('/gm/global_event', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    event_type: eventType,
                    value: value
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert(data.message || '事件已觸發');
                    location.reload();
                } else {
                    alert('觸發失敗');
                }
            });
        }

        async function createCustomGlobalEvent() {
            const title = document.getElementById('custom-event-title').value.trim();
            const description = document.getElementById('custom-event-description').value.trim();
            const effect_type = document.getElementById('custom-event-effect-type').value;
            const effect_value = parseInt(document.getElementById('custom-event-effect-value').value) || 0;

            if (!title) {
                alert('請輸入事件標題');
                return;
            }

            const res = await fetch('/gm/create_global_event', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ title, description, effect_type: effect_type || null, effect_value })
            });
            const data = await res.json();

            if (data.success) {
                alert(data.message || '全球事件已建立');
                document.getElementById('custom-event-title').value = '';
                document.getElementById('custom-event-description').value = '';
                document.getElementById('custom-event-effect-type').value = '';
                document.getElementById('custom-event-effect-value').value = '5';
            } else {
                alert(data.error || '建立失敗');
            }
        }

        // ==================== GM Team 管理加強版 ====================
        async function loadGMTeams() {
            const container = document.getElementById('gm-teams-list');
            container.innerHTML = '<div class="text-zinc-400 text-center py-4">載入中...</div>';
            
            const res = await fetch('/gm/teams');
            const data = await res.json();
            
            if (!data.teams || data.teams.length === 0) {
                container.innerHTML = '<div class="text-zinc-400 text-center py-8">尚未有任何 Team</div>';
                return;
            }
            
            container.innerHTML = '';
            
            // 統一排序（同玩家一樣）
            data.teams.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
            
            for (const team of data.teams) {
                const div = document.createElement('div');
                div.className = 'bg-zinc-800 rounded-2xl p-5 border border-zinc-700';
                const safeName = (team.team_name || '').replace(/'/g, "\\'");
                
                div.innerHTML = `
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <div class="font-mono font-bold text-emerald-400">${team.team_id}</div>
                            <div class="text-lg font-semibold flex items-center gap-x-2">
                                ${team.team_name}
                                <button onclick="gmEditTeamName('${team.team_id}', '${safeName}')" 
                                        class="text-xs px-2 py-0.5 bg-zinc-700 hover:bg-zinc-600 rounded">改名</button>
                            </div>
                            <div class="text-xs text-zinc-400 mt-0.5">${team.member_count} 位成員</div>
                        </div>
                        <div>
                            <div class="text-xs px-3 py-1 rounded-full text-center ${team.route === 'iggy' ? 'bg-red-900/60 text-red-400' : team.route === 'marah' ? 'bg-blue-900/60 text-blue-400' : 'bg-zinc-700 text-zinc-400'}">
                                ${team.route === 'iggy' ? '🔥 Iggy 線' : team.route === 'marah' ? '🌊 Marah 線' : '未設定路線'}
                            </div>
                        </div>
                    </div>
                    
                    <div class="flex flex-wrap gap-2 mb-3">
                        <button onclick="gmAssignSquadToTeam('${team.team_id}')" 
                                class="px-3 py-1.5 text-xs bg-amber-600 hover:bg-amber-700 rounded-xl flex items-center gap-x-1">
                            <i class="fa-solid fa-exchange-alt"></i>
                            <span>轉隊 / 分配</span>
                        </button>
                        <button onclick="gmSetRoutePrompt('${team.team_id}')" 
                                class="px-3 py-1.5 text-xs bg-purple-600 hover:bg-purple-700 rounded-xl">設定路線</button>
                        <button onclick="gmViewTeamMembers('${team.team_id}', '${safeName}')" 
                                class="px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-xl">查看成員</button>
                    </div>
                `;
                container.appendChild(div);
            }
        }

        async function gmCreateTeam() {
            const name = document.getElementById('new-team-name').value.trim() || '新小隊';
            const res = await fetch('/gm/create_team', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({team_name: name})
            });
            const data = await res.json();
            if (data.success) {
                alert(`Team ${data.team_id} 已建立`);
                document.getElementById('new-team-name').value = '';
                loadGMTeams();
            }
        }

        function gmEditTeamName(teamId, currentName) {
            const safeVal = (currentName || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100]';
            
            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-zinc-700">
                    <div class="text-xl font-bold mb-1">修改隊名</div>
                    <div class="text-sm text-zinc-400 mb-4">Team ID: ${teamId}</div>
                    
                    <input type="text" id="edit-team-name-input" value="${safeVal}" 
                           class="w-full bg-zinc-800 border border-zinc-700 focus:border-amber-500 rounded-2xl px-5 py-3 text-lg mb-6">
                    
                    <div class="flex gap-x-3">
                        <button onclick="this.closest('.fixed').remove()" 
                                class="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm">
                            取消
                        </button>
                        <button onclick="confirmUpdateTeamName('${teamId}', this)" 
                                class="flex-1 py-3 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl text-sm">
                            確認修改
                        </button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            setTimeout(() => {
                const input = modal.querySelector('#edit-team-name-input');
                if (input) input.focus();
            }, 100);
        }

        function confirmUpdateTeamName(teamId, buttonElement) {
            const input = document.getElementById('edit-team-name-input');
            const newName = input.value.trim();
            
            if (!newName) {
                alert('隊名不能為空');
                return;
            }

            buttonElement.disabled = true;
            buttonElement.textContent = '更新中...';

            fetch('/gm/update_team_name', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    team_id: teamId,
                    new_name: newName
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    buttonElement.closest('.fixed').remove();
                    alert('隊名已成功更新！');
                    loadGMTeams();
                } else {
                    alert(data.error || '更新失敗');
                    buttonElement.disabled = false;
                    buttonElement.textContent = '確認修改';
                }
            })
            .catch(() => {
                alert('發生錯誤，請重試');
                buttonElement.disabled = false;
                buttonElement.textContent = '確認修改';
            });
        }

        async function gmAssignSquadToTeam(teamId) {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100]';

            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-zinc-700">
                    <div class="text-xl font-bold mb-1">分配 / 轉隊玩家</div>
                    <div class="text-sm text-zinc-400 mb-4">Team ID: ${teamId}</div>

                    <div class="mb-4">
                        <div class="text-sm text-zinc-400 mb-2">選擇玩家：</div>
                        <select id="assign-player-select"
                                class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-3 text-sm">
                            <option value="">載入中...</option>
                        </select>
                    </div>

                    <div class="flex gap-x-3">
                        <button onclick="this.closest('.fixed').remove()"
                                class="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm">
                            取消
                        </button>
                        <button onclick="confirmAssignPlayer('${teamId}', this)"
                                class="flex-1 py-3 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl text-sm">
                            確認分配
                        </button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            try {
                const res = await fetch(
                    `/gm/assignable_players?team_id=${encodeURIComponent(teamId)}`,
                    { credentials: 'same-origin' }
                );
                const data = await res.json();

                const select = modal.querySelector('#assign-player-select');
                select.innerHTML = '<option value="">-- 請選擇玩家 --</option>';

                if (!res.ok || data.success === false) {
                    select.innerHTML = '<option value="">載入失敗</option>';
                    alert(data.error || '載入玩家列表失敗，請重新登入 GM');
                    return;
                }

                const players = data.players || [];
                if (players.length === 0) {
                    select.innerHTML = '<option value="">（無可分配玩家 — 可能全部已在隊內）</option>';
                    return;
                }

                players.forEach(player => {
                    const option = document.createElement('option');
                    option.value = player.squad_id;
                    option.textContent = player.label || `${player.display_name} (${player.squad_id})`;
                    select.appendChild(option);
                });
            } catch (e) {
                alert('載入玩家列表失敗');
                modal.remove();
            }
        }

        async function confirmAssignPlayer(teamId, buttonElement) {
            const modal = buttonElement.closest('.fixed');
            const select = modal.querySelector('#assign-player-select');
            const squadId = select.value;

            if (!squadId) {
                alert('請選擇一個玩家');
                return;
            }

            buttonElement.disabled = true;
            buttonElement.textContent = '分配中...';

            const res = await fetch('/gm/assign_squad', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    squad_id: squadId,
                    team_id: teamId
                })
            });

            const data = await res.json();

            if (data.success) {
                modal.remove();
                alert(data.message || '分配成功！');
                loadGMTeams();
            } else {
                alert(data.error || '分配失敗');
                buttonElement.disabled = false;
                buttonElement.textContent = '確認分配';
            }
        }

        function gmSetRoutePrompt(teamId) {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100]';
            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-zinc-700">
                    <div class="text-xl font-bold mb-1">設定 Team 路線</div>
                    <div class="text-sm text-zinc-400 mb-6">Team ID: ${teamId}</div>
                    
                    <div class="grid grid-cols-2 gap-4 mb-6">
                        <div onclick="gmConfirmSetRoute('${teamId}', 'iggy', this)" 
                             class="route-card route-iggy p-6 text-center cursor-pointer">
                            <div class="text-3xl mb-2">🔥</div>
                            <div class="text-xl font-bold">Iggy 路線</div>
                            <div class="text-xs mt-1 opacity-80">界線、力量、面對 Judas</div>
                        </div>
                        
                        <div onclick="gmConfirmSetRoute('${teamId}', 'marah', this)" 
                             class="route-card route-marah p-6 text-center cursor-pointer">
                            <div class="text-3xl mb-2">🌊</div>
                            <div class="text-xl font-bold">Marah 路線</div>
                            <div class="text-xs mt-1 opacity-80">智慧、韌性、深度連結</div>
                        </div>
                    </div>
                    
                    <button onclick="this.closest('.fixed').remove()" 
                            class="w-full py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm">
                        取消
                    </button>
                </div>
            `;
            document.body.appendChild(modal);
        }

        function gmConfirmSetRoute(teamId, route, element) {
            fetch('/gm/set_team_route', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({team_id: teamId, route: route})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    element.closest('.fixed').remove();
                    alert('路線已成功設定為 ' + (route === 'iggy' ? 'Iggy' : 'Marah'));
                    loadGMTeams();
                } else {
                    alert('設定失敗');
                }
            });
        }

        async function gmViewTeamMembers(teamId, teamName) {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100]';

            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-2xl mx-4 rounded-3xl p-6 border border-zinc-700 max-h-[80vh] overflow-auto">
                    <div class="flex justify-between items-center mb-6">
                        <div>
                            <div class="text-xl font-bold">${teamName}</div>
                            <div class="text-sm text-zinc-400">Team ID: ${teamId}</div>
                        </div>
                        <button onclick="this.closest('.fixed').remove()"
                                class="text-3xl leading-none text-zinc-400 hover:text-white">×</button>
                    </div>
                    <div id="team-members-content">
                        <div class="text-center py-8 text-zinc-400">載入中...</div>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            const contentEl = modal.querySelector('#team-members-content');
            try {
                const res = await fetch(`/gm/team_members/${teamId}`);
                const data = await res.json();

                if (!data.members || data.members.length === 0) {
                    contentEl.innerHTML = '<div class="text-center py-6 text-zinc-400">暫無成員</div>';
                    return;
                }

                contentEl.innerHTML = '';
                data.members.forEach(m => {
                    const el = document.createElement('div');
                    el.className = 'bg-zinc-800 border border-zinc-700 rounded-2xl p-4 mb-3';
                    const name = m.display_name || m.squad_id;
                    el.innerHTML = `
                        <div class="flex justify-between items-start mb-2">
                            <div class="flex items-center gap-x-3">
                                <img src="/static/avatars/${m.avatar || 'default.png'}"
                                     class="w-10 h-10 rounded-full object-cover border border-zinc-600 shrink-0">
                                <div>
                                    <div class="font-semibold text-lg">${name}</div>
                                    <div class="text-xs text-zinc-500 font-mono">${m.squad_id}</div>
                                </div>
                            </div>
                            <a href="/gm/squad/${m.squad_id}" class="text-xs px-3 py-1 bg-amber-500/20 text-amber-400 rounded-xl hover:bg-amber-500/30">詳情</a>
                        </div>
                        <div class="grid grid-cols-5 gap-2 text-center text-xs">
                            <div><div class="text-red-400 font-mono">${m.hp}</div><div class="text-zinc-500">HP</div></div>
                            <div><div class="text-purple-400 font-mono">${m.sanity}</div><div class="text-zinc-500">San</div></div>
                            <div><div class="text-orange-400 font-mono">${m.power}</div><div class="text-zinc-500">Pow</div></div>
                            <div><div class="text-blue-400 font-mono">${m.intellect}</div><div class="text-zinc-500">Int</div></div>
                            <div><div class="text-emerald-400 font-mono">${m.resilience}</div><div class="text-zinc-500">Res</div></div>
                        </div>
                    `;
                    contentEl.appendChild(el);
                });
            } catch (e) {
                contentEl.innerHTML = '<div class="text-red-400 text-center py-6">載入失敗</div>';
            }
        }

        async function downloadTeamImages(teamId) {
            try {
                const res = await fetch(`/gm/download_team_images/${encodeURIComponent(teamId)}`, { credentials: 'same-origin' });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    alert(data.error || '下載失敗');
                    return;
                }
                const blob = await res.blob();
                const disposition = res.headers.get('Content-Disposition') || '';
                let filename = `team_${teamId}_images.zip`;
                const match = disposition.match(/filename="?([^";]+)"?/);
                if (match) filename = match[1];
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = filename;
                link.click();
                URL.revokeObjectURL(url);
            } catch (e) {
                alert('下載失敗');
            }
        }

        async function viewPlayerLogs(squadId) {
            const modal = document.getElementById('player-log-modal');
            const titleEl = document.getElementById('player-log-modal-title');
            const contentEl = document.getElementById('player-log-modal-content');
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            titleEl.textContent = '載入中...';
            contentEl.innerHTML = '<div class="text-zinc-400 text-center py-8">載入中...</div>';

            try {
                const res = await fetch(`/gm/player_logs/${encodeURIComponent(squadId)}`, { credentials: 'same-origin' });
                const data = await res.json();

                if (!res.ok || !data.success) {
                    titleEl.textContent = '載入失敗';
                    contentEl.innerHTML = `<div class="text-red-400 text-center py-8">${data.error || '載入失敗'}</div>`;
                    return;
                }

                const player = data.player || {};
                const teamLabel = player.team_name || player.team_id || '未入隊';
                titleEl.textContent = `${player.display_name || squadId} · ${teamLabel}`;

                const logs = data.logs || [];
                if (logs.length === 0) {
                    contentEl.innerHTML = '<div class="text-zinc-400 text-center py-8">暫無任務記錄</div>';
                    return;
                }

                contentEl.innerHTML = '';
                logs.forEach(log => {
                    const div = document.createElement('div');
                    div.className = 'border border-zinc-700 rounded-2xl p-4 mb-3';
                    div.innerHTML = `
                        <div class="flex flex-wrap justify-between items-start gap-2 mb-2">
                            <div>
                                <div class="font-semibold text-amber-400">${log.task_name}</div>
                                <div class="text-xs text-zinc-500 font-mono">${log.task_id || ''}</div>
                            </div>
                            <span class="text-xs px-2 py-0.5 bg-emerald-900/50 text-emerald-300 rounded-full">${log.status}</span>
                        </div>
                        <div class="text-xs text-zinc-500 mb-2">${log.timestamp || ''}</div>
                        ${log.description ? `<div class="text-zinc-300 text-sm mb-3 whitespace-pre-wrap">${log.description}</div>` : ''}
                        ${(log.photo_url || log.photo_path) ? `
                            <img src="${log.photo_url || '/' + log.photo_path}" class="max-h-48 rounded-xl border border-zinc-700">
                        ` : ''}
                    `;
                    contentEl.appendChild(div);
                });
            } catch (e) {
                titleEl.textContent = '載入失敗';
                contentEl.innerHTML = '<div class="text-red-400 text-center py-8">載入失敗</div>';
            }
        }

        function hidePlayerLogModal() {
            const modal = document.getElementById('player-log-modal');
            modal.classList.remove('flex');
            modal.classList.add('hidden');
        }

        function formatOverviewTime(ts) {
            if (!ts) return '—';
            try {
                const d = new Date(ts);
                if (isNaN(d.getTime())) return ts;
                return d.toLocaleString('zh-HK', { hour12: false });
            } catch (e) {
                return ts;
            }
        }

        async function loadTeamsOverview() {
            const container = document.getElementById('gm-overview-content');
            container.innerHTML = '<div class="text-zinc-400 text-center py-8">載入中...</div>';

            try {
                const res = await fetch('/gm/teams_overview', { credentials: 'same-origin' });
                const data = await res.json();

                if (!res.ok || !data.success) {
                    container.innerHTML = '<div class="text-red-400 text-center py-8">載入失敗</div>';
                    return;
                }

                const teams = data.teams || [];
                const solo = data.solo_players || [];

                if (teams.length === 0 && solo.length === 0) {
                    container.innerHTML = '<div class="text-zinc-400 text-center py-8">暫無隊伍或玩家資料</div>';
                    return;
                }

                let html = '';

                if (teams.length > 0) {
                    html += '<div class="space-y-4">';
                    teams.forEach(team => {
                        const routeClass = team.route === 'iggy'
                            ? 'bg-red-900/40 text-red-300'
                            : team.route === 'marah'
                                ? 'bg-blue-900/40 text-blue-300'
                                : 'bg-zinc-700 text-zinc-300';
                        html += `
                            <div class="bg-zinc-800 border border-zinc-700 rounded-2xl p-5 text-left">
                                <div class="flex flex-wrap justify-between items-start gap-3 mb-4">
                                    <div>
                                        <div class="text-lg font-semibold text-emerald-400">${team.team_name}</div>
                                        <div class="text-xs text-zinc-500 font-mono mt-0.5">${team.team_id}</div>
                                        <div class="text-sm text-zinc-300 mt-1">隊長：${team.leader_name} · ${team.member_count} 位成員</div>
                                    </div>
                                    <span class="text-xs px-3 py-1 rounded-full ${routeClass}">${team.route_label}</span>
                                </div>
                                <div class="grid grid-cols-2 md:grid-cols-5 gap-3 text-center text-xs mb-4">
                                    <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-red-400 font-mono text-base">${team.avg_hp}</div><div class="text-zinc-500">平均 HP</div></div>
                                    <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-purple-400 font-mono text-base">${team.avg_sanity}</div><div class="text-zinc-500">平均 San</div></div>
                                    <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-orange-400 font-mono text-base">${team.avg_power}</div><div class="text-zinc-500">平均 Pow</div></div>
                                    <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-blue-400 font-mono text-base">${team.avg_intellect}</div><div class="text-zinc-500">平均 Int</div></div>
                                    <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-emerald-400 font-mono text-base">${team.avg_resilience}</div><div class="text-zinc-500">平均 Res</div></div>
                                </div>
                                <div class="flex flex-wrap gap-x-6 gap-y-1 text-sm text-zinc-400 mb-4">
                                    <span>已完成任務：<strong class="text-amber-400">${team.distinct_tasks}</strong></span>
                                    <span>劇情階段：<strong class="text-zinc-200">Stage ${team.story_stage}</strong></span>
                                    <span>提交次數：<strong class="text-zinc-200">${team.submission_count}</strong></span>
                                    <span>最近提交：<strong class="text-zinc-200">${formatOverviewTime(team.last_submission)}</strong></span>
                                </div>
                                <div class="flex flex-wrap gap-2 mb-4">
                                    <button onclick="downloadTeamImages('${team.team_id}')"
                                            class="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 rounded-xl flex items-center gap-x-1">
                                        <i class="fa-solid fa-download"></i>
                                        <span>下載該隊圖片 (ZIP)</span>
                                    </button>
                                </div>
                                ${(team.members && team.members.length) ? `
                                    <div class="border-t border-zinc-700 pt-3">
                                        <div class="text-xs text-zinc-500 mb-2">隊員任務記錄</div>
                                        <div class="flex flex-wrap gap-2">
                                            ${team.members.map(m => `
                                                <button onclick="viewPlayerLogs('${m.squad_id}')"
                                                        class="px-2 py-1 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-lg">
                                                    ${m.is_leader ? '👑 ' : ''}${m.display_name}
                                                </button>
                                            `).join('')}
                                        </div>
                                    </div>
                                ` : ''}
                            </div>
                        `;
                    });
                    html += '</div>';
                }

                if (solo.length > 0) {
                    html += `
                        <div class="mt-8">
                            <h3 class="text-lg font-semibold text-left mb-3 text-zinc-300">未加入隊伍的玩家</h3>
                            <div class="overflow-x-auto">
                                <table class="w-full text-sm text-left">
                                    <thead>
                                        <tr class="border-b border-zinc-700 text-zinc-400">
                                            <th class="py-2 pr-4">玩家</th>
                                            <th class="py-2 pr-4">路線</th>
                                            <th class="py-2 pr-4">HP/San/Pow/Int/Res</th>
                                            <th class="py-2 pr-4">任務</th>
                                            <th class="py-2 pr-4">階段</th>
                                            <th class="py-2 pr-4">提交</th>
                                            <th class="py-2 pr-4">最近提交</th>
                                            <th class="py-2">操作</th>
                                        </tr>
                                    </thead>
                                    <tbody class="divide-y divide-zinc-800">
                    `;
                    solo.forEach(p => {
                        html += `
                            <tr class="hover:bg-zinc-800/50">
                                <td class="py-3 pr-4">
                                    <a href="/gm/squad/${p.squad_id}" class="text-amber-400 hover:underline">${p.display_name}</a>
                                    <div class="text-xs text-zinc-500 font-mono">${p.squad_id}</div>
                                </td>
                                <td class="py-3 pr-4 text-xs">${p.route_label}</td>
                                <td class="py-3 pr-4 font-mono text-xs">${p.hp}/${p.sanity}/${p.power}/${p.intellect}/${p.resilience}</td>
                                <td class="py-3 pr-4">${p.distinct_tasks}</td>
                                <td class="py-3 pr-4">Stage ${p.story_stage}</td>
                                <td class="py-3 pr-4">${p.submission_count}</td>
                                <td class="py-3 text-xs text-zinc-400">${formatOverviewTime(p.last_submission)}</td>
                                <td class="py-3">
                                    ${p.submission_count > 0 ? `
                                        <button onclick="viewPlayerLogs('${p.squad_id}')"
                                                class="px-2 py-1 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-lg">任務 Log</button>
                                    ` : '<span class="text-zinc-500">—</span>'}
                                </td>
                            </tr>
                        `;
                    });
                    html += '</tbody></table></div></div>';
                }

                container.innerHTML = html;
            } catch (e) {
                container.innerHTML = '<div class="text-red-400 text-center py-8">載入失敗</div>';
            }
        }

        function switchGMTab(tab) {
            const squadsTab = document.getElementById('gm-squads-tab');
            const teamsTab = document.getElementById('gm-teams-tab');
            const overviewTab = document.getElementById('gm-overview-tab');
            const btnSquads = document.getElementById('tab-squads');
            const btnTeams = document.getElementById('tab-teams');
            const btnOverview = document.getElementById('tab-overview');
            const allTabs = [squadsTab, teamsTab, overviewTab];
            const allBtns = [btnSquads, btnTeams, btnOverview];

            allTabs.forEach(el => el.classList.add('hidden'));
            allBtns.forEach(btn => btn.classList.remove('active', 'bg-amber-500', 'text-zinc-950'));

            if (tab === 'teams') {
                teamsTab.classList.remove('hidden');
                btnTeams.classList.add('active', 'bg-amber-500', 'text-zinc-950');
                loadGMTeams();
            } else if (tab === 'overview') {
                overviewTab.classList.remove('hidden');
                btnOverview.classList.add('active', 'bg-amber-500', 'text-zinc-950');
                loadTeamsOverview();
            } else {
                squadsTab.classList.remove('hidden');
                btnSquads.classList.add('active', 'bg-amber-500', 'text-zinc-950');
            }
        }

        setTimeout(() => {
            const btn = document.getElementById('tab-squads');
            if (btn) btn.classList.add('active', 'bg-amber-500', 'text-zinc-950');
        }, 300);
        </script>

        <!-- 玩家任務 Log Modal -->
        <div id="player-log-modal" onclick="if (event.target.id === 'player-log-modal') hidePlayerLogModal()"
             class="hidden fixed inset-0 bg-black/80 items-center justify-center z-[60]">
            <div onclick="event.stopImmediatePropagation()"
                 class="bg-zinc-900 w-full max-w-2xl mx-4 rounded-3xl p-6 border border-zinc-700 max-h-[85vh] flex flex-col">
                <div class="flex justify-between items-start mb-4 shrink-0">
                    <div>
                        <div class="text-lg font-bold" id="player-log-modal-title">任務 Log</div>
                        <div class="text-xs text-zinc-500 mt-0.5">玩家過往提交記錄</div>
                    </div>
                    <button onclick="hidePlayerLogModal()" class="text-3xl leading-none text-zinc-400 hover:text-white">×</button>
                </div>
                <div id="player-log-modal-content" class="overflow-y-auto flex-1"></div>
            </div>
        </div>

        <!-- 清空圖片確認 Modal -->
        <div id="clear-images-modal" onclick="if (event.target.id === 'clear-images-modal') hideClearImagesModal()"
             class="hidden fixed inset-0 bg-black/80 flex items-center justify-center z-[60]">
            <div onclick="event.stopImmediatePropagation()"
                 class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-red-500/30">

                <div class="text-red-400 font-semibold text-xl mb-2">⚠️ 確認清空所有上傳圖片</div>
                <div class="text-zinc-300 mb-6">此操作無法復原。請輸入 <span class="font-mono text-amber-400">CLEAR_IMAGES</span> 確認。</div>

                <input type="text" id="clear-images-confirm" placeholder="輸入 CLEAR_IMAGES"
                       class="w-full bg-zinc-800 border border-zinc-700 focus:border-red-500 rounded-2xl px-5 py-3 mb-4">

                <div class="flex gap-x-3">
                    <button onclick="hideClearImagesModal()"
                            class="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl">取消</button>
                    <button onclick="confirmClearAllImages()"
                            class="flex-1 py-3 bg-red-600 hover:bg-red-700 rounded-2xl font-medium">確認刪除</button>
                </div>
            </div>
        </div>

        <!-- 重置確認 Modal -->
        <div id="reset-modal" onclick="if (event.target.id === 'reset-modal') hideResetModal()" 
             class="hidden fixed inset-0 bg-black/80 flex items-center justify-center z-[60]">
            <div onclick="event.stopImmediatePropagation()" 
                 class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-red-500/30">
                
                <div class="text-red-400 font-semibold text-xl mb-2">⚠️ 確認重置遊戲</div>
                <div class="text-zinc-300 mb-6">此操作無法復原。請輸入重置密碼確認。</div>
                
                <input type="password" id="reset-password" placeholder="輸入重置密碼" 
                       class="w-full bg-zinc-800 border border-zinc-700 focus:border-red-500 rounded-2xl px-5 py-3 mb-4">
                
                <div class="flex gap-x-3">
                    <button onclick="hideResetModal()" 
                            class="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl">取消</button>
                    <button onclick="confirmResetGame()" 
                            class="flex-1 py-3 bg-red-600 hover:bg-red-700 rounded-2xl font-medium">確認重置</button>
                </div>
            </div>
        </div>

        <script>
        function showClearImagesModal() {
            document.getElementById('clear-images-modal').classList.remove('hidden');
            document.getElementById('clear-images-modal').classList.add('flex');
            document.getElementById('clear-images-confirm').focus();
        }

        function hideClearImagesModal() {
            document.getElementById('clear-images-modal').classList.remove('flex');
            document.getElementById('clear-images-modal').classList.add('hidden');
            document.getElementById('clear-images-confirm').value = '';
        }

        async function confirmClearAllImages() {
            const confirmText = document.getElementById('clear-images-confirm').value.trim();

            if (confirmText !== 'CLEAR_IMAGES') {
                alert('確認碼錯誤！請輸入 CLEAR_IMAGES');
                return;
            }

            if (!confirm('確定要刪除所有玩家上傳過的圖片嗎？此操作不可恢復！')) {
                return;
            }

            try {
                const res = await fetch('/gm/clear_all_images', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ confirm: confirmText })
                });
                const data = await res.json();

                if (data.success) {
                    alert(data.message || '圖片已清空');
                    hideClearImagesModal();
                } else {
                    alert(data.error || '清空失敗');
                }
            } catch (e) {
                alert('發生錯誤，請重試');
            }
        }

        function showResetModal() {
            document.getElementById('reset-modal').classList.remove('hidden');
            document.getElementById('reset-modal').classList.add('flex');
            document.getElementById('reset-password').focus();
        }

        function hideResetModal() {
            document.getElementById('reset-modal').classList.remove('flex');
            document.getElementById('reset-modal').classList.add('hidden');
            document.getElementById('reset-password').value = '';
        }

        function confirmResetGame() {
            const password = document.getElementById('reset-password').value;
            
            fetch('/gm/reset_game', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({password: password})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert(data.message || '遊戲已重置');
                    window.location.reload();
                } else {
                    alert(data.error || '密碼錯誤或重置失敗');
                }
            })
            .catch(() => {
                alert('發生錯誤，請重試');
            });
        }
        </script>
    </div>

</body>
</html>
"""

GM_SQUAD_DETAIL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ squad.display_name or squad.squad_id }} 詳情 • GM</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
</head>
<body class="bg-zinc-950 text-white p-8">
    <div class="max-w-5xl mx-auto">
        <div class="mb-8">
            <a href="/gm/dashboard" class="text-amber-400 hover:underline flex items-center gap-x-2 mb-2">
                <i class="fa-solid fa-arrow-left"></i>
                <span>返回 GM Dashboard</span>
            </a>
            
            <div class="flex items-end gap-x-4">
                <img src="/static/avatars/{{ squad.avatar or 'default.png' }}"
                     class="w-16 h-16 rounded-full object-cover border-2 border-zinc-600">
                <div class="flex items-end gap-x-3">
                    <h1 class="text-3xl font-bold">{{ squad.display_name or squad.squad_id }}</h1>
                </div>
            </div>
            
            <div class="text-sm text-zinc-400 mt-1">玩家詳情與提交記錄</div>
        </div>

        <div class="bg-zinc-900 rounded-3xl p-6 mb-8">
            <h2 class="text-lg font-semibold mb-4">玩家目前狀態</h2>
            
            <div class="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-4 text-sm">
                <div>
                    <span class="text-zinc-400">顯示名稱</span><br>
                    <span class="font-semibold text-lg">{{ squad.display_name or squad.squad_id }}</span>
                </div>
                <div>
                    <span class="text-zinc-400">所屬 Team</span><br>
                    <span class="font-mono text-emerald-400">{{ squad.team_id or '未加入任何隊' }}</span>
                </div>
                <div>
                    <span class="text-zinc-400">路線</span><br>
                    <span class="font-mono">{{ squad.route_label }}</span>
                </div>
                <div>
                    <span class="text-zinc-400">Resource</span><br>
                    <span class="font-mono text-purple-400">{{ squad.resources }}</span>
                </div>
                <div>
                    <span class="text-zinc-400">PIN 狀態</span><br>
                    <span class="font-mono {{ 'text-emerald-400' if squad.has_pin else 'text-zinc-500' }}">
                        {{ '已設定' if squad.has_pin else '未設定' }}
                    </span>
                </div>
                
                <div class="col-span-2 md:col-span-4 grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-3 mt-2 pt-4 border-t border-zinc-700">
                    <div>HP: <span class="font-mono text-red-400">{{ squad.hp }}</span></div>
                    <div>Sanity: <span class="font-mono text-purple-400">{{ squad.sanity }}</span></div>
                    <div>Power: <span class="font-mono text-orange-400">{{ squad.power }}</span></div>
                    <div>Intellect: <span class="font-mono text-blue-400">{{ squad.intellect }}</span></div>
                    <div>Resilience: <span class="font-mono text-emerald-400">{{ squad.resilience }}</span></div>
                </div>
            </div>
        </div>

        <button onclick="gmResetPlayerPin('{{ squad.squad_id }}', '{{ squad.display_name or squad.squad_id }}')"
                class="mb-8 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm">
            重置玩家 PIN
        </button>

        <!-- 手動調整數值 -->
        <div class="bg-zinc-900 rounded-3xl p-6 mt-6">
            <h2 class="text-lg font-semibold mb-4">手動調整數值</h2>
            
            <form id="adjust-form" class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <input type="hidden" name="squad_id" value="{{ squad.squad_id }}">
                
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">HP</label>
                    <div class="flex gap-x-2">
                        <input type="number" name="value" id="hp-value" value="{{ squad.hp }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('hp')" 
                                class="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
                
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">Sanity</label>
                    <div class="flex gap-x-2">
                        <input type="number" name="value" id="sanity-value" value="{{ squad.sanity }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('sanity')" 
                                class="px-4 py-2 bg-amber-600 hover:bg-amber-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
                
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">Power</label>
                    <div class="flex gap-x-2">
                        <input type="number" id="power-value" value="{{ squad.power }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('power')" 
                                class="px-4 py-2 bg-orange-600 hover:bg-orange-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">Intellect</label>
                    <div class="flex gap-x-2">
                        <input type="number" id="intellect-value" value="{{ squad.intellect }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('intellect')" 
                                class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">Resilience</label>
                    <div class="flex gap-x-2">
                        <input type="number" id="resilience-value" value="{{ squad.resilience }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('resilience')" 
                                class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">Resource</label>
                    <div class="flex gap-x-2">
                        <input type="number" id="resource-value" value="{{ squad.resources }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('resources')" 
                                class="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
            </form>
        </div>

        <script>
        function gmResetPlayerPin(squadId, displayName) {
            if (!confirm(`確定要重置 ${displayName || squadId} 的 PIN 嗎？`)) return;

            const newPin = prompt('輸入新 PIN（留空則自動生成 4 位數字）');

            fetch('/gm/reset_pin', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    squad_id: squadId,
                    new_pin: newPin || ''
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert(`${displayName || squadId} 的新 PIN 是：${data.new_pin}\\n請告知玩家！`);
                    location.reload();
                } else {
                    alert(data.error || '重置失敗');
                }
            });
        }

        function adjustValue(field) {
            let valueInput;
            const ids = {hp:'hp-value', sanity:'sanity-value', power:'power-value', intellect:'intellect-value', resilience:'resilience-value', resources:'resource-value'};
            valueInput = document.getElementById(ids[field]);

            const value = valueInput.value;
            const squadId = '{{ squad.squad_id }}';

            fetch('/gm/adjust', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    squad_id: squadId,
                    field: field,
                    value: value
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert(field + ' 已更新');
                    location.reload();
                } else {
                    alert('更新失敗: ' + data.error);
                }
            });
        }
        </script>

        <div class="bg-zinc-900 rounded-3xl p-6">
            <h2 class="text-lg font-semibold mb-4">提交記錄（{{ submissions|length }} 筆）</h2>
            
            {% if submissions %}
                <div class="space-y-6">
                    {% for sub in submissions %}
                    <div class="border border-zinc-700 rounded-2xl p-5">
                        <div class="flex justify-between text-sm mb-2">
                            <div>
                                <span class="text-amber-400 font-mono">{{ sub.task_id }}</span>
                            </div>
                            <div class="text-zinc-400 text-xs">{{ sub.timestamp }}</div>
                        </div>
                        
                        {% if sub.content %}
                        <div class="text-zinc-300 mb-3">{{ sub.content }}</div>
                        {% endif %}
                        
                        {% if sub.photo_url or sub.photo_path %}
                        <div>
                            <div class="text-xs text-zinc-400 mb-1">上傳相片：</div>
                            <img src="{{ sub.photo_url or '/' + sub.photo_path }}" class="max-h-64 rounded-xl border border-zinc-700">
                        </div>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
            {% else %}
                <div class="text-zinc-400 py-8 text-center">此小隊尚未有任何提交記錄。</div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

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