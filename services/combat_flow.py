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
    escape_success_rate: Optional[float] = None,
    rng: Optional[float] = None,
) -> Dict[str, Any]:
    """
    INV-E terminal orchestration: escape gate first, then per-attacker engine calls.
    Returns a pure breakdown dict (caller persists to DB).

    If escape_success_rate is None, derive from average resilience of escapers.
    """
    actions = deepcopy(dict(player_actions or {}))
    round_breakdown: Dict[str, Any] = {
        "actions_performed": [],
        "failed_escape_squads": [],
        "damages_dealt": {},
        "damages_taken": {},
        "team_escaped": False,
        "defender_count": 0,
        "escape_success_rate": None,
    }

    escape_intent = [
        sid for sid, act in actions.items()
        if (act.get("action_type") or act.get("action")) == "escape"
    ]

    if escape_intent:
        if escape_success_rate is None:
            from utils.stats_formulas import escape_rate_for_participants
            parts = [
                active_combatants[sid]
                for sid in escape_intent
                if sid in active_combatants
            ]
            escape_success_rate = escape_rate_for_participants(parts, escape_intent)
        escape_success_rate = float(escape_success_rate)
        round_breakdown["escape_success_rate"] = escape_success_rate
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