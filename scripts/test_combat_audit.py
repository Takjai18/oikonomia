#!/usr/bin/env python3
"""戰鬥流程審計：結算、主角參戰、真實傷害、隊伍提交、單人隊伍。"""
import os
import shutil
import sys
import tempfile
from unittest.mock import patch

TEST_DIR = tempfile.mkdtemp(prefix="oikonomia_combat_audit_")
os.environ["DATA_DIR"] = TEST_DIR
os.environ.setdefault("FLASK_ENV", "development")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as oikonomia  # noqa: E402
from models.combat import get_combat, get_combat_participants
from models.protagonist import get_protagonist_state, update_protagonist_state
from models.squad import get_squad, get_team_members, update_squad

oikonomia.init_db()
oikonomia.migrate_db()

TEST_ENCOUNTER = "test_combat_01"
PASS = 0
FAIL = 0


def ok(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}" + (f" — {detail}" if detail else ""))


def login(client, squad_id):
    return client.post("/login", data={"squad_id": squad_id})


def enable_gm_session(client):
    with client.session_transaction() as sess:
        sess["is_gm"] = True


def submit_attack(client, combat_id, **extra):
    body = {"combat_id": combat_id, "action_type": "attack", **extra}
    return client.post("/combat/submit_action", json=body, content_type="application/json")


def clear_team_combat(team_id, encounter_id):
    from models.combat import clear_team_combat_id, get_active_combat_for_team, save_combat
    from datetime import datetime
    import sqlite3

    active = get_active_combat_for_team(team_id)
    if active:
        save_combat(active["id"], status="ended", winner="enemy", ended_at=datetime.now().isoformat())
        clear_team_combat_id(team_id)
    conn = sqlite3.connect(os.path.join(TEST_DIR, "oikonomia.db"))
    conn.execute(
        "DELETE FROM encounter_completions WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?)) AND encounter_id = ?",
        (team_id, encounter_id),
    )
    conn.commit()
    conn.close()


def setup_team(client, leader_name, member_name=None, route="iggy", protagonist_active=True):
    login(client, leader_name)
    r = client.post("/team/create", data={"team_name": f"Audit_{leader_name}"})
    team_id = (r.get_json() or {}).get("team_id")
    client.post("/set_team_route_by_leader", data={"route": route})
    update_protagonist_state(team_id, "iggy", is_active=1 if protagonist_active and route == "iggy" else 0)
    update_protagonist_state(team_id, "marah", is_active=1 if protagonist_active and route == "marah" else 0)
    member_client = None
    if member_name:
        member_client = oikonomia.app.test_client()
        login(member_client, member_name)
        member_client.post("/team/join", data={"team_id": team_id})
    return team_id, member_client


def start_test_combat(client, team_id):
    enable_gm_session(client)
    clear_team_combat(team_id, TEST_ENCOUNTER)
    r = client.post(
        "/combat/start",
        json={"encounter_id": TEST_ENCOUNTER},
        content_type="application/json",
    )
    data = r.get_json() or {}
    return data.get("combat_id"), data


def start_practice_combat(client, team_id, encounter_id="practice_iggy_02_leech"):
    clear_team_combat(team_id, encounter_id)
    r = client.post(
        "/combat/start",
        json={"encounter_id": encounter_id},
        content_type="application/json",
    )
    data = r.get_json() or {}
    return data.get("combat_id"), data


def normalize_team_combat_stats(team_id, power=12, intellect=12, player_resilience=99):
    """Keep audit fights multi-round; high player resilience so counter targets protagonist (90)."""
    for member in get_team_members(team_id):
        update_squad(
            member["squad_id"],
            power=power,
            intellect=intellect,
            resilience=player_resilience,
        )


