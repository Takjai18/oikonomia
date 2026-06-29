"""Story progression and team task completion tracking."""
import sqlite3
from datetime import datetime

from models.settings import settings
from utils.helpers import normalize_team_id


def _parse_distinct_task_row(row):
    distinct_count = row["distinct_count"] or 0
    raw_list = row["task_list"]
    task_ids = set(raw_list.split(",")) if raw_list else set()
    task_ids.discard("")
    return distinct_count, task_ids


def count_team_distinct_tasks(squad_id, team_id):
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        if team_id:
            clean_team_id = normalize_team_id(team_id)
            row = conn.execute("""
                SELECT
                    COUNT(DISTINCT task_id) AS distinct_count,
                    GROUP_CONCAT(DISTINCT task_id) AS task_list
                FROM submissions
                WHERE squad_id IN (
                    SELECT squad_id FROM squads
                    WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))
                )
            """, (clean_team_id,)).fetchone()
        else:
            row = conn.execute("""
                SELECT
                    COUNT(DISTINCT task_id) AS distinct_count,
                    GROUP_CONCAT(DISTINCT task_id) AS task_list
                FROM submissions
                WHERE squad_id = ?
            """, (squad_id,)).fetchone()
        return _parse_distinct_task_row(row)
    finally:
        conn.close()


def resolve_story_stage(completed_count, completed_task_ids):
    thresholds = settings.story_stage_thresholds or {}
    required_tasks = settings.story_stage_required_tasks or {}
    stage = 0
    for target_stage, min_tasks in thresholds.items():
        if completed_count >= min_tasks:
            stage = max(stage, target_stage)
    for target_stage, required in required_tasks.items():
        if required and any(t in completed_task_ids for t in required):
            stage = max(stage, target_stage)
    return min(stage, max(thresholds.keys(), default=0))


def is_story_viewed(squad_id, story_id):
    conn = sqlite3.connect(settings.db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM story_views WHERE squad_id = ? AND story_id = ?",
            (squad_id, story_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def narrative_story_id_for_stage(route, stage):
    if not route:
        return None
    stories = settings.narrative_stories or {}
    story_id = f"{route}_stage{stage}"
    return story_id if story_id in stories else None


def get_pending_story_id(squad):
    squad_id = squad.get("squad_id")
    route = squad.get("route")
    if not route:
        pending_welcome = "welcome"
        if not is_story_viewed(squad_id, pending_welcome):
            return pending_welcome
        return None

    completed_count, completed_task_ids = count_team_distinct_tasks(
        squad_id, squad.get("team_id")
    )
    stage = resolve_story_stage(completed_count, completed_task_ids)
    story_id = narrative_story_id_for_stage(route, stage)
    if not story_id:
        return None
    stories = settings.narrative_stories or {}
    story = stories.get(story_id, {})
    if story.get("min_stage", 0) > stage:
        return None
    if is_story_viewed(squad_id, story_id):
        return None
    return story_id


def mark_story_viewed(squad_id, story_id):
    conn = sqlite3.connect(settings.db_path)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO story_views (squad_id, story_id, viewed_at)
               VALUES (?, ?, ?)""",
            (squad_id, story_id, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()