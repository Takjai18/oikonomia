"""Progressive unlock + GM sandbox (unlock) mode."""
from __future__ import annotations

import json
import os

from data.progression_gates import (
    ENCOUNTER_GATES,
    SIDE_TASK_PREFIXES,
    TASK_GATES,
    TASK_STORY_UNLOCKS,
)
from models.encounter_outcomes import encounter_already_completed
from models.settings import settings
from services.story import (
    count_team_distinct_tasks,
    get_viewed_story_ids,
    grant_story_unlock,
    is_story_viewed,
)


def _gm_unlock_path():
    base = os.path.dirname(settings.db_path or "") or "."
    return os.path.join(base, "gm_unlock_mode.json")


def _load_unlock_map():
    path = _gm_unlock_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f) or {}
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_unlock_map(data):
    path = _gm_unlock_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=0)
        return True
    except OSError:
        return False


def is_gm_unlock_mode(squad_id):
    """True if GM enabled sandbox unlock for this player (ignore all story/task gates)."""
    if not squad_id:
        return False
    data = _load_unlock_map()
    bag = data.get("squad_ids") or []
    return str(squad_id) in {str(x) for x in bag}


def set_gm_unlock_mode(squad_id, enabled):
    if not squad_id:
        return False
    data = _load_unlock_map()
    bag = set(str(x) for x in (data.get("squad_ids") or []))
    sid = str(squad_id)
    if enabled:
        bag.add(sid)
    else:
        bag.discard(sid)
    data["squad_ids"] = sorted(bag)
    return _save_unlock_map(data)


def list_gm_unlock_squads():
    data = _load_unlock_map()
    return sorted(str(x) for x in (data.get("squad_ids") or []))


def _viewed_set(squad_id):
    try:
        return set(get_viewed_story_ids(squad_id) or [])
    except Exception:
        return set()


def _done_tasks(squad):
    squad_id = squad.get("squad_id")
    team_id = squad.get("team_id")
    if not squad_id:
        return set()
    try:
        _, done = count_team_distinct_tasks(squad_id, team_id)
        return set(done or set())
    except Exception:
        return set()


def _has_all(have, need):
    if not need:
        return True
    return all(x in have for x in need)


def _has_any(have, need):
    if not need:
        return True
    return any(x in have for x in need)


def _encounters_done(squad, encounter_ids):
    if not encounter_ids:
        return True
    team_id = squad.get("team_id")
    if not team_id:
        return False
    for eid in encounter_ids:
        if not encounter_already_completed(team_id, eid):
            return False
    return True


def evaluate_gate(gate, squad, *, viewed=None, done=None):
    """Return (ok: bool, reason: str|None). Empty gate = ok."""
    if not gate:
        return True, None
    if gate.get("hidden"):
        return False, "此內容已隱藏"

    squad_id = squad.get("squad_id")
    if is_gm_unlock_mode(squad_id):
        return True, None

    viewed = viewed if viewed is not None else _viewed_set(squad_id)
    done = done if done is not None else _done_tasks(squad)

    if not _has_all(viewed, gate.get("requires_stories") or []):
        return False, "請先完成前置劇情"
    if not _has_any(viewed, gate.get("requires_any_stories") or []):
        # requires_any_stories with empty list means True via _has_any
        if gate.get("requires_any_stories"):
            return False, "請先完成分支劇情"
    if not _has_all(done, gate.get("requires_tasks") or []):
        return False, "請先完成前置任務"
    if gate.get("requires_any_tasks") and not _has_any(done, gate["requires_any_tasks"]):
        return False, "請先完成相關任務"
    if not _encounters_done(squad, gate.get("requires_encounters") or []):
        return False, "請先完成前置戰鬥"

    return True, None


def is_side_task(task_id):
    tid = str(task_id or "")
    return any(tid.startswith(p) for p in SIDE_TASK_PREFIXES)


def is_task_unlocked(squad, task_id):
    """Whether explore task should be visible / submittable."""
    if not task_id:
        return False
    if is_gm_unlock_mode(squad.get("squad_id")):
        return True
    if is_side_task(task_id):
        return True
    gate = TASK_GATES.get(task_id)
    if gate is None:
        # Mainline task without gate → require at least team+prologue (show after welcome)
        # Non-gated mainline still visible; prefer explicit gates for story tasks.
        return True
    ok, _ = evaluate_gate(gate, squad)
    return ok


def task_lock_reason(squad, task_id):
    if is_task_unlocked(squad, task_id):
        return None
    gate = TASK_GATES.get(task_id) or {}
    _, reason = evaluate_gate(gate, squad)
    return reason or "尚未解鎖"


def is_encounter_unlocked(squad, encounter_id, encounter=None):
    if is_gm_unlock_mode(squad.get("squad_id")):
        return True
    from models.encounter import encounter_is_practice

    if encounter and encounter_is_practice(encounter):
        return True
    gate = ENCOUNTER_GATES.get(encounter_id)
    if not gate:
        # Default: allow if story_stage check in route passes (caller still applies stage)
        return True
    ok, _ = evaluate_gate(gate, squad)
    return ok


def encounter_lock_reason(squad, encounter_id):
    if is_encounter_unlocked(squad, encounter_id):
        return None
    gate = ENCOUNTER_GATES.get(encounter_id) or {}
    _, reason = evaluate_gate(gate, squad)
    return reason or "尚未解鎖此戰鬥"


def filter_locations_for_squad(locations_dict, squad):
    """Return {task_id: loc} visible to this player."""
    out = {}
    for tid, loc in (locations_dict or {}).items():
        if is_task_unlocked(squad, tid):
            out[tid] = loc
    return out


def grant_task_story_unlocks(squad, task_id):
    """After a task is newly completed, queue follow-up stories for the team."""
    story_ids = TASK_STORY_UNLOCKS.get(task_id) or []
    if not story_ids:
        return None
    from models.squad import get_team_members

    team_id = squad.get("team_id")
    members = get_team_members(team_id) if team_id else [squad]
    first = None
    for sid_story in story_ids:
        for m in members or []:
            sid = m.get("squad_id") if isinstance(m, dict) else None
            if not sid:
                continue
            if is_story_viewed(sid, sid_story):
                continue
            grant_story_unlock(sid, sid_story)
            if first is None and sid == squad.get("squad_id"):
                first = sid_story
    return first
