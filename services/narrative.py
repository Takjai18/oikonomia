"""Narrative story UI helpers."""
from data.narrative_stories import (
    CONDITIONAL_NARRATIVE_FRAGMENTS,
    NARRATIVE_PORTRAITS,
    NARRATIVE_STORIES,
)
from data.story_config import STORY_CONTENT, STORY_STAGE_THRESHOLDS
from models.settings import settings
from services.story import count_team_distinct_tasks, is_story_viewed, resolve_story_stage


def enrich_story_lines(story):
    """為每行補上 portrait URL；旁白行標記 is_narration 且不附頭像。"""
    enriched = dict(story)
    lines = []
    for line in story.get("lines") or []:
        row = dict(line)
        char = row.get("character")
        is_narration = bool(row.get("is_narration")) or not char or char == "旁白"
        row["is_narration"] = is_narration
        if is_narration:
            row.pop("portrait", None)
        else:
            row.setdefault(
                "portrait",
                NARRATIVE_PORTRAITS.get(char, NARRATIVE_PORTRAITS["旁白"]),
            )
        lines.append(row)
    enriched["lines"] = lines
    return enriched


def get_story_for_route(route, stage):
    if not route:
        return {
            "title": "故事尚未開始",
            "content": "你尚未選擇路線。請先完成路線選擇，故事將會展開。",
        }
    route_stories = STORY_CONTENT.get(route, {})
    return route_stories.get(stage, route_stories.get(0, {"title": "故事進行中", "content": ""}))


def next_stage_threshold(current_stage):
    thresholds = settings.story_stage_thresholds or STORY_STAGE_THRESHOLDS
    return thresholds.get(current_stage + 1)


def squad_can_access_story(squad, story_id, story=None):
    """Progressive access: unlock_only stories need grant/view; free stories use min_stage."""
    from services.story import _squad_has_story_unlock

    if not squad or not story_id:
        return False
    stories = settings.narrative_stories or NARRATIVE_STORIES
    story = story or stories.get(story_id)
    if not story:
        return False
    squad_id = squad.get("squad_id")
    story_route = story.get("route")
    route = squad.get("route")
    if story_route and route and story_route != route:
        return False
    # Always allow welcome / already viewed (replay list handled by caller).
    if story_id == "welcome":
        return True
    if is_story_viewed(squad_id, story_id):
        return True
    if _squad_has_story_unlock(squad_id, story_id):
        return True
    # unlock_only: never show by stage alone (prevents Act 2 spoilers before Bubuo).
    if story.get("unlock_only"):
        return False
    completed_count, completed_task_ids = count_team_distinct_tasks(
        squad_id, squad.get("team_id")
    )
    stage = resolve_story_stage(completed_count, completed_task_ids)
    if story.get("min_stage", 0) > stage:
        return False
    if story.get("requires_team") and not squad.get("team_id"):
        return False
    return True


def get_available_narrative_stories(squad):
    squad_id = squad.get("squad_id")
    route = squad.get("route")
    stories = settings.narrative_stories or NARRATIVE_STORIES
    results = []
    for story_id, story in stories.items():
        story_route = story.get("route")
        if story_route and story_route != route:
            continue
        if not squad_can_access_story(squad, story_id, story):
            continue
        viewed = is_story_viewed(squad_id, story_id)
        if viewed and not story.get("replayable"):
            continue
        payload = enrich_story_lines(story)
        payload["viewed"] = viewed
        results.append(payload)
    return results


def get_conditional_narrative_fragment(fragment_id, team_id=None):
    """
    Return trauma/ending fragment by id (weakness_grace, trauma_caution, …).
    team_id reserved for future route-specific variants.
    """
    _ = team_id
    fragments = CONDITIONAL_NARRATIVE_FRAGMENTS
    configured = getattr(settings, "conditional_narrative_fragments", None)
    if configured:
        fragments = configured
    return dict(fragments.get(fragment_id) or {})