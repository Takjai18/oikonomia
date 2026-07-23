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


def record_task_completion_from_qr(squad_id, task_id, note=None):
    """Mark a location task complete after a successful QR claim (idempotent per squad).

    Returns True if a new submission row was inserted.
    Accepts main locations OR Act1 checklist sub-keys (act1_water, …).
    """
    if not squad_id or not task_id:
        return False
    locations = settings.locations or {}
    allowed_sub = set()
    try:
        from data.act1_qr_hooks import ACT1_ALL_SUB_KEYS
        allowed_sub = set(ACT1_ALL_SUB_KEYS)
    except Exception:
        pass
    if task_id not in locations and task_id not in allowed_sub:
        return False
    loc_name = (locations.get(task_id) or {}).get("name") or task_id
    content = note or f"QR 掃描完成：{loc_name}"
    conn = sqlite3.connect(settings.db_path)
    try:
        existing = conn.execute(
            "SELECT 1 FROM submissions WHERE squad_id = ? AND task_id = ? LIMIT 1",
            (squad_id, task_id),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            """INSERT INTO submissions (squad_id, task_id, content, photo_path, timestamp)
               VALUES (?, ?, ?, NULL, ?)""",
            (squad_id, task_id, content, datetime.now().isoformat()),
        )
        conn.commit()
        return True
    except sqlite3.Error:
        conn.rollback()
        return False
    finally:
        conn.close()


def narrative_story_id_for_stage(route, stage):
    if not route:
        return None
    stories = settings.narrative_stories or {}
    story_id = f"{route}_stage{stage}"
    return story_id if story_id in stories else None


def get_pending_story_id(squad):
    """Onboarding order: welcome prologue → (character stats) → Act / stage story.

    Stage stories are withheld until stats_allocated so new players see:
    PIN → 序章 → 建角 → Act 1.
    """
    squad_id = squad.get("squad_id")
    if not squad_id:
        return None

    # 1) Always finish world prologue first (even when forced_route is set).
    if not is_story_viewed(squad_id, "welcome"):
        return "welcome"

    # 2) Character creation sits between prologue and Act 1.
    if not squad.get("stats_allocated"):
        return None

    # 3) Act 1+ requires a team (create/join) before mainline stories.
    if not squad.get("team_id"):
        return None

    # 4) Explicit unlock stories (post-combat / post-task) — ordered, progressive.
    # Do NOT dump every act; only surface if granted via grant_story_unlock.
    PROGRESSIVE_UNLOCK_ORDER = (
        "iggy_act1_post_bubo",
        "iggy_act1_identity",
        "iggy_stage1",
        "iggy_act2_branch_leave",
        "iggy_act2_branch_care",
        "iggy_act2_post_polis",
        "iggy_stage2",
        "iggy_act3_shelter",
        "iggy_act3_found_iggy",
        "iggy_act3_julian",
        "iggy_act4_albert_test",
        "iggy_act4_meifoo",
        "iggy_act4_phoenix",
        "iggy_act5_betrayal",
        "iggy_act6_approach",
        "iggy_ending_victory",
    )
    for unlock_id in PROGRESSIVE_UNLOCK_ORDER:
        if is_story_viewed(squad_id, unlock_id):
            continue
        if _squad_has_story_unlock(squad_id, unlock_id):
            return unlock_id

    # 5) Route / stage mainline (e.g. iggy_stage0 after team create).
    # Stories marked unlock_only=True never auto-fire from task-count stage.
    route = (squad.get("route") or "").strip().lower()
    if not route:
        from data.route_config import FORCED_ROUTE
        route = (FORCED_ROUTE or "").strip().lower() or None
    if not route:
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
    if story.get("unlock_only"):
        return None
    if story.get("min_stage", 0) > stage:
        return None
    if is_story_viewed(squad_id, story_id):
        return None
    return story_id


def _story_unlocks_path():
    """Optional JSON side-file under data_dir for pending unlocks (no migration)."""
    import os
    base = os.path.dirname(settings.db_path or "") or "."
    return os.path.join(base, "story_unlocks.json")


def grant_story_unlock(squad_id, story_id):
    """Queue a story to auto-show (e.g. after Bubuo win or personal items)."""
    import json
    import os
    if not squad_id or not story_id:
        return False
    path = _story_unlocks_path()
    data = {}
    try:
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f) or {}
    except (OSError, json.JSONDecodeError):
        data = {}
    bag = set(data.get(squad_id) or [])
    bag.add(story_id)
    data[squad_id] = sorted(bag)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=0)
        return True
    except OSError:
        return False


def _squad_has_story_unlock(squad_id, story_id):
    import json
    import os
    path = _story_unlocks_path()
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f) or {}
        return story_id in (data.get(squad_id) or [])
    except (OSError, json.JSONDecodeError):
        return False


def clear_story_unlock(squad_id, story_id):
    import json
    import os
    path = _story_unlocks_path()
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f) or {}
        bag = set(data.get(squad_id) or [])
        bag.discard(story_id)
        if bag:
            data[squad_id] = sorted(bag)
        else:
            data.pop(squad_id, None)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=0)
    except (OSError, json.JSONDecodeError):
        pass


def get_viewed_story_ids(squad_id):
    conn = sqlite3.connect(settings.db_path)
    try:
        rows = conn.execute(
            "SELECT story_id FROM story_views WHERE squad_id = ? ORDER BY viewed_at",
            (squad_id,),
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


def mark_story_viewed(squad_id, story_id):
    clear_story_unlock(squad_id, story_id)
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