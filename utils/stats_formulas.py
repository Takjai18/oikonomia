"""Shared player stat formulas (resilience → HP / escape)."""
from __future__ import annotations

from typing import Iterable, Mapping, Optional, Sequence, Tuple, Union

# Allocation base after character create (power / resilience start at 10).
BASE_RESILIENCE = 10
BASE_MAX_HP = 100
# Each point of resilience above base adds this many max HP (and current HP when raised).
HP_PER_RESILIENCE_ABOVE_BASE = 2
MAX_HP_CEILING = 999

# Escape: rate = base + resilience * per_point, clamped.
ESCAPE_RATE_BASE = 0.20
ESCAPE_RATE_PER_RESILIENCE = 0.012
ESCAPE_RATE_FLOOR = 0.15
ESCAPE_RATE_CAP = 0.90


def resilience_hp_bonus(resilience: Union[int, float, None]) -> int:
    """Extra max HP from resilience above the allocation base (10)."""
    try:
        r = int(resilience or 0)
    except (TypeError, ValueError):
        r = 0
    return max(0, r - BASE_RESILIENCE) * HP_PER_RESILIENCE_ABOVE_BASE


def max_hp_from_resilience(resilience: Union[int, float, None]) -> int:
    """Canonical max HP for a given resilience (no item overflow)."""
    return min(MAX_HP_CEILING, BASE_MAX_HP + resilience_hp_bonus(resilience))


def delta_max_hp_for_resilience_change(
    old_resilience: Union[int, float, None],
    new_resilience: Union[int, float, None],
) -> int:
    return resilience_hp_bonus(new_resilience) - resilience_hp_bonus(old_resilience)


def apply_resilience_change_to_hp(
    current_hp: Union[int, float, None],
    current_max_hp: Union[int, float, None],
    old_resilience: Union[int, float, None],
    new_resilience: Union[int, float, None],
) -> Tuple[int, int]:
    """Adjust hp / max_hp when resilience changes.

    Raising resilience increases max_hp and current hp by the same bonus delta.
    Lowering resilience shrinks max_hp and clamps current hp.
    Preserves extra max_hp above the pure formula (e.g. from hp_up items) by
    applying only the resilience-component delta.
    """
    try:
        hp = int(current_hp or 0)
    except (TypeError, ValueError):
        hp = 0
    try:
        max_hp = int(current_max_hp or BASE_MAX_HP)
    except (TypeError, ValueError):
        max_hp = BASE_MAX_HP

    delta = delta_max_hp_for_resilience_change(old_resilience, new_resilience)
    max_hp = min(MAX_HP_CEILING, max(1, max_hp + delta))
    if delta > 0:
        hp = min(max_hp, hp + delta)
    else:
        hp = min(max_hp, max(0, hp))
    # Floor: max_hp never below pure resilience formula.
    formula_max = max_hp_from_resilience(new_resilience)
    if max_hp < formula_max:
        gain = formula_max - max_hp
        max_hp = formula_max
        hp = min(max_hp, hp + gain)
    return hp, max_hp


def escape_success_rate_from_resilience(
    resilience: Union[int, float, None],
    *,
    base: float = ESCAPE_RATE_BASE,
    per_point: float = ESCAPE_RATE_PER_RESILIENCE,
    floor: float = ESCAPE_RATE_FLOOR,
    cap: float = ESCAPE_RATE_CAP,
) -> float:
    """Chance (0–1) to successfully flee; higher resilience → higher chance."""
    try:
        r = float(resilience or 0)
    except (TypeError, ValueError):
        r = 0.0
    rate = base + r * per_point
    return max(floor, min(cap, rate))


def average_resilience(values: Optional[Iterable[Union[int, float, None]]]) -> float:
    nums = []
    for v in values or []:
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            continue
    if not nums:
        return float(BASE_RESILIENCE)
    return sum(nums) / len(nums)


def escape_rate_for_participants(
    participants: Sequence[Mapping],
    escapers: Optional[Sequence[str]] = None,
    *,
    combat_settings: Optional[Mapping] = None,
) -> float:
    """Team escape rate from average effective resilience of escaping members.

    If combat_settings explicitly sets escape_success_rate, that value wins
    (encounter designers can still hard-code a rate).
    """
    settings = combat_settings or {}
    if "escape_success_rate" in settings and settings.get("escape_success_rate") is not None:
        try:
            return max(0.0, min(1.0, float(settings["escape_success_rate"])))
        except (TypeError, ValueError):
            pass

    by_id = {
        str(p.get("squad_id") or ""): p
        for p in (participants or [])
        if p and p.get("squad_id")
    }
    if escapers:
        pool = [by_id[s] for s in escapers if s in by_id]
    else:
        pool = list(by_id.values())
    if not pool:
        pool = list(participants or [])

    res_vals = []
    for p in pool:
        # Prefer effective resilience if trauma already applied upstream.
        try:
            res_vals.append(int(p.get("resilience") or BASE_RESILIENCE))
        except (TypeError, ValueError):
            res_vals.append(BASE_RESILIENCE)
    return escape_success_rate_from_resilience(average_resilience(res_vals))
