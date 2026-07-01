import sqlite3
from datetime import datetime

from models.settings import default_protagonist_template, settings
from utils.db_tx import immediate_transaction
from utils.helpers import normalize_team_id


def resolve_team_display_route(team_id, team_row=None):
    clean_id = normalize_team_id(team_id)
    if not clean_id:
        return None

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = team_row
        if row is None:
            row = conn.execute(
                "SELECT team_id, route, leader_squad_id FROM teams WHERE team_id = ?",
                (clean_id,),
            ).fetchone()
        if not row:
            return None

        route = row["route"] if hasattr(row, "keys") else row.get("route")
        if route:
            return route

        leader_id = row["leader_squad_id"] if hasattr(row, "keys") else row.get("leader_squad_id")
        if leader_id:
            leader = conn.execute(
                "SELECT route FROM squads WHERE squad_id = ?", (leader_id,)
            ).fetchone()
            if leader and leader["route"]:
                return leader["route"]

        member_row = conn.execute(
            """SELECT route FROM squads
               WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))
                 AND route IS NOT NULL AND TRIM(route) != ''
               LIMIT 1""",
            (clean_id,),
        ).fetchone()
        if member_row:
            return member_row["route"]
        return None
    finally:
        conn.close()


def official_team_route(team):
    route = (team or {}).get("route")
    return route if route in ("iggy", "marah") else None


def official_squad_route(squad):
    """Single source of truth: team.route overrides squads.route when in a team."""
    if not squad:
        return None
    team_id = squad.get("team_id")
    if team_id:
        team = get_team_by_id(team_id)
        route = official_team_route(team)
        if route:
            return route
    route = squad.get("route")
    return route if route in ("iggy", "marah") else None


def is_team_leader_session(team, squad_id):
    if not team or not squad_id:
        return False
    if team.get("leader_squad_id") == squad_id:
        return True
    from models.squad import get_squad

    squad = get_squad(squad_id)
    return bool(squad and squad.get("is_team_leader") == 1)


def sync_team_route(team_id, route):
    clean_id = normalize_team_id(team_id)
    if not clean_id or route not in ("iggy", "marah"):
        return
    with immediate_transaction() as conn:
        c = conn.cursor()
        c.execute("UPDATE teams SET route = ? WHERE team_id = ?", (route, clean_id))
        c.execute(
            "UPDATE squads SET route = ? WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))",
            (route, clean_id),
        )
    from models.protagonist import initialize_protagonist_for_team

    initialize_protagonist_for_team(clean_id, route)


def backfill_team_routes_from_members():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        teams = conn.execute(
            "SELECT team_id FROM teams WHERE route IS NULL OR TRIM(route) = ''"
        ).fetchall()
        for team in teams:
            resolved = resolve_team_display_route(team["team_id"])
            if resolved:
                sync_team_route(team["team_id"], resolved)
    finally:
        conn.close()


