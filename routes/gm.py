"""GM API routes (migrated from app.py)."""
import io
import os
import random
import re
import sqlite3
import zipfile
from datetime import datetime

from flask import Blueprint, current_app, jsonify, redirect, render_template_string, request, send_file, session

from models.combat import get_combat, resolve_player_phase
from models.encounter import load_encounter
from models.settings import settings
from models.squad import get_all_squads, get_squad, update_squad
from models.team import get_next_team_id, get_team_by_id, sync_team_route
from routes.gm_templates import GM_DASHBOARD_HTML, GM_LOGIN_HTML, GM_SQUAD_DETAIL_HTML

from services.global_events import apply_global_effect, create_global_event
from services.gm_admin import RESET_GAME_PASSWORD, clear_all_submission_images, reset_game_data
from services.teams_overview import (
    build_active_combats_overview,
    build_teams_overview,
    get_all_teams_with_stats,
)
from services.gm_auth import clear_gm_session, establish_gm_session, gm_session_valid
from utils.combat_v2_flag import combat_v2_active, is_combat_v2_enabled, set_combat_v2_enabled
from utils.db_tx import immediate_transaction, with_db_retry
from utils.env import is_production_env
from utils.helpers import (
    hkt_timestamp,
    normalize_photo_url,
    normalize_team_id,
    photo_public_url,
    resolve_upload_disk_path,
    safe_zip_arcname,
)
from utils.tasks import task_display_name

gm_bp = Blueprint("gm", __name__, url_prefix="/gm")


def _get_gm_pin():
    pin = os.environ.get("GM_PIN")
    if pin:
        return pin
    if is_production_env():
        raise RuntimeError("GM_PIN environment variable is required in production")
    return "gm2026"


def _require_gm():
    if not gm_session_valid(session):
        clear_gm_session(session)
        return jsonify({"success": False, "error": "未授權"}), 403
    return None


def _require_gm_html():
    if not gm_session_valid(session):
        clear_gm_session(session)
        return redirect("/gm")
    return None


# ==================== GM HTML Pages ====================

@gm_bp.route("/", strict_slashes=False)
def gm_login_page():
    return render_template_string(GM_LOGIN_HTML)


@gm_bp.route("/dashboard")
def gm_dashboard():
    denied = _require_gm_html()
    if denied:
        return denied

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    submission_counts = {
        row["squad_id"]: row["total"]
        for row in conn.execute(
            "SELECT squad_id, COUNT(*) AS total FROM submissions GROUP BY squad_id"
        ).fetchall()
    }
    conn.close()

    squad_list = []
    for s in get_all_squads():
        squad_list.append({
            **s,
            "zoo_count": len(s["zoo_skills"]),
            "submission_count": submission_counts.get(s["squad_id"], 0),
            "route_label": {"iggy": "Iggy", "marah": "Marah"}.get(s.get("route"), "未選"),
        })
    last_update = datetime.now().strftime("%H:%M:%S")
    return render_template_string(GM_DASHBOARD_HTML, squads=squad_list, last_update=last_update)


@gm_bp.route("/squad/<squad_id>")
def gm_squad_detail_page(squad_id):
    denied = _require_gm_html()
    if denied:
        return denied

    conn = sqlite3.connect(settings.db_path)
    c = conn.cursor()
    squad = get_squad(squad_id)
    if not squad:
        conn.close()
        return "找不到該小隊", 404
    squad["zoo_count"] = len(squad["zoo_skills"])
    squad["route_label"] = {"iggy": "Iggy 路線", "marah": "Marah 路線"}.get(squad.get("route"), "未選路線")

    c.execute("""
        SELECT task_id, content, photo_path, timestamp
        FROM submissions
        WHERE squad_id = ?
        ORDER BY timestamp DESC
    """, (squad_id,))
    submissions_raw = c.fetchall()
    conn.close()

    submissions = []
    for sub in submissions_raw:
        submissions.append({
            "task_id": sub[0],
            "content": sub[1],
            "photo_path": normalize_photo_url(sub[2]),
            "photo_url": photo_public_url(sub[2]),
            "timestamp": sub[3],
        })

    return render_template_string(GM_SQUAD_DETAIL_HTML, squad=squad, submissions=submissions)


# ==================== GM API ====================

@gm_bp.route("/login", methods=["POST"])
def gm_login():
    pin = request.form.get("pin", "")
    if pin == _get_gm_pin():
        establish_gm_session(session)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "PIN 錯誤"}), 401


