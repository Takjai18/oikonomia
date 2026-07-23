"""Authentication and onboarding routes."""
import os
import re
import sqlite3
import time
from datetime import datetime

from flask import Blueprint, jsonify, request, session

from models.combat import (
    get_active_combat_for_team,
    get_combat,
    reconcile_finished_active_combat,
)
from models.settings import settings
from models.squad import get_squad, update_squad
from services.player_status import build_player_status
from services.session_auth import attach_restore_token, establish_player_session, verify_restore_token
from utils.db_tx import get_db_connection, immediate_transaction, with_db_retry

auth_bp = Blueprint("auth", __name__)

_AUTH_DYNAMIC_PATHS = frozenset({
    "/login",
    "/session/restore",
    "/set_pin",
    "/allocate_stats",
})

_DYNAMIC_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@auth_bp.after_request
def auth_dynamic_no_cache(response):
    """Prevent Android Chrome from disk-caching session/auth JSON."""
    if request.path in _AUTH_DYNAMIC_PATHS:
        for key, value in _DYNAMIC_NO_CACHE_HEADERS.items():
            response.headers[key] = value
    return response


@auth_bp.route("/login", methods=["POST"])
def login():
    name = request.form.get("squad_id", "").strip()
    input_pin = re.sub(r"\D", "", request.form.get("pin", "").strip())[:4]

    if not name:
        return jsonify({"error": "請輸入名稱"}), 400

    def _login_lookup_and_maybe_create():
        conn = get_db_connection(row_factory=sqlite3.Row)
        try:
            row = conn.execute(
                "SELECT * FROM squads WHERE LOWER(TRIM(display_name)) = LOWER(TRIM(?))",
                (name,),
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT * FROM squads WHERE squad_id = ?",
                    (name,),
                ).fetchone()

            if row:
                stored_pin = str(row["pin"] or "").strip()
                has_pin = len(stored_pin) == 4 and stored_pin.isdigit()

                if has_pin:
                    if not input_pin:
                        return {"require_pin": True, "message": "請輸入 PIN"}
                    if len(input_pin) != 4:
                        return {"success": False, "error": "PIN 必須為 4 位數字"}
                    if input_pin != stored_pin:
                        return {"success": False, "error": "PIN 錯誤"}

                squad_id = row["squad_id"]
            else:
                squad_id = f"PLAYER-{int(time.time() * 1000) % 100000}"
                while get_squad(squad_id):
                    squad_id = f"PLAYER-{(int(time.time() * 1000) + int(time.time() * 1000000) % 9999) % 100000}"

                conn.execute(
                    """INSERT INTO squads
                       (squad_id, display_name, power, intellect, resilience, stats_allocated)
                       VALUES (?, ?, 10, 10, 10, 0)""",
                    (squad_id, name),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM squads WHERE squad_id = ?",
                    (squad_id,),
                ).fetchone()

            establish_player_session(squad_id)
            return {"squad_id": squad_id, "row": row}
        finally:
            conn.close()

    try:
        outcome = with_db_retry(_login_lookup_and_maybe_create)
    except sqlite3.OperationalError:
        return jsonify({
            "success": False,
            "error": "伺服器忙碌，請稍後再試",
        }), 503

    if outcome.get("require_pin"):
        return jsonify({
            "success": False,
            "require_pin": True,
            "message": outcome.get("message", "請輸入 PIN"),
        })
    if outcome.get("success") is False:
        return jsonify(outcome), 400

    squad_id = outcome["squad_id"]
    row = outcome["row"]

    squad = get_squad(squad_id)
    status = build_player_status(squad)
    stored_pin = str(row["pin"] or "").strip()
    has_pin = len(stored_pin) == 4 and stored_pin.isdigit()
    status["require_set_pin"] = not has_pin
    status["has_pin"] = has_pin
    attach_restore_token(status, squad_id)
    return jsonify(status)


