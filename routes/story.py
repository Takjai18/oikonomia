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
    squad_can_access_story,
)
from services.story import (
    count_team_distinct_tasks,
    get_pending_story_id,
    get_viewed_story_ids,
    is_story_viewed,
    mark_story_viewed,
    resolve_story_stage,
    clear_story_unlock,
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

    if not squad_can_access_story(squad, story_id, story):
        return jsonify({"error": "此劇情尚未解鎖（請先完成前置任務／戰鬥）"}), 403

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
    try:
        clear_story_unlock(session["squad_id"], story_id)
    except Exception:
        pass

    next_step = None
    squad = get_squad(session["squad_id"])
    if squad:
        try:
            from services.progression import get_next_mainline_step
            next_step = get_next_mainline_step(squad, prefer_story=True)
        except Exception:
            next_step = None

    return jsonify({
        "success": True,
        "story_id": story_id,
        "next_step": next_step,
        "pending_story_id": (next_step or {}).get("story_id")
        if (next_step or {}).get("type") == "story"
        else None,
    })


@story_bp.route("/api/story/views")
def api_story_views():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    return jsonify({
        "success": True,
        "viewed_story_ids": get_viewed_story_ids(session["squad_id"]),
    })


@story_bp.route("/api/story/pending")
def api_pending_story():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"error": "玩家不存在"}), 404

    pending_id = get_pending_story_id(squad)
    next_step = None
    try:
        from services.progression import get_next_mainline_step
        next_step = get_next_mainline_step(squad, prefer_story=True)
    except Exception:
        next_step = None

    if not pending_id:
        return jsonify({
            "success": True,
            "pending_story_id": None,
            "next_step": next_step,
        })

    story = enrich_story_lines(NARRATIVE_STORIES[pending_id])
    return jsonify({
        "success": True,
        "pending_story_id": pending_id,
        "story": story,
        "next_step": next_step,
    })


@story_bp.route("/api/mainline/next")
def api_mainline_next():
    """Next mainline beat after story/task/combat — for auto-guide UI."""
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401
    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"error": "玩家不存在"}), 404
    from services.progression import get_next_mainline_step
    step = get_next_mainline_step(squad, prefer_story=True)
    return jsonify({"success": True, "next_step": step})