@gm_bp.route("/teams")
def gm_teams():
    denied = _require_gm()
    if denied:
        return denied

    return jsonify({"teams": get_all_teams_with_stats()})


@gm_bp.route("/create_team", methods=["POST"])
def gm_create_team():
    denied = _require_gm()
    if denied:
        return denied

    team_name = request.form.get("team_name", "").strip() or "新小隊"
    team_id = get_next_team_id()
    created_at = datetime.now().isoformat()

    conn = sqlite3.connect(settings.db_path)
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO teams (team_id, team_name, route, created_at, leader_squad_id) VALUES (?, ?, ?, ?, ?)",
            (team_id, team_name, None, created_at, None),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"success": True, "team_id": team_id, "team_name": team_name})


@gm_bp.route("/assign_squad", methods=["POST"])
def gm_assign_squad():
    denied = _require_gm()
    if denied:
        return denied

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

    update_squad(squad_id, team_id=normalize_team_id(new_team_id), is_team_leader=0)

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


@gm_bp.route("/set_team_route", methods=["POST"])
def gm_set_team_route():
    denied = _require_gm()
    if denied:
        return denied

    team_id = request.form.get("team_id", "").strip().upper()
    route = request.form.get("route", "").strip().lower()

    if route not in ("iggy", "marah"):
        return jsonify({"success": False, "error": "路線必須是 iggy 或 marah"}), 400
    if not get_team_by_id(team_id):
        return jsonify({"success": False, "error": "Team 不存在"}), 400

    sync_team_route(team_id, route)
    return jsonify({"success": True})


@gm_bp.route("/global_event", methods=["POST"])
def gm_global_event():
    denied = _require_gm()
    if denied:
        return denied

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


@gm_bp.route("/create_global_event", methods=["POST"])
def gm_create_global_event():
    denied = _require_gm()
    if denied:
        return denied

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


@gm_bp.route("/global_events")
def gm_get_global_events():
    denied = _require_gm()
    if denied:
        return denied

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        events = conn.execute("""
            SELECT id, title, description, effect_type, effect_value, created_by, timestamp
            FROM global_events
            ORDER BY timestamp DESC
            LIMIT 50
        """).fetchall()
    finally:
        conn.close()

    return jsonify({
        "success": True,
        "events": [dict(e) for e in events],
    })


@gm_bp.route("/teams_overview")
def gm_teams_overview():
    denied = _require_gm()
    if denied:
        return denied

    overview = build_teams_overview()
    return jsonify({"success": True, **overview})


@gm_bp.route("/active_combats")
def gm_active_combats():
    denied = _require_gm()
    if denied:
        return denied

    return jsonify({"success": True, "combats": build_active_combats_overview()})


@gm_bp.route("/combat/resolve_phase", methods=["POST"])
def gm_combat_resolve_phase():
    denied = _require_gm()
    if denied:
        return denied

    body = request.json if request.is_json else request.form
    combat_id = body.get("combat_id")
    if not combat_id:
        return jsonify({"success": False, "error": "缺少 combat_id"}), 400

    combat = get_combat(int(combat_id))
    if not combat:
        return jsonify({"success": False, "error": "戰鬥不存在"}), 404
    if combat.get("status") == "resolving":
        return jsonify({
            "success": False,
            "error": "回合結算中，請稍候再試",
        }), 409
    if combat.get("status") != "player_phase":
        return jsonify({
            "success": False,
            "error": f"目前狀態為 {combat.get('status')}，只能強制結算 player_phase",
        }), 400

    combat, winner = resolve_player_phase(int(combat_id))
    encounter = load_encounter(combat["encounter_id"]) if combat else None

    if winner == "squad":
        return jsonify({
            "success": True,
            "outcome": "victory",
            "winner": "squad",
            "combat_id": int(combat_id),
            "narrative": (encounter or {}).get("success", {}).get("narrative"),
        })
    if winner == "enemy":
        return jsonify({
            "success": True,
            "outcome": "defeat",
            "winner": "enemy",
            "combat_id": int(combat_id),
            "narrative": (encounter or {}).get("failure", {}).get("narrative"),
        })

    return jsonify({
        "success": True,
        "combat_id": int(combat_id),
        "status": combat.get("status") if combat else None,
        "current_phase": combat.get("current_phase") if combat else None,
        "enemy_hp": combat.get("enemy_hp") if combat else None,
        "winner": winner,
        "message": "Phase 已強制結算，戰鬥繼續",
    })