@auth_bp.route("/session/restore", methods=["POST"])
def session_restore():
    body = request.json if request.is_json else {}
    token = (body.get("restore_token") or request.form.get("restore_token") or "").strip()
    squad_id = verify_restore_token(token)
    if not squad_id:
        return jsonify({"success": False, "error": "無效或已過期的裝置憑證"}), 401

    squad = get_squad(squad_id)
    if not squad:
        return jsonify({"success": False, "error": "帳號不存在"}), 401

    establish_player_session(squad_id)
    status = build_player_status(squad)
    attach_restore_token(status, squad_id)

    team_id = squad.get("team_id")
    if team_id:
        def _restore_active_combat_hint():
            active_combat = get_active_combat_for_team(team_id)
            if not active_combat:
                return None
            is_live, combat_id, _enc_id = reconcile_finished_active_combat(
                active_combat, team_id=team_id,
            )
            if not is_live or not combat_id:
                return None
            fresh = get_combat(combat_id) or active_combat
            if fresh.get("status") in ("ended",):
                return None
            return combat_id, fresh.get("status")

        hint = with_db_retry(_restore_active_combat_hint)
        if hint:
            status["current_combat_id"] = hint[0]
            status["combat_status_interrupted"] = hint[1]

    return jsonify(status)


@auth_bp.route("/set_pin", methods=["POST"])
def set_pin():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    new_pin = request.form.get("pin", "").strip()

    if not new_pin or len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({"success": False, "error": "請輸入 4 位數字 PIN"}), 400

    update_squad(session["squad_id"], pin=new_pin)

    payload = {"success": True, "message": "PIN 設定成功", "has_pin": True}
    attach_restore_token(payload, session["squad_id"])
    return jsonify(payload)


@auth_bp.route("/allocate_stats", methods=["POST"])
def allocate_stats():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"success": False, "error": "玩家不存在"}), 404

    if squad.get("stats_allocated"):
        return jsonify({"success": False, "error": "你已經分配過能力值"}), 400

    data = request.json or {}
    try:
        power = int(data.get("power", 10))
        resilience = int(data.get("resilience", 10))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "數值格式錯誤"}), 400

    if power < 10 or resilience < 10:
        return jsonify({"success": False, "error": "每項屬性最少要有 10 點"}), 400

    # Intellect retired: free points only go to power + resilience.
    total_free = (power - 10) + (resilience - 10)
    if total_free != 30:
        return jsonify({"success": False, "error": "必須剛好使用 30 點自由點數（力量／韌性）"}), 400

    from utils.helpers import resolve_player_pick_avatar

    stored_avatar, _path = resolve_player_pick_avatar(data.get("avatar") or "")
    if not stored_avatar:
        return jsonify({
            "success": False,
            "error": "請選擇可用頭像（僅限玩家頭像庫）",
        }), 400

    squad_id = session["squad_id"]

    from utils.stats_formulas import max_hp_from_resilience

    # Resilience also sets max HP (and starting HP) at character create.
    max_hp = max_hp_from_resilience(resilience)
    hp = max_hp

    def _write_allocation():
        with immediate_transaction() as conn:
            conn.execute(
                """UPDATE squads
                   SET power = ?, intellect = 10, resilience = ?,
                       max_hp = ?, hp = ?,
                       avatar = ?, stats_allocated = 1, last_update = ?
                   WHERE squad_id = ?""",
                (
                    power,
                    resilience,
                    max_hp,
                    hp,
                    stored_avatar,
                    datetime.now().isoformat(),
                    squad_id,
                ),
            )

    try:
        with_db_retry(_write_allocation)
    except sqlite3.OperationalError:
        return jsonify({
            "success": False,
            "error": "伺服器忙碌，請再點一次「確認分配」",
        }), 503

    squad = get_squad(squad_id)
    status = build_player_status(squad)
    attach_restore_token(status, session["squad_id"])
    return jsonify({"success": True, "message": "能力值分配成功", **status})