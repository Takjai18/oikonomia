"""Player-facing API routes."""
import json
import math
import os
import sqlite3
from datetime import datetime

from flask import Blueprint, jsonify, request, session

from data.locations import LOCATIONS
from models.settings import settings
from models.squad import get_squad, update_squad
from services.player_status import build_player_status, reconcile_status_combat_fields
from services.session_auth import attach_restore_token
from services.story import (
    count_team_distinct_tasks,
    get_pending_story_id,
    resolve_story_stage,
)
from utils.helpers import (
    list_image_files,
    list_player_pick_avatars,
    normalize_photo_url,
    photo_public_url,
    resolve_player_pick_avatar,
    PLAYER_AVATAR_SUBDIR,
)
from utils.uploads import save_task_submission_audio, save_task_submission_photo

player_bp = Blueprint("player", __name__)

_DYNAMIC_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@player_bp.after_request
def player_dynamic_no_cache(response):
    if request.path in ("/status", "/my_team"):
        for key, value in _DYNAMIC_NO_CACHE_HEADERS.items():
            response.headers[key] = value
    return response


@player_bp.route("/submit_task", methods=["POST"])
def submit_task():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    task_id = (request.form.get("task_id") or "").strip()
    content = request.form.get("content", "")

    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"error": "未登入"}), 401

    team_id = squad.get("team_id")
    if not team_id:
        return jsonify({"error": "你未加入任何 Team，無法提交任務"}), 400

    if not task_id or task_id not in LOCATIONS:
        return jsonify({"success": False, "error": "無效任務"}), 400

    from services.progression import is_task_unlocked, task_lock_reason, grant_task_story_unlocks

    if not is_task_unlocked(squad, task_id):
        return jsonify({
            "success": False,
            "error": task_lock_reason(squad, task_id) or "此任務尚未解鎖（請先完成前置劇情）",
        }), 403

    loc = LOCATIONS[task_id]
    task_type = loc.get("task_type") or ""

    def _normalize_answer(raw, mode=None, aliases=None):
        s = str(raw or "").strip()
        if mode == "digits":
            return "".join(ch for ch in s if ch.isdigit())
        s_low = s.lower().replace(" ", "")
        if aliases:
            for a in aliases:
                if s_low == str(a).lower().replace(" ", ""):
                    return str(aliases[0]).lower().replace(" ", "") if aliases else s_low
        return s_low

    # Quiz: verify answer; optional one team-wide attempt.
    if task_type == "quiz":
        expected = _normalize_answer(
            loc.get("answer"),
            mode=loc.get("answer_normalize"),
            aliases=loc.get("answer_aliases"),
        )
        given = _normalize_answer(
            content,
            mode=loc.get("answer_normalize"),
            aliases=loc.get("answer_aliases"),
        )
        # Treat aliases as match if equal to expected after normalize via aliases
        aliases = loc.get("answer_aliases") or [loc.get("answer")]
        alias_norms = {
            _normalize_answer(a, mode=loc.get("answer_normalize"))
            for a in aliases
        }
        correct = given == expected or given in alias_norms

        conn_chk = sqlite3.connect(settings.db_path)
        try:
            rows = conn_chk.execute(
                """SELECT content FROM submissions
                   WHERE task_id = ? AND squad_id IN (
                       SELECT squad_id FROM squads WHERE team_id = ?
                   )""",
                (task_id, team_id),
            ).fetchall()
        finally:
            conn_chk.close()
        prior = [str(r[0] or "") for r in rows]
        if any(p.startswith("CORRECT:") or p == "CORRECT" for p in prior):
            return jsonify({
                "success": True,
                "message": "此題目已答對過，無需再交",
            })
        if loc.get("one_team_attempt", True) and any(
            p.startswith("WRONG:") for p in prior
        ):
            return jsonify({
                "success": False,
                "error": "全組已用盡唯一作答機會（答案錯誤）。請聯絡 GM。",
            }), 403
        if not correct:
            # Record failed attempt (counts as team submission for one-shot)
            conn_w = sqlite3.connect(settings.db_path)
            try:
                conn_w.execute(
                    """INSERT INTO submissions (squad_id, task_id, content, photo_path, timestamp)
                       VALUES (?, ?, ?, NULL, ?)""",
                    (
                        session["squad_id"],
                        task_id,
                        f"WRONG:{content}",
                        datetime.now().isoformat(),
                    ),
                )
                conn_w.commit()
            finally:
                conn_w.close()
            return jsonify({
                "success": False,
                "error": "答案不正確" + (
                    "——全組機會已用盡" if loc.get("one_team_attempt", True) else ""
                ),
            }), 400
        # Force content marker for correct completion
        content = f"CORRECT:{content}"

    # Minigame: client must report a win for the expected gameId.
    minigame_payload = None
    if task_type == "minigame":
        try:
            minigame_payload = json.loads(content) if content else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return jsonify({"success": False, "error": "小遊戲結果格式錯誤"}), 400
        if not isinstance(minigame_payload, dict):
            return jsonify({"success": False, "error": "小遊戲結果格式錯誤"}), 400
        expected_game = loc.get("minigame_id")
        if minigame_payload.get("result") != "win" or (
            expected_game and minigame_payload.get("gameId") != expected_game
        ):
            return jsonify({"success": False, "error": "小遊戲尚未過關"}), 400
        # Team-synced games must finish as a squad session win.
        if expected_game in ("flash_memory", "mastermind", "memory_match", "whack_a_mole"):
            try:
                from services.team_minigame import is_session_won
                if not is_session_won(team_id, task_id):
                    return jsonify({
                        "success": False,
                        "error": "全隊尚未完成此同步遊戲（請全隊一起通關）",
                    }), 400
            except Exception:
                return jsonify({
                    "success": False,
                    "error": "無法驗證全隊遊戲狀態，請重試",
                }), 400

    requires_team_photo = task_type == "gps"
    requires_audio = (
        task_type == "minigame" and loc.get("minigame_id") == "voice_record"
    )

    photo_path = None
    photo = request.files.get("photo") if "photo" in request.files else None
    if photo and photo.filename:
        upload_result = save_task_submission_photo(photo, session["squad_id"])
        if not upload_result["ok"]:
            return jsonify({
                "success": False,
                "error": upload_result["error"],
            }), upload_result["status"]
        photo_path = upload_result["photo_path"]

    audio = request.files.get("audio") if "audio" in request.files else None
    if audio and audio.filename:
        audio_result = save_task_submission_audio(audio, session["squad_id"])
        if not audio_result["ok"]:
            return jsonify({
                "success": False,
                "error": audio_result["error"],
            }), audio_result["status"]
        # Reuse photo_path column for media attachment path (audio or photo).
        photo_path = audio_result["audio_path"]

    # GPS 任務：定位之外必須影相（相片需有所有組員樣子，作現場證明）
    if requires_team_photo and not photo_path:
        return jsonify({
            "success": False,
            "error": "GPS 任務必須上傳相片。由於定位有時唔準，相片需清楚顯示所有組員樣子，以確認大家到現場。",
        }), 400

    if requires_audio and not photo_path:
        return jsonify({
            "success": False,
            "error": "錄音任務必須上載錄音檔",
        }), 400

    conn = sqlite3.connect(settings.db_path)
    try:
        c = conn.cursor()
        c.execute("""
            SELECT id, content FROM submissions
            WHERE task_id = ? AND squad_id IN (
                SELECT squad_id FROM squads WHERE team_id = ?
            )
        """, (task_id, team_id))
        prior_rows = c.fetchall()
        if task_type == "quiz":
            already_submitted = any(
                str(r[1] or "").startswith("CORRECT") for r in prior_rows
            )
        else:
            already_submitted = bool(prior_rows)

        if already_submitted and task_type == "quiz":
            return jsonify({
                "success": True,
                "message": "此題目已答對過，無需再交",
            })

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
            # First completion of a task: restore 10% max HP for the whole party.
            try:
                from models.squad import restore_party_hp_percent
                restore_party_hp_percent(
                    team_id=team_id,
                    starter_id=session["squad_id"],
                    percent=10,
                    include_protagonist=True,
                )
            except Exception:
                pass
            # Mission stat rewards: player pending points + Iggy random
            stat_reward = int(loc.get("stat_points_reward") or 0)
            reward_meta = None
            if stat_reward > 0 and team_id:
                try:
                    from services.stat_rewards import grant_mission_stat_rewards
                    reward_meta = grant_mission_stat_rewards(
                        team_id, stat_reward, protagonist_key="iggy",
                    )
                except Exception:
                    reward_meta = None
            squad = get_squad(session["squad_id"])
            new_count, new_tasks = count_team_distinct_tasks(session["squad_id"], team_id)
            old_stage = resolve_story_stage(old_count, old_tasks)
            new_stage = resolve_story_stage(new_count, new_tasks)
            # Progressive: task completion may queue the next story beat (not whole act).
            unlock_story = grant_task_story_unlocks(squad, task_id)
            # Iggy grows with mainline completions
            try:
                from models.protagonist import sync_protagonist_growth
                if team_id:
                    sync_protagonist_growth(team_id)
            except Exception:
                pass
            pending_story_id = None
            next_step = None
            pending_stat_points = 0
            if squad:
                pending_story_id = get_pending_story_id(squad) or unlock_story
                try:
                    from services.progression import get_next_mainline_step
                    next_step = get_next_mainline_step(squad, prefer_story=True)
                except Exception:
                    next_step = None
                try:
                    from services.stat_rewards import get_pending_points
                    pending_stat_points = get_pending_points(session["squad_id"])
                except Exception:
                    pending_stat_points = 0
            msg = "任務提交成功！+6 神智 +1 Resource，全隊回復 10% 生命值"
            if stat_reward > 0:
                msg += f"；全隊獲得 {stat_reward} 點可分配能力（Iggy 已隨機提升）"
            if loc.get("reward_hint"):
                msg += f"。提示：{loc['reward_hint']}"
            return jsonify({
                "success": True,
                "message": msg,
                "pending_story_id": pending_story_id,
                "next_step": next_step,
                "stage": new_stage,
                "stage_advanced": new_stage > old_stage,
                "stat_points_reward": stat_reward,
                "pending_stat_points": pending_stat_points,
                "reward_hint": loc.get("reward_hint"),
                "stat_reward_meta": reward_meta,
            })
        return jsonify({
            "success": True,
            "message": "提交已記錄，但呢個任務已經計過分（只計一次）",
        })
    finally:
        conn.close()


