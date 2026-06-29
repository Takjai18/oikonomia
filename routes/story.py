"""Story / narrative API routes."""
from flask import Blueprint, jsonify, session

from data.narrative_stories import NARRATIVE_STORIES
from data.story_config import STORY_STAGE_THRESHOLDS
from models.squad import get_squad
from services.narrative import (
    enrich_story_lines,
    get_available_narrative_stories,
    get_story_for_route,
    next_stage_threshold,
)
from services.story import (
    count_team_distinct_tasks,
    get_pending_story_id,
    is_story_viewed,
    mark_story_viewed,
    resolve_story_stage,
)

story_bp = Blueprint("story", __name__)


@story_bp.route("/story_progress")
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

    pending_story_id = get_pending_story_id(squad)
    narrative_stories = get_available_narrative_stories(squad)

    return jsonify({
        "stage": stage,
        "completed_tasks": completed_count,
        "route": route,
        "next_stage_at": next_stage_threshold(stage),
        "stage_thresholds": STORY_STAGE_THRESHOLDS,
        "story": story,
        "pending_story_id": pending_story_id,
        "narrative_stories": narrative_stories,
    })


@story_bp.route("/api/story/<story_id>")
def api_get_story(story_id):
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    story = NARRATIVE_STORIES.get(story_id)
    if not story:
        return jsonify({"error": "劇情不存在"}), 404

    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"error": "玩家不存在"}), 404

    story_route = story.get("route")
    if story_route and squad.get("route") != story_route:
        return jsonify({"error": "此劇情不適用於你目前的路線"}), 403

    if story.get("min_stage") is not None and story_route:
        completed_count, completed_task_ids = count_team_distinct_tasks(
            session["squad_id"], squad.get("team_id")
        )
        stage = resolve_story_stage(completed_count, completed_task_ids)
        if story.get("min_stage", 0) > stage:
            return jsonify({"error": "故事階段未解鎖"}), 403

    payload = enrich_story_lines(story)
    payload["viewed"] = is_story_viewed(session["squad_id"], story_id)
    payload["skippable"] = story.get("skippable", True)
    return jsonify({"success": True, **payload})


@story_bp.route("/api/story/<story_id>/complete", methods=["POST"])
def api_complete_story(story_id):
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    if story_id not in NARRATIVE_STORIES:
        return jsonify({"error": "劇情不存在"}), 404

    mark_story_viewed(session["squad_id"], story_id)
    return jsonify({"success": True, "story_id": story_id})


@story_bp.route("/api/story/pending")
def api_pending_story():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"error": "玩家不存在"}), 404

    pending_id = get_pending_story_id(squad)
    if not pending_id:
        return jsonify({"success": True, "pending_story_id": None})

    story = enrich_story_lines(NARRATIVE_STORIES[pending_id])
    return jsonify({
        "success": True,
        "pending_story_id": pending_id,
        "story": story,
    })