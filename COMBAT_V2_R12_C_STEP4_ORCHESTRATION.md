# COMBAT_V2_R12_C_STEP4_ORCHESTRATION（局部審計 · 純計算層與戰後編排）

> **目的**：審計 **Greenfield Step 4** — `combat_engine` 純函式、`combat_flow` INV-E 混合結算、`combat_outcomes` 冪等與 `settlement_id`  
> **日期**：2026-07-01 · **commit**：`0e2fa93`  
> **Baseline**：假設已讀 `COMBAT_V2_AUDIT_BUNDLE.md` + `combat_greenfield_final.md` §1.1 INV-E  
> **生成**：`python3 scripts/build_combat_v2_partial_bundles.py`

---

## 0. 給 Gemini 的指令

**焦點問題**：
1. 逃跑失敗後防禦分母與攻擊結算是否滿足 INV-E？（`normalize_failed_escape_actions` vs `_resolve_player_phase_body`）
2. `calculate_incoming_damage` piercing 10% 是否可被極端 buff 繞過？
3. `resolve_combat_outcome` 冪等閘門 vs 巢狀 transaction 死鎖取捨是否安全？
4. `build_victory_outcome_payload` 的 `settlement_id` 是否單調遞增？

**輸出**：【Critical】→【High/Medium】→【Low】→ 健康度 X/10

---

## 1. 純計算層

