"""Iggy (and route protagonist) combat stats grow with mainline progress.

Iggy starts extremely weak (HP 10) after the snow rescue; each mainline milestone
raises max HP / power / resilience / sanity modestly — never overpowered vs
buffed 4-player encounters.
"""

# Ordered mainline milestones that power growth (subset of locations.mainline).
GROWTH_MILESTONES = [
    "act1_supplies",
    "act1_escape",
    "act2_stealth",
    "act2_polis_fight",
    "act3_village_intel",
    "act3_search_iggy",
    "act3_village_battle",
    "albert_ching_1",
    "albert_ching_2",
    "albert_ching_3",
    "act3_choihung_rally",
    "act4_julian_gate",
    "act5_return_camp",
    "act6_savio_gate",
]

# Base after prologue / first meet (near death, but must survive Bubuo tutorial hits).
# base_damage~8 vs res 8 → ~3 dmg/hit; HP 24 allows several hits with team defend.
IGGY_BASE = {
    "max_hp": 24,
    "power": 6,
    "resilience": 8,
    "sanity": 35,
}

# Per milestone completed (soft curve).
IGGY_PER_TIER = {
    "max_hp": 5,
    "power": 2,
    "resilience": 2,
    "sanity": 3,
}

# Soft caps — stay well below player peak (~40 power after alloc).
IGGY_CAPS = {
    "max_hp": 85,
    "power": 42,
    "resilience": 40,
    "sanity": 75,
}

MARAH_BASE = {
    "max_hp": 12,
    "power": 5,
    "resilience": 8,
    "sanity": 40,
}
MARAH_PER_TIER = {
    "max_hp": 5,
    "power": 2,
    "resilience": 2,
    "sanity": 3,
}
MARAH_CAPS = {
    "max_hp": 80,
    "power": 38,
    "resilience": 45,
    "sanity": 80,
}


def count_growth_tier(completed_task_ids):
    done = set(completed_task_ids or [])
    # Branch tasks: either stealth OR polis counts as one Act2 step
    tier = 0
    for mid in GROWTH_MILESTONES:
        if mid in ("act2_stealth", "act2_polis_fight"):
            continue
        if mid in done:
            tier += 1
    if "act2_stealth" in done or "act2_polis_fight" in done:
        tier += 1
    return tier


def _scaled(base, per, caps, tier):
    out = {}
    for k in base:
        val = int(base[k]) + int(per.get(k, 0)) * int(tier)
        out[k] = min(int(caps.get(k, val)), val)
    return out


def compute_protagonist_growth_stats(protagonist_key, completed_task_ids):
    """Return max_hp, power, resilience, sanity for the given key."""
    tier = count_growth_tier(completed_task_ids)
    if protagonist_key == "marah":
        return _scaled(MARAH_BASE, MARAH_PER_TIER, MARAH_CAPS, tier)
    # default iggy
    return _scaled(IGGY_BASE, IGGY_PER_TIER, IGGY_CAPS, tier)


def growth_summary_label(tier):
    return f"成長階段 {tier}/{len(GROWTH_MILESTONES) - 1}"
