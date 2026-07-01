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


def test_consume_dry_run_defers_delete():
    from models.item import CombatItemConsumeBatch

    class FakeBatch(CombatItemConsumeBatch):
        def __init__(self):
            self._catalog = {9: {"id": 9, "name": "Test", "has_ability": True, "effect_type": "power_up", "effect_value": 5}}
            self._owned = {("s1", 9)}
            self._consumed = set()
            self._pending = set()

    batch = FakeBatch()
    ok1, item1, err1 = batch.consume_dry_run("s1", 9)
    ok2, _, err2 = batch.consume_dry_run("s1", 9)
    if ok1 and item1 and not ok2 and err2:
        ok("consume_dry_run validates without DB write")
    else:
        fail("consume_dry_run validates without DB write", f"{ok1},{ok2},{err1},{err2}")


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
    test_consume_dry_run_defers_delete()
    test_victory_payload_settlement_id()
    print(f"\n=== 結果：{PASS} 通過 / {FAIL} 失敗 ===\n")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())