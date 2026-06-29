"""Team management routes."""
import sqlite3

from flask import Blueprint, jsonify, request, session

from models.settings import settings
from models.squad import get_all_squads, get_squad, update_squad
from models.team import (
    create_team_with_leader,
    get_next_team_id,
    get_team_by_id,
    get_team_protagonists,
    is_team_leader_session,
    join_squad_to_team,
    official_team_route,
    sync_team_route,
    transfer_team_leadership,
)
from services.player_status import build_player_status
from utils.helpers import normalize_photo_url, normalize_team_id, photo_public_url

team_bp = Blueprint("team", __name__)


@team_bp.route("/team")
def get_team():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401
    return jsonify({"members": get_all_squads()})


@team_bp.route("/my_team")
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
    conn = sqlite3.connect(settings.db_path)
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
    official_route = official_team_route(team)
    team_payload = {**team, "route": official_route}
    return jsonify({
        "success": True,
        "has_team": True,
        "team": team_payload,
        "route": official_route,
        "members": members,
        "is_team_leader": squad.get("is_team_leader", 0),
        "current_squad_id": session["squad_id"],
        "protagonists": protagonists,
    })


@team_bp.route("/available_teams")
def available_teams():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    current_team_id = squad.get("team_id") if squad else None
    has_team = bool(current_team_id and str(current_team_id).strip())
    clean_current_id = normalize_team_id(current_team_id) if has_team else None

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM teams ORDER BY created_at DESC").fetchall()

    teams = []
    for row in rows:
        member_count = conn.execute(
            "SELECT COUNT(*) FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))",
            (row["team_id"],),
        ).fetchone()[0]

        is_joined = bool(
            clean_current_id
            and normalize_team_id(row["team_id"]) == clean_current_id
        )

        official_route = official_team_route(dict(row))
        teams.append({
            "team_id": row["team_id"],
            "team_name": row["team_name"],
            "route": official_route,
            "can_join": bool(official_route),
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


@team_bp.route("/team/join", methods=["POST"])
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

    clean_tid = normalize_team_id(team["team_id"])
    team_route = official_team_route(team)
    if not team_route:
        return jsonify({
            "success": False,
            "error": "該隊尚未選擇路線，暫時無法加入",
        }), 400

    try:
        join_squad_to_team(session["squad_id"], clean_tid, team_route)
    except ValueError:
        return jsonify({"success": False, "error": "你已加入 Team，無法重複加入"}), 400
    except Exception:
        return jsonify({"success": False, "error": "加入失敗，請稍後再試"}), 500

    team = get_team_by_id(clean_tid) or team
    status = build_player_status(get_squad(session["squad_id"]))
    return jsonify({
        "success": True,
        "team": {**team, "route": official_team_route(team)},
        **status,
    })


@team_bp.route("/team/create", methods=["POST"])
def create_player_team():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if squad.get("team_id"):
        return jsonify({"success": False, "error": "你已加入 Team，請先離開現有隊伍"}), 400

    team_name = request.form.get("team_name", "").strip() or "新小隊"
    team_id = get_next_team_id()

    create_team_with_leader(team_id, team_name, session["squad_id"], route=None)
    return jsonify({
        "success": True,
        "team_id": team_id,
        "team_name": team_name,
        "needs_team_route": True,
        "message": "隊伍已建立，請在下方為隊伍選擇路線",
    })


@team_bp.route("/team/update_name", methods=["POST"])
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

    conn = sqlite3.connect(settings.db_path)
    try:
        c = conn.cursor()
        c.execute("UPDATE teams SET team_name = ? WHERE team_id = ?", (new_name, team_id))
        conn.commit()
    except Exception:
        conn.rollback()
        return jsonify({"success": False, "error": "更新失敗，請稍後再試"}), 500
    finally:
        conn.close()

    return jsonify({"success": True, "team_name": new_name})


@team_bp.route("/team/transfer_leadership", methods=["POST"])
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

    try:
        transfer_team_leadership(team_id, target_squad_id)
    except Exception:
        return jsonify({"success": False, "error": "轉讓失敗，請稍後再試"}), 500

    updated = get_squad(session["squad_id"])
    return jsonify({
        "success": True,
        "message": "隊長已成功轉讓",
        "is_team_leader": updated.get("is_team_leader", 0),
    })


@team_bp.route("/team/set_route", methods=["POST"])
def set_team_route():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    data = request.get_json(silent=True) or {}
    team_id = normalize_team_id(data.get("team_id") or "")
    route = (data.get("route") or "").lower()

    if not team_id or route not in ("iggy", "marah"):
        return jsonify({"success": False, "error": "參數錯誤"}), 400

    team = get_team_by_id(team_id)
    if not team:
        return jsonify({"success": False, "error": "隊伍不存在"}), 404

    if not is_team_leader_session(team, session["squad_id"]):
        return jsonify({"success": False, "error": "只有隊長可以設定路線"}), 403

    squad = get_squad(session["squad_id"])
    if normalize_team_id(squad.get("team_id")) != team_id:
        return jsonify({"success": False, "error": "你只能設定自己隊伍的路線"}), 403

    if official_team_route(team):
        return jsonify({"success": False, "error": "隊伍已設定路線，無法更改"}), 400

    sync_team_route(team_id, route)
    updated = get_squad(session["squad_id"])
    status = build_player_status(updated)
    return jsonify({
        "success": True,
        "message": "路線已更新，全隊已同步",
        "route": route,
        **status,
    })


@team_bp.route("/set_team_route_by_leader", methods=["POST"])
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

    sync_team_route(team_id, route)

    updated = get_squad(session["squad_id"])
    status = build_player_status(updated)
    status["squad"] = updated
    return jsonify(status)


@team_bp.route("/set_route", methods=["POST"])
def set_route():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    route = request.form.get("route", "").lower()
    if route not in ("iggy", "marah"):
        return jsonify({"error": "請選擇 Iggy 或 Marah 路線"}), 400

    squad = get_squad(session["squad_id"])
    if squad.get("team_id"):
        return jsonify({
            "error": "已加入隊伍，路線由隊長統一設定；請到 Team 頁面查看",
        }), 400

    if squad.get("route"):
        return jsonify({"error": "你已選擇路線，無法更改"}), 400

    update_squad(session["squad_id"], route=route)
    return jsonify(build_player_status(get_squad(session["squad_id"])))


@team_bp.route("/team_task_logs")
def team_task_logs():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    team_id = squad.get("team_id") if squad else None

    conn = sqlite3.connect(settings.db_path)
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