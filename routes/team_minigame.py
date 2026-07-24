"""Team minigame API (flash_memory + mastermind)."""
from flask import Blueprint, jsonify, request, session

from data.locations import LOCATIONS
from models.squad import get_squad
from services import team_minigame as tmg
from services.progression import is_task_unlocked, task_lock_reason

team_minigame_bp = Blueprint("team_minigame", __name__)


def _require_player():
    if "squad_id" not in session:
        return None, (jsonify({"success": False, "error": "未登入"}), 401)
    squad = get_squad(session["squad_id"])
    if not squad:
        return None, (jsonify({"success": False, "error": "未登入"}), 401)
    if not squad.get("team_id"):
        return None, (jsonify({"success": False, "error": "請先加入隊伍"}), 400)
    return squad, None


def _task_game(task_id: str):
    loc = LOCATIONS.get(task_id) or {}
    return loc.get("minigame_id"), loc.get("minigame_config") or {}, loc


@team_minigame_bp.route("/api/team_minigame/join", methods=["POST"])
def api_join():
    squad, err = _require_player()
    if err:
        return err
    body = request.json if request.is_json else request.form
    task_id = (body.get("task_id") or "").strip()
    if task_id not in LOCATIONS:
        return jsonify({"success": False, "error": "無效任務"}), 400
    if not is_task_unlocked(squad, task_id):
        return jsonify({
            "success": False,
            "error": task_lock_reason(squad, task_id) or "任務未解鎖",
        }), 403
    game_id, config, _loc = _task_game(task_id)
    if game_id not in ("flash_memory", "mastermind", "memory_match", "whack_a_mole"):
        return jsonify({"success": False, "error": "此任務不支援全隊同步"}), 400
    try:
        status = tmg.join_session(
            squad["team_id"], task_id, game_id, session["squad_id"], config=config,
        )
        return jsonify(status)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@team_minigame_bp.route("/api/team_minigame/status")
def api_status():
    squad, err = _require_player()
    if err:
        return err
    task_id = (request.args.get("task_id") or "").strip()
    if not task_id:
        return jsonify({"success": False, "error": "缺少 task_id"}), 400
    try:
        status = tmg.poll_status(squad["team_id"], task_id, session["squad_id"])
        return jsonify(status)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@team_minigame_bp.route("/api/team_minigame/start", methods=["POST"])
def api_start():
    squad, err = _require_player()
    if err:
        return err
    body = request.json if request.is_json else request.form
    task_id = (body.get("task_id") or "").strip()
    try:
        status = tmg.start_session(squad["team_id"], task_id, session["squad_id"])
        return jsonify(status)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@team_minigame_bp.route("/api/team_minigame/flash_answer", methods=["POST"])
def api_flash_answer():
    squad, err = _require_player()
    if err:
        return err
    body = request.json if request.is_json else request.form
    task_id = (body.get("task_id") or "").strip()
    answer = body.get("answer") or ""
    try:
        status = tmg.submit_flash_answer(
            squad["team_id"], task_id, session["squad_id"], answer,
        )
        return jsonify(status)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@team_minigame_bp.route("/api/team_minigame/mastermind_guess", methods=["POST"])
def api_mastermind_guess():
    squad, err = _require_player()
    if err:
        return err
    body = request.json if request.is_json else {}
    task_id = (body.get("task_id") or "").strip()
    guess = body.get("guess") or []
    if not isinstance(guess, list):
        return jsonify({"success": False, "error": "guess 必須是陣列"}), 400
    try:
        status = tmg.submit_mastermind_guess(
            squad["team_id"], task_id, session["squad_id"], guess,
        )
        return jsonify(status)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@team_minigame_bp.route("/api/team_minigame/memory_wave", methods=["POST"])
def api_memory_wave():
    """Report completion (or fail) of one memory-match wave (1–3)."""
    squad, err = _require_player()
    if err:
        return err
    body = request.json if request.is_json else {}
    task_id = (body.get("task_id") or "").strip()
    wave = body.get("wave")
    success = bool(body.get("success"))
    try:
        status = tmg.report_memory_wave(
            squad["team_id"], task_id, session["squad_id"], wave, success,
        )
        return jsonify(status)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@team_minigame_bp.route("/api/team_minigame/whack_result", methods=["POST"])
def api_whack_result():
    """Report whack-a-mole run result (hits within time limit)."""
    squad, err = _require_player()
    if err:
        return err
    body = request.json if request.is_json else {}
    task_id = (body.get("task_id") or "").strip()
    hits = body.get("hits")
    success = bool(body.get("success"))
    try:
        status = tmg.report_whack_result(
            squad["team_id"], task_id, session["squad_id"], hits, success,
        )
        return jsonify(status)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@team_minigame_bp.route("/api/team_minigame/reset", methods=["POST"])
def api_reset():
    squad, err = _require_player()
    if err:
        return err
    body = request.json if request.is_json else request.form
    task_id = (body.get("task_id") or "").strip()
    game_id, config, _ = _task_game(task_id)
    if game_id not in ("flash_memory", "mastermind", "memory_match", "whack_a_mole"):
        return jsonify({"success": False, "error": "無效遊戲"}), 400
    tmg.reset_session(squad["team_id"], task_id, game_id, config)
    status = tmg.join_session(
        squad["team_id"], task_id, game_id, session["squad_id"], config=config,
    )
    return jsonify(status)