def get_next_team_id():
    conn = sqlite3.connect(settings.db_path)
    c = conn.cursor()
    c.execute("SELECT team_id FROM teams ORDER BY team_id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if not row:
        return "TEAM-01"
    num = int(row[0].split("-")[1]) + 1
    return f"TEAM-{num:02d}"


def get_team_by_id(team_id):
    if not team_id:
        return None

    clean_id = normalize_team_id(team_id)

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT t.team_id, t.team_name, t.route, t.leader_squad_id, t.created_at,
               t.ending_type, t.ending_locked_at,
               COUNT(s.squad_id) AS member_count
        FROM teams t
        LEFT JOIN squads s ON UPPER(TRIM(s.team_id)) = UPPER(TRIM(t.team_id))
        WHERE t.team_id = ?
        GROUP BY t.team_id
        """,
        (clean_id,),
    ).fetchone()
    conn.close()

    if not row:
        return None

    return {
        "team_id": row["team_id"],
        "team_name": row["team_name"],
        "route": row["route"],
        "leader_squad_id": row["leader_squad_id"],
        "created_at": row["created_at"],
        "ending_type": row["ending_type"],
        "ending_locked_at": row["ending_locked_at"],
        "member_count": row["member_count"],
    }


def get_team_protagonists(team_id):
    """
    SSOT: protagonist HP/sanity/trauma from protagonist_states;
    static combat stats from PROTAGONIST_PROFILES (not squads.protagonist_stats JSON).
    """
    from models.protagonist import PROTAGONIST_PROFILES, get_protagonist_state

    clean_team_id = normalize_team_id(team_id)
    default = default_protagonist_template()
    if not clean_team_id:
        return {
            "iggy": default.copy(),
            "marah": default.copy(),
            "active_route": None,
        }

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    team_row = conn.execute(
        "SELECT route FROM teams WHERE team_id = ?", (clean_team_id,)
    ).fetchone()
    conn.close()

    if not team_row:
        return {
            "iggy": default.copy(),
            "marah": default.copy(),
            "active_route": None,
        }

    route = team_row["route"]
    result = {
        "iggy": default.copy(),
        "marah": default.copy(),
        "active_route": route,
    }

    for key in ("iggy", "marah"):
        profile = PROTAGONIST_PROFILES.get(key, {})
        state = get_protagonist_state(clean_team_id, key, create=True)
        entry = {
            **default.copy(),
            "name": profile.get("display_name", key.title()),
            "avatar": profile.get("avatar"),
            "power": int(profile.get("power", default.get("power", 100))),
            "intellect": int(profile.get("intellect", default.get("intellect", 100))),
            "resilience": int(profile.get("resilience", default.get("resilience", 100))),
        }
        if state:
            entry.update({
                "hp": int(state.get("hp", 100)),
                "max_hp": int(state.get("max_hp", 100)),
                "sanity": int(state.get("sanity", 100)),
                "trauma_count": int(state.get("trauma_count", 0)),
                "near_death_until": state.get("near_death_until"),
            })
        result[key] = entry

    return result


def join_squad_to_team(squad_id, team_id, route):
    """Atomically join a squad to a team (fails if squad already has a team)."""
    clean_id = normalize_team_id(team_id)
    if not clean_id or not squad_id or route not in ("iggy", "marah"):
        raise ValueError("invalid join parameters")

    now = datetime.now().isoformat()
    with immediate_transaction() as conn:
        c = conn.cursor()
        c.execute(
            """UPDATE squads
               SET team_id = ?, is_team_leader = 0, route = ?, last_update = ?
               WHERE squad_id = ?
                 AND (team_id IS NULL OR TRIM(team_id) = '')""",
            (clean_id, route, now, squad_id),
        )
        if c.rowcount == 0:
            raise ValueError("squad already in a team")


def transfer_team_leadership(team_id, target_squad_id):
    """Atomically transfer team leadership (squads + teams.leader_squad_id)."""
    clean_id = normalize_team_id(team_id)
    if not clean_id or not target_squad_id:
        raise ValueError("missing team_id or target_squad_id")

    with immediate_transaction() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE squads SET is_team_leader = 0 WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))",
            (clean_id,),
        )
        c.execute(
            "UPDATE squads SET is_team_leader = 1 WHERE squad_id = ?",
            (target_squad_id,),
        )
        c.execute(
            "UPDATE teams SET leader_squad_id = ? WHERE team_id = ?",
            (target_squad_id, clean_id),
        )


def create_team_with_leader(team_id, team_name, leader_squad_id, route=None):
    """Atomically create a team row and assign the leader squad."""
    created_at = datetime.now().isoformat()
    with immediate_transaction() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO teams (team_id, team_name, route, created_at, leader_squad_id) VALUES (?, ?, ?, ?, ?)",
            (team_id, team_name, route, created_at, leader_squad_id),
        )
        c.execute(
            "UPDATE squads SET team_id = ?, is_team_leader = 1, last_update = ? WHERE squad_id = ?",
            (team_id, created_at, leader_squad_id),
        )