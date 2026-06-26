#!/usr/bin/env python3
"""
Oikonomia - Summer Camp 2026 Web App Prototype
Built by Grok Build
Priority: Beautiful Dashboard + GPS + Photo Upload
"""

from flask import Flask, render_template_string, request, jsonify, session, redirect, send_from_directory
import sqlite3
import json
import os
from datetime import datetime
import math
import time
import random

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "oikonomia-2026-prototype")
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get("RENDER") == "true" or os.environ.get("FLASK_ENV") == "production",
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_PATH = "oikonomia.db"

DEFAULT_PROTAGONIST = {"hp": 100, "sanity": 100, "power": 100, "intellect": 100, "resilience": 100}
SQUAD_ATTRIBUTES = ["hp", "sanity", "power", "intellect", "resilience"]

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
    else:
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
        count = conn.execute("""
            SELECT COUNT(DISTINCT task_id)
            FROM submissions
            WHERE squad_id IN (SELECT squad_id FROM squads WHERE team_id = ?)
        """, (team_id,)).fetchone()[0]
        rows = conn.execute("""
            SELECT DISTINCT task_id
            FROM submissions
            WHERE squad_id IN (SELECT squad_id FROM squads WHERE team_id = ?)
        """, (team_id,)).fetchall()
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

# ==================== 輔助函數 ====================
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
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        team_row = conn.execute(
            "SELECT route, leader_squad_id FROM teams WHERE team_id = ?",
            (squad["team_id"],),
        ).fetchone()
        conn.close()

        if team_row:
            if team_row["route"]:
                squad["route"] = team_row["route"]
            if team_row["leader_squad_id"] == squad["squad_id"]:
                squad["is_team_leader"] = 1

    return squad

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
        "SELECT COUNT(*) FROM squads WHERE team_id = ?", (clean_id,)
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
            "SELECT COUNT(*) FROM squads WHERE team_id = ?", (row["team_id"],)
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

# ==================== Routes ====================
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

    session["squad_id"] = row["squad_id"]
    conn.close()

    return jsonify({
        "success": True,
        "squad": get_squad(row["squad_id"]),
        "require_set_pin": not has_pin,
    })

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
            "photo_path": row["photo_path"],
            "timestamp": row["timestamp"],
        })

    return jsonify({"submissions": submissions})

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
def status():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401
    return jsonify(get_squad(session["squad_id"]))

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
        return jsonify({"has_team": False})
    team = get_team_by_id(squad["team_id"])
    if not team:
        return jsonify({"has_team": False})
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM squads WHERE team_id = ? ORDER BY squad_id", (squad["team_id"],)
    ).fetchall()
    conn.close()
    members = [row_to_squad(r) for r in rows]
    return jsonify({"has_team": True, "team": team, "members": members})