"""Pure combat calculation engine (no side effects, no DB, no trauma/ending).

Extracted from models/combat.py calculation helpers for unit testing and
future combat_flow orchestration. Trauma-adjusted stats must already be
reflected on Combatant fields before calling these functions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Union

# Defaults match app.py bootstrap (settings.dice_multipliers / combat_attack_base_damage).
COMBAT_ATTACK_BASE_DAMAGE = 10
DEFEND_TEAM_DAMAGE_FACTOR = 0.5
DEFAULT_DICE_MULTIPLIERS: Dict[int, float] = {0: 0.0, 1: 1.0, 2: 1.5, 3: 2.0}


@dataclass
class Combatant:
    """Simplified combat unit (player squad or enemy)."""

    id: str
    power: int
    intellect: int
    resilience: int
    sanity: int = 100
    item_bonus: int = 0


@dataclass
class RoundResult:
    """Single-round calculation output (data only)."""

    damage_dealt: int
    damage_taken: int
    is_critical: bool
    dice_multiplier: float
    defender_count: int
    notes: List[str] = field(default_factory=list)


def get_effective_attack_stat(combatant: Combatant) -> int:
    """Attack stat used for damage (max of power and intellect)."""
    return max(int(combatant.power), int(combatant.intellect))


def calculate_attack_damage(
    attacker: Combatant,
    enemy_resilience: int,
    multiplier: float = 1.0,
    item_bonus: int = 0,
    base_damage: int = COMBAT_ATTACK_BASE_DAMAGE,
) -> int:
    """Player (or ally) attack damage against an enemy."""
    if multiplier <= 0:
        return 0
    attack_stat = get_effective_attack_stat(attacker)
    bonus = item_bonus if item_bonus else int(attacker.item_bonus or 0)
    raw = ((attack_stat * 1.5) + base_damage + bonus) * multiplier - (int(enemy_resilience) * 0.8)
    return max(1, int(raw))


def calculate_incoming_damage(
    enemy_base_damage: int,
    player_resilience: int,
    defending: bool = False,
    team_defend_multiplier: Optional[float] = None,
    *,
    min_damage_ratio: float = 0.1,
) -> int:
    """Enemy counter damage against a player (10% piercing floor by default)."""
    base = int(enemy_base_damage)
    reduction = math.floor(int(player_resilience) * 0.6)
    damage = base - reduction
    piercing = max(1, math.floor(base * min_damage_ratio))
    damage = max(piercing, damage)

    multiplier = team_defend_multiplier
    if multiplier is None:
        multiplier = DEFEND_TEAM_DAMAGE_FACTOR if defending else 1.0
    if multiplier < 1.0:
        damage = math.floor(damage * multiplier)
    return max(piercing, damage)


def dice_multiplier(
    dice_result: Union[int, str, None],
    dice_multipliers: Optional[Mapping[int, float]] = None,
) -> float:
    """Map server combat dice (0=miss, 1=normal, 2=strong, 3=crit) to multiplier."""
    table = dict(dice_multipliers or DEFAULT_DICE_MULTIPLIERS)
    try:
        dice = int(dice_result)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        dice = 2
    return float(table.get(max(0, min(3, dice)), 1.0))


def count_team_defenders(actions: Optional[Dict[str, Any]]) -> int:
    """Count players who chose defend this phase."""
    if not actions:
        return 0
    return sum(
        1
        for action_data in actions.values()
        if (action_data.get("action_type") or action_data.get("action")) == "defend"
    )


def team_defend_damage_multiplier(defender_count: int) -> float:
    """Team-wide defend damage reduction factor."""
    if defender_count > 0:
        return DEFEND_TEAM_DAMAGE_FACTOR
    return 1.0


def _is_active_combat_participant(participant: Mapping[str, Any]) -> bool:
    if int(participant.get("hp") or 0) <= 0:
        return False
    until = participant.get("near_death_until")
    if until:
        from datetime import datetime

        try:
            if datetime.now() < datetime.fromisoformat(until):
                return False
        except ValueError:
            pass
    return True


def select_enemy_counter_target(
    participants: List[Mapping[str, Any]],
    actions: Mapping[str, Any],
    enemy_base_damage: int,
) -> Optional[Mapping[str, Any]]:
    """
    Enemy counter targeting (Greenfield Spec 1.1) — pure calculation, resolve once per round.
    Priority: one-shot > escaping > HP<50% > trauma > protagonist last.
    """
    candidates = [p for p in participants if _is_active_combat_participant(p)]
    if not candidates:
        return None

    def sort_key(member: Mapping[str, Any]):
        hp = int(member.get("hp") or 0)
        max_hp = max(1, int(member.get("max_hp") or hp or 1))
        sid = member.get("squad_id")
        action_type = (actions.get(sid) or {}).get("action_type") or ""
        trauma = int(member.get("trauma_count") or 0)
        can_oneshot = 1 if int(enemy_base_damage) >= hp else 0
        is_escaping = 1 if action_type == "escape" else 0
        low_hp = 1 if (hp / max_hp) < 0.5 else 0
        has_trauma = 1 if trauma > 0 else 0
        non_protagonist = 0 if member.get("is_protagonist") else 1
        return (can_oneshot, is_escaping, low_hp, has_trauma, non_protagonist)

    candidates.sort(key=sort_key, reverse=True)
    return candidates[0]


def resolve_round_calculation(
    attacker: Combatant,
    enemy: Combatant,
    player_actions: Dict[str, Any],
    enemy_base_damage: int,
    dice_result: int,
    dice_multipliers: Optional[Mapping[int, float]] = None,
) -> RoundResult:
    """Full single-attacker round calculation (no DB / trauma / ending)."""
    mult = dice_multiplier(dice_result, dice_multipliers=dice_multipliers)
    defender_count = count_team_defenders(player_actions)
    team_mult = team_defend_damage_multiplier(defender_count)

    damage_dealt = calculate_attack_damage(
        attacker=attacker,
        enemy_resilience=enemy.resilience,
        multiplier=mult,
        item_bonus=attacker.item_bonus,
    )

    damage_taken = calculate_incoming_damage(
        enemy_base_damage=enemy_base_damage,
        player_resilience=attacker.resilience,
        defending=defender_count > 0,
        team_defend_multiplier=team_mult,
    )

    is_critical = mult > 1.2

    return RoundResult(
        damage_dealt=damage_dealt,
        damage_taken=damage_taken,
        is_critical=is_critical,
        dice_multiplier=mult,
        defender_count=defender_count,
        notes=[],
    )


## 2. Step 4 編排（INV-E）

"""
Step 4 orchestration — mixed-round action pipeline (INV-E).
Delegates math to services.combat_engine; no DB writes here.
"""
from __future__ import annotations

import random
from copy import deepcopy
from typing import Any, Dict, Mapping, Optional

from services.combat_engine import (
    Combatant,
    RoundResult,
    count_team_defenders,
    resolve_round_calculation,
)


def normalize_failed_escape_actions(
    player_actions: Mapping[str, Any],
    *,
    escape_triggered: bool,
    escape_success: bool,
) -> Dict[str, Any]:
    """
    INV-E: after team escape fails, mark escapers as failed_escape.
    They remain in player_actions for defend denominator / targeting but deal no damage.
    """
    actions = dict(player_actions or {})
    if not escape_triggered or escape_success:
        return actions

    for sid, act in list(actions.items()):
        action_type = (act.get("action_type") or act.get("action") or "")
        if action_type == "escape":
            actions[sid] = {
                **act,
                "action_type": "failed_escape",
                "defending": False,
            }
    return actions


def _participant_to_combatant(participant: Mapping[str, Any]) -> Combatant:
    return Combatant(
        id=str(participant.get("squad_id") or ""),
        power=int(participant.get("power") or 0),
        intellect=int(participant.get("intellect") or 0),
        resilience=int(participant.get("resilience") or 0),
        sanity=int(participant.get("sanity") or 0),
        item_bonus=int(participant.get("item_bonus") or 0),
    )


def process_mixed_round_actions(
    active_combatants: Mapping[str, Mapping[str, Any]],
    enemy_stats: Mapping[str, Any],
    player_actions: Mapping[str, Any],
    enemy_base_damage: int,
    *,
    escape_success_rate: float = 0.4,
    rng: Optional[float] = None,
) -> Dict[str, Any]:
    """
    INV-E terminal orchestration: escape gate first, then per-attacker engine calls.
    Returns a pure breakdown dict (caller persists to DB).
    """
    actions = deepcopy(dict(player_actions or {}))
    round_breakdown: Dict[str, Any] = {
        "actions_performed": [],
        "failed_escape_squads": [],
        "damages_dealt": {},
        "damages_taken": {},
        "team_escaped": False,
        "defender_count": 0,
    }

    escape_intent = [
        sid for sid, act in actions.items()
        if (act.get("action_type") or act.get("action")) == "escape"
    ]

    if escape_intent:
        roll = random.random() if rng is None else float(rng)
        if roll < escape_success_rate:
            round_breakdown["team_escaped"] = True
            return round_breakdown

        actions = normalize_failed_escape_actions(
            actions,
            escape_triggered=True,
            escape_success=False,
        )
        round_breakdown["failed_escape_squads"] = list(escape_intent)

    enemy = Combatant(
        id="enemy",
        power=int(enemy_stats.get("power") or 0),
        intellect=int(enemy_stats.get("intellect") or 0),
        resilience=int(enemy_stats.get("resilience") or 0),
    )

    round_breakdown["defender_count"] = count_team_defenders(actions)

    for sid, participant in active_combatants.items():
        if sid == "enemy":
            continue

        action_data = actions.get(sid, {"action_type": "pass"})
        action_type = action_data.get("action_type") or action_data.get("action") or "pass"
        if action_type in ("failed_escape", "escape"):
            round_breakdown["actions_performed"].append({
                "squad_id": sid,
                "action": action_type,
                "damage_dealt": 0,
                "damage_taken": 0,
                "is_critical": False,
            })
            continue

        combatant = _participant_to_combatant(participant)
        dice_result = action_data.get("dice_result", action_data.get("dice", 1))
        calc_result: RoundResult = resolve_round_calculation(
            attacker=combatant,
            enemy=enemy,
            player_actions=actions,
            enemy_base_damage=enemy_base_damage,
            dice_result=dice_result,
        )

        round_breakdown["damages_dealt"][sid] = calc_result.damage_dealt
        round_breakdown["damages_taken"][sid] = calc_result.damage_taken
        round_breakdown["actions_performed"].append({
            "squad_id": sid,
            "action": action_type,
            "damage_dealt": calc_result.damage_dealt,
            "damage_taken": calc_result.damage_taken,
            "is_critical": calc_result.is_critical,
        })

    return round_breakdown

## 3. 生產路徑 escape 接入

# models/combat.py (L979–L1068)

def _resolve_player_phase_body(combat_id):
    combat = get_combat(combat_id)
    if not combat or combat.get("status") != COMBAT_STATUS_RESOLVING:
        _release_player_phase_resolution(combat_id)
        return combat, None

    encounter = load_encounter(combat["encounter_id"])
    combat_settings = (encounter or {}).get("combat_settings", {})
    participants = get_combat_participants(combat)
    participant_by_id = {p["squad_id"]: p for p in participants}
    team_id = _combat_team_id(combat, participants)
    story_stage = get_team_story_stage(team_id) if team_id else 0
    player_control_ids = (
        get_player_control_protagonist_ids(team_id, encounter, story_stage, participants)
        if team_id else []
    )
    actions = inject_protagonist_auto_actions(
        combat.get("phase_actions") or {},
        participants,
        encounter,
        player_control_ids,
    )
    item_consume_batch = build_combat_item_consume_batch(actions)

    enemy_hp = int(combat.get("enemy_hp") or 0)
    enemy_resilience = int(combat.get("enemy_resilience") or 0)
    enemy_sanity = int(combat.get("enemy_sanity") or 0)
    enemy_base_damage = int(combat.get("enemy_base_damage") or 0)
    enemy_name = combat.get("enemy_name") or "敵人"

    escape_triggered = any(
        (a.get("action_type") or a.get("action")) == "escape"
        for a in actions.values()
    )
    if escape_triggered:
        escape_rate = _escape_success_rate(combat_settings)
        if random.random() < escape_rate:
            combat = append_combat_log(
                combat,
                f"全隊逃跑成功！（成功率 {int(escape_rate * 100)}%）",
                log_type="escape_success",
            )
            save_combat(combat_id, logs=combat.get("logs"))
            return _end_combat(combat_id, "escaped", encounter), "escaped"
        combat = append_combat_log(
            combat,
            "全隊逃跑失敗，將繼續結算戰鬥行動",
            log_type="escape_failed",
        )
        actions = normalize_failed_escape_actions(
            actions,
            escape_triggered=True,
            escape_success=False,
        )

    total_damage_to_enemy = 0
    berserk_players = []

    for player_squad_id, action_data in actions.items():
        player = participant_by_id.get(player_squad_id)
        if not player:
            continue
        display = player.get("display_name") or player_squad_id
        sanity = int(player.get("sanity") or 0)

        if int(player.get("hp") or 0) <= 0:
            combat = append_combat_log(
                combat,
                f"{display} 已無法行動",
                log_type="incapacitated",
            )
            continue

        action_type = action_data.get("action_type") or action_data.get("action") or "pass"
        if action_type == "failed_escape":
            combat = append_combat_log(
                combat,
                f"{display} 由於逃跑失敗，本回合陷入破防僵直，無法輸出任何傷害。",
                log_type="failed_escape_stuck",
            )
            continue

        if is_berserk(sanity):
            berserk_players.append(player_squad_id)
            if random.random() < 0.30:
                self_dmg = max(1, int(get_effective_attack_stat(player) * 0.3))
                apply_damage_to_combat_participant(player_squad_id, self_dmg, participant=player)
                combat = append_combat_log(
                    combat,
                    f"{display} 暴走！攻擊自己，造成 {self_dmg} 點傷害",

## 4. 戰後編排與 settlement_id

"""Orchestrate post-combat rewards, trauma, and ending side effects."""
from models.protagonist import trauma_bad_ending_narrative
from services.ending import judge_ending


def _outcome_already_recorded(team_id, encounter_id):
    if not team_id or not encounter_id:
        return False
    from models.encounter_outcomes import encounter_already_completed

    return encounter_already_completed(team_id, encounter_id)


def resolve_combat_outcome(winner, team_id, encounter, starter_id, combat_id=None):
    """
    Post-combat orchestration — idempotency enforced by encounter_completions SSOT.
    No outer with_db_retry: pipeline / completion checks must not race on dirty snapshots.
    """
    from models.encounter_outcomes import (
        apply_encounter_failure,
        apply_encounter_failure_solo,
        apply_encounter_success_solo,
        apply_trauma_bad_ending_victory,
    )
    from services.narrative_orchestrator import execute_post_combat_success_pipeline

    result = {
        "winner": winner,
        "trauma_bad_ending": False,
        "log_messages": [],
        "ending": None,
        "applied_success": False,
        "applied_failure": False,
    }
    if not encounter or not winner:
        return result

    encounter_id = encounter.get("encounter_id")

    if winner == "escaped":
        result["log_messages"].append({
            "message": "全隊成功逃離戰場",
            "log_type": "escape_success",
        })
        return result

    if winner == "squad":
        ending = judge_ending(team_id) if team_id else {}
        result["ending"] = ending
        trauma_total = int(ending.get("protagonist_trauma_total") or 0)

        if team_id and ending.get("should_apply_bad_ending_victory"):
            if not _outcome_already_recorded(team_id, encounter_id):
                apply_trauma_bad_ending_victory(team_id, encounter)
                result["applied_success"] = True
            result["trauma_bad_ending"] = True
            result["log_messages"].append({
                "message": (
                    f"主角心理創傷過深（累計 {trauma_total}）——"
                    "勝利無法帶來真正救贖"
                ),
                "log_type": "trauma_ending",
            })
        elif team_id:
            try:
                snap = execute_post_combat_success_pipeline(
                    team_id, encounter_id, starter_id,
                )
                result["applied_success"] = "拒絕重複" not in snap.log_message
                result["log_messages"].append({
                    "message": snap.log_message,
                    "log_type": "story_progression",
                })
            except Exception as exc:
                result["log_messages"].append({
                    "message": f"劇情推進管線觸發等冪保護: {exc}",
                    "log_type": "idempotent_blocked",
                })
        elif starter_id and not _outcome_already_recorded(starter_id, encounter_id):
            apply_encounter_success_solo(starter_id, encounter)
            result["applied_success"] = True
        return result

    if winner == "enemy":
        id_key = team_id or starter_id
        if id_key and not _outcome_already_recorded(id_key, encounter_id):
            if team_id:
                apply_encounter_failure(team_id, encounter)
                result["applied_failure"] = True
            elif starter_id:
                apply_encounter_failure_solo(starter_id, encounter)
                result["applied_failure"] = True
        if team_id:
            result["ending"] = judge_ending(team_id)
        return result

    return result


def build_victory_outcome_payload(
    encounter,
    team_id=None,
    combat_id=None,
    current_round=0,
):
    """Build JSON payload for combat victory responses (INV-C monotonic fields)."""
    ending = judge_ending(team_id) if team_id else {}
    trauma_bad = bool(ending.get("trauma_bad_ending"))
    safe_combat_id = int(combat_id) if combat_id is not None else 0
    round_idx = max(0, int(current_round or 0))
    settled_round_index = max(0, round_idx - 1)

    payload = {
        "success": True,
        "status": "ended",
        "outcome": "victory",
        "winner": "squad",
        "combat_id": safe_combat_id or None,
        "settled_round_index": settled_round_index,
        "settlement_id": f"{safe_combat_id}:{settled_round_index}",
        "narrative": (encounter or {}).get("success", {}).get("narrative"),
        "reflection_prompt": (encounter or {}).get("reflection_prompt"),
        "ending_condition": ending.get("ending_condition"),
        "protagonist_trauma_total": ending.get("protagonist_trauma_total", 0),
        "trauma_level": ending.get("trauma_level", "safe"),
    }
    if team_id:
        payload["ending"] = ending
        payload["ending_preview"] = ending.get("ending_preview")
    if trauma_bad:
        payload["trauma_bad_ending"] = True
        payload["narrative"] = trauma_bad_ending_narrative(encounter)
        payload["reflection_prompt"] = None
    return payload


def get_collapsed_combat_members(participants):
    """Squads that triggered INV-D (HP≤0 or active near-death)."""
    from models.squad import is_near_death_active

    collapsed = []
    for p in participants or []:
        if not p:
            continue
        if int(p.get("hp") or 0) <= 0 or is_near_death_active(p):
            collapsed.append(p)
    return collapsed


def build_defeat_outcome_payload(encounter, participants=None, team_id=None):
    dead = get_collapsed_combat_members(participants)
    if not dead and team_id:
        from models.squad import get_team_members

        dead = get_collapsed_combat_members(get_team_members(team_id))

    dead_ids = [m.get("squad_id") for m in dead if m.get("squad_id")]
    dead_names = [
        m.get("display_name") or m.get("squad_id")
        for m in dead
        if m.get("squad_id")
    ]
    failure = (encounter or {}).get("failure") or {}

    return {
        "success": True,
        "status": "ended",
        "outcome": "defeat",
        "outcome_type": "COMBAT_FAILED",
        "winner": "enemy",
        "narrative": failure.get("narrative"),
        "narrative_failure": failure.get("narrative")
        or failure.get("description")
        or "隊伍在西貢叢林中倒下了…",
        "requires_gm": True,
        "dead_squad_ids": dead_ids,
        "dead_squad_names": dead_names,
        "active": False,
    }

## 5. 單元測試

#!/usr/bin/env python3
"""Unit tests for services/combat_flow.py (INV-E pure orchestration)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.combat_flow import (
    normalize_failed_escape_actions,
    process_mixed_round_actions,
)

