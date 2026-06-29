"""Encounter listing and detail routes."""
import os

from flask import Blueprint, jsonify, session

from models.combat import get_active_combat_for_team, get_combat_by_squad
from models.settings import settings
from models.encounter import (
    encounter_is_practice,
    encounter_is_replayable,
    encounter_route_matches,
    encounter_visible_to_player,
    load_all_encounters,
    load_encounter,
)
from models.encounter_outcomes import encounter_already_completed, get_team_encounter_logs
from models.squad import get_squad
from services.story import count_team_distinct_tasks, resolve_story_stage

encounters_bp = Blueprint("encounters", __name__)


@encounters_bp.route("/encounters")
def list_encounters_api():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"error": "玩家不存在"}), 404

    team_id = squad.get("team_id")
    route = squad.get("route")
    completed_count, completed_task_ids = count_team_distinct_tasks(
        session["squad_id"], team_id
    )
    stage = resolve_story_stage(completed_count, completed_task_ids)
    if team_id:
        active_session = get_active_combat_for_team(team_id)
    else:
        active_session = get_combat_by_squad(session["squad_id"])

    show_test = (
        session.get("is_gm")
        or os.environ.get("OIKONOMIA_SHOW_TEST_ENCOUNTERS", "").lower() in ("1", "true", "yes")
    )
    encounters = []
    for enc in load_all_encounters():
        if not encounter_visible_to_player(enc, show_test=show_test):
            continue
        if not encounter_route_matches(enc.get("route"), route):
            continue
        if enc.get("story_stage", 0) > stage:
            continue
        completed = encounter_already_completed(team_id, enc["encounter_id"]) if team_id else False
        replayable = encounter_is_replayable(enc)
        encounters.append({
            "encounter_id": enc["encounter_id"],
            "title": enc.get("title"),
            "description": enc.get("description"),
            "location_hint": enc.get("location_hint"),
            "story_stage": enc.get("story_stage"),
            "trigger_type": enc.get("trigger_type"),
            "completed": completed and not replayable,
            "replayable": replayable,
            "is_practice": encounter_is_practice(enc),
            "enemy_name": (enc.get("enemy") or {}).get("name"),
            "enemy_hp": (enc.get("enemy") or {}).get("hp"),
        })

    thresholds = settings.story_stage_thresholds or {}
    next_stage = None
    tasks_needed = None
    for target_stage in sorted(thresholds.keys()):
        if target_stage > stage:
            next_stage = target_stage
            tasks_needed = max(0, int(thresholds[target_stage]) - completed_count)
            break

    if not route:
        progress_hint = "請先由隊長在儀表板選擇 Iggy 或 Marah 路線，先會見到對應遭遇戰。"
    elif not encounters:
        if tasks_needed:
            progress_hint = (
                f"故事階段 {stage}：完成多 {tasks_needed} 個探索任務，"
                f"升至階段 {next_stage} 後會解鎖更多遭遇戰。"
            )
        else:
            progress_hint = "暫無符合你路線同故事階段嘅遭遇戰。"
    else:
        practice_count = sum(1 for e in encounters if e.get("is_practice"))
        story_count = len(encounters) - practice_count
        if story_count and practice_count:
            progress_hint = (
                f"故事階段 {stage}：{story_count} 場劇情戰 + {practice_count} 場練習戰"
                "（練習可重複挑戰，唔使開新角色）。"
            )
        elif practice_count:
            progress_hint = f"已解鎖 {practice_count} 場練習戰（可無限重複，方便測試戰鬥）。"
        elif len(encounters) == 1:
            progress_hint = (
                f"故事階段 {stage}：目前解鎖 1 場劇情遭遇戰；"
                "下方練習戰可重複測試戰鬥。"
            )
        else:
            progress_hint = f"故事階段 {stage}：已解鎖 {len(encounters)} 場遭遇戰。"

    encounters.sort(
        key=lambda e: (
            1 if e.get("is_practice") else 0,
            e.get("story_stage") or 0,
            e.get("encounter_id") or "",
        )
    )

    return jsonify({
        "success": True,
        "encounters": encounters,
        "player_story_stage": stage,
        "route": route,
        "completed_task_count": completed_count,
        "progress_hint": progress_hint,
        "active_combat": bool(active_session),
        "active_combat_id": active_session["id"] if active_session else None,
        "active_encounter_id": active_session["encounter_id"] if active_session else None,
    })


@encounters_bp.route("/encounters/<encounter_id>")
def get_encounter_api(encounter_id):
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    encounter = load_encounter(encounter_id)
    if not encounter:
        return jsonify({"error": "Encounter 不存在"}), 404

    squad = get_squad(session["squad_id"])
    team_id = squad.get("team_id") if squad else None
    return jsonify({
        "success": True,
        "encounter": {
            "encounter_id": encounter["encounter_id"],
            "title": encounter.get("title"),
            "description": encounter.get("description"),
            "location_hint": encounter.get("location_hint"),
            "enemy": encounter.get("enemy"),
            "combat_settings": encounter.get("combat_settings"),
            "reflection_prompt": encounter.get("reflection_prompt"),
            "completed": encounter_already_completed(team_id, encounter_id) if team_id else False,
        },
    })


@encounters_bp.route("/encounter_logs")
def encounter_logs_api():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"error": "玩家不存在"}), 404

    team_id = squad.get("team_id")
    if not team_id:
        return jsonify({
            "success": True,
            "has_team": False,
            "logs": [],
        })

    return jsonify({
        "success": True,
        "has_team": True,
        "logs": get_team_encounter_logs(team_id),
    })


@encounters_bp.route("/encounters/<encounter_id>/start", methods=["POST"])
def start_encounter_api(encounter_id):
    """Legacy alias → POST /combat/start"""
    from routes.combat import combat_start_api
    return combat_start_api(encounter_id=encounter_id)