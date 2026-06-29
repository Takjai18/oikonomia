"""Player status payload builders."""
from models.protagonist import ProtagonistLifeState, get_protagonist_life_state
from models.team import get_team_by_id, get_team_protagonists, official_team_route
from services.ending import judge_ending


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
        "ending": ending,
        "trauma_level": ending.get("trauma_level", "safe"),
        "ending_preview": ending.get("ending_preview"),
        "is_team_leader": squad.get("is_team_leader", 0),
    }