PASS = 0
FAIL = 0


def ok(label):
    global PASS
    PASS += 1
    print(f"  ✓ {label}")


def fail(label, detail=""):
    global FAIL
    FAIL += 1
    print(f"  ✗ {label}" + (f" — {detail}" if detail else ""))


def test_normalize_failed_escape():
    actions = {
        "A": {"action_type": "escape", "dice_result": 1},
        "B": {"action_type": "attack", "dice_result": 2},
    }
    out = normalize_failed_escape_actions(
        actions, escape_triggered=True, escape_success=False,
    )
    if out["A"]["action_type"] == "failed_escape" and out["B"]["action_type"] == "attack":
        ok("normalize_failed_escape marks escaper only")
    else:
        fail("normalize_failed_escape marks escaper only", str(out))


def test_mixed_round_escape_fail_continues_attack():
    participants = {
        "A": {"squad_id": "A", "power": 40, "intellect": 10, "resilience": 10, "sanity": 50},
        "B": {"squad_id": "B", "power": 50, "intellect": 10, "resilience": 10, "sanity": 50},
    }
    actions = {
        "A": {"action_type": "escape", "dice_result": 1},
        "B": {"action_type": "attack", "dice_result": 2},
    }
    breakdown = process_mixed_round_actions(
        participants,
        {"resilience": 5},
        actions,
        enemy_base_damage=20,
        escape_success_rate=0.4,
        rng=0.99,
    )
    if breakdown.get("team_escaped") is False and "A" in breakdown.get("failed_escape_squads", []):
        ok("mixed round escape fail retains escaper in breakdown")
    else:
        fail("mixed round escape fail retains escaper", str(breakdown))

    b_dealt = breakdown.get("damages_dealt", {}).get("B", 0)
    a_dealt = breakdown.get("damages_dealt", {}).get("A", 0)
    if b_dealt > 0 and a_dealt == 0:
        ok("mixed round attacker damage while escaper deals zero")
    else:
        fail("mixed round attacker damage while escaper deals zero", str(breakdown))


