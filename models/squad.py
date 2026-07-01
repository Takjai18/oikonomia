import json
import sqlite3
from datetime import datetime

from models.settings import default_protagonist_template, settings
from utils.helpers import normalize_team_id
from utils.validators import parse_status_effects


def is_near_death_active(squad):
    until = (squad or {}).get("near_death_until")
    if not until:
        return False
    try:
        return datetime.now() < datetime.fromisoformat(until)
    except ValueError:
        return False


def _bulk_team_routes(team_ids):
    ids = [normalize_team_id(tid) for tid in dict.fromkeys(team_ids) if tid]
    if not ids:
        return {}
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT team_id, route FROM teams WHERE team_id IN ({placeholders})",
            ids,
        ).fetchall()
        return {
            normalize_team_id(row["team_id"]): row["route"]
            for row in rows
            if row["route"] in ("iggy", "marah")
        }
    finally:
        conn.close()


def apply_authoritative_route(squad, team_routes=None):
    if not squad:
        return squad
    team_id = squad.get("team_id")
    if not team_id:
        return squad
    clean_id = normalize_team_id(team_id)
    route = (team_routes or {}).get(clean_id)
    if route in ("iggy", "marah"):
        squad["route"] = route
    return squad

DEFAULT_MAX_HP = 100
HP_STAT_CEILING = 999


def squad_max_hp(squad):
    """Effective HP ceiling for a squad (defaults to 100, never below current hp)."""
    if not squad:
        return DEFAULT_MAX_HP
    hp = int(squad.get("hp") or 0)
    max_hp = int(squad.get("max_hp") or DEFAULT_MAX_HP)
    return max(max_hp, hp, DEFAULT_MAX_HP)


def apply_hp_change(hp, max_hp, delta):
    """Apply HP delta; positive deltas raise max_hp so players can exceed 100."""
    hp = int(hp or 0)
    max_hp = int(max_hp or DEFAULT_MAX_HP)
    try:
        delta = int(delta)
    except (TypeError, ValueError):
        return hp, max_hp
    if delta > 0:
        max_hp = min(HP_STAT_CEILING, max_hp + delta)
        hp = min(max_hp, hp + delta)
    else:
        hp = max(0, hp + delta)
    return hp, max_hp


def row_to_squad(row):
    d = dict(row)
    protagonist = default_protagonist_template()
    if d.get("protagonist_stats"):
        try:
            protagonist = json.loads(d["protagonist_stats"])
        except (json.JSONDecodeError, TypeError):
            pass

    squad = {
        "squad_id": d["squad_id"],
        "display_name": d.get("display_name") or d["squad_id"],
        "sanity": d.get("sanity", 50),
        "hp": d.get("hp", 100),
        "max_hp": d.get("max_hp", DEFAULT_MAX_HP),
        "power": d.get("power", 100),
        "intellect": d.get("intellect", 100),
        "resilience": d.get("resilience", 100),
        "resources": d.get("resources", 0),
        "zoo_skills": json.loads(d["zoo_skills"]) if d.get("zoo_skills") else [],
        "route": d.get("route"),
        "team_id": d.get("team_id"),
        "is_team_leader": 1 if d.get("is_team_leader") else 0,
        "has_pin": bool(d.get("pin")),
        "avatar": d.get("avatar"),
        "insight_fragments": d.get("insight_fragments") or 0,
        "status_effects": parse_status_effects(d.get("status_effects")),
        "trauma_resilience": d.get("trauma_resilience") or 0,
        "trauma_power": d.get("trauma_power") or 0,
        "trauma_intellect": d.get("trauma_intellect") or 0,
        "near_death_until": d.get("near_death_until"),
        "current_combat_id": d.get("current_combat_id"),
        "stats_allocated": 1 if d.get("stats_allocated") else 0,
        "protagonist": protagonist,
    }
    squad["max_hp"] = squad_max_hp(squad)
    return squad


def fetch_squads_by_ids(squad_ids):
    ids = [sid for sid in dict.fromkeys(squad_ids) if sid]
    if not ids:
        return {}
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM squads WHERE squad_id IN ({placeholders})",
            ids,
        ).fetchall()
        return {row["squad_id"]: row_to_squad(row) for row in rows}
    finally:
        conn.close()


def get_squad(squad_id):
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM squads WHERE squad_id = ?", (squad_id,)).fetchone()
    conn.close()

    if not row:
        return None

    squad = row_to_squad(row)

    if squad.get("team_id"):
        from models.team import get_team_protagonists, official_squad_route

        clean_team_id = normalize_team_id(squad["team_id"])
        conn = sqlite3.connect(settings.db_path)
        conn.row_factory = sqlite3.Row
        team_row = conn.execute(
            "SELECT route, leader_squad_id FROM teams WHERE team_id = ?",
            (clean_team_id,),
        ).fetchone()
        conn.close()

        if team_row:
            squad = apply_authoritative_route(
                squad,
                {clean_team_id: team_row["route"]},
            )
            if team_row["leader_squad_id"] == squad["squad_id"]:
                squad["is_team_leader"] = 1
            squad["protagonists"] = get_team_protagonists(clean_team_id)

        route = official_squad_route(squad)
        if route:
            squad["route"] = route

    return squad


def update_squad(squad_id, **kwargs):
    allowed = {
        "sanity", "hp", "max_hp", "power", "intellect", "resilience", "resources", "route",
        "protagonist_stats", "team_id", "is_team_leader", "display_name", "pin",
        "avatar", "insight_fragments", "status_effects",
        "trauma_resilience", "trauma_power", "trauma_intellect",
        "near_death_until", "current_combat_id", "stats_allocated",
    }
    conn = sqlite3.connect(settings.db_path)
    c = conn.cursor()
    updates = []
    params = []
    if "hp" in kwargs and kwargs["hp"] is not None:
        try:
            new_hp = int(kwargs["hp"])
        except (TypeError, ValueError):
            new_hp = None
        if new_hp is not None:
            current = get_squad(squad_id) or {}
            current_max = squad_max_hp(current)
            if new_hp > current_max:
                kwargs["max_hp"] = min(HP_STAT_CEILING, new_hp)
            kwargs["hp"] = max(0, new_hp)

    for key, val in kwargs.items():
        if key not in allowed:
            continue
        if key in ("pin", "current_combat_id", "near_death_until") and val is None:
            updates.append(f"{key} = NULL")
        elif val is not None:
            updates.append(f"{key} = ?")
            params.append(val)
    if updates:
        updates.append("last_update = ?")
        params.append(datetime.now().isoformat())
        params.append(squad_id)
        try:
            c.execute(f"UPDATE squads SET {', '.join(updates)} WHERE squad_id = ?", params)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    conn.close()


def get_all_squads():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM squads ORDER BY squad_id").fetchall()
    conn.close()
    squads = [row_to_squad(r) for r in rows]
    team_routes = _bulk_team_routes(s["team_id"] for s in squads if s.get("team_id"))
    return [apply_authoritative_route(s, team_routes) for s in squads]


def get_team_members(team_id):
    if not team_id:
        return []
    clean_team_id = normalize_team_id(team_id)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))",
        (clean_team_id,),
    ).fetchall()
    conn.close()
    team_routes = _bulk_team_routes([clean_team_id])
    return [apply_authoritative_route(row_to_squad(r), team_routes) for r in rows]


def get_team_average_stat(team_id, stat):
    members = get_team_members(team_id)
    if not members:
        return 0
    values = [int(m.get(stat) or 0) for m in members]
    return sum(values) / len(values)