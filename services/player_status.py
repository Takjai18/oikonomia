"""Player status payload builders."""
from models.combat import (
    _combat_is_finished_for_reconcile,
    get_active_combat_for_team,
    get_combat,
    get_combat_by_squad,
)
from models.protagonist import ProtagonistLifeState, get_protagonist_life_state
from models.team import get_team_by_id, get_team_protagonists, official_team_route
from services.ending import build_protagonist_control_status, judge_ending


def build_player_status(squad):
    from data.route_config import FORCED_ROUTE
    from models.combat import is_zoo_unlocked_for_team, zoo_unlock_story_stage
    from models.team import official_squad_route

    if not squad:
        return None

    # Persist forced route when DB still empty/wrong (covers login + /status paths).
    if FORCED_ROUTE:
        squad = _ensure_forced_route_persisted(squad)

    def _mainline(s):
        try:
            from services.progression import list_mainline_tasks_for_squad
            return list_mainline_tasks_for_squad(s)
        except Exception:
            return []

    if not squad.get("team_id"):
        return {
            "success": True,
            **squad,
            "team": None,
            "protagonists": {},
            "route": official_squad_route(squad),
            "forced_route": FORCED_ROUTE,
            "zoo_unlocked": False,
            "zoo_unlock_story_stage": zoo_unlock_story_stage(),
            "is_team_leader": 0,
            "mainline_tasks": _mainline(squad),
        }

    team_id = squad["team_id"]
    team = get_team_by_id(team_id)
    protagonists = get_team_protagonists(team_id)
    route = official_team_route(team)
    ending = judge_ending(team_id)
    zoo_unlocked = is_zoo_unlocked_for_team(team_id)

    protagonist_states = {}
    for key in ("iggy", "marah"):
        if key in (protagonists or {}):
            life = get_protagonist_life_state(team_id, key)
            protagonist_states[key] = life.value if isinstance(life, ProtagonistLifeState) else life

    return {
        "success": True,
        **squad,
        "route": route,
        "team": team,
        "protagonists": protagonists,
        "protagonist_life_states": protagonist_states,
        "protagonist_control_status": build_protagonist_control_status(team_id, route),
        "ending": ending,
        "trauma_level": ending.get("trauma_level", "safe"),
        "trauma_summary": ending.get("trauma_summary"),
        "ending_preview": ending.get("ending_preview"),
        "forced_route": FORCED_ROUTE,
        "zoo_unlocked": zoo_unlocked,
        "zoo_unlock_story_stage": zoo_unlock_story_stage(),
        "is_team_leader": squad.get("is_team_leader", 0),
        "mainline_tasks": _mainline(squad),
    }


def _ensure_forced_route_persisted(squad):
    """Write FORCED_ROUTE to squad/team when missing or mismatched (idempotent)."""
    from data.route_config import FORCED_ROUTE
    from models.squad import get_squad, update_squad
    from models.team import get_team_by_id, sync_team_route

    if not FORCED_ROUTE or not squad:
        return squad

    squad_id = squad.get("squad_id")
    team_id = squad.get("team_id")
    changed = False

    if team_id:
        team = get_team_by_id(team_id)
        team_route = ((team or {}).get("route") or "").strip().lower()
        if team_route != FORCED_ROUTE:
            sync_team_route(team_id, FORCED_ROUTE)
            changed = True
    else:
        squad_route = (squad.get("route") or "").strip().lower()
        if squad_route != FORCED_ROUTE and squad_id:
            update_squad(squad_id, route=FORCED_ROUTE)
            changed = True

    if changed and squad_id:
        return get_squad(squad_id) or squad
    return squad


def reconcile_status_combat_fields(squad):
    """
    Read-only lobby /status guard: strip stale current_combat_id from the
    payload when the combat row is already finished. Does not write to SQLite
    (high-frequency GET must stay side-effect free). DB heal remains on
    combat end, /session/restore, and /encounters reconcile paths.
    """
    if not squad:
        return None, None

    squad_id = squad.get("squad_id")
    team_id = squad.get("team_id")
    combat = None

    combat_id = squad.get("current_combat_id")
    if combat_id:
        combat = get_combat(combat_id)
    elif team_id:
        combat = get_active_combat_for_team(team_id)
    elif squad_id:
        combat = get_combat_by_squad(squad_id)

    if not combat:
        return None, None

    if _combat_is_finished_for_reconcile(combat) or combat.get("status") == "ended":
        return None, None

    return combat.get("id"), combat.get("status")