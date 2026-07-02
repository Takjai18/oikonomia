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
    if not squad:
        return None

    if not squad.get("team_id"):
        return {
            "success": True,
            **squad,
            "team": None,
            "protagonists": {},
            "route": squad.get("route"),
            "is_team_leader": 0,
        }

    team_id = squad["team_id"]
    team = get_team_by_id(team_id)
    protagonists = get_team_protagonists(team_id)
    route = official_team_route(team)
    ending = judge_ending(team_id)

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
        "is_team_leader": squad.get("is_team_leader", 0),
    }


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