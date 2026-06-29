#!/usr/bin/env python3
"""P1: 本地 combat 全流程測試（Team + Iggy → enc_iggy_01_leech）"""
import os
import shutil
import sys
import tempfile
from unittest.mock import patch

# 使用獨立測試 DB，避免污染本機 oikonomia.db
TEST_DIR = tempfile.mkdtemp(prefix="oikonomia_combat_test_")
os.environ["DATA_DIR"] = TEST_DIR

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as oikonomia  # noqa: E402
from models.combat import (
    calculate_incoming_damage,
    count_team_defenders,
    get_combat,
    get_combat_participants,
    team_defend_damage_multiplier,
)
from models.squad import apply_hp_change, get_squad, squad_max_hp, update_squad
from models.item import apply_item_effect_to_squad

oikonomia.init_db()
oikonomia.migrate_db()

ENCOUNTER_ID = "enc_iggy_01_leech"
TEST_ENCOUNTER_ID = "test_combat_01"
PASS = 0
FAIL = 0
MAX_FIGHT_ROUNDS = 8


def ok(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}" + (f" — {detail}" if detail else ""))


def login(client, name):
    r = client.post("/login", data={"squad_id": name})
    return r.get_json()


def submit_attack(client, combat_id):
    """Submit attack; server rolls dice (client dice_result is ignored)."""
    return client.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "attack"},
        content_type="application/json",
    )


def test_protagonist_combat_participant(combat_id, route="iggy"):
    combat = get_combat(combat_id)
    participants = get_combat_participants(combat) if combat else []
    pros = [p for p in participants if p.get("is_protagonist")]
    ok("protagonist joins combat", len(pros) >= 1, f"found {len(pros)}")
    if pros:
        ok(
            f"route protagonist is {route}",
            any(p.get("protagonist_key") == route for p in pros),
            str([p.get("protagonist_key") for p in pros]),
        )
        ok("protagonist has hp", int(pros[0].get("hp") or 0) > 0)


def test_player_max_hp(leader_id):
    """HP ceiling can exceed 100 via boosts."""
    hp, max_hp = apply_hp_change(100, 100, 20)
    ok("hp boost raises max above 100", max_hp == 120 and hp == 120, f"{hp}/{max_hp}")
    hp2, max_hp2 = apply_hp_change(80, 120, 0)
    ok("damage does not lower max_hp", max_hp2 == 120 and hp2 == 80, f"{hp2}/{max_hp2}")

    update_squad(leader_id, hp=90, max_hp=100)
    applied = apply_item_effect_to_squad(leader_id, {
        "has_ability": 1,
        "effect_type": "hp_up",
        "effect_value": 25,
    })
    squad = get_squad(leader_id) or {}
    ok("hp_up item raises max_hp", applied and int(squad.get("max_hp") or 0) == 125, str(squad))
    ok("hp_up item heals to new cap", int(squad.get("hp") or 0) == 115, str(squad))
    ok("squad_max_hp helper", squad_max_hp(squad) == 125)


def test_defend_team_buff_helpers():
    """Unit checks for Defend team-wide damage reduction."""
    actions = {
        "a": {"action_type": "attack"},
        "b": {"action_type": "defend"},
    }
    ok("count_team_defenders", count_team_defenders(actions) == 1)
    ok("team_defend_multiplier", team_defend_damage_multiplier(1) == 0.5)
    ok("no defend multiplier", team_defend_damage_multiplier(0) == 1.0)
    base = calculate_incoming_damage(12, 10)
    reduced = calculate_incoming_damage(12, 10, team_defend_multiplier=0.5)
    ok("team defend halves counter", reduced == max(0, base // 2), f"{base} -> {reduced}")


def test_defend_team_buff_integration(client, client2, leader_id, member_id):
    """
    Low-resilience leader is counter target; high-resilience teammate Defends.
    Counter damage should be halved even though the target attacked.
    """
    update_squad(leader_id, resilience=10)
    update_squad(member_id, resilience=80)

    r = client.post(
        "/combat/start",
        json={"encounter_id": TEST_ENCOUNTER_ID},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    ok("defend test: start combat", start.get("success") and combat_id, str(start))

    leader_before = int((get_squad(leader_id) or {}).get("hp") or 0)

    r1 = client.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "attack"},
        content_type="application/json",
    )
    ok("defend test: leader attacks", (r1.get_json() or {}).get("status") == "waiting_for_teammates")

    r2 = client2.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "defend"},
        content_type="application/json",
    )
    phase = r2.get_json() or {}
    ok("defend test: member defends", phase.get("success") or phase.get("status"), str(phase)[:200])

    leader_after = int((get_squad(leader_id) or {}).get("hp") or 0)
    raw_counter = calculate_incoming_damage(12, 10)
    buffed_counter = calculate_incoming_damage(12, 10, team_defend_multiplier=0.5)
    damage_taken = leader_before - leader_after
    ok(
        "defend test: team buff reduces counter",
        damage_taken == buffed_counter and damage_taken < raw_counter,
        f"hp -{damage_taken}, expected {buffed_counter} (raw {raw_counter})",
    )


def fight_until_victory(client, client2, combat_id):
    """
    Both players attack each player_phase until victory or max rounds.
    Patches roll_combat_dice → 3 so damage is deterministic (server-side dice).
    """
    last = {}
    clients = (client, client2)
    with patch("routes.combat.roll_combat_dice", return_value=3):
        for _round in range(MAX_FIGHT_ROUNDS):
            for idx, c in enumerate(clients):
                r = submit_attack(c, combat_id)
                last = r.get_json() or {}
                if r.status_code >= 400:
                    return last, f"HTTP {r.status_code} player{idx + 1}"
                if not last.get("success"):
                    return last, f"player{idx + 1} submit failed"
                if last.get("outcome") == "victory":
                    return last, None
                if last.get("status") == "waiting_for_teammates":
                    continue

            st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
            if st.get("outcome") == "victory" or st.get("status") == "ended":
                return st, None
            if st.get("status") not in ("player_phase", None):
                continue
    return last, f"no victory after {MAX_FIGHT_ROUNDS} rounds"


def main():
    client = oikonomia.app.test_client()
    print(f"\n=== Combat 全流程測試 (DATA_DIR={TEST_DIR}) ===\n")

    # --- 玩家 1：建隊 + Iggy 路線 ---
    p1 = login(client, "TestLeader")
    ok("玩家1 登入", p1 and p1.get("squad_id"))
    leader_id = p1.get("squad_id")

    r = client.post("/team/create", data={"team_name": "CombatTest隊"})
    team_data = r.get_json()
    ok("建隊成功", team_data.get("success"), str(team_data))
    team_id = team_data.get("team_id")

    r = client.post("/set_team_route_by_leader", data={"route": "iggy"})
    route_data = r.get_json()
    ok("設定 Iggy 路線", route_data.get("route") == "iggy" or route_data.get("team", {}).get("route") == "iggy", str(route_data))

    # --- 玩家 2：加入隊伍 ---
    client2 = oikonomia.app.test_client()
    p2 = login(client2, "TestMember")
    ok("玩家2 登入", p2 and p2.get("squad_id"))
    member_id = p2.get("squad_id")

    r2 = client2.post("/team/join", data={"team_id": team_id})
    join_data = r2.get_json()
    ok("玩家2 加入隊伍", join_data.get("success"), str(join_data))

    test_defend_team_buff_helpers()

    # --- 開始 encounter（max_hp 測試會改 TestLeader stats，先跑主線）---
    r = client.post(
        "/combat/start",
        json={"encounter_id": ENCOUNTER_ID},
        content_type="application/json",
    )
    start = r.get_json()
    ok("開始 encounter", start.get("success"), str(start))
    combat_id = start.get("combat_id")
    precheck_passed = start.get("precheck_passed")
    print(f"    combat_id={combat_id}, status={start.get('status')}, precheck_passed={precheck_passed}")

    fight = {}
    if start.get("status") == "precheck" and precheck_passed:
        r = client.post(
            "/combat/start",
            json={"encounter_id": ENCOUNTER_ID, "confirm": "fight"},
            content_type="application/json",
        )
        fight = r.get_json()
        ok("Precheck → 選擇戰鬥", fight.get("success") and fight.get("status") == "player_phase", str(fight))
        combat_id = fight.get("combat_id")

    in_player_phase = start.get("status") == "player_phase" or fight.get("status") == "player_phase"
    ok("進入 player_phase", in_player_phase)
    test_protagonist_combat_participant(combat_id, route="iggy")

    # --- 兩玩家提交行動（server-side 骰子，loop 至勝利）---
    final, err = fight_until_victory(client, client2, combat_id)
    ok("戰鬥流程完成（無錯誤）", err is None, err or str(final)[:200])
    ok("submit_action 觸發勝利", final.get("outcome") == "victory", str(final)[:200])
    ok("勝利有反思題目", bool((final.get("reflection_prompt") or {}).get("questions")))

    # --- Defend 全隊 buff（主線戰鬥結束後另開 test encounter）---
    test_defend_team_buff_integration(client, client2, leader_id, member_id)

    test_player_max_hp(leader_id)

    # --- 輪詢狀態（戰鬥已結束應仍回傳 outcome）---
    r = client.get(f"/combat/status?combat_id={combat_id}")
    status = r.get_json()
    ok("輪詢 combat/status", status.get("success"), str(status)[:200])
    ok("status 回傳勝利 outcome", status.get("outcome") == "victory", str(status))
    ok("status 回傳 narrative", bool(status.get("narrative")))

    # --- encounter 列表 ---
    r = client.get("/encounters")
    enc_list = r.get_json()
    ok("GET /encounters", enc_list.get("success"), str(enc_list)[:150])

    # --- 驗證 API version marker ---
    r = client.get("/api/version")
    ver = r.get_json()
    ok("combat_system marker", ver.get("markers", {}).get("combat_system") is True)
    ok("server_combat_dice marker", ver.get("markers", {}).get("server_combat_dice") is True)
    ok("defend_team_buff marker", ver.get("markers", {}).get("defend_team_buff") is True)
    ok("combat_round_continue marker", ver.get("markers", {}).get("combat_round_continue") is True)
    ok("player_max_hp marker", ver.get("markers", {}).get("player_max_hp") is True)
    ok("protagonist_combat marker", ver.get("markers", {}).get("protagonist_combat") is True)
    ok("version 正確", ver.get("version") == oikonomia.read_deploy_version())

    print(f"\n=== 結果：{PASS} 通過 / {FAIL} 失敗 ===\n")
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())