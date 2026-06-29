"""Protagonist combat state: persistence, participation, AI, trauma."""
import sqlite3
from datetime import datetime, timedelta
from enum import Enum

from models.settings import default_protagonist_template, settings
from models.squad import DEFAULT_MAX_HP, get_team_members
from models.team import get_team_by_id, get_team_protagonists
from services.story import count_team_distinct_tasks, resolve_story_stage

PROTAGONIST_PREFIX = "protagonist:"
FINAL_STAGE_THRESHOLD = 3
TRAUMA_BAD_ENDING_LIMIT = 3


class ProtagonistLifeState(str, Enum):
    """High-level protagonist state for UI and narrative triggers."""

    NORMAL = "normal"
    NEAR_DEATH = "near_death"
    TRAUMATIZED = "traumatized"
    RESOLVED = "resolved"


PROTAGONIST_PROFILES = {
    "iggy": {
        "display_name": "Iggy",
        "avatar": "guardian_male_01.png",
        "power": 100,
        "intellect": 85,
        "resilience": 90,
    },
    "marah": {
        "display_name": "Marah",
        "avatar": "healer_female_01.png",
        "power": 75,
        "intellect": 100,
        "resilience": 95,
    },
}


def _db():
    return settings.db_path


def protagonist_squad_id(team_id, protagonist_key):
    clean = (team_id or "").strip().upper()
    return f"{PROTAGONIST_PREFIX}{protagonist_key}:{clean}"


def is_protagonist_participant(squad_id):
    return bool(squad_id and str(squad_id).startswith(PROTAGONIST_PREFIX))


def parse_protagonist_squad_id(squad_id):
    if not is_protagonist_participant(squad_id):
        return None, None
    body = str(squad_id)[len(PROTAGONIST_PREFIX):]
    if ":" not in body:
        return None, None
    key, team_id = body.split(":", 1)
    if key not in ("iggy", "marah"):
        return None, None
    return key, team_id


def get_team_story_stage(team_id):
    members = get_team_members(team_id)
    if not members:
        return 0
    leader = next((m for m in members if m.get("is_team_leader")), members[0])
    count, tasks = count_team_distinct_tasks(leader["squad_id"], team_id)
    return resolve_story_stage(count, tasks)


def initialize_protagonist_for_team(team_id, protagonist_key):
    """Create protagonist row when team picks a route (idempotent)."""
    clean_team = (team_id or "").strip().upper()
    if not clean_team or protagonist_key not in ("iggy", "marah"):
        return None
    existing = get_protagonist_state(clean_team, protagonist_key, create=False)
    if existing:
        return existing
    base = default_protagonist_template()
    now = datetime.now().isoformat()
    hp = int(base.get("hp", 100))
    max_hp = int(base.get("hp", DEFAULT_MAX_HP))
    sanity = int(base.get("sanity", 100))
    conn = sqlite3.connect(_db())
    try:
        conn.execute(
            """INSERT OR IGNORE INTO protagonist_states
               (team_id, protagonist, hp, max_hp, sanity, trauma_count, is_active, last_updated)
               VALUES (?, ?, ?, ?, ?, 0, 1, ?)""",
            (clean_team, protagonist_key, hp, max_hp, sanity, now),
        )
        conn.commit()
    finally:
        conn.close()
    return get_protagonist_state(clean_team, protagonist_key, create=False)


def get_active_protagonists(team_id):
    """Rows with is_active=1 (combat-eligible protagonists)."""
    clean_team = (team_id or "").strip().upper()
    if not clean_team:
        return []
    conn = sqlite3.connect(_db())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT team_id, protagonist, hp, max_hp, sanity, trauma_count,
                      is_active, near_death_until, last_updated
               FROM protagonist_states
               WHERE team_id = ? AND COALESCE(is_active, 1) = 1""",
            (clean_team,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def log_trauma_event(team_id, protagonist_key, delta, reason=None):
    """Append audit row for trauma changes (reason = near_death, encounter_failure, …)."""
    clean_team = (team_id or "").strip().upper()
    if not clean_team or protagonist_key not in ("iggy", "marah"):
        return
    conn = sqlite3.connect(_db())
    try:
        conn.execute(
            """INSERT INTO protagonist_trauma_log
               (team_id, protagonist, delta, reason, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (clean_team, protagonist_key, int(delta), reason, datetime.now().isoformat()),
        )
        conn.commit()
    except sqlite3.Error:
        pass
    finally:
        conn.close()


