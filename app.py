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

app = Flask(__name__)
app.secret_key = "oikonomia-2026-prototype"

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
        protagonist_stats TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        squad_id TEXT,
        task_id TEXT,
        content TEXT,
        photo_path TEXT,
        timestamp TEXT
    )''')
    conn.commit()
    conn.close()
    migrate_db()

def migrate_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(squads)")
    cols = {row[1] for row in c.fetchall()}
    additions = {
        "power": "INTEGER DEFAULT 100",
        "intellect": "INTEGER DEFAULT 100",
        "resilience": "INTEGER DEFAULT 100",
        "route": "TEXT",
        "protagonist_stats": "TEXT",
    }
    for col, typedef in additions.items():
        if col not in cols:
            c.execute(f"ALTER TABLE squads ADD COLUMN {col} {typedef}")
    c.execute(
        "UPDATE squads SET protagonist_stats = ? WHERE protagonist_stats IS NULL",
        (json.dumps(DEFAULT_PROTAGONIST),),
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
        "sanity": d.get("sanity", 50),
        "hp": d.get("hp", 100),
        "power": d.get("power", 100),
        "intellect": d.get("intellect", 100),
        "resilience": d.get("resilience", 100),
        "resources": d.get("resources", 0),
        "zoo_skills": json.loads(d["zoo_skills"]) if d.get("zoo_skills") else [],
        "route": d.get("route"),
        "protagonist": protagonist,
    }

def get_squad(squad_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM squads WHERE squad_id = ?", (squad_id,)).fetchone()
    conn.close()
    return row_to_squad(row) if row else None

def get_all_squads():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM squads ORDER BY squad_id").fetchall()
    conn.close()
    return [row_to_squad(r) for r in rows]

def update_squad(squad_id, **kwargs):
    allowed = {"sanity", "hp", "power", "intellect", "resilience", "resources", "route", "protagonist_stats"}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    updates = []
    params = []
    for key, val in kwargs.items():
        if key in allowed and val is not None:
            updates.append(f"{key} = ?")
            params.append(val)
    if updates:
        updates.append("last_update = ?")
        params.append(datetime.now().isoformat())
        params.append(squad_id)
        c.execute(f"UPDATE squads SET {', '.join(updates)} WHERE squad_id = ?", params)
        conn.commit()
    conn.close()

# ==================== Routes ====================
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/login", methods=["POST"])
def login():
    squad_id = request.form.get("squad_id", "").strip().upper()
    if not squad_id.startswith("FRAG-"):
        return jsonify({"error": "請輸入正確嘅 Fragment ID (例如 FRAG-01)"}), 400

    squad = get_squad(squad_id)
    if not squad:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO squads (squad_id) VALUES (?)", (squad_id,))
        conn.commit()
        conn.close()
        squad = get_squad(squad_id)

    session["squad_id"] = squad_id
    return jsonify({"success": True, "squad": squad})

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

    photo_path = None
    if "photo" in request.files:
        photo = request.files["photo"]
        if photo.filename:
            filename = f"{session['squad_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            photo_path = os.path.join(UPLOAD_FOLDER, filename)
            photo.save(photo_path)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO submissions (squad_id, task_id, content, photo_path, timestamp)
                 VALUES (?, ?, ?, ?, ?)""",
              (session["squad_id"], task_id, content, photo_path, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    # 簡單獎勵
    squad = get_squad(session["squad_id"])
    new_sanity = min(100, squad["sanity"] + 6)
    new_resources = squad["resources"] + 1
    update_squad(session["squad_id"], sanity=new_sanity, resources=new_resources)

    return jsonify({"success": True, "message": "任務提交成功！+6 Sanity +1 Resource"})

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

    # 清空提交記錄
    c.execute("DELETE FROM submissions")

    # 重置所有小隊數值
    c.execute("""
        UPDATE squads 
        SET hp = 100, sanity = 50, power = 100, intellect = 100, resilience = 100,
            resources = 0, zoo_skills = '[]', route = NULL, protagonist_stats = ?
    """, (json.dumps(DEFAULT_PROTAGONIST),))

    conn.commit()
    conn.close()

    # 可選：刪除上傳相片（如果想清乾淨）
    # import shutil
    # if os.path.exists("uploads"):
    #     shutil.rmtree("uploads")
    #     os.makedirs("uploads")

    return jsonify({"success": True, "message": "遊戲已重置"})

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
    </style>
</head>
<body class="game-bg text-zinc-200">
    <div class="max-w-4xl mx-auto">
        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-5 border-b border-zinc-800">
            <div class="flex items-center gap-x-3">
                <div class="w-9 h-9 bg-amber-500 rounded-2xl flex items-center justify-center">
                    <i class="fa-solid fa-link text-zinc-950"></i>
                </div>
                <div>
                    <span class="title-font text-3xl font-bold">Oikonomia</span>
                </div>
            </div>
            <div id="nav" class="hidden items-center gap-x-1 text-sm">
                <button onclick="showSection('dashboard')" class="px-5 py-2 nav-btn">Dashboard</button>
                <button onclick="showSection('explore')" class="px-5 py-2 nav-btn">探索</button>
                <button onclick="showSection('team')" class="px-5 py-2 nav-btn">Team</button>
            </div>
        </div>

        <!-- Login -->
        <div id="login-screen" class="max-w-md mx-auto px-6 py-16">
            <div class="text-center mb-8">
                <i class="fa-solid fa-user-secret text-6xl text-amber-400 mb-4"></i>
                <h1 class="text-3xl font-bold">你已從臍帶中斷裂</h1>
            </div>
            <form onsubmit="login(event)" class="section-card rounded-3xl p-8 space-y-4">
                <input type="text" id="squad_id" value="FRAG-01" 
                       class="w-full bg-zinc-900 border border-zinc-700 focus:border-amber-500 rounded-2xl px-6 py-4 text-xl font-mono">
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

                <div class="mb-6">
                    <div class="text-sm text-amber-400">FRAGMENT</div>
                    <div id="squad-name" class="text-4xl font-semibold"></div>
                    <div id="route-badge" class="hidden mt-2 text-sm"></div>
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

            <!-- Explore -->
            <div id="explore" class="section hidden">
                <h2 class="text-2xl font-semibold mb-4">探索地點</h2>
                <div id="location-list" class="space-y-4"></div>
            </div>

            <!-- Team -->
            <div id="team" class="section hidden">
                <h2 class="text-2xl font-semibold mb-2">Team</h2>
                <p class="text-sm text-zinc-400 mb-6">所有 Fragment 即時狀態</p>
                <div id="team-list" class="space-y-4"></div>
            </div>
        </div>
    </div>

    <script>
        let currentSquad = null;

        function showSection(id) {
            document.querySelectorAll('.section').forEach(s => s.classList.add('hidden'));
            document.getElementById(id).classList.remove('hidden');
            if (id === 'explore') loadLocations();
            if (id === 'team') loadTeam();
        }

        function setStatBar(prefix, stat, value) {
            const el = document.getElementById(prefix + stat + '-value');
            const bar = document.getElementById(prefix + stat + '-bar');
            if (el) el.textContent = value;
            if (bar) bar.style.width = value + '%';
        }

        function updateDashboard(squad) {
            ['hp','sanity','power','intellect','resilience'].forEach(s => setStatBar('', s, squad[s] ?? 100));
            document.getElementById('resource-value').textContent = squad.resources || 0;

            const hasRoute = !!squad.route;
            document.getElementById('route-picker').classList.toggle('hidden', hasRoute);
            document.getElementById('protagonist-panel').classList.toggle('hidden', !hasRoute);

            const badge = document.getElementById('route-badge');
            if (hasRoute) {
                const label = squad.route === 'iggy' ? '🔥 Iggy 路線' : '🌊 Marah 路線';
                badge.textContent = label;
                badge.className = 'mt-2 text-sm px-3 py-1 rounded-full inline-block ' +
                    (squad.route === 'iggy' ? 'bg-red-900/50 text-red-300' : 'bg-blue-900/50 text-blue-300');
                badge.classList.remove('hidden');
                document.getElementById('protagonist-title').textContent =
                    squad.route === 'iggy' ? '🔥 Iggy' : '🌊 Marah';
            } else {
                badge.classList.add('hidden');
            }

            if (squad.protagonist && hasRoute) {
                const p = squad.protagonist;
                ['hp','sanity','power','intellect','resilience'].forEach(s => setStatBar('p-', s, p[s] ?? 100));
            }
        }

        async function selectRoute(route) {
            if (!confirm(route === 'iggy' ? '確認選擇 Iggy 路線？' : '確認選擇 Marah 路線？')) return;
            const res = await fetch('/set_route', { method: 'POST', body: new URLSearchParams({route}) });
            const data = await res.json();
            if (!data.success) { alert(data.error || '選擇失敗'); return; }
            currentSquad = data.squad;
            updateDashboard(currentSquad);
        }

        async function loadTeam() {
            const res = await fetch('/team');
            const data = await res.json();
            const container = document.getElementById('team-list');
            container.innerHTML = '';
            if (!data.members || data.members.length === 0) {
                container.innerHTML = '<div class="text-zinc-400 text-center py-8">暫無小隊資料</div>';
                return;
            }
            data.members.forEach(m => {
                const routeLabel = m.route === 'iggy' ? 'Iggy' : m.route === 'marah' ? 'Marah' : '未選';
                const isYou = currentSquad && m.squad_id === currentSquad.squad_id;
                const el = document.createElement('div');
                el.className = 'cartoon-box p-5' + (isYou ? ' ring-2 ring-amber-500/50' : '');
                el.innerHTML = `
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <div class="font-mono font-bold text-amber-400">${m.squad_id}${isYou ? ' (你)' : ''}</div>
                            <div class="text-xs text-zinc-400 mt-0.5">${routeLabel} 路線</div>
                        </div>
                    </div>
                    <div class="grid grid-cols-5 gap-2 text-center text-xs">
                        <div><div class="text-red-400 font-mono">${m.hp}</div><div class="text-zinc-500">HP</div></div>
                        <div><div class="text-purple-400 font-mono">${m.sanity}</div><div class="text-zinc-500">San</div></div>
                        <div><div class="text-orange-400 font-mono">${m.power}</div><div class="text-zinc-500">Pow</div></div>
                        <div><div class="text-blue-400 font-mono">${m.intellect}</div><div class="text-zinc-500">Int</div></div>
                        <div><div class="text-emerald-400 font-mono">${m.resilience}</div><div class="text-zinc-500">Res</div></div>
                    </div>`;
                container.appendChild(el);
            });
        }

        async function login(e) {
            e.preventDefault();
            const id = document.getElementById('squad_id').value.trim();
            const res = await fetch('/login', { method: 'POST', body: new URLSearchParams({squad_id: id}) });
            const data = await res.json();
            if (!data.success) { alert(data.error); return; }

            currentSquad = data.squad;
            document.getElementById('login-screen').classList.add('hidden');
            document.getElementById('game-content').classList.remove('hidden');
            document.getElementById('nav').classList.remove('hidden');
            document.getElementById('nav').classList.add('flex');
            document.getElementById('squad-name').textContent = currentSquad.squad_id;
            updateDashboard(currentSquad);
            showSection('dashboard');
            loadAnnouncements();
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

        async function loadLocations() {
            const res = await fetch('/locations');
            const locs = await res.json();
            const container = document.getElementById('location-list');
            container.innerHTML = '';
            Object.keys(locs).forEach(key => {
                const loc = locs[key];
                const el = document.createElement('div');
                el.className = 'section-card rounded-3xl p-5 cursor-pointer';
                el.innerHTML = `<div class="font-semibold">${loc.name}</div><div class="text-xs text-amber-400">${loc.hint}</div>`;
                el.onclick = () => {
                    console.log("你點擊了地點：", key);
                    openLocation(key, loc);
                };
                container.appendChild(el);
            });
        }

        function openLocation(id, loc) {
            currentLocation = { id: id, ...loc };

            // 建立簡單 Modal
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/70 flex items-end md:items-center justify-center z-50';
            modal.innerHTML = `
                <div class="bg-zinc-900 w-full md:w-[480px] md:rounded-t-3xl md:rounded-b-3xl rounded-t-3xl p-6 border-t border-zinc-700">
                    <div class="flex justify-between items-start mb-4">
                        <div>
                            <div class="font-semibold text-2xl">${loc.name}</div>
                            <div class="text-sm text-amber-400 mt-0.5">${loc.hint}</div>
                        </div>
                        <button class="text-3xl leading-none text-zinc-400 hover:text-white" onclick="this.closest('.fixed').remove()">×</button>
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
                alert('你的手機唔支援定位');
                return;
            }

            navigator.geolocation.getCurrentPosition(async (position) => {
                const res = await fetch('/verify_gps', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        loc_id: locId,
                        lat: position.coords.latitude,
                        lng: position.coords.longitude
                    })
                });
                const data = await res.json();
                alert(data.message);
                if (data.success) {
                    document.querySelector('.fixed').remove();
                }
            }, () => {
                alert('無法取得定位，請檢查權限');
            });
        }

        async function submitPhotoWithFile(locId, file, modal) {
            const formData = new FormData();
            formData.append('task_id', locId);
            formData.append('photo', file);

            const res = await fetch('/submit_task', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            alert(data.message);
            if (modal) modal.remove();
        }

        async function submitPhotoTask(locId, btn) {
            btn.disabled = true;
            btn.textContent = '提交中...';

            const formData = new FormData();
            formData.append('task_id', locId);

            const res = await fetch('/submit_task', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            alert(data.message);
            btn.closest('.fixed').remove();
        }

        async function startPuzzle(locId, btn) {
            const answer = prompt('請輸入答案：');
            if (!answer) return;

            // 簡單示範，之後可以改做真實後端驗證
            if (answer.toLowerCase() === 'iggy') {
                alert('正確！獲得 Sanity +8');
                btn.closest('.fixed').remove();
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
</head>
<body class="bg-zinc-950 text-white p-8">
    <div class="max-w-6xl mx-auto">
        <div class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-3xl font-bold">GM Dashboard</h1>
                <p class="text-zinc-400 text-sm mt-1">即時監控所有小隊狀態</p>
            </div>
            <div class="flex items-center gap-x-3">
                <div class="text-xs px-3 py-1.5 bg-zinc-800 rounded-2xl text-emerald-400 flex items-center gap-x-2">
                    <i class="fa-solid fa-sync fa-spin"></i>
                    <span>自動刷新中</span>
                </div>
                <button onclick="location.reload()" 
                        class="px-5 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-2xl text-sm flex items-center gap-x-2">
                    <i class="fa-solid fa-redo"></i>
                    <span>手動刷新</span>
                </button>
                <a href="/" class="px-5 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-2xl text-sm">返回玩家端</a>
            </div>
        </div>

        <div class="bg-zinc-900 rounded-3xl p-6">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-semibold">所有小隊即時狀態</h2>
                <div class="text-xs text-zinc-500">最後更新：{{ last_update }}</div>
            </div>
            
            <table class="w-full">
                <thead>
                    <tr class="border-b border-zinc-700 text-left text-sm text-zinc-400">
                        <th class="py-3 pl-2">Squad ID</th>
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
                        <td class="py-4 pl-2 font-mono font-semibold text-amber-400">{{ squad.squad_id }}</td>
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
        </script>
        
        <div class="mt-4 text-xs text-zinc-500 px-1">
            提示：之後會加入手動調整、查看提交記錄、Global Event 等功能。
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
                    <div class="text-xs text-zinc-400">會清空所有提交記錄，並將所有小隊數值重置為初始值</div>
                </div>
                <button onclick="showResetModal()" 
                        class="px-6 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm font-medium">
                    重置遊戲
                </button>
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

    <script>
        // 每 8 秒自動刷新
        setInterval(() => {
            location.reload();
        }, 8000);
    </script>
</body>
</html>
"""

GM_SQUAD_DETAIL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ squad.squad_id }} 詳情 • GM</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-white p-8">
    <div class="max-w-5xl mx-auto">
        <div class="flex justify-between items-center mb-8">
            <div>
                <a href="/gm/dashboard" class="text-amber-400 hover:underline">← 返回 GM Dashboard</a>
                <h1 class="text-3xl font-bold mt-2">{{ squad.squad_id }} 提交記錄</h1>
            </div>
        </div>

        <div class="bg-zinc-900 rounded-3xl p-6 mb-8">
            <h2 class="text-lg font-semibold mb-4">小隊目前狀態</h2>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>路線: <span class="font-mono text-amber-400">{{ squad.route_label }}</span></div>
                <div>HP: <span class="font-mono text-red-400">{{ squad.hp }}</span></div>
                <div>Sanity: <span class="font-mono text-purple-400">{{ squad.sanity }}</span></div>
                <div>Power: <span class="font-mono text-orange-400">{{ squad.power }}</span></div>
                <div>Intellect: <span class="font-mono text-blue-400">{{ squad.intellect }}</span></div>
                <div>Resilience: <span class="font-mono text-emerald-400">{{ squad.resilience }}</span></div>
                <div>Resource: <span class="font-mono">{{ squad.resources }}</span></div>
                <div>Zoo 能力: <span class="font-mono">{{ squad.zoo_count }} 個</span></div>
            </div>
        </div>

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