# ==================== 玩家詳情（JSON API；HTML 頁面仍由 app.py /gm/squad 提供） ====================

@gm_bp.route("/squad/<squad_id>/data")
def gm_get_squad_detail(squad_id):
    denied = _require_gm()
    if denied:
        return denied

    squad = get_squad(squad_id)
    if not squad:
        return jsonify({"success": False, "error": "找不到玩家"}), 404

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        submissions = conn.execute("""
            SELECT task_id, content, photo_path, timestamp
            FROM submissions
            WHERE squad_id = ?
            ORDER BY timestamp DESC
        """, (squad_id,)).fetchall()
    finally:
        conn.close()

    submission_list = []
    for sub in submissions:
        submission_list.append({
            "task_id": sub["task_id"],
            "content": sub["content"],
            "photo_path": normalize_photo_url(sub["photo_path"]),
            "photo_url": photo_public_url(sub["photo_path"]),
            "timestamp": sub["timestamp"],
        })

    return jsonify({
        "success": True,
        "squad": squad,
        "submissions": submission_list,
    })


@gm_bp.route("/reset_pin", methods=["POST"])
def gm_reset_pin():
    denied = _require_gm()
    if denied:
        return denied

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

    update_squad(squad_id, pin=new_pin)
    return jsonify({
        "success": True,
        "message": f"已重置 {squad_id} 的 PIN",
        "new_pin": new_pin,
    })


@gm_bp.route("/adjust", methods=["POST"])
def gm_adjust():
    denied = _require_gm()
    if denied:
        return denied

    squad_id = request.form.get("squad_id")
    field = request.form.get("field")
    value = request.form.get("value")

    if not squad_id or not field or value is None:
        return jsonify({"success": False, "error": "缺少參數"}), 400

    allowed_fields = {"hp", "max_hp", "sanity", "power", "intellect", "resilience", "resources"}
    if field not in allowed_fields:
        return jsonify({"success": False, "error": "無效欄位"}), 400

    if not get_squad(squad_id):
        return jsonify({"success": False, "error": "玩家不存在"}), 404

    try:
        value = int(value)
    except ValueError:
        return jsonify({"success": False, "error": "數值必須為整數"}), 400

    update_squad(squad_id, **{field: value})
    squad = get_squad(squad_id)
    return jsonify({
        "success": True,
        "message": f"{squad_id} 的 {field} 已更新為 {value}",
        "squad": squad,
    })


