import json
import os
import re

from models.item import team_has_item_by_name
from models.settings import settings
from models.squad import get_team_average_stat


def load_encounter(encounter_id):
    # Read-only cache of static JSON files (encounters/*.json).
    # Safe across workers when JSON does not change during the camp.
    # Set SKIP_ENCOUNTER_CACHE=1 to always read from disk (e.g. live GM edits).
    import os
    cache = settings.encounter_cache
    if not os.environ.get("SKIP_ENCOUNTER_CACHE") and encounter_id in cache:
        return cache[encounter_id]
    path = os.path.join(settings.encounters_dir, f"{encounter_id}.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cache[encounter_id] = data
    return data


def list_encounter_ids():
    encounters_dir = settings.encounters_dir
    if not os.path.isdir(encounters_dir):
        return []
    return sorted(
        name[:-5] for name in os.listdir(encounters_dir)
        if name.endswith(".json")
    )


def load_all_encounters():
    return [load_encounter(eid) for eid in list_encounter_ids() if load_encounter(eid)]


def encounter_route_matches(encounter_route, squad_route):
    if not encounter_route or encounter_route == "test":
        return True
    if not squad_route:
        return False
    return encounter_route == squad_route


def evaluate_precheck_condition(condition, team_id):
    if not condition:
        return False
    cond = condition.strip()
    parts = re.split(r"\s+OR\s+", cond, flags=re.I)
    return any(_evaluate_precheck_clause(p.strip(), team_id) for p in parts if p.strip())


def _evaluate_precheck_clause(clause, team_id):
    item_match = re.match(r"has_item\s+'([^']+)'", clause, re.I)
    if item_match:
        return team_has_item_by_name(team_id, item_match.group(1))
    stat_match = re.match(r"average_(\w+)\s*>=\s*(\d+)", clause, re.I)
    if stat_match:
        stat = stat_match.group(1).lower()
        threshold = int(stat_match.group(2))
        squad_attrs = settings.squad_attributes or []
        if stat not in squad_attrs:
            return False
        return get_team_average_stat(team_id, stat) >= threshold
    return False