@app.route("/available_teams")
def available_teams():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    current_team_id = squad.get("team_id") if squad else None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM teams ORDER BY created_at DESC").fetchall()

    teams = []
    for row in rows:
        member_count = conn.execute(
            "SELECT COUNT(*) FROM squads WHERE team_id = ?", (row["team_id"],)
        ).fetchone()[0]

        is_joined = (row["team_id"] == current_team_id)

        teams.append({
            "team_id": row["team_id"],
            "team_name": row["team_name"],
            "route": row["route"],
            "member_count": member_count,
            "is_joined": is_joined
        })

    conn.close()
    return jsonify({"teams": teams})

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

    update_squad(session["squad_id"], team_id=team["team_id"], is_team_leader=0)
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

    team_id = squad.get("team_id")
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

    return jsonify({"success": True, "squad": get_squad(session["squad_id"])})

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
    return jsonify({"success": True, "squad": get_squad(session["squad_id"])})

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
            photo_path = os.path.join(UPLOAD_FOLDER, filename)
            photo.save(photo_path)

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
    avatar_dir = os.path.join(app.static_folder, "avatars")
    if not os.path.exists(avatar_dir):
        return jsonify({"avatars": []})
    files = [
        filename for filename in os.listdir(avatar_dir)
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

    avatar_path = os.path.join(app.static_folder, "avatars", avatar_filename)
    if not os.path.exists(avatar_path):
        return jsonify({"success": False, "error": "頭像不存在"}), 400

    update_squad(session["squad_id"], avatar=avatar_filename)
    return jsonify({"success": True, "avatar": avatar_filename})

# ==================== GM Routes ====================

GM_PIN = "gm2026"  # GM 登入 PIN，你可以之後改

@app.route("/gm")
def gm_login_page():
    return render_template_string(GM_LOGIN_HTML)

@app.route("/gm/login", methods=["POST"])
def gm_login():
    pin = request.form.get("pin", "")
    if pin == GM_PIN:
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
            "photo_path": sub[2],
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

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if event_type == "adjust_sanity":
        # 全營 Sanity 調整
        c.execute("UPDATE squads SET sanity = sanity + ?", (value,))
        message = f"全營 Sanity {'+' if value > 0 else ''}{value}"

    elif event_type == "judas_strengthen":
        # Judas 加強事件（範例：全營 Sanity 下降 + 記錄事件）
        c.execute("UPDATE squads SET sanity = sanity - 8")
        message = "Judas 加強！全營 Sanity -8"

    elif event_type == "iggy_collapse":
        c.execute("UPDATE squads SET sanity = sanity - 12")
        message = "Iggy 開始崩潰！全營 Sanity -12"

    else:
        conn.close()
        return jsonify({"success": False, "error": "未知事件類型"})

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": message})

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

    # 2. 清空所有 Team
    c.execute("DELETE FROM teams")

    # 3. 刪除所有玩家記錄（Squad = 獨立玩家ID）
    c.execute("DELETE FROM squads")

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "遊戲已完全重置（所有玩家ID、Team、提交記錄已清空）",
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

    from datetime import datetime, timedelta

    # HKT 時間（UTC+8）
    hkt_time = datetime.utcnow() + timedelta(hours=8)
    timestamp = hkt_time.strftime("%Y-%m-%d %H:%M")

    ANNOUNCEMENTS.append({
        "message": message,
        "timestamp": timestamp
    })

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
        return jsonify({"error": "未授權"}), 403

    team_id = request.args.get("team_id", "").strip().upper()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if team_id:
        rows = conn.execute("""
            SELECT squad_id, display_name, team_id
            FROM squads
            WHERE team_id IS NULL OR team_id != ?
            ORDER BY display_name
        """, (team_id,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT squad_id, display_name, team_id FROM squads ORDER BY display_name
        """).fetchall()

    conn.close()

    players = []
    for row in rows:
        label = row["display_name"] or row["squad_id"]
        if row["team_id"]:
            label += f"（現於 {row['team_id']}）"
        players.append({
            "squad_id": row["squad_id"],
            "display_name": row["display_name"] or row["squad_id"],
            "current_team_id": row["team_id"],
            "label": label,
        })

    return jsonify({"players": players})

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
    update_squad(squad_id, team_id=new_team_id, is_team_leader=is_leader)

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
    return send_from_directory(UPLOAD_FOLDER, filename)

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
        body { font-family: 'Noto Sans TC', system-ui, sans-serif; }
        .title-font { font-family: 'Playfair Display', Georgia, serif; }
        .game-bg { background: linear-gradient(145deg, #0f172a 0%, #1e1135 100%); }
        .section-card { 
            background: rgba(15, 23, 42, 0.9); 
            border: 1px solid rgba(245, 158, 11, 0.1);
        }
        .status-bar { transition: width 0.4s ease; }
        .nav-active { background-color: rgba(245, 158, 11, 0.15); color: #f59e0b; border-radius: 9999px; }
        .nav-btn {
            color: #a1a1aa;
            transition: all 0.2s;
        }
        .nav-btn:hover {
            color: #f4f4f5;
            background-color: rgba(63, 63, 70, 0.3);
            border-radius: 9999px;
        }
        .cartoon-box {
            border: 3px solid #2C3E50;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.05);
            box-shadow: 6px 6px 0px rgba(44, 62, 80, 0.6);
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
        .location-card { cursor: pointer; padding: 1.25rem; border-radius: 1.5rem; margin-bottom: 1rem;
            background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(245, 158, 11, 0.1); }
        .location-card:active { opacity: 0.85; }
        .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 50;
            display: flex; align-items: flex-end; justify-content: center; }
        .modal-box { background: #18181b; width: 100%; max-width: 480px; padding: 1.5rem;
            border-radius: 1.5rem 1.5rem 0 0; border-top: 1px solid #3f3f46; }
        @media (min-width: 768px) {
            .modal-overlay { align-items: center; }
            .modal-box { border-radius: 1.5rem; }
        }
    </style>
</head>
<body class="game-bg text-zinc-200">
    <div class="max-w-4xl mx-auto">
        <!-- ==================== Header ==================== -->
        <div class="flex items-center justify-between px-6 py-5 border-b border-zinc-800">
            <div class="flex items-center gap-x-3">
                <div class="w-9 h-9 bg-amber-500 rounded-2xl flex items-center justify-center">
                    <i class="fa-solid fa-link text-zinc-950"></i>
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

        <!-- Login -->
        <div id="login-screen" class="max-w-md mx-auto px-6 py-16">
            <div class="text-center mb-8">
                <i class="fa-solid fa-user-secret text-6xl text-amber-400 mb-4"></i>
                <h1 class="text-3xl font-bold">你已從臍帶中斷裂</h1>
                <p class="text-zinc-400 mt-2">輸入名稱登入（首次無需 PIN）</p>
            </div>
            <form onsubmit="login(event)" class="section-card rounded-3xl p-8 space-y-4">
                <input type="text" id="squad_id" placeholder="輸入你的名稱" 
                       class="w-full bg-zinc-900 border border-zinc-700 focus:border-amber-500 rounded-2xl px-6 py-4 text-xl mb-3">
                <input type="password" id="login_pin" placeholder="輸入 PIN（第一次登入可留空）" maxlength="4"
                       inputmode="numeric" pattern="[0-9]*"
                       class="w-full bg-zinc-900 border border-zinc-700 focus:border-amber-500 rounded-2xl px-6 py-4 text-xl tracking-widest text-center font-mono">
                <button type="submit" 
                        class="w-full bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold py-4 rounded-2xl">
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
                        <div class="text-sm text-amber-400">FRAGMENT</div>
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

                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                    <!-- Squad 五維 -->
                    <div class="cartoon-box p-5">
                        <h3 class="font-bold mb-4 flex items-center gap-2"><i class="fa-solid fa-shield-halved text-emerald-400"></i> Squad Status</h3>
                        <div class="space-y-3">
                            <div class="stat-row" data-stat="hp"><div class="flex justify-between text-sm mb-1"><span>❤️ HP</span><span id="hp-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="hp-bar" class="h-2.5 bg-red-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div class="stat-row" data-stat="sanity"><div class="flex justify-between text-sm mb-1"><span>🧠 Sanity</span><span id="sanity-value" class="font-mono">50</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="sanity-bar" class="h-2.5 bg-purple-500 rounded-full status-bar" style="width:50%"></div></div></div>
                            <div class="stat-row" data-stat="power"><div class="flex justify-between text-sm mb-1"><span>⚡ Power</span><span id="power-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="power-bar" class="h-2.5 bg-orange-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div class="stat-row" data-stat="intellect"><div class="flex justify-between text-sm mb-1"><span>📖 Intellect</span><span id="intellect-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="intellect-bar" class="h-2.5 bg-blue-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div class="stat-row" data-stat="resilience"><div class="flex justify-between text-sm mb-1"><span>🛡️ Resilience</span><span id="resilience-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="resilience-bar" class="h-2.5 bg-emerald-500 rounded-full status-bar" style="width:100%"></div></div></div>
                        </div>
                        <div class="mt-4 pt-3 border-t border-zinc-700 flex justify-between text-sm">
                            <span><i class="fa-solid fa-gem text-purple-400 mr-1"></i>Resource</span>
                            <span id="resource-value" class="font-mono text-purple-400">0</span>
                        </div>
                    </div>

                    <!-- Protagonist 五維 -->
                    <div id="protagonist-panel" class="hidden cartoon-box p-5">
                        <h3 id="protagonist-title" class="font-bold mb-4">🔥 Iggy / Marah</h3>
                        <div class="space-y-3">
                            <div><div class="flex justify-between text-sm mb-1"><span>❤️ HP</span><span id="p-hp-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="p-hp-bar" class="h-2.5 bg-red-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>🧠 Sanity</span><span id="p-sanity-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="p-sanity-bar" class="h-2.5 bg-purple-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>⚡ Power</span><span id="p-power-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="p-power-bar" class="h-2.5 bg-orange-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>📖 Intellect</span><span id="p-intellect-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="p-intellect-bar" class="h-2.5 bg-blue-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>🛡️ Resilience</span><span id="p-resilience-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="p-resilience-bar" class="h-2.5 bg-emerald-500 rounded-full status-bar" style="width:100%"></div></div></div>
                        </div>
                    </div>
                </div>

                <!-- Zoo Skills -->
                <div>
                    <div class="font-medium mb-3 flex items-center gap-x-2">
                        <i class="fa-solid fa-magic text-amber-400"></i>
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
                        <div class="text-sm text-amber-400">LOG</div>
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

                <div class="cartoon-box p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="font-bold text-xl flex items-center gap-x-2">
                            <i class="fa-solid fa-tasks text-amber-400"></i>
                            <span>任務記錄</span>
                        </h3>
                        <button onclick="loadMySubmissions()"
                                class="text-xs px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-2xl">
                            刷新記錄
                        </button>
                    </div>
                    <div id="submission-list" class="space-y-4"></div>
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
                    <div class="text-sm text-amber-400">TEAM</div>
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
                    <div id="team-members-list" class="grid grid-cols-1 md:grid-cols-2 gap-4"></div>
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
            if (id === 'team') loadMyTeam();
            if (id === 'log') {
                loadStoryLog();
                loadMySubmissions();
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

        async function loadMySubmissions() {
            const container = document.getElementById('submission-list');
            container.innerHTML = '<div class="text-zinc-400">載入中...</div>';

            try {
                const res = await fetch('/my_submissions', { credentials: 'same-origin' });
                const data = await res.json();

                if (!data.submissions || data.submissions.length === 0) {
                    container.innerHTML = `<div class="text-zinc-400 py-6 text-center">你尚未提交任何任務。</div>`;
                    return;
                }

                container.innerHTML = '';
                data.submissions.forEach(sub => {
                    const el = document.createElement('div');
                    el.className = 'bg-zinc-800 border border-zinc-700 rounded-2xl p-5';
                    el.innerHTML = `
                        <div class="flex justify-between items-start mb-3">
                            <div>
                                <span class="font-mono text-amber-400">${sub.task_id}</span>
                            </div>
                            <div class="text-xs text-zinc-400">${sub.timestamp}</div>
                        </div>

                        ${sub.content ? `<div class="text-zinc-300 mb-3">${sub.content}</div>` : ''}

                        ${sub.photo_path ? `
                            <div class="mt-2">
                                <img src="/${sub.photo_path}" class="max-h-48 rounded-xl border border-zinc-700">
                            </div>
                        ` : ''}

                        <div class="mt-3 text-xs text-emerald-400">
                            <i class="fa-solid fa-check-circle mr-1"></i> 已提交（+6 Sanity / +1 Resource）
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

        function updateDashboard(squad) {
            ['hp','sanity','power','intellect','resilience'].forEach(s => setStatBar('', s, squad[s] ?? 100));
            document.getElementById('resource-value').textContent = squad.resources || 0;
            document.getElementById('squad-name').textContent = squad.display_name || squad.squad_id;

            const routePicker = document.getElementById('route-picker');
            const routeBadge = document.getElementById('route-badge');
            const isLeader = squad.is_team_leader === 1;
            const hasTeamRoute = squad.route;
            const inTeam = !!squad.team_id;

            document.getElementById('protagonist-panel').classList.toggle('hidden', !hasTeamRoute);

            if (hasTeamRoute) {
                if (routePicker) setVisible(routePicker, false);
                if (routeBadge) {
                    setVisible(routeBadge, true);
                    routeBadge.innerHTML = squad.route === 'iggy'
                        ? `<span class="inline-flex items-center gap-x-1 px-3 py-1 bg-red-900/60 text-red-400 rounded-full text-xs font-medium">🔥 Iggy 路線</span>`
                        : `<span class="inline-flex items-center gap-x-1 px-3 py-1 bg-blue-900/60 text-blue-400 rounded-full text-xs font-medium">🌊 Marah 路線</span>`;
                }
                document.getElementById('protagonist-title').textContent =
                    squad.route === 'iggy' ? '🔥 Iggy' : '🌊 Marah';
            } else if (inTeam && isLeader) {
                if (routePicker) setVisible(routePicker, true);
                if (routeBadge) setVisible(routeBadge, false);
            } else if (inTeam && !isLeader) {
                if (routePicker) setVisible(routePicker, false);
                if (routeBadge) {
                    setVisible(routeBadge, true);
                    routeBadge.innerHTML = `<span class="text-xs text-zinc-400">等待隊長選擇路線...</span>`;
                }
            } else {
                if (routePicker) setVisible(routePicker, true);
                if (routeBadge) setVisible(routeBadge, false);
            }

            if (squad.protagonist && hasTeamRoute) {
                const p = squad.protagonist;
                ['hp','sanity','power','intellect','resilience'].forEach(s => setStatBar('p-', s, p[s] ?? 100));
            }

            if (currentSquad) currentSquad.avatar = squad.avatar;
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

            if (data.squad) {
                currentSquad = data.squad;
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
                } else {
                    setVisible(noBox, false);
                    setVisible(hasBox, true);
                }

                if (!data.has_team) {
                    loadAvailableTeams();
                    return;
                }

                const team = data.team;
                const isLeader = currentSquad && currentSquad.is_team_leader === 1;
                const safeTeamName = (team.team_name || '').replace(/'/g, "\\'");

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

                const list = document.getElementById('team-members-list');
                list.innerHTML = '';
                const members = data.members || [];
                if (members.length === 0) {
                    list.innerHTML = '<div class="text-zinc-400 col-span-2 text-center py-6">暫無隊友</div>';
                } else {
                members.forEach(m => {
                    const isYou = currentSquad && m.squad_id === currentSquad.squad_id;
                    const el = document.createElement('div');
                    el.className = 'cartoon-box p-4' + (isYou ? ' ring-2 ring-amber-500/50' : '');

                    const displayName = m.display_name || m.squad_id;

                    el.innerHTML = `
                        <div class="flex items-center gap-x-3">
                            <img src="${avatarSrc(m.avatar)}"
                                 class="w-12 h-12 rounded-full object-cover border border-zinc-600 shrink-0">
                            <div class="flex-1">
                                <div class="font-semibold text-lg">
                                    ${displayName}
                                    ${isYou ? '<span class="text-xs text-amber-400 ml-1">(你)</span>' : ''}
                                </div>
                            </div>
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
                loadAvailableTeams();
            } catch (e) {
                console.error('loadMyTeam failed', e);
                setVisible(noBox, true);
                setVisible(hasBox, false);
                loadAvailableTeams();
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
                data.teams.forEach(team => {
                    const el = document.createElement('div');
                    el.className = 'flex items-center justify-between bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-2xl px-4 py-3';

                    let actionBtn = '';
                    if (team.is_joined) {
                        actionBtn = `<span class="px-4 py-1 text-xs bg-zinc-600 text-zinc-300 rounded-xl">已加入</span>`;
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

        async function completeLogin(data) {
            currentSquad = data.squad;
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

        function showLocationPermissionGuide() {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100] px-4';

            const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);

            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-md rounded-3xl p-6 border border-zinc-700">
                    <div class="text-xl font-bold mb-4">需要開啟定位權限</div>

                    <div class="text-zinc-300 mb-6 leading-relaxed">
                        請到手機設定開啟定位權限，先至可以用到探索功能。
                    </div>

                    <div class="space-y-3">
                        ${isIOS ? `
                            <div class="bg-zinc-800 p-4 rounded-2xl text-sm">
                                <strong>iPhone / iPad：</strong><br>
                                設定 → Oikonomia → 位置 → 選擇「使用 App 期間」或「永遠」
                            </div>
                        ` : `
                            <div class="bg-zinc-800 p-4 rounded-2xl text-sm">
                                <strong>Android：</strong><br>
                                設定 → 應用程式 → Oikonomia → 權限 → 位置 → 允許
                            </div>
                        `}

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
                fetch('/status').then(r => r.json()).then(d => updateDashboard(d));
            }
        }, 12000);

        let currentAvatar = null;

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
    </script>

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
                        <th class="py-3">Player ID</th>
                        <th class="py-3">路線</th>
                        <th class="py-3">HP</th>
                        <th class="py-3">Sanity</th>
                        <th class="py-3">Pow/Int/Res</th>
                        <th class="py-3">提交次數</th>
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
                            
                            {% if squad.submission_count > 0 %}
                            <a href="/gm/squad/{{ squad.squad_id }}" 
                               class="ml-3 px-3 py-1 text-xs bg-amber-500 hover:bg-amber-600 text-zinc-950 rounded-full">
                                查看詳情
                            </a>
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
                const res = await fetch(`/gm/assignable_players?team_id=${teamId}`);
                const data = await res.json();

                const select = modal.querySelector('#assign-player-select');
                select.innerHTML = '<option value="">-- 請選擇玩家 --</option>';

                (data.players || []).forEach(player => {
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

        function switchGMTab(tab) {
            const squadsTab = document.getElementById('gm-squads-tab');
            const teamsTab = document.getElementById('gm-teams-tab');
            const btnSquads = document.getElementById('tab-squads');
            const btnTeams = document.getElementById('tab-teams');

            if (tab === 'squads') {
                squadsTab.classList.remove('hidden');
                teamsTab.classList.add('hidden');
                btnSquads.classList.add('active', 'bg-amber-500', 'text-zinc-950');
                btnTeams.classList.remove('active', 'bg-amber-500', 'text-zinc-950');
            } else {
                squadsTab.classList.add('hidden');
                teamsTab.classList.remove('hidden');
                btnTeams.classList.add('active', 'bg-amber-500', 'text-zinc-950');
                btnSquads.classList.remove('active', 'bg-amber-500', 'text-zinc-950');
                loadGMTeams();
            }
        }

        setTimeout(() => {
            const btn = document.getElementById('tab-squads');
            if (btn) btn.classList.add('active', 'bg-amber-500', 'text-zinc-950');
        }, 300);
        </script>

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

                    {% if squad.display_name %}
                    <div class="text-xs text-zinc-500 pb-1 font-mono">
                        {{ squad.squad_id }}
                    </div>
                    {% endif %}
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
                        
                        {% if sub.photo_path %}
                        <div>
                            <div class="text-xs text-zinc-400 mb-1">上傳相片：</div>
                            <img src="/{{ sub.photo_path }}" class="max-h-64 rounded-xl border border-zinc-700">
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
    app.run(host="0.0.0.0", port=port, debug=debug)