def test_victory_payload_settlement_id():
    from services.combat_outcomes import build_victory_outcome_payload

    payload = build_victory_outcome_payload(
        {"success": {"narrative": "win"}},
        combat_id=42,
        current_round=3,
    )
    if payload.get("settlement_id") == "42:2" and payload.get("settled_round_index") == 2:
        ok("victory payload includes settlement_id")
    else:
        fail("victory payload includes settlement_id", str(payload))


def main():
    print("=== Combat flow orchestrator tests ===\n")
    test_normalize_failed_escape()
    test_mixed_round_escape_fail_continues_attack()
    test_victory_payload_settlement_id()
    print(f"\n=== 結果：{PASS} 通過 / {FAIL} 失敗 ===\n")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
#!/usr/bin/env python3
"""Unit tests for services/combat_engine.py (pure calculation, no Flask/DB)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.combat_engine import (
    Combatant,
    calculate_attack_damage,
    calculate_incoming_damage,
    count_team_defenders,
    dice_multiplier,
    resolve_round_calculation,
    select_enemy_counter_target,
    team_defend_damage_multiplier,
)

PASS = 0
FAIL = 0


def ok(label):
    global PASS
    PASS += 1
    print(f"  ✓ {label}")


def fail(label, detail=""):
    global FAIL
    FAIL += 1
    print(f"  ✗ {label}" + (f" — {detail}" if detail else ""))


def test_calculate_attack_damage_basic():
    attacker = Combatant(id="p1", power=60, intellect=40, resilience=50)
    dmg = calculate_attack_damage(attacker, enemy_resilience=30, multiplier=1.0)
    # ((60*1.5)+10)*1 - (30*0.8) = 100 - 24 = 76
    if dmg == 76:
        ok("calculate_attack_damage basic")
    else:
        fail("calculate_attack_damage basic", f"got {dmg}, expected 76")

    miss = calculate_attack_damage(attacker, enemy_resilience=30, multiplier=0.0)
    if miss == 0:
        ok("calculate_attack_damage zero multiplier")
    else:
        fail("calculate_attack_damage zero multiplier", f"got {miss}")


def test_dice_multiplier_edge_cases():
    cases = [(0, 0.0), (1, 1.0), (2, 1.5), (3, 2.0), (99, 2.0), ("bad", 1.5)]
    for dice, expected in cases:
        got = dice_multiplier(dice)
        if got == expected:
            ok(f"dice_multiplier({dice!r})")
        else:
            fail(f"dice_multiplier({dice!r})", f"got {got}, expected {expected}")


def test_resolve_round_calculation_with_defend():
    attacker = Combatant(id="p1", power=50, intellect=50, resilience=40)
    enemy = Combatant(id="e1", power=0, intellect=0, resilience=20)
    actions = {
        "s1": {"action_type": "defend"},
        "s2": {"action_type": "attack"},
    }
    result = resolve_round_calculation(
        attacker=attacker,
        enemy=enemy,
        player_actions=actions,
        enemy_base_damage=50,
        dice_result=2,
    )
    if result.defender_count == 1:
        ok("resolve_round_calculation defender_count")
    else:
        fail("resolve_round_calculation defender_count", str(result.defender_count))

    if result.dice_multiplier == 1.5:
        ok("resolve_round_calculation dice_multiplier")
    else:
        fail("resolve_round_calculation dice_multiplier", str(result.dice_multiplier))

    if result.damage_dealt > 0 and result.is_critical:
        ok("resolve_round_calculation damage_dealt + critical")
    else:
        fail("resolve_round_calculation damage_dealt + critical")

    expected_taken = calculate_incoming_damage(
        50,
        40,
        defending=True,
        team_defend_multiplier=team_defend_damage_multiplier(1),
    )
    if result.damage_taken == expected_taken:
        ok("resolve_round_calculation damage_taken with defend")
    else:
        fail(
            "resolve_round_calculation damage_taken with defend",
            f"got {result.damage_taken}, expected {expected_taken}",
        )


def test_count_team_defenders():
    if count_team_defenders(None) == 0:
        ok("count_team_defenders empty")
    else:
        fail("count_team_defenders empty")
    actions = {"a": {"action": "defend"}, "b": {"action_type": "attack"}}
    if count_team_defenders(actions) == 1:
        ok("count_team_defenders mixed")
    else:
        fail("count_team_defenders mixed")


def test_incoming_damage_piercing_floor():
    dmg = calculate_incoming_damage(50, 200, defending=False)
    if dmg >= 5:
        ok("incoming damage piercing floor (10% of base)")
    else:
        fail("incoming damage piercing floor", f"got {dmg}")


def test_incoming_damage_extreme_team_defend():
    """INV-D: 10% piercing floor survives extreme team-defend multipliers."""
    base = 5
    dmg = calculate_incoming_damage(
        base, 0, team_defend_multiplier=0.001,
    )
    piercing = max(1, base // 10)
    if dmg >= piercing and dmg > 0:
        ok("incoming damage extreme defend cannot zero out piercing")
    else:
        fail("incoming damage extreme defend cannot zero out piercing", f"got {dmg}")


def test_select_enemy_counter_target_engine():
    participants = [
        {"squad_id": "A", "hp": 80, "max_hp": 100, "resilience": 5, "is_protagonist": False},
        {"squad_id": "B", "hp": 30, "max_hp": 100, "resilience": 3, "is_protagonist": False},
    ]
    actions = {"B": {"action_type": "escape"}}
    target = select_enemy_counter_target(participants, actions, enemy_base_damage=50)
    if target and target.get("squad_id") == "B":
        ok("select_enemy_counter_target prefers escaper")
    else:
        fail("select_enemy_counter_target prefers escaper", str(target))


def main():
    print("=== Combat engine unit tests ===\n")
    test_calculate_attack_damage_basic()
    test_dice_multiplier_edge_cases()
    test_count_team_defenders()
    test_resolve_round_calculation_with_defend()
    test_incoming_damage_piercing_floor()
    test_incoming_damage_extreme_team_defend()
    test_select_enemy_counter_target_engine()
    print(f"\n=== 結果：{PASS} 通過 / {FAIL} 失敗 ===\n")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

---
*End of R12-C · 2026-07-01*
