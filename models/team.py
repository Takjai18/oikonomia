import json
import sqlite3

from models.settings import settings
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
    conn = sqlite3.connect(settings.db_path)
    try:
        c = conn.cursor()
        c.execute("UPDATE teams SET route = ? WHERE team_id = ?", (route, clean_id))
        c.execute(
            "UPDATE squads SET route = ? WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))",
            (route, clean_id),
        )
        conn.commit()
    finally:
        conn.close()


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
        "member_count": row["member_count"],
    }


def get_team_protagonists(team_id):
    clean_team_id = normalize_team_id(team_id)
    default = settings.default_protagonist.copy()
    if not clean_team_id:
        return {
            "iggy": default.copy(),
            "marah": default.copy(),
            "active_route": None,
        }

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    team_row = conn.execute(
        "SELECT route, leader_squad_id FROM teams WHERE team_id = ?", (clean_team_id,)
    ).fetchone()
    if not team_row:
        conn.close()
        return {
            "iggy": default.copy(),
            "marah": default.copy(),
            "active_route": None,
        }

    route = team_row["route"]
    leader_id = team_row["leader_squad_id"]
    if leader_id:
        squad_row = conn.execute(
            "SELECT protagonist_stats FROM squads WHERE squad_id = ?", (leader_id,)
        ).fetchone()
    else:
        squad_row = conn.execute(
            "SELECT protagonist_stats FROM squads WHERE team_id = ? LIMIT 1",
            (clean_team_id,),
        ).fetchone()
    conn.close()

    protagonist = default.copy()
    if squad_row and squad_row["protagonist_stats"]:
        try:
            protagonist = json.loads(squad_row["protagonist_stats"])
        except (json.JSONDecodeError, TypeError):
            pass

    iggy = default.copy()
    marah = default.copy()
    if route == "iggy":
        iggy = protagonist
    elif route == "marah":
        marah = protagonist

    return {"iggy": iggy, "marah": marah, "active_route": route}