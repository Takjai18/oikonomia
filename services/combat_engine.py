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
        dice = 1
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