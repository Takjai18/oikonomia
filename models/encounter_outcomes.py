"""Encounter completion, rewards, and failure side effects."""
import json
import random
import sqlite3
from datetime import datetime, timedelta

from models.settings import settings
from models.item import get_item_by_qr_code_value, grant_item_to_squad
from models.squad import get_squad, get_team_members, update_squad
from utils.helpers import normalize_team_id
from utils.validators import parse_status_effects, serialize_status_effects


def _db():
    return settings.db_path


def apply_status_debuff(squad_id, debuff_key):
    squad = get_squad(squad_id)
    if not squad:
        return
    effects = parse_status_effects(squad.get("status_effects"))
    effects[debuff_key] = {"applied_at": datetime.now().isoformat()}
    update_squad(squad_id, status_effects=serialize_status_effects(effects))
    if debuff_key == "resilience_-8_until_healed":
        apply_trauma_on_failure(squad_id, "resilience", 8)

def add_insight_fragments(team_id, amount):
    if not team_id or amount <= 0:
        return
    for member in get_team_members(team_id):
        squad = get_squad(member["squad_id"])
        if squad:
            update_squad(
                member["squad_id"],
                insight_fragments=int(squad.get("insight_fragments") or 0) + amount,
            )

def encounter_already_completed(team_id, encounter_id):
    if not team_id:
        return False
    clean_team_id = normalize_team_id(team_id)
    conn = sqlite3.connect(_db())
    row = conn.execute(
        "SELECT id FROM encounter_completions WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?)) AND encounter_id = ?",
        (clean_team_id, encounter_id),
    ).fetchone()
    conn.close()
    return bool(row)

def record_encounter_completion(team_id, encounter_id, outcome, unlocks=None, narrative=None):
    clean_team_id = normalize_team_id(team_id)
    conn = sqlite3.connect(_db())
    conn.execute(
        """INSERT OR REPLACE INTO encounter_completions
           (team_id, encounter_id, outcome, unlocks, narrative, completed_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            clean_team_id,
            encounter_id,
            outcome,
            json.dumps(unlocks or [], ensure_ascii=False),
            narrative,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()

def apply_trauma_on_failure(squad_id, stat, amount):
    trauma_key = {
        "resilience": "trauma_resilience",
        "power": "trauma_power",
        "intellect": "trauma_intellect",
    }.get(stat)
    if not trauma_key:
        return
    squad = get_squad(squad_id)
    if not squad:
        return
    new_trauma = int(squad.get(trauma_key) or 0) + amount
    update_squad(squad_id, **{trauma_key: new_trauma})

def apply_encounter_success(team_id, encounter, started_by):
    success = encounter.get("success", {})
    add_insight_fragments(team_id, success.get("insight_fragment", 0))
    unlocks = []
    if success.get("next_story_unlock"):
        unlocks.append(success["next_story_unlock"])
    for reward in success.get("rewards", []):
        if reward.get("type") == "item" and random.random() <= float(reward.get("chance", 1)):
            item = get_item_by_qr_code_value(reward.get("item_id"))
            if item and started_by:
                grant_item_to_squad(started_by, item["id"], source="encounter")
    record_encounter_completion(
        team_id,
        encounter["encounter_id"],
        "success",
        unlocks=unlocks,
        narrative=success.get("narrative"),
    )

def apply_failure_side_effects(squad_id, failure):
    """失敗附加效果：trauma、debuff、神智傷害、強制瀕死"""
    if not squad_id or not failure:
        return
    trauma = failure.get("trauma", {})
    stat = trauma.get("stat", "resilience")
    amount = int(trauma.get("amount", 0))
    if amount:
        apply_trauma_on_failure(squad_id, stat, amount)
    if failure.get("debuff"):
        apply_status_debuff(squad_id, failure["debuff"])
    sanity_dmg = int(failure.get("sanity_damage") or 0)
    if sanity_dmg:
        squad = get_squad(squad_id)
        if squad:
            new_sanity = max(0, int(squad.get("sanity") or 0) - sanity_dmg)
            update_squad(squad_id, sanity=new_sanity)
    if failure.get("force_near_death"):
        update_squad(
            squad_id,
            hp=0,
            near_death_until=(datetime.now() + timedelta(minutes=settings.near_death_minutes)).isoformat(),
        )

def apply_encounter_failure(team_id, encounter):
    failure = encounter.get("failure", {})
    for member in get_team_members(team_id):
        apply_failure_side_effects(member["squad_id"], failure)
    record_encounter_completion(
        team_id,
        encounter["encounter_id"],
        "failure",
        narrative=failure.get("narrative"),
    )

def apply_encounter_success_solo(squad_id, encounter):
    success = encounter.get("success", {})
    squad = get_squad(squad_id)
    if squad:
        fragments = int(squad.get("insight_fragments") or 0) + int(success.get("insight_fragment", 0))
        update_squad(squad_id, insight_fragments=fragments)
    for reward in success.get("rewards", []):
        if reward.get("type") == "item" and random.random() <= float(reward.get("chance", 1)):
            item = get_item_by_qr_code_value(reward.get("item_id"))
            if item:
                grant_item_to_squad(squad_id, item["id"], source="encounter")

def apply_encounter_failure_solo(squad_id, encounter):
    apply_failure_side_effects(squad_id, encounter.get("failure", {}))

def apply_trauma_bad_ending_victory(team_id, encounter):
    """Victory in combat but protagonist trauma locks team into bad ending."""
    from models.protagonist import record_team_ending, trauma_bad_ending_narrative

    narrative = trauma_bad_ending_narrative(encounter)
    record_encounter_completion(
        team_id,
        encounter["encounter_id"],
        "trauma_bad_ending",
        unlocks=[],
        narrative=narrative,
    )
    record_team_ending(team_id, "bad_ending", source=encounter.get("encounter_id"))


def apply_precheck_skip(team_id, encounter):
    skip = encounter.get("precheck", {}).get("skip_reward", {})
    add_insight_fragments(team_id, skip.get("insight_fragment", 0))
    record_encounter_completion(
        team_id,
        encounter["encounter_id"],
        "skipped_precheck",
        narrative=skip.get("narrative"),
    )