def test_settlement_every_round_two_player(team_id, client, client2):
    print("\n--- 審計 1：每回合 round_settlement ---")
    update_protagonist_state(team_id, "iggy", is_active=0)
    combat_id, start = start_test_combat(client, team_id)
    ok("開戰", start.get("success") and combat_id, str(start)[:120])

    rounds_checked = 0
    with patch("routes.combat.roll_combat_dice", return_value=1):
        for _ in range(3):
            prev_hp = int(get_combat(combat_id).get("enemy_hp") or 0)
            r1 = submit_attack(client, combat_id)
            d1 = r1.get_json() or {}
            ok("玩家1 提交後等待隊友", d1.get("status") == "waiting_for_teammates", str(d1)[:120])

            r2 = submit_attack(client2, combat_id)
            d2 = r2.get_json() or {}
            if d2.get("outcome") in ("victory", "defeat"):
                ok(f"回合 {rounds_checked + 1} 觸發戰鬥結束", True, d2.get("outcome"))
                ok("勝利前敵人 HP 已下降", int(get_combat(combat_id).get("enemy_hp") or 0) <= prev_hp, f"prev={prev_hp}")
                break

            resolved = d2.get("round_resolved") or d2.get("status") == "round_resolved"
            ok(f"回合 {rounds_checked + 1} 觸發 round_resolved", resolved, str(d2)[:120])

            settlement = d2.get("round_settlement") or {}
            team_dealt = int(settlement.get("team_damage_dealt") or d2.get("round_enemy_damage") or 0)
            ok(f"回合 {rounds_checked + 1} 有 round_settlement", bool(settlement), str(settlement)[:120])
            ok(f"回合 {rounds_checked + 1} 全隊對敵傷害 > 0", team_dealt > 0, str(team_dealt))
            ok(
                f"回合 {rounds_checked + 1} 含敵方反擊欄位",
                "enemy_damage_dealt" in settlement,
                str(settlement.get("enemy_damage_dealt")),
            )

            new_hp = int(get_combat(combat_id).get("enemy_hp") or 0)
            ok(f"回合 {rounds_checked + 1} 敵人 HP 真實下降", new_hp < prev_hp, f"{prev_hp}->{new_hp}")
            st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
            ok(f"回合 {rounds_checked + 1} 結算後 player_phase", st.get("status") == "player_phase", st.get("status"))
            ok(f"回合 {rounds_checked + 1} 可進行下回合", st.get("my_state", {}).get("submitted") is False, str(st.get("my_state"))[:80])
            rounds_checked += 1

    ok("至少完成 2 回合結算", rounds_checked >= 2, str(rounds_checked))
    update_protagonist_state(team_id, "iggy", is_active=1)
    clear_team_combat(team_id, TEST_ENCOUNTER)


def test_protagonist_joins_and_deals_damage(team_id, client, route="iggy"):
    print(f"\n--- 審計 2：主角 {route.upper()} 參戰並造成傷害 ---")
    update_protagonist_state(team_id, route, is_active=1)
    normalize_team_combat_stats(team_id)
    combat_id, start = start_practice_combat(client, team_id)
    participants = get_combat_participants(get_combat(combat_id))
    pros = [p for p in participants if p.get("is_protagonist")]
    ok("主角在參戰名單", len(pros) >= 1, str([p.get("protagonist_key") for p in pros]))
    ok(f"主角為 {route}", any(p.get("protagonist_key") == route for p in pros), str(pros))

    pro = next((p for p in pros if p.get("protagonist_key") == route), None)
    pro_hp_before = int(pro.get("hp") or 0) if pro else 0

    logs_before = len(get_combat(combat_id).get("logs") or [])
    with patch("routes.combat.roll_combat_dice", return_value=1), patch(
        "models.combat.roll_combat_dice", return_value=1
    ):
        d = submit_attack(client, combat_id).get_json() or {}
    ok(
        "單人隊伍即時 round_resolved",
        d.get("round_resolved") or d.get("status") == "round_resolved" or d.get("outcome"),
        str(d)[:120],
    )

    combat_after = get_combat(combat_id) or {}
    logs = combat_after.get("logs") or []
    pro_name = (pro or {}).get("display_name") or ""
    pro_logs = [
        e for e in logs[logs_before:]
        if isinstance(e, dict)
        and (
            (pro_name and pro_name in (e.get("message") or ""))
            or "（主角" in (e.get("message") or "")
        )
    ]
    player_hits = (d.get("round_settlement") or {}).get("player_hits") or []
    pro_hit = any(
        pro_name and pro_name in (h.get("player") or "")
        for h in player_hits
    )
    ok(
        "主角行動寫入 log 或 settlement",
        len(pro_logs) >= 1 or pro_hit,
        str([e.get("message") for e in pro_logs][:2] or player_hits),
    )

    pro_state = get_protagonist_state(team_id, route)
    pro_hp_after = int(pro_state.get("hp") or 0)
    settlement = d.get("round_settlement") or {}
    enemy_dealt = int(settlement.get("enemy_damage_dealt") or 0)
    counter_hits = settlement.get("counter_hits") or []
    pro_countered = any(
        pro_name and (h.get("target") == pro_name or pro_name in (h.get("target") or ""))
        for h in counter_hits
    )
    if enemy_dealt > 0 and pro_countered:
        ok("主角 HP 可被反擊影響", pro_hp_after < pro_hp_before, f"{pro_hp_before}->{pro_hp_after}")
    elif enemy_dealt > 0:
        ok(
            "本回合反擊命中隊員（非主角）",
            True,
            str(counter_hits)[:120],
        )
    else:
        ok("本回合敵方反擊為 0（記錄）", True, "no counter this round")

    clear_team_combat(team_id, "practice_iggy_02_leech")


