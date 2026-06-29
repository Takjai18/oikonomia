import json
import os
import re

from models.item import team_has_item_by_name
from models.settings import settings
from models.squad import get_team_average_stat


def _encounter_json_path(encounter_id):
    return os.path.join(settings.encounters_dir, f"{encounter_id}.json")


def _read_encounter_file(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _encounter_file_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def load_encounter(encounter_id):
    """Load encounter JSON; cache invalidates when file mtime changes."""
    path = _encounter_json_path(encounter_id)
    if not os.path.isfile(path):
        cache = settings.encounter_cache
        if cache is not None:
            cache.pop(encounter_id, None)
        return None

    if os.environ.get("SKIP_ENCOUNTER_CACHE"):
        return _read_encounter_file(path)

    cache = settings.encounter_cache
    if cache is None:
        return _read_encounter_file(path)

    mtime = _encounter_file_mtime(path)
    if mtime is None:
        return None

    cached = cache.get(encounter_id)
    if isinstance(cached, tuple) and len(cached) == 2:
        cached_mtime, data = cached
        if cached_mtime == mtime:
            return data

    data = _read_encounter_file(path)
    cache[encounter_id] = (mtime, data)
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