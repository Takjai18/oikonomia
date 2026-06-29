"""Miscellaneous public API routes."""
import os
import sqlite3

from flask import Blueprint, abort, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename

from data.locations import LOCATIONS
from models.combat import (
    count_team_defenders,
    resolve_player_phase,
    build_combat_round_preview,
    roll_combat_dice,
)
from models.protagonist import build_protagonist_participant
from models.settings import settings
from services.announcements import list_announcements
from utils.app_state import DB_INIT_ERROR
from utils.deploy import player_template_text, read_deploy_version
from utils.helpers import list_image_files, resolve_upload_disk_path
from utils.qr import sign_qr_token
from utils.uploads import save_task_submission_photo

misc_bp = Blueprint("misc", __name__)


@misc_bp.route("/")
def index():
    return render_template("index.html")


@misc_bp.route("/api/version")
def api_version():
    upload_folder = settings.upload_folder
    upload_count = len([
        name for name in os.listdir(upload_folder)
        if os.path.isfile(os.path.join(upload_folder, name))
    ]) if os.path.isdir(upload_folder) else 0
    avatar_dir = settings.avatar_dir
    portrait_dir = settings.portrait_dir
    template_text = player_template_text()
    return jsonify({
        "success": DB_INIT_ERROR is None,
        "version": read_deploy_version(),
        "db_init_error": DB_INIT_ERROR,
        "markers": {
            "iggy_card": "iggy-card",
            "show_only_protagonist": "showOnlyProtagonistCard",
            "combat_system": callable(resolve_player_phase),
            "combat_preview": callable(build_combat_round_preview),
            "combat_modal": "combat-action-modal" in template_text,
            "session_restore_v2": "tryLoginWithStoredSquad" in template_text,
            "settings_modal": "openSettingsModal" in template_text,
            "settings_js_safe": "resetAllSettings" in template_text and ".join('\\n')" in template_text,
            "server_combat_dice": callable(roll_combat_dice),
            "combat_actions_table": True,
            "qr_signed_v2": callable(sign_qr_token),
            "task_photo_validation": callable(save_task_submission_photo),
            "model_layer_phase1": True,
            "model_combat_layer": True,
            "combat_stats_v2": "combatStatValue" in template_text,
            "combat_ui_safe": "safeSetText" in template_text,
            "input_modal": "input-modal-overlay" in template_text,
            "routes_refactored": True,
            "upload_path_hardened": True,
            "defend_team_buff": callable(count_team_defenders),
            "combat_round_continue": "continueCombatAfterRound" in template_text,
            "player_max_hp": "max_hp" in template_text and "DEFAULT_PLAYER_MAX_HP" in template_text,
            "protagonist_combat": callable(build_protagonist_participant),
            "trauma_ending": "combat-result-trauma-badge" in template_text
                and "renderTeamEndingBanner" in template_text,
            "confirm_modal": "confirm-modal-overlay" in template_text
                and "showConfirmModal" in template_text,
            "protagonist_player_control": "protagonist-control-bar" in template_text
                and "controllingProtagonist" in template_text,
            "encounter_logs": "encounter-logs-list" in template_text
                and "loadEncounterLogs" in template_text,
            "enemy_hp_sync_v2": "syncEnemyHpDisplay" in template_text
                and "enemy_hp_after" in template_text,
            "enemy_hp_sync_v3": "resolveAuthoritativeEnemyHp" in template_text
                and "Math.min(...candidates)" in template_text,
            "enemy_hp_sync_v4": "fetchNoCache" in template_text
                and "appendCacheBust" in template_text,
            "enemy_hp_sync_v5": "animateCombatNumber" in template_text
                and "combatUiSnapshotKey" in template_text,
            "enemy_hp_sync_v6": "queueVictoryDuringSettlement" in template_text
                and "X-Requested-With" in template_text,
            "enemy_hp_sync_v7": "syncHpOnlyFromPoll" in template_text,
            "combat_instant_settlement": "combat_instant_settlement" in template_text,
        },
        "db_path": settings.db_path,
        "upload_folder": upload_folder,
        "legacy_upload_folder": settings.legacy_upload_folder,
        "upload_file_count": upload_count,
        "avatar_dir": avatar_dir,
        "avatar_count": len(list_image_files(avatar_dir, exclude=("default.png",))),
        "portrait_dir": portrait_dir,
        "portrait_count": len(list_image_files(portrait_dir, exclude=("default.png",))),
    })


@misc_bp.route("/locations")
def get_locations():
    return jsonify(LOCATIONS)


@misc_bp.route("/global_events")
def get_global_events():
    conn = sqlite3.connect(settings.db_path)
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


@misc_bp.route("/announcements")
def get_announcements():
    return jsonify({"announcements": list_announcements()})


@misc_bp.route("/uploads/<path:filename>")
def serve_upload(filename):
    safe_name = secure_filename(os.path.basename(str(filename or "").replace("\\", "/")))
    if not safe_name:
        abort(404)
    disk_path = resolve_upload_disk_path(safe_name)
    if not disk_path or not os.path.isfile(disk_path):
        abort(404)
    return send_from_directory(os.path.dirname(disk_path), os.path.basename(disk_path))


@misc_bp.route("/debug/teams")
def debug_teams():
    conn = sqlite3.connect(settings.db_path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='teams'")
    exists = c.fetchone() is not None
    count = 0
    if exists:
        count = c.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    conn.close()
    return jsonify({"teams_table_exists": exists, "team_count": count})