@player_bp.route("/allocate_stats", methods=["POST"])
def allocate_stats():
    """Spend pending mission stat points (power / resilience / sanity / max_hp)."""
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401
    body = request.json if request.is_json else request.form
    alloc = {
        "power": body.get("power") or 0,
        "resilience": body.get("resilience") or 0,
        "sanity": body.get("sanity") or 0,
        "max_hp": body.get("max_hp") or 0,
    }
    from services.stat_rewards import spend_pending_points
    result = spend_pending_points(session["squad_id"], alloc)
    code = 200 if result.get("success") else 400
    return jsonify(result), code


@player_bp.route("/status")
def get_status():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if not squad:
        session.clear()
        return jsonify({"success": False, "error": "未登入"}), 401

    status = build_player_status(squad)
    try:
        from services.stat_rewards import get_pending_points
        status["pending_stat_points"] = get_pending_points(session["squad_id"])
    except Exception:
        status["pending_stat_points"] = 0
    combat_id, combat_status = reconcile_status_combat_fields(squad)
    if combat_id:
        status["current_combat_id"] = combat_id
        if combat_status:
            status["combat_status_interrupted"] = combat_status
    else:
        status["current_combat_id"] = None
        status.pop("combat_status_interrupted", None)

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
    """Player pick list: only static/avatars/new avatars for players/."""
    basenames = list_player_pick_avatars()
    # Return relative paths under /static/avatars/ for storage + display
    avatars = [f"{PLAYER_AVATAR_SUBDIR}/{name}" for name in basenames]
    return jsonify({
        "avatars": avatars,
        "avatar_subdir": PLAYER_AVATAR_SUBDIR,
        "avatar_dir": settings.avatar_dir,
    })


@player_bp.route("/available_portraits")
def available_portraits():
    portrait_dir = settings.portrait_dir
    files = list_image_files(portrait_dir, exclude=("default.png",))
    return jsonify({"portraits": files, "portrait_dir": portrait_dir})


@player_bp.route("/set_avatar", methods=["POST"])
def set_avatar():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    stored, _path = resolve_player_pick_avatar(request.form.get("avatar", ""))
    if not stored:
        return jsonify({
            "success": False,
            "error": "請選擇可用頭像（僅限玩家頭像庫）",
        }), 400

    update_squad(session["squad_id"], avatar=stored)
    return jsonify({"success": True, "avatar": stored})


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