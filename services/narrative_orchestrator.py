"""
Oikonomia — Narrative & Post-Combat Reward Orchestrator Service
Phase 1.5 Step 3: SSOT Transaction Protection for Story Progression
"""
import json
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from models.encounter import encounter_skips_progression, load_encounter
from models.item import get_item_by_id, get_item_by_qr_code_value
from models.settings import settings
from models.squad import get_team_members
from utils.db_tx import immediate_transaction, with_db_retry
from utils.helpers import normalize_team_id


@dataclass
class StoryProgressionSnapshot:
    team_id: str
    encounter_id: str
    old_stage: int
    new_stage: int
    reward_items_granted: list
    narrative_unlocked: bool
    log_message: str


def _serialize_rewards(rewards):
    if not rewards:
        return None
    return json.dumps(rewards, ensure_ascii=False)


def _resolve_reward_entries(encounter):
    """Map encounter success.rewards to (catalog_item_id, chance) pairs."""
    success = encounter.get("success", {})
    entries = []

    block = success.get("rewards")
    if isinstance(block, dict):
        for raw_id in block.get("item_ids") or []:
            try:
                catalog_id = int(raw_id)
            except (TypeError, ValueError):
                item = get_item_by_qr_code_value(str(raw_id))
                catalog_id = item["id"] if item else None
            if catalog_id:
                entries.append((int(catalog_id), 1.0))
        return entries

    if not isinstance(block, list):
        return entries

    for reward in block:
        if reward.get("type") != "item":
            continue
        ref = reward.get("item_id")
        item = None
        if ref is not None:
            item = get_item_by_qr_code_value(str(ref))
            if not item:
                try:
                    item = get_item_by_id(int(ref))
                except (TypeError, ValueError):
                    item = None
        if item:
            try:
                chance = float(reward.get("chance", 1))
            except (TypeError, ValueError):
                chance = 1.0
            entries.append((int(item["id"]), max(0.0, min(1.0, chance))))
    return entries


def _tx_body(conn, clean_team, encounter, encounter_id, starter_squad_id, now):
    from models.protagonist import get_team_story_stage

    c = conn.cursor()

    already_done = c.execute(
        """SELECT 1 FROM encounter_completions
           WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?)) AND encounter_id = ?""",
        (clean_team, encounter_id),
    ).fetchone()
    if already_done:
        return StoryProgressionSnapshot(
            team_id=clean_team,
            encounter_id=encounter_id,
            old_stage=0,
            new_stage=0,
            reward_items_granted=[],
            narrative_unlocked=False,
            log_message="此遭遇戰前已完成，拒絕重複結算劇情",
        )

    if encounter_skips_progression(encounter):
        return StoryProgressionSnapshot(
            team_id=clean_team,
            encounter_id=encounter_id,
            old_stage=0,
            new_stage=0,
            reward_items_granted=[],
            narrative_unlocked=False,
            log_message="練習遭遇不記錄故事進度",
        )

    success = encounter.get("success", {})
    old_stage = get_team_story_stage(clean_team)
    insight = int(success.get("insight_fragment") or 0)
    unlocks = []
    if success.get("next_story_unlock"):
        unlocks.append(success["next_story_unlock"])

    if insight > 0:
        for member in get_team_members(clean_team):
            row = c.execute(
                "SELECT insight_fragments FROM squads WHERE squad_id = ?",
                (member["squad_id"],),
            ).fetchone()
            if not row:
                continue
            new_val = int(row[0] or 0) + insight
            c.execute(
                "UPDATE squads SET insight_fragments = ? WHERE squad_id = ?",
                (new_val, member["squad_id"]),
            )

    granted_items = []
    granted_meta = []
    owned_count = c.execute(
        "SELECT COUNT(*) FROM player_items WHERE squad_id = ?",
        (starter_squad_id,),
    ).fetchone()[0]
    max_slots = settings.max_inventory_slots

    for catalog_item_id, chance in _resolve_reward_entries(encounter):
        if chance < 1.0 and random.random() > chance:
            continue
        if owned_count >= max_slots:
            break

        dup = c.execute(
            """SELECT COUNT(*) FROM player_items pi
               JOIN squads s ON pi.squad_id = s.squad_id
               WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?)) AND pi.item_id = ?""",
            (clean_team, catalog_item_id),
        ).fetchone()[0]
        if dup > 0:
            continue

        own_dup = c.execute(
            "SELECT 1 FROM player_items WHERE squad_id = ? AND item_id = ?",
            (starter_squad_id, catalog_item_id),
        ).fetchone()
        if own_dup:
            continue

        try:
            c.execute(
                """INSERT INTO player_items (squad_id, item_id, source, obtained_at)
                   VALUES (?, ?, 'combat_reward', ?)""",
                (starter_squad_id, catalog_item_id, now),
            )
        except sqlite3.IntegrityError:
            continue

        granted_items.append(catalog_item_id)
        item_row = c.execute(
            "SELECT name FROM items WHERE id = ?",
            (catalog_item_id,),
        ).fetchone()
        if item_row:
            granted_meta.append({"name": item_row[0], "item_id": catalog_item_id})
        owned_count += 1

    rewards_payload = {
        "insight_fragments": insight,
        "items": granted_meta,
        "unlocks": list(unlocks),
    }
    c.execute(
        """INSERT INTO encounter_completions
           (team_id, encounter_id, outcome, unlocks, narrative, rewards, completed_at)
           VALUES (?, ?, 'success', ?, ?, ?, ?)""",
        (
            clean_team,
            encounter_id,
            json.dumps(unlocks, ensure_ascii=False),
            success.get("narrative"),
            _serialize_rewards(rewards_payload),
            now,
        ),
    )

    new_stage = get_team_story_stage(clean_team)
    title = encounter.get("title") or encounter_id
    log_text = (
        f"🛡️ 隊伍成功通關 [{title}], 發放獎勵物品 ID: {granted_items}。"
        f"故事進度: Stage {old_stage} -> {new_stage}"
    )

    return StoryProgressionSnapshot(
        team_id=clean_team,
        encounter_id=encounter_id,
        old_stage=old_stage,
        new_stage=new_stage,
        reward_items_granted=granted_items,
        narrative_unlocked=(new_stage > old_stage),
        log_message=log_text,
    )


def execute_post_combat_success_pipeline(
    team_id: str,
    encounter_id: str,
    starter_squad_id: str,
) -> StoryProgressionSnapshot:
    """
    權威戰後劇情解鎖管線：在單一 Atomic Transaction 內發放獎勵、解鎖故事階段、寫入遭遇完成誌。
    防禦鎖定：杜絕高延遲環境下重複刷新 API 導致重複獲得物品或重複推進劇情的漏洞。
    """
    clean_team = normalize_team_id(team_id)
    if not clean_team:
        raise ValueError("team_id is required")
    if not starter_squad_id:
        raise ValueError("starter_squad_id is required")

    encounter = load_encounter(encounter_id)
    if not encounter:
        raise ValueError(f"Encounter {encounter_id} not found")

    now = datetime.now().isoformat()
    db_path = settings.db_path

    def _run():
        with immediate_transaction(db_path) as conn:
            return _tx_body(
                conn, clean_team, encounter, encounter_id, starter_squad_id, now,
            )

    return with_db_retry(_run)