@gm_bp.route("/download_team_images/<team_id>")
def gm_download_team_images(team_id):
    denied = _require_gm()
    if denied:
        return denied

    clean_id = normalize_team_id(team_id)
    team = get_team_by_id(clean_id)
    if not team:
        return jsonify({"success": False, "error": "找不到該隊伍"}), 404

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT s.id, s.photo_path, s.task_id, sq.display_name, sq.squad_id
            FROM submissions s
            JOIN squads sq ON s.squad_id = sq.squad_id
            WHERE UPPER(TRIM(sq.team_id)) = UPPER(TRIM(?))
              AND s.photo_path IS NOT NULL AND TRIM(s.photo_path) != ''
            ORDER BY s.timestamp
        """, (clean_id,)).fetchall()
    finally:
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


@gm_bp.route("/player_logs/<squad_id>")
def gm_player_logs(squad_id):
    denied = _require_gm()
    if denied:
        return denied

    squad = get_squad(squad_id)
    if not squad:
        return jsonify({"success": False, "error": "找不到玩家"}), 404

    team_info = get_team_by_id(squad.get("team_id")) if squad.get("team_id") else None

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
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
    finally:
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


@gm_bp.route("/reset_game", methods=["POST"])
def gm_reset_game():
    denied = _require_gm()
    if denied:
        return denied

    password = request.form.get("password", "")
    if password != RESET_GAME_PASSWORD:
        return jsonify({"success": False, "error": "密碼錯誤"})

    reset_game_data()
    return jsonify({
        "success": True,
        "message": "遊戲已完全重置（所有玩家ID、Team、提交記錄已清空）",
    })


@gm_bp.route("/clear_all_images", methods=["POST"])
def gm_clear_all_images():
    denied = _require_gm()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    confirm = data.get("confirm", "")
    if confirm != "CLEAR_IMAGES":
        return jsonify({"success": False, "error": "確認碼錯誤"}), 400

    deleted_count, cleared_count = clear_all_submission_images()
    return jsonify({
        "success": True,
        "message": f"已成功刪除 {deleted_count} 張圖片（清空 {cleared_count} 筆提交記錄中的圖片欄位）",
        "deleted_files": deleted_count,
        "cleared_records": cleared_count,
    })


@gm_bp.route("/api/combat_v2", methods=["GET"])
def gm_combat_v2_status():
    denied = _require_gm()
    if denied:
        return denied
    enabled = is_combat_v2_enabled()
    return jsonify({
        "success": True,
        "enabled": enabled,
        "active": combat_v2_active(),
        "message": "戰鬥系統 V2 已開啟" if enabled else "戰鬥系統 V2 已關閉（玩家端顯示維護提示）",
    })


@gm_bp.route("/api/combat_v2", methods=["POST"])
def gm_set_combat_v2():
    denied = _require_gm()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    raw = data.get("enabled")
    if raw is None:
        raw = request.form.get("enabled")
    if isinstance(raw, str):
        raw = raw.strip().lower() in ("1", "true", "yes", "on")
    elif raw is not None:
        raw = bool(raw)
    else:
        return jsonify({"success": False, "error": "請提供 enabled（true/false）"}), 400

    set_combat_v2_enabled(raw)
    return jsonify({
        "success": True,
        "enabled": raw,
        "active": combat_v2_active(),
        "message": "已開啟戰鬥系統 V2" if raw else "已關閉戰鬥系統 V2",
    })


@gm_bp.route("/announcement", methods=["POST"])
def gm_send_announcement():
    denied = _require_gm()
    if denied:
        return denied

    message = request.form.get("message", "").strip()
    if not message:
        return jsonify({"success": False, "error": "訊息不能為空"})

    create_global_event("公告", message, "announcement", 0, "GM")
    return jsonify({"success": True, "message": "公告已發送"})


@gm_bp.route("/team_members/<team_id>")
def gm_team_members(team_id):
    denied = _require_gm()
    if denied:
        return denied

    team = get_team_by_id(team_id)
    if not team:
        return jsonify({"error": "Team 不存在"}), 404

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT squad_id FROM squads WHERE team_id = ? ORDER BY display_name, squad_id",
            (team_id,),
        ).fetchall()
    finally:
        conn.close()

    squad_ids = [row["squad_id"] for row in rows]
    from models.squad import fetch_squads_by_ids

    members_dict = fetch_squads_by_ids(squad_ids)
    members = [members_dict[sid] for sid in squad_ids if members_dict.get(sid)]
    return jsonify({"team": team, "members": members})


@gm_bp.route("/assignable_players")
def gm_assignable_players():
    denied = _require_gm()
    if denied:
        return denied

    target_team_id = normalize_team_id(request.args.get("team_id", ""))

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT squad_id, display_name, team_id
            FROM squads
            ORDER BY COALESCE(display_name, squad_id), squad_id
        """).fetchall()
    finally:
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


@gm_bp.route("/update_team_name", methods=["POST"])
def gm_update_team_name():
    denied = _require_gm()
    if denied:
        return denied

    team_id = request.form.get("team_id", "").strip().upper()
    new_name = request.form.get("new_name", "").strip()

    if not team_id or not new_name:
        return jsonify({"success": False, "error": "參數不完整"}), 400
    if not get_team_by_id(team_id):
        return jsonify({"success": False, "error": "Team 不存在"}), 400

    conn = sqlite3.connect(settings.db_path)
    try:
        c = conn.cursor()
        c.execute("UPDATE teams SET team_name = ? WHERE team_id = ?", (new_name, team_id))
        conn.commit()
    finally:
        conn.close()

    return jsonify({"success": True, "message": "隊名已更新"})


