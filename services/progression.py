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
    """Return {task_id: loc} visible to this player (enriched with progress)."""
    out = {}
    done = _done_tasks(squad)
    for tid, loc in (locations_dict or {}).items():
        if not is_task_unlocked(squad, tid):
            continue
        entry = dict(loc)
        entry["completed"] = tid in done
        if tid == "act1_supplies" or entry.get("qr_checklist"):
            entry["checklist"] = build_act1_checklist_for_squad(squad)
            progress = act1_supplies_progress(squad)
            entry["checklist_done"] = progress["done"]
            entry["checklist_total"] = progress["total"]
            entry["checklist_label"] = f"{progress['done']}/{progress['total']}"
            if progress["complete"]:
                entry["completed"] = True
        out[tid] = entry
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


# ---------------------------------------------------------------------------
# Act 1 unified QR checklist
# ---------------------------------------------------------------------------

def act1_supplies_progress(squad):
    """How many of the 4 Act1 QR sub-keys the team has completed."""
    from data.act1_qr_hooks import ACT1_ALL_SUB_KEYS, ACT1_CHECKLIST

    done = _done_tasks(squad)
    # Also treat owning the item as progress (in case sub submission missing)
    owned_qr = _team_owned_qr_codes(squad)
    completed_keys = set()
    for item in ACT1_CHECKLIST:
        sub = item["sub_key"]
        qr = item["qr"]
        if sub in done or qr in owned_qr or qr.lower() in owned_qr:
            completed_keys.add(sub)
    total = len(ACT1_ALL_SUB_KEYS)
    n = len(completed_keys)
    return {
        "done": n,
        "total": total,
        "complete": n >= total,
        "completed_keys": sorted(completed_keys),
    }


def _team_owned_qr_codes(squad):
    """Set of qr_code_value strings owned by any team member."""
    import sqlite3

    squad_id = squad.get("squad_id")
    team_id = squad.get("team_id")
    if not squad_id:
        return set()
    conn = sqlite3.connect(settings.db_path)
    try:
        if team_id:
            rows = conn.execute(
                """SELECT DISTINCT i.qr_code_value
                   FROM player_items pi
                   JOIN items i ON i.id = pi.item_id
                   JOIN squads s ON s.squad_id = pi.squad_id
                   WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?))
                     AND i.qr_code_value IS NOT NULL""",
                (team_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT DISTINCT i.qr_code_value
                   FROM player_items pi
                   JOIN items i ON i.id = pi.item_id
                   WHERE pi.squad_id = ? AND i.qr_code_value IS NOT NULL""",
                (squad_id,),
            ).fetchall()
        return {str(r[0]).strip() for r in rows if r and r[0]}
    except sqlite3.Error:
        return set()
    finally:
        conn.close()


def build_act1_checklist_for_squad(squad):
    """UI checklist rows for act1_supplies (with lock / done state)."""
    from data.act1_qr_hooks import ACT1_CHECKLIST, ACT1_QR_HOOKS

    progress = act1_supplies_progress(squad)
    completed = set(progress["completed_keys"])
    viewed = _viewed_set(squad.get("squad_id"))
    unlock = is_gm_unlock_mode(squad.get("squad_id"))
    rows = []
    for item in ACT1_CHECKLIST:
        hooks = ACT1_QR_HOOKS.get(item["qr"]) or {}
        req = hooks.get("requires_stories") or []
        locked = False if unlock else not all(s in viewed for s in req)
        done = item["sub_key"] in completed
        rows.append({
            "qr": item["qr"],
            "sub_key": item["sub_key"],
            "label": item["label"],
            "phase": item.get("phase"),
            "note": item.get("note"),
            "done": done,
            "locked": locked and not done,
            "lock_hint": (
                "需先完成布布戰與篝火劇情" if item.get("phase") == "identity" and locked
                else ("需先看完雪山開場" if locked else None)
            ),
        })
    return rows


def can_claim_act1_qr(squad, qr_code_value):
    """Whether this physical QR may be claimed now (story gate per checklist item)."""
    from data.act1_qr_hooks import hooks_for_qr_code

    hooks = hooks_for_qr_code(qr_code_value)
    if not hooks:
        return True, None
    if is_gm_unlock_mode(squad.get("squad_id")):
        return True, None
    # Parent task must be visible
    parent = hooks.get("parent_task_id") or "act1_supplies"
    if not is_task_unlocked(squad, parent):
        return False, task_lock_reason(squad, parent) or "請先完成前置劇情"
    req = hooks.get("requires_stories") or []
    viewed = _viewed_set(squad.get("squad_id"))
    if req and not all(s in viewed for s in req):
        if "iggy_act1_post_bubo" in req:
            return False, "請先擊敗布布並看完篝火劇情，再掃徽章／鐵片"
        return False, "請先完成前置劇情"
    return True, None


def list_mainline_tasks_for_squad(squad):
    """Dashboard mainline overview: unlocked / completed story tasks only."""
    locations = settings.locations or {}
    done = _done_tasks(squad)
    rows = []
    for tid, loc in locations.items():
        if not loc.get("mainline"):
            continue
        unlocked = is_task_unlocked(squad, tid)
        completed = tid in done
        if tid == "act1_supplies":
            prog = act1_supplies_progress(squad)
            completed = completed or prog["complete"]
        # Show if unlocked or already completed (history)
        if not unlocked and not completed:
            continue
        entry = {
            "task_id": tid,
            "name": loc.get("name") or tid,
            "hint": loc.get("hint") or "",
            "story_act": loc.get("story_act"),
            "mainline_order": loc.get("mainline_order") or 999,
            "task_type": loc.get("task_type"),
            "unlocked": unlocked,
            "completed": completed,
            "status": "done" if completed else ("active" if unlocked else "locked"),
        }
        if tid == "act1_supplies":
            prog = act1_supplies_progress(squad)
            entry["progress_label"] = f"{prog['done']}/{prog['total']}"
            entry["checklist"] = build_act1_checklist_for_squad(squad)
        rows.append(entry)
    rows.sort(key=lambda r: (r.get("mainline_order") or 999, r.get("task_id") or ""))
    return rows