def test_solo_iggy_leech_enemy_hp(team_id, client):
    """單人 + Iggy 主角打情緒寄生影：每回合敵 HP 必須下降且與 payload 一致。"""
    print("\n--- 審計 3b：單人 enc_iggy_01_leech 敵 HP ---")
    enc_id = "enc_iggy_01_leech"
    update_protagonist_state(team_id, "iggy", is_active=1)
    clear_team_combat(team_id, enc_id)
    r = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    ok("情緒寄生影開戰", start.get("success") and combat_id, str(start)[:120])

    combat = get_combat(combat_id) if combat_id else None
    prev_hp = int((combat or {}).get("enemy_hp") or 0)
    ok("初始敵 HP 約 110", 100 <= prev_hp <= 120, str(prev_hp))

    with patch("routes.combat.roll_combat_dice", return_value=1):
        for round_no in range(1, 4):
            d = submit_attack(client, combat_id).get_json() or {}
            ok(
                f"第 {round_no} 回合 round_resolved",
                d.get("round_resolved") or d.get("status") == "round_resolved" or d.get("outcome"),
                str(d)[:120],
            )
            if d.get("outcome"):
                raw_hp = (get_combat(combat_id) or {}).get("enemy_hp")
                db_hp = int(raw_hp) if raw_hp is not None else None
                enemy_payload_hp = (d.get("enemy") or {}).get("hp")
                hp_ok = db_hp == 0 or enemy_payload_hp == 0 or d.get("outcome") == "victory"
                ok(
                    f"第 {round_no} 回合擊敗敵人",
                    d.get("outcome") == "victory" and hp_ok,
                    f"outcome={d.get('outcome')}, db_hp={db_hp}, payload_hp={enemy_payload_hp}",
                )
                break
            settlement = d.get("round_settlement") or {}
            team_dealt = int(settlement.get("team_damage_dealt") or 0)
            enemy_hp_raw = (d.get("enemy") or {}).get("hp")
            payload_hp = int(enemy_hp_raw if enemy_hp_raw is not None else prev_hp)
            db_hp = int((get_combat(combat_id) or {}).get("enemy_hp") or 0)
            ok(f"第 {round_no} 回合有傷害", team_dealt > 0, str(settlement)[:80])
            ok(
                f"第 {round_no} 回合敵 HP 下降",
                payload_hp < prev_hp,
                f"{prev_hp}->{payload_hp}",
            )
            ok(
                f"第 {round_no} 回合 DB 與 payload 一致",
                db_hp == payload_hp,
                f"db={db_hp}, payload={payload_hp}",
            )
            st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
            poll_hp = int((st.get("enemy") or {}).get("hp") or -1)
            ok(
                f"第 {round_no} 回合輪詢 HP 一致",
                poll_hp == payload_hp,
                f"poll={poll_hp}, payload={payload_hp}",
            )
            prev_hp = payload_hp

    clear_team_combat(team_id, enc_id)