@gm_bp.route("/api/override_trauma_ending", methods=["POST"])
def gm_override_trauma_ending_api():
    """
    [GM 特權網關] 權威人工覆蓋：手動扭轉隊伍創傷數值與結局鎖定狀態。
    寫入專項特權審計日誌，並向全營廣播界線重組事件。
    """
    if not gm_session_valid(session):
        clear_gm_session(session)
        return jsonify({
            "success": False,
            "error": "拒絕存取：缺少 GM 權限憑證",
        }), 403

    body = request.json if request.is_json else {}
    team_id = normalize_team_id(body.get("team_id") or "")
    protagonist_key = (body.get("protagonist_key") or "").strip().lower()

    if not team_id:
        return jsonify({"success": False, "error": "缺少 team_id"}), 400

    target_trauma = body.get("target_trauma")
    target_ending_type = (body.get("target_ending_type") or "").strip().lower() or None

    if target_trauma is not None:
        if protagonist_key not in ("iggy", "marah"):
            return jsonify({
                "success": False,
                "error": "調整創傷必須指定有效的主角 key ('iggy'|'marah')",
            }), 400
        try:
            target_trauma = max(0, int(target_trauma))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "無效的創傷數值"}), 400

    if target_ending_type and target_ending_type not in (
        "clear", "bad_ending", "normal_ending",
    ):
        return jsonify({"success": False, "error": "無效的 target_ending_type"}), 400

    if target_trauma is None and not target_ending_type:
        return jsonify({"success": False, "error": "缺少有效的覆蓋變更指令"}), 400

    now = datetime.now().isoformat()
    raw_operator = (session.get("gm_operator") or session.get("squad_id") or "").strip()
    gm_operator = re.sub(r"[^a-zA-Z0-9_\-]", "", raw_operator)
    if not gm_operator:
        current_app.logger.error(
            "CRITICAL PRIVILEGE VIOLATION: Anonymous or malformed GM operator "
            "bypass attempted from IP %s at %s (raw=%r)",
            request.remote_addr,
            now,
            raw_operator,
        )
        return jsonify({
            "success": False,
            "error": "資安審計攔截：未能識別當前工作人員身分，操作已遭封鎖",
        }), 403

    def _override_tx(conn):
        c = conn.cursor()

        team_exists = c.execute(
            "SELECT 1 FROM teams WHERE team_id = ?",
            (team_id,),
        ).fetchone()
        if not team_exists:
            return False, "找不到指定的隊伍編號"

        log_parts = []

        if target_trauma is not None:
            old_row = c.execute(
                """SELECT trauma_count FROM protagonist_states
                   WHERE team_id = ? AND protagonist = ?""",
                (team_id, protagonist_key),
            ).fetchone()
            old_trauma = int(old_row[0] or 0) if old_row else 0

            c.execute(
                """INSERT INTO protagonist_states
                   (team_id, protagonist, hp, max_hp, sanity, trauma_count, is_active, last_updated)
                   VALUES (?, ?, 100, 100, 100, ?, 1, ?)
                   ON CONFLICT(team_id, protagonist) DO UPDATE SET
                       trauma_count = excluded.trauma_count,
                       last_updated = excluded.last_updated""",
                (team_id, protagonist_key, target_trauma, now),
            )

            c.execute(
                """INSERT INTO protagonist_trauma_log
                   (team_id, protagonist, delta, reason, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    team_id,
                    protagonist_key,
                    target_trauma - old_trauma,
                    f"GM_OVERRIDE_BY_{gm_operator}",
                    now,
                ),
            )
            log_parts.append(
                f"🧠 {protagonist_key} 創傷強制變更: {old_trauma} -> {target_trauma}",
            )

        if target_ending_type:
            if target_ending_type == "clear":
                c.execute(
                    "UPDATE teams SET ending_type = NULL, ending_locked_at = NULL WHERE team_id = ?",
                    (team_id,),
                )
                log_parts.append("🌑 結局鎖定狀態徹底解除重置")
            elif target_ending_type == "bad_ending":
                c.execute(
                    """UPDATE teams SET ending_type = 'bad_ending', ending_locked_at = ?
                       WHERE team_id = ?""",
                    (now, team_id),
                )
                log_parts.append("🌑 強制鎖定為陰影結局 (bad_ending)")
            elif target_ending_type == "normal_ending":
                c.execute(
                    """UPDATE teams SET ending_type = 'normal_ending', ending_locked_at = ?
                       WHERE team_id = ?""",
                    (now, team_id),
                )
                log_parts.append("☀️ 強制鎖定為常規結局 (normal_ending)")

        summary_log = "; ".join(log_parts)
        return True, summary_log

    def _run():
        with immediate_transaction(settings.db_path) as conn:
            return _override_tx(conn)

    success, audit_msg = with_db_retry(_run)

    if not success:
        return jsonify({"success": False, "error": audit_msg}), 400

    create_global_event(
        title=f"🛠️ GM 人工干預：隊伍 [{team_id}] 歷史重組",
        description=(
            f"工作人員 {gm_operator} 啟動特權網關調整該隊邊界：{audit_msg}。"
        ),
        effect_type="announcement",
        effect_value=0,
        created_by=gm_operator,
    )

    return jsonify({
        "success": True,
        "message": f"覆蓋指令發放成功：{audit_msg}",
        "team_id": team_id,
        "timestamp": now,
    })