def apply_trauma(team_id, protagonist_key, amount=1, reason=None):
    """Unified trauma increment; optional reason logged to protagonist_trauma_log."""
    state = get_protagonist_state(team_id, protagonist_key, create=False)
    if not state:
        return None
    delta = int(amount)
    if delta == 0:
        return int(state.get("trauma_count") or 0)
    new_trauma = int(state.get("trauma_count") or 0) + delta
    update_protagonist_state(team_id, protagonist_key, trauma_count=new_trauma)
    if reason:
        log_trauma_event(team_id, protagonist_key, delta, reason)
    return new_trauma


def get_protagonist_life_state(team_id, protagonist_key):
    """Map DB row to ProtagonistLifeState."""
    state = get_protagonist_state(team_id, protagonist_key, create=False)
    if not state:
        return ProtagonistLifeState.NORMAL

    until = state.get("near_death_until")
    if until:
        try:
            if datetime.now() < datetime.fromisoformat(until):
                return ProtagonistLifeState.NEAR_DEATH
        except ValueError:
            pass

    trauma = int(state.get("trauma_count") or 0)
    hp = int(state.get("hp") or 0)
    if has_trauma_bad_ending(team_id) or trauma > TRAUMA_BAD_ENDING_LIMIT:
        return ProtagonistLifeState.TRAUMATIZED
    if trauma >= 2:
        return ProtagonistLifeState.TRAUMATIZED
    if hp > 0 and trauma > 0 and not until:
        return ProtagonistLifeState.RESOLVED
    return ProtagonistLifeState.NORMAL


def check_ending_condition(team_id):
    """Return 'bad_ending' if protagonist trauma exceeds limit, else 'normal_ending'."""
    if has_trauma_bad_ending(team_id):
        return "bad_ending"
    return "normal_ending"


def get_team_ending_type(team_id):
    clean_team = (team_id or "").strip().upper()
    if not clean_team:
        return None
    conn = sqlite3.connect(_db())
    try:
        row = conn.execute(
            "SELECT ending_type FROM teams WHERE team_id = ?",
            (clean_team,),
        ).fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


def record_team_ending(team_id, ending_type, source=None):
    """Persist irreversible bad ending on teams row (source = encounter_id, optional)."""
    clean_team = (team_id or "").strip().upper()
    if not clean_team or ending_type != "bad_ending":
        return False
    if get_team_ending_type(clean_team) == "bad_ending":
        return True
    now = datetime.now().isoformat()
    conn = sqlite3.connect(_db())
    try:
        conn.execute(
            "UPDATE teams SET ending_type = ?, ending_locked_at = ? WHERE team_id = ?",
            (ending_type, now, clean_team),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def get_team_ending_state(team_id):
    """Snapshot for APIs/UI: trauma totals, condition, locked ending."""
    clean_team = (team_id or "").strip().upper()
    empty = {
        "ending_condition": "normal_ending",
        "ending_type": None,
        "protagonist_trauma_total": 0,
        "trauma_bad_ending": False,
        "trauma_limit": TRAUMA_BAD_ENDING_LIMIT,
        "trauma_until_bad": TRAUMA_BAD_ENDING_LIMIT + 1,
    }
    if not clean_team:
        return empty
    trauma_total = get_team_protagonist_trauma_total(clean_team)
    locked = get_team_ending_type(clean_team)
    condition = locked if locked else check_ending_condition(clean_team)
    return {
        "ending_condition": condition,
        "ending_type": locked,
        "protagonist_trauma_total": trauma_total,
        "trauma_bad_ending": condition == "bad_ending",
        "trauma_limit": TRAUMA_BAD_ENDING_LIMIT,
        "trauma_until_bad": max(0, TRAUMA_BAD_ENDING_LIMIT + 1 - trauma_total),
    }


def get_protagonist_state(team_id, protagonist_key, create=True):
    clean_team = (team_id or "").strip().upper()
    if not clean_team or protagonist_key not in ("iggy", "marah"):
        return None

    conn = sqlite3.connect(_db())
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT team_id, protagonist, hp, max_hp, sanity, trauma_count,
                      is_active, near_death_until, last_updated
               FROM protagonist_states
               WHERE team_id = ? AND protagonist = ?""",
            (clean_team, protagonist_key),
        ).fetchone()
        if row:
            return dict(row)

        if not create:
            return None

        base = default_protagonist_template()
        profile = PROTAGONIST_PROFILES.get(protagonist_key, {})
        now = datetime.now().isoformat()
        hp = int(base.get("hp", 100))
        max_hp = int(base.get("hp", DEFAULT_MAX_HP))
        sanity = int(base.get("sanity", 100))
        conn.execute(
            """INSERT INTO protagonist_states
               (team_id, protagonist, hp, max_hp, sanity, trauma_count, is_active, last_updated)
               VALUES (?, ?, ?, ?, ?, 0, 1, ?)""",
            (clean_team, protagonist_key, hp, max_hp, sanity, now),
        )
        conn.commit()
        return {
            "team_id": clean_team,
            "protagonist": protagonist_key,
            "hp": hp,
            "max_hp": max_hp,
            "sanity": sanity,
            "trauma_count": 0,
            "is_active": 1,
            "near_death_until": None,
            "last_updated": now,
        }
    finally:
        conn.close()


def update_protagonist_state(team_id, protagonist_key, **kwargs):
    allowed = {"hp", "max_hp", "sanity", "trauma_count", "is_active", "near_death_until"}
    updates, params = [], []
    for key, val in kwargs.items():
        if key not in allowed:
            continue
        if key == "near_death_until" and val is None:
            updates.append("near_death_until = NULL")
        elif val is not None:
            updates.append(f"{key} = ?")
            params.append(val)
    if not updates:
        return get_protagonist_state(team_id, protagonist_key)

    updates.append("last_updated = ?")
    params.append(datetime.now().isoformat())
    clean_team = (team_id or "").strip().upper()
    params.extend([clean_team, protagonist_key])

    conn = sqlite3.connect(_db())
    try:
        conn.execute(
            f"UPDATE protagonist_states SET {', '.join(updates)} "
            "WHERE team_id = ? AND protagonist = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()
    return get_protagonist_state(team_id, protagonist_key)


def enrich_protagonists_dict(team_id, protagonists):
    if not protagonists or not team_id:
        return protagonists
    for key in ("iggy", "marah"):
        if key not in protagonists:
            continue
        state = get_protagonist_state(team_id, key, create=True)
        if not state:
            continue
        protagonists[key] = {
            **protagonists.get(key, {}),
            "hp": state["hp"],
            "max_hp": state.get("max_hp", DEFAULT_MAX_HP),
            "sanity": state["sanity"],
            "trauma_count": state.get("trauma_count", 0),
            "near_death_until": state.get("near_death_until"),
        }
    return protagonists


def get_team_protagonist_trauma_total(team_id):
    clean_team = (team_id or "").strip().upper()
    if not clean_team:
        return 0
    conn = sqlite3.connect(_db())
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(trauma_count), 0) FROM protagonist_states WHERE team_id = ?",
            (clean_team,),
        ).fetchone()
        return int(row[0] or 0)
    finally:
        conn.close()


def has_trauma_bad_ending(team_id):
    return get_team_protagonist_trauma_total(team_id) > TRAUMA_BAD_ENDING_LIMIT


def resolve_combat_protagonist_keys(team_id, encounter, story_stage):
    """Which protagonists join this combat."""
    team = get_team_by_id(team_id) or {}
    route = team.get("route")
    cfg = (encounter or {}).get("protagonist_participation") or {}
    if cfg.get("enabled") is False:
        return []

    dual = story_stage >= FINAL_STAGE_THRESHOLD or cfg.get("dual_protagonists")
    if dual:
        candidates = [k for k in ("iggy", "marah") if cfg.get(k, True)]
    elif route == "iggy" and cfg.get("iggy", True):
        candidates = ["iggy"]
    elif route == "marah" and cfg.get("marah", True):
        candidates = ["marah"]
    else:
        return []

    keys = []
    for key in candidates:
        state = get_protagonist_state(team_id, key, create=False)
        if state and not int(state.get("is_active") or 0):
            continue
        if not state:
            state = initialize_protagonist_for_team(team_id, key)
        if state and int(state.get("is_active") or 1):
            keys.append(key)
    return keys


def protagonist_player_control_enabled(encounter, story_stage):
    settings_block = (encounter or {}).get("combat_settings") or {}
    if settings_block.get("protagonist_player_control") is True:
        return True
    if settings_block.get("protagonist_player_control") is False:
        return False
    return story_stage >= FINAL_STAGE_THRESHOLD


def get_player_control_protagonist_ids(team_id, encounter, story_stage, participants):
    if not protagonist_player_control_enabled(encounter, story_stage):
        return []
    team = get_team_by_id(team_id) or {}
    route = team.get("route")
    if route not in ("iggy", "marah"):
        return []
    sid = protagonist_squad_id(team_id, route)
    active_ids = {
        p["squad_id"] for p in participants
        if p.get("is_protagonist") and p["squad_id"] == sid
    }
    return list(active_ids)


def get_controllable_protagonist_squad_id(team_id, route, encounter, story_stage):
    if not protagonist_player_control_enabled(encounter, story_stage):
        return None
    if route not in ("iggy", "marah"):
        return None
    return protagonist_squad_id(team_id, route)


def _protagonist_base_stats(team_id, protagonist_key):
    protagonists = get_team_protagonists(team_id)
    template = protagonists.get(protagonist_key) or default_protagonist_template()
    profile = PROTAGONIST_PROFILES.get(protagonist_key, {})
    return {
        "display_name": template.get("name") or profile.get("display_name") or protagonist_key.title(),
        "avatar": profile.get("avatar", "default.png"),
        "power": int(template.get("power") or profile.get("power") or 100),
        "intellect": int(template.get("intellect") or profile.get("intellect") or 100),
        "resilience": int(template.get("resilience") or profile.get("resilience") or 100),
    }


def build_protagonist_participant(team_id, protagonist_key):
    state = get_protagonist_state(team_id, protagonist_key, create=True)
    if not state:
        return None
    base = _protagonist_base_stats(team_id, protagonist_key)
    clean_team = (team_id or "").strip().upper()
    return {
        "squad_id": protagonist_squad_id(clean_team, protagonist_key),
        "display_name": base["display_name"],
        "avatar": base["avatar"],
        "team_id": clean_team,
        "is_protagonist": True,
        "protagonist_key": protagonist_key,
        "hp": int(state.get("hp") or 0),
        "max_hp": int(state.get("max_hp") or DEFAULT_MAX_HP),
        "sanity": int(state.get("sanity") or 0),
        "power": base["power"],
        "intellect": base["intellect"],
        "resilience": base["resilience"],
        "near_death_until": state.get("near_death_until"),
        "trauma_count": int(state.get("trauma_count") or 0),
        "is_team_leader": 0,
    }


def refresh_combat_participants(participants):
    refreshed = []
    for p in participants:
        if p.get("is_protagonist"):
            rebuilt = build_protagonist_participant(p.get("team_id"), p.get("protagonist_key"))
            refreshed.append(rebuilt or p)
        else:
            refreshed.append(p)
    squad_ids = [p["squad_id"] for p in refreshed if not p.get("is_protagonist")]
    from models.squad import fetch_squads_by_ids

    squads = fetch_squads_by_ids(squad_ids)
    out = []
    for p in refreshed:
        if p.get("is_protagonist"):
            out.append(p)
        else:
            out.append(squads.get(p["squad_id"], p))
    return out


def apply_damage_to_protagonist(team_id, protagonist_key, damage, participant=None):
    state = get_protagonist_state(team_id, protagonist_key, create=False)
    if not state:
        return None
    new_hp = max(0, int(state.get("hp") or 0) - int(damage))
    updates = {"hp": new_hp}
    if new_hp <= 0:
        updates["near_death_until"] = (
            datetime.now() + timedelta(minutes=settings.near_death_minutes)
        ).isoformat()
        updates["trauma_count"] = apply_trauma(
            team_id, protagonist_key, 1, reason="near_death_damage",
        )
    return update_protagonist_state(team_id, protagonist_key, **updates)


def trauma_bad_ending_narrative(encounter):
    custom = (encounter or {}).get("success", {}).get("trauma_bad_ending_narrative")
    if custom:
        return custom
    return (
        "你們表面上贏了這一仗，但主角身上累積的心理創傷已太深——"
        "即使擊敗最後的陰影，也無法迎來真正的救贖結局。"
    )