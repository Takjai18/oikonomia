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

OUTCOME_LABELS = {
    "success": "勝利",
    "failure": "失敗",
    "trauma_bad_ending": "陰影結局",
    "skipped_precheck": "迴避戰鬥",
}

STAT_LABELS = {
    "resilience": "韌性",
    "power": "力量",
    "intellect": "智力",
    "sanity": "神智",
}


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


def _serialize_rewards(rewards):
    if not rewards:
        return None
    return json.dumps(rewards, ensure_ascii=False)


def _parse_rewards(raw):
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def build_reward_lines(rewards, outcome=None):
    """Human-readable reward / penalty lines for UI."""
    rewards = rewards or {}
    lines = []
    insight = int(rewards.get("insight_fragments") or 0)
    if insight > 0:
        lines.append(f"洞察碎片 +{insight}")

    for item in rewards.get("items") or []:
        name = item.get("name") or item.get("item_id") or "物品"
        lines.append(f"獲得物品：{name}")

    for unlock in rewards.get("unlocks") or []:
        lines.append(f"解鎖故事：{unlock}")

    for effect in rewards.get("failure_effects") or []:
        if effect.get("type") == "trauma":
            stat = STAT_LABELS.get(effect.get("stat"), effect.get("stat", ""))
            lines.append(f"{stat}創傷 +{effect.get('amount', 0)}")
        elif effect.get("type") == "sanity_damage":
            lines.append(f"神智 -{effect.get('amount', 0)}")
        elif effect.get("type") == "debuff":
            lines.append(f"狀態：{effect.get('key', '')}")
        elif effect.get("type") == "near_death":
            lines.append("陷入瀕死")

    if outcome == "trauma_bad_ending":
        lines.append("心理創傷過深，無法迎來真正救贖")

    if not lines and outcome == "success":
        lines.append("（無額外獎勵）")
    if not lines and outcome == "failure":
        lines.append("（無額外懲罰記錄）")
    if not lines and outcome == "skipped_precheck":
        lines.append("（迴避戰鬥）")

    return lines


def record_encounter_completion(
    team_id, encounter_id, outcome, unlocks=None, narrative=None, rewards=None,
):
    clean_team_id = normalize_team_id(team_id)
    rewards_payload = dict(rewards or {})
    if unlocks and not rewards_payload.get("unlocks"):
        rewards_payload["unlocks"] = list(unlocks)
    conn = sqlite3.connect(_db())
    conn.execute(
        """INSERT OR REPLACE INTO encounter_completions
           (team_id, encounter_id, outcome, unlocks, narrative, rewards, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            clean_team_id,
            encounter_id,
            outcome,
            json.dumps(unlocks or rewards_payload.get("unlocks") or [], ensure_ascii=False),
            narrative,
            _serialize_rewards(rewards_payload),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def _failure_rewards_from_config(failure):
    effects = []
    if not failure:
        return {"failure_effects": effects}
    trauma = failure.get("trauma") or {}
    amount = int(trauma.get("amount") or 0)
    if amount:
        effects.append({
            "type": "trauma",
            "stat": trauma.get("stat", "resilience"),
            "amount": amount,
        })
    if failure.get("debuff"):
        effects.append({"type": "debuff", "key": failure["debuff"]})
    sanity_dmg = int(failure.get("sanity_damage") or 0)
    if sanity_dmg:
        effects.append({"type": "sanity_damage", "amount": sanity_dmg})
    if failure.get("force_near_death"):
        effects.append({"type": "near_death"})
    return {"failure_effects": effects}


def get_team_encounter_logs(team_id, limit=50):
    clean_team_id = normalize_team_id(team_id)
    if not clean_team_id:
        return []
    from models.encounter import load_encounter

    conn = sqlite3.connect(_db())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT encounter_id, outcome, unlocks, narrative, rewards, completed_at
               FROM encounter_completions
               WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))
               ORDER BY completed_at DESC
               LIMIT ?""",
            (clean_team_id, int(limit)),
        ).fetchall()
    finally:
        conn.close()

    logs = []
    for row in rows:
        enc = load_encounter(row["encounter_id"]) or {}
        rewards = _parse_rewards(row["rewards"])
        if not rewards.get("unlocks"):
            try:
                rewards["unlocks"] = json.loads(row["unlocks"] or "[]")
            except (json.JSONDecodeError, TypeError):
                rewards["unlocks"] = []
        outcome = row["outcome"]
        logs.append({
            "encounter_id": row["encounter_id"],
            "title": enc.get("title") or row["encounter_id"],
            "outcome": outcome,
            "outcome_label": OUTCOME_LABELS.get(outcome, outcome),
            "narrative": row["narrative"],
            "completed_at": row["completed_at"],
            "rewards": rewards,
            "reward_lines": build_reward_lines(rewards, outcome=outcome),
        })
    return logs


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
    insight = int(success.get("insight_fragment", 0))
    add_insight_fragments(team_id, insight)
    unlocks = []
    if success.get("next_story_unlock"):
        unlocks.append(success["next_story_unlock"])
    rewards = {
        "insight_fragments": insight,
        "items": [],
        "unlocks": list(unlocks),
    }
    for reward in success.get("rewards", []):
        if reward.get("type") == "item" and random.random() <= float(reward.get("chance", 1)):
            item = get_item_by_qr_code_value(reward.get("item_id"))
            if item and started_by:
                ok, _, _ = grant_item_to_squad(started_by, item["id"], source="encounter")
                if ok:
                    rewards["items"].append({
                        "name": item.get("name"),
                        "item_id": item.get("id"),
                    })
    record_encounter_completion(
        team_id,
        encounter["encounter_id"],
        "success",
        unlocks=unlocks,
        narrative=success.get("narrative"),
        rewards=rewards,
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
        rewards=_failure_rewards_from_config(failure),
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
        rewards={"failure_effects": [], "note": "trauma_bad_ending"},
    )
    record_team_ending(team_id, "bad_ending", source=encounter.get("encounter_id"))


def apply_precheck_skip(team_id, encounter):
    skip = encounter.get("precheck", {}).get("skip_reward", {})
    insight = int(skip.get("insight_fragment", 0))
    add_insight_fragments(team_id, insight)
    record_encounter_completion(
        team_id,
        encounter["encounter_id"],
        "skipped_precheck",
        narrative=skip.get("narrative"),
        rewards={"insight_fragments": insight},
    )