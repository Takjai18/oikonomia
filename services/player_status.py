"""Player status payload builders."""
from models.protagonist import get_team_ending_state
from models.team import get_team_by_id, get_team_protagonists, official_team_route


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

    team = get_team_by_id(squad["team_id"])
    protagonists = get_team_protagonists(squad["team_id"])
    route = official_team_route(team)

    return {
        "success": True,
        **squad,
        "route": route,
        "team": team,
        "protagonists": protagonists,
        "ending": get_team_ending_state(squad["team_id"]),
        "is_team_leader": squad.get("is_team_leader", 0),
    }