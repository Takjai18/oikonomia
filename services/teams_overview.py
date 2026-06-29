"""GM team listings and combat overview builders."""
import sqlite3

from models.combat import get_combat_participants, row_to_combat
from models.encounter import load_encounter
from models.settings import settings
from models.squad import get_squad
from models.team import get_team_by_id
from services.story import _parse_distinct_task_row, resolve_story_stage
from utils.helpers import normalize_team_id


def query_teams_list(current_team_id=None):
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT t.team_id, t.team_name, t.route, t.created_at,
               COUNT(s.squad_id) AS member_count
        FROM teams t
        LEFT JOIN squads s ON UPPER(TRIM(s.team_id)) = UPPER(TRIM(t.team_id))
        GROUP BY t.team_id
        ORDER BY t.created_at DESC
        """
    ).fetchall()
    conn.close()

    current_clean = normalize_team_id(current_team_id) if current_team_id else None
    return [
        {
            "team_id": row["team_id"],
            "team_name": row["team_name"],
            "route": row["route"],
            "created_at": row["created_at"],
            "member_count": row["member_count"],
            "is_joined": row["team_id"] == current_clean,
        }
        for row in rows
    ]


def get_all_teams_with_stats():
    return query_teams_list()


def _bulk_submission_stats_by_team(conn):
    rows = conn.execute("""
        SELECT UPPER(TRIM(s.team_id)) AS team_key,
               COUNT(*) AS total,
               MAX(sub.timestamp) AS last_ts
        FROM submissions sub
        INNER JOIN squads s ON s.squad_id = sub.squad_id
        WHERE s.team_id IS NOT NULL AND TRIM(s.team_id) != ''
        GROUP BY team_key
    """).fetchall()
    return {
        row["team_key"]: {"total": row["total"], "last_ts": row["last_ts"]}
        for row in rows
    }


def _bulk_distinct_tasks_by_team(conn):
    rows = conn.execute("""
        SELECT UPPER(TRIM(s.team_id)) AS team_key,
               COUNT(DISTINCT sub.task_id) AS distinct_count,
               GROUP_CONCAT(DISTINCT sub.task_id) AS task_list
        FROM submissions sub
        INNER JOIN squads s ON s.squad_id = sub.squad_id
        WHERE s.team_id IS NOT NULL AND TRIM(s.team_id) != ''
        GROUP BY team_key
    """).fetchall()
    return {row["team_key"]: _parse_distinct_task_row(row) for row in rows}


def _bulk_submission_stats_by_squad(conn):
    rows = conn.execute("""
        SELECT sub.squad_id, COUNT(*) AS total, MAX(sub.timestamp) AS last_ts
        FROM submissions sub
        INNER JOIN squads s ON s.squad_id = sub.squad_id
        WHERE s.team_id IS NULL OR TRIM(s.team_id) = ''
        GROUP BY sub.squad_id
    """).fetchall()
    return {
        row["squad_id"]: {"total": row["total"], "last_ts": row["last_ts"]}
        for row in rows
    }


def _bulk_distinct_tasks_by_squad(conn):
    rows = conn.execute("""
        SELECT sub.squad_id,
               COUNT(DISTINCT sub.task_id) AS distinct_count,
               GROUP_CONCAT(DISTINCT sub.task_id) AS task_list
        FROM submissions sub
        INNER JOIN squads s ON s.squad_id = sub.squad_id
        WHERE s.team_id IS NULL OR TRIM(s.team_id) = ''
        GROUP BY sub.squad_id
    """).fetchall()
    return {row["squad_id"]: _parse_distinct_task_row(row) for row in rows}


def build_teams_overview():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        team_rows = conn.execute("""
            SELECT
                t.team_id,
                t.team_name,
                t.route,
                t.leader_squad_id,
                t.created_at,
                COUNT(s.squad_id) AS member_count,
                COALESCE(ROUND(AVG(s.hp)), 0) AS avg_hp,
                COALESCE(ROUND(AVG(s.sanity)), 0) AS avg_sanity,
                COALESCE(ROUND(AVG(s.power)), 0) AS avg_power,
                COALESCE(ROUND(AVG(s.intellect)), 0) AS avg_intellect,
                COALESCE(ROUND(AVG(s.resilience)), 0) AS avg_resilience,
                COALESCE(ROUND(AVG(s.resources)), 0) AS avg_resources
            FROM teams t
            LEFT JOIN squads s
                ON UPPER(TRIM(s.team_id)) = UPPER(TRIM(t.team_id))
            GROUP BY t.team_id
            ORDER BY t.created_at DESC
        """).fetchall()
        member_rows = conn.execute("""
            SELECT * FROM squads
            WHERE team_id IS NOT NULL AND TRIM(team_id) != ''
        """).fetchall()
        unassigned_rows = conn.execute("""
            SELECT * FROM squads
            WHERE team_id IS NULL OR TRIM(team_id) = ''
            ORDER BY COALESCE(display_name, squad_id)
        """).fetchall()

        members_by_team = {}
        for member in member_rows:
            members_by_team.setdefault(
                normalize_team_id(member["team_id"]), []
            ).append(member)

        submission_stats_by_team = _bulk_submission_stats_by_team(conn)
        task_stats_by_team = _bulk_distinct_tasks_by_team(conn)
        submission_stats_by_squad = _bulk_submission_stats_by_squad(conn)
        task_stats_by_squad = _bulk_distinct_tasks_by_squad(conn)

        route_labels = {"iggy": "🔥 Iggy", "marah": "🌊 Marah"}
        teams = []
        for team_row in team_rows:
            team_id = team_row["team_id"]
            clean_id = normalize_team_id(team_id)
            members = members_by_team.get(clean_id, [])

            leader_id = team_row["leader_squad_id"]
            leader_name = None
            if leader_id:
                for member in members:
                    if member["squad_id"] == leader_id:
                        leader_name = member["display_name"] or member["squad_id"]
                        break

            distinct_tasks, task_ids = task_stats_by_team.get(clean_id, (0, set()))
            story_stage = resolve_story_stage(distinct_tasks, task_ids)
            sub_stats = submission_stats_by_team.get(clean_id, {})
            route = team_row["route"]
            teams.append({
                "team_id": team_id,
                "team_name": team_row["team_name"],
                "route": route,
                "route_label": route_labels.get(route, "未選路線"),
                "leader_squad_id": leader_id,
                "leader_name": leader_name or "未設定",
                "member_count": team_row["member_count"] or 0,
                "avg_hp": int(team_row["avg_hp"] or 0),
                "avg_sanity": int(team_row["avg_sanity"] or 0),
                "avg_power": int(team_row["avg_power"] or 0),
                "avg_intellect": int(team_row["avg_intellect"] or 0),
                "avg_resilience": int(team_row["avg_resilience"] or 0),
                "avg_resources": int(team_row["avg_resources"] or 0),
                "distinct_tasks": distinct_tasks,
                "story_stage": story_stage,
                "submission_count": sub_stats.get("total", 0),
                "last_submission": sub_stats.get("last_ts"),
                "members": [
                    {
                        "squad_id": m["squad_id"],
                        "display_name": m["display_name"] or m["squad_id"],
                        "hp": m["hp"],
                        "sanity": m["sanity"],
                        "power": m["power"],
                        "intellect": m["intellect"],
                        "resilience": m["resilience"],
                        "is_leader": 1 if leader_id and m["squad_id"] == leader_id else 0,
                    }
                    for m in members
                ],
            })

        solo_players = []
        for row in unassigned_rows:
            squad_id = row["squad_id"]
            distinct_tasks, task_ids = task_stats_by_squad.get(squad_id, (0, set()))
            sub_stats = submission_stats_by_squad.get(squad_id, {})
            solo_players.append({
                "squad_id": squad_id,
                "display_name": row["display_name"] or squad_id,
                "route": row["route"],
                "route_label": route_labels.get(row["route"], "未選路線"),
                "hp": row["hp"],
                "sanity": row["sanity"],
                "power": row["power"],
                "intellect": row["intellect"],
                "resilience": row["resilience"],
                "resources": row["resources"],
                "distinct_tasks": distinct_tasks,
                "story_stage": resolve_story_stage(distinct_tasks, task_ids),
                "submission_count": sub_stats.get("total", 0),
                "last_submission": sub_stats.get("last_ts"),
            })

        return {"teams": teams, "solo_players": solo_players}
    finally:
        conn.close()


def build_active_combats_overview():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM combats WHERE status NOT IN ('ended') ORDER BY id DESC"
    ).fetchall()
    conn.close()

    combats = []
    for row in rows:
        combat = row_to_combat(row)
        encounter = load_encounter(combat["encounter_id"])
        squad = get_squad(combat["squad_id"])
        team_id = squad.get("team_id") if squad else None
        team = get_team_by_id(team_id) if team_id else None
        participants = get_combat_participants(combat)
        phase_actions = combat.get("phase_actions") or {}

        combats.append({
            "combat_id": combat["id"],
            "encounter_id": combat["encounter_id"],
            "title": (encounter or {}).get("title", combat["encounter_id"]),
            "status": combat.get("status"),
            "current_phase": combat.get("current_phase", 0),
            "enemy_name": combat.get("enemy_name"),
            "enemy_hp": combat.get("enemy_hp"),
            "enemy_max_hp": combat.get("enemy_max_hp"),
            "team_id": team_id,
            "team_name": (team or {}).get("team_name"),
            "submitted_count": len(phase_actions),
            "participant_count": len(participants),
            "can_resolve": combat.get("status") == "player_phase",
            "phase_deadline": combat.get("phase_deadline"),
        })
    return combats