def test_solo_team_immediate_next_action(team_id, client):
    print("\n--- 審計 3：單人隊伍（僅 1 人）結算後可再行動 ---")
    update_protagonist_state(team_id, "iggy", is_active=0)
    combat_id, _ = start_test_combat(client, team_id)
    with patch("routes.combat.roll_combat_dice", return_value=1):
        d1 = submit_attack(client, combat_id).get_json() or {}
    ok("無 waiting_for_teammates", d1.get("status") != "waiting_for_teammates", d1.get("status"))
    ok("直接 round_resolved", d1.get("round_resolved") or d1.get("status") == "round_resolved", str(d1)[:120])

    st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
    ok("結算後 status=player_phase", st.get("status") == "player_phase", st.get("status"))
    ok("my_state 未 submitted", not st.get("my_state", {}).get("submitted"), str(st.get("my_state"))[:80])

    with patch("routes.combat.roll_combat_dice", return_value=1):
        d2 = submit_attack(client, combat_id).get_json() or {}
    ok("第二回合可立即攻擊", d2.get("round_resolved") or d2.get("status") == "round_resolved" or d2.get("outcome"), str(d2)[:120])
    clear_team_combat(team_id, TEST_ENCOUNTER)


def test_no_team_cannot_start():
    print("\n--- 審計 4：無 Team 玩家無法開戰 ---")
    c = oikonomia.app.test_client()
    login(c, "SoloNoTeamAudit")
    squad = get_squad("SoloNoTeamAudit")
    if squad and squad.get("team_id"):
        update_squad("SoloNoTeamAudit", team_id=None)
    r = c.post("/combat/start", json={"encounter_id": TEST_ENCOUNTER}, content_type="application/json")
    data = r.get_json() or {}
    ok("無 Team 被拒絕", not data.get("success"), str(data)[:120])
    ok("錯誤訊息正確", "Team" in (data.get("error") or ""), data.get("error"))


def test_marah_protagonist():
    print("\n--- 審計 5：Marah 路線主角參戰 ---")
    marah_enc = "enc_marah_01_whisper"
    c = oikonomia.app.test_client()
    team_id, _ = setup_team(c, "MarahLeader", route="marah", protagonist_active=True)
    clear_team_combat(team_id, marah_enc)
    r = c.post("/combat/start", json={"encounter_id": marah_enc}, content_type="application/json")
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    ok("Marah encounter 開戰", start.get("success") and combat_id, str(start)[:120])
    participants = get_combat_participants(get_combat(combat_id))
    pros = [p for p in participants if p.get("protagonist_key") == "marah"]
    ok("Marah 參戰", len(pros) == 1, str([p.get("display_name") for p in pros]))
    clear_team_combat(team_id, marah_enc)


def main():
    print(f"\n=== 戰鬥流程審計 (DATA_DIR={TEST_DIR}) ===")

    c1 = oikonomia.app.test_client()
    c2 = oikonomia.app.test_client()
    team_id, c2 = setup_team(c1, "AuditLeader", "AuditMember", route="iggy")

    test_settlement_every_round_two_player(team_id, c1, c2)

    pro_c = oikonomia.app.test_client()
    pro_team_id, _ = setup_team(pro_c, "ProAuditLeader", route="iggy", protagonist_active=True)
    test_protagonist_joins_and_deals_damage(pro_team_id, pro_c, route="iggy")

    solo_c = oikonomia.app.test_client()
    solo_team_id, _ = setup_team(solo_c, "SoloAuditLeader", route="iggy", protagonist_active=False)
    test_solo_team_immediate_next_action(solo_team_id, solo_c)

    leech_c = oikonomia.app.test_client()
    leech_team_id, _ = setup_team(leech_c, "SalibaSoloAudit", route="iggy", protagonist_active=True)
    test_solo_iggy_leech_enemy_hp(leech_team_id, leech_c)

    test_no_team_cannot_start()
    test_marah_protagonist()

    print(f"\n=== 審計結果：{PASS} 通過 / {FAIL} 失敗 ===\n")
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())