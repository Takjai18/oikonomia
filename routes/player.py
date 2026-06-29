"""Player-facing API routes."""
import math
import os
import sqlite3
from datetime import datetime

from flask import Blueprint, jsonify, request, session

from data.locations import LOCATIONS
from models.settings import settings
from models.squad import get_squad, update_squad
from services.player_status import build_player_status
from services.session_auth import attach_restore_token
from services.story import (
    count_team_distinct_tasks,
    get_pending_story_id,
    resolve_story_stage,
)
from utils.helpers import list_image_files, normalize_photo_url, photo_public_url
from utils.uploads import save_task_submission_photo

player_bp = Blueprint("player", __name__)


@player_bp.route("/submit_task", methods=["POST"])
def submit_task():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    task_id = request.form.get("task_id", "unknown")
    content = request.form.get("content", "")

    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"error": "未登入"}), 401

    team_id = squad.get("team_id")
    if not team_id:
        return jsonify({"error": "你未加入任何 Team，無法提交任務"}), 400

    conn = sqlite3.connect(settings.db_path)
    try:
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
                upload_result = save_task_submission_photo(photo, session["squad_id"])
                if not upload_result["ok"]:
                    return jsonify({
                        "success": False,
                        "error": upload_result["error"],
                    }), upload_result["status"]
                photo_path = upload_result["photo_path"]

        c.execute(
            """INSERT INTO submissions (squad_id, task_id, content, photo_path, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (session["squad_id"], task_id, content, photo_path, datetime.now().isoformat()),
        )
        conn.commit()

        if not already_submitted:
            old_count, old_tasks = count_team_distinct_tasks(session["squad_id"], team_id)
            new_sanity = min(100, squad["sanity"] + 6)
            new_resources = squad["resources"] + 1
            update_squad(session["squad_id"], sanity=new_sanity, resources=new_resources)
            squad = get_squad(session["squad_id"])
            new_count, new_tasks = count_team_distinct_tasks(session["squad_id"], team_id)
            old_stage = resolve_story_stage(old_count, old_tasks)
            new_stage = resolve_story_stage(new_count, new_tasks)
            pending_story_id = None
            if new_stage > old_stage and squad:
                pending_story_id = get_pending_story_id(squad)
            return jsonify({
                "success": True,
                "message": "任務提交成功！+6 神智 +1 Resource（第一次提交）",
                "pending_story_id": pending_story_id,
                "stage": new_stage,
            })
        return jsonify({
            "success": True,
            "message": "提交已記錄，但呢個任務已經計過分（只計一次）",
        })
    finally:
        conn.close()


@player_bp.route("/status")
def get_status():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if not squad:
        session.clear()
        return jsonify({"success": False, "error": "未登入"}), 401

    status = build_player_status(squad)
    attach_restore_token(status, session["squad_id"])
    return jsonify(status)


@player_bp.route("/my_submissions")
def my_submissions():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    conn = sqlite3.connect(settings.db_path)
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


@player_bp.route("/verify_gps", methods=["POST"])
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
            "loc_name": loc["name"],
        })
    return jsonify({
        "success": False,
        "message": f"距離太遠（相差約 {int(distance)} 米）",
    })


@player_bp.route("/available_avatars")
def available_avatars():
    avatar_dir = settings.avatar_dir
    files = list_image_files(avatar_dir, exclude=("default.png",))
    return jsonify({"avatars": files, "avatar_dir": avatar_dir})


@player_bp.route("/available_portraits")
def available_portraits():
    portrait_dir = settings.portrait_dir
    files = list_image_files(portrait_dir, exclude=("default.png",))
    return jsonify({"portraits": files, "portrait_dir": portrait_dir})


@player_bp.route("/set_avatar", methods=["POST"])
def set_avatar():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    avatar_filename = os.path.basename(request.form.get("avatar", "").strip())
    if not avatar_filename:
        return jsonify({"success": False, "error": "請選擇頭像"}), 400

    avatar_path = os.path.join(settings.avatar_dir, avatar_filename)
    if not os.path.exists(avatar_path):
        return jsonify({"success": False, "error": "頭像不存在"}), 400

    update_squad(session["squad_id"], avatar=avatar_filename)
    return jsonify({"success": True, "avatar": avatar_filename})


@player_bp.route("/update_display_name", methods=["POST"])
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