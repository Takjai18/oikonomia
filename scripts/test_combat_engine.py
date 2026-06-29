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


def main():
    print("=== Combat engine unit tests ===\n")
    test_calculate_attack_damage_basic()
    test_dice_multiplier_edge_cases()
    test_count_team_defenders()
    test_resolve_round_calculation_with_defend()
    print(f"\n=== 結果：{PASS} 通過 / {FAIL} 失敗 ===\n")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())