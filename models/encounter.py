import json
import os

from models.settings import settings


def load_encounter(encounter_id):
    cache = settings.encounter_cache
    if encounter_id in cache:
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