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


def _test_db_path():
    return os.path.join(TEST_DIR, "oikonomia.db")


def clear_encounter_completion(team_id, encounter_id):
    """Remove completion row so test encounter can be replayed."""
    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    conn.execute(
        "DELETE FROM encounter_completions "
        "WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?)) AND encounter_id = ?",
        (team_id, encounter_id),
    )
    conn.commit()
    conn.close()


def teardown_test_combat(team_id, encounter_id):
    """End in-progress test combat without recording encounter completion."""
    from datetime import datetime

    from models.combat import clear_team_combat_id, get_active_combat_for_team, save_combat

    active = get_active_combat_for_team(team_id)
    if not active or active.get("encounter_id") != encounter_id:
        return
    if active.get("status") == "ended":
        clear_team_combat_id(team_id)
        return
    save_combat(
        active["id"],
        status="ended",
        winner="enemy",
        ended_at=datetime.now().isoformat(),
    )
    clear_team_combat_id(team_id)


def enable_gm_session(client):
    with client.session_transaction() as sess:
        sess["is_gm"] = True


def prepare_test_encounter(client, team_id, encounter_id):
    """Reset encounter for isolated integration tests sharing TEST_ENCOUNTER_ID."""
    enable_gm_session(client)
    teardown_test_combat(team_id, encounter_id)
    clear_encounter_completion(team_id, encounter_id)


def combat_enemy_hp(combat, default=0):
    """Read enemy_hp; 0 is valid (do not use `or default` which treats 0 as missing)."""
    if not combat or combat.get("enemy_hp") is None:
        return default
    return int(combat.get("enemy_hp"))


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


def test_maybe_resolve_ready_claim_inside_tx():
    """R11: all_phase_actions_submitted must run inside CAS transaction boundary."""
    import sqlite3
    from datetime import datetime

    from models.combat import (
        _claim_ready_player_phase_resolution,
        maybe_resolve_player_phase,
        upsert_combat_action,
    )

    now = datetime.now().isoformat()
    conn = sqlite3.connect(_test_db_path())
    conn.execute("DELETE FROM combat_actions")
    conn.execute("DELETE FROM combats WHERE encounter_id = 'test_claim_gate'")
    conn.execute("DELETE FROM squads WHERE squad_id IN ('cg1', 'cg2')")
    conn.execute("DELETE FROM teams WHERE team_id = 'T-CLAIM'")
    conn.execute(
        "INSERT INTO teams (team_id, team_name, route, created_at) VALUES ('T-CLAIM', 'ClaimGate', 'iggy', ?)",
        (now,),
    )
    for sid, leader in (("cg1", 1), ("cg2", 0)):
        conn.execute(
            """INSERT INTO squads
               (squad_id, display_name, team_id, hp, max_hp, sanity, power, intellect,
                resilience, is_team_leader, route, zoo_skills, last_update)
               VALUES (?, ?, 'T-CLAIM', 100, 100, 50, 30, 20, 20, ?, 'iggy', '[]', ?)""",
            (sid, sid, leader, now),
        )
    conn.execute(
        """INSERT INTO combats (
               squad_id, encounter_id, status, current_phase, enemy_hp,
               enemy_resilience, enemy_sanity, enemy_base_damage, enemy_name,
               phase_actions, logs, phase_started_at, started_at
           ) VALUES ('cg1', 'test_claim_gate', 'player_phase', 0, 60, 10, 50, 5, 'Boss', '{}', '[]', ?, ?)""",
        (now, now),
    )
    combat_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute("UPDATE squads SET current_combat_id = ? WHERE squad_id IN ('cg1', 'cg2')", (combat_id,))
    conn.commit()
    conn.close()

    upsert_combat_action(combat_id, "cg1", 0, "attack", 6, None)
    partial, winner = maybe_resolve_player_phase(combat_id, {})
    ok(
        "maybe_resolve incomplete phase stays player_phase",
        partial and partial.get("status") == "player_phase" and winner is None,
        str((partial or {}).get("status")),
    )
    claimed_partial, _ = _claim_ready_player_phase_resolution(combat_id, {})
    ok("claim_ready rejects incomplete phase", claimed_partial is False)

    upsert_combat_action(combat_id, "cg2", 0, "attack", 6, None)
    claimed_full, _ = _claim_ready_player_phase_resolution(combat_id, {})
    ok("claim_ready accepts complete phase", claimed_full is True)
    if claimed_full:
        from models.combat import _release_player_phase_resolution

        _release_player_phase_resolution(combat_id)

    resolved, winner2 = maybe_resolve_player_phase(combat_id, {})
    ok(
        "maybe_resolve complete phase progresses combat",
        resolved and resolved.get("status") != "player_phase",
        str((resolved or {}).get("status")),
    )


def test_maybe_resolve_monotonic_phase_guard():
    """R11 Scope C: peer resolve must not double-settle same round."""
    import sqlite3
    from datetime import datetime

    from models.combat import get_combat, maybe_resolve_player_phase, upsert_combat_action

    now = datetime.now().isoformat()
    conn = sqlite3.connect(_test_db_path())
    conn.execute("DELETE FROM combat_actions")
    conn.execute(f"DELETE FROM combats WHERE encounter_id = '{TEST_ENCOUNTER_ID}'")
    conn.execute("DELETE FROM squads WHERE squad_id IN ('mr1', 'mr2')")
    conn.execute("DELETE FROM teams WHERE team_id = 'T-MONO'")
    conn.execute(
        "INSERT INTO teams (team_id, team_name, route, created_at) VALUES ('T-MONO', 'Mono', 'iggy', ?)",
        (now,),
    )
    for sid, leader in (("mr1", 1), ("mr2", 0)):
        conn.execute(
            """INSERT INTO squads
               (squad_id, display_name, team_id, hp, max_hp, sanity, power, intellect,
                resilience, is_team_leader, route, zoo_skills, last_update)
               VALUES (?, ?, 'T-MONO', 100, 100, 50, 30, 20, 20, ?, 'iggy', '[]', ?)""",
            (sid, sid, leader, now),
        )
    conn.execute(
        """INSERT INTO combats (
               squad_id, encounter_id, status, current_phase, enemy_hp,
               enemy_resilience, enemy_sanity, enemy_base_damage, enemy_name,
               phase_actions, logs, phase_started_at, started_at
           ) VALUES ('mr1', ?, 'player_phase', 0, 5000, 10, 50, 5, 'Boss', '{}', '[]', ?, ?)""",
        (TEST_ENCOUNTER_ID, now, now),
    )
    combat_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "UPDATE squads SET current_combat_id = ? WHERE squad_id IN ('mr1', 'mr2')",
        (combat_id,),
    )
    conn.commit()
    conn.close()

    upsert_combat_action(combat_id, "mr1", 0, "attack", 6, None)
    upsert_combat_action(combat_id, "mr2", 0, "attack", 6, None)

    first, _ = maybe_resolve_player_phase(combat_id, {})
    after_first = get_combat(combat_id)
    progressed = (
        int(after_first.get("current_phase") or 0) >= 1
        or after_first.get("status") in ("enemy_phase", "ended")
    )
    ok("monotonic: first resolve progresses combat", progressed, str(after_first.get("status")))

    logs_len_1 = len(after_first.get("logs") or [])
    enemy_hp_1 = int(after_first.get("enemy_hp") or 0)

    second, winner2 = maybe_resolve_player_phase(combat_id, {})
    after_second = get_combat(combat_id)
    ok(
        "monotonic: second resolve does not re-run same round",
        int(after_second.get("current_phase") or 0) == int(after_first.get("current_phase") or 0)
        and len(after_second.get("logs") or []) == logs_len_1
        and int(after_second.get("enemy_hp") or 0) == enemy_hp_1,
        f"phase={after_second.get('current_phase')} logs={len(after_second.get('logs') or [])} winner2={winner2}",
    )


def test_phase2_gm_override_gateway():
    """Phase 2 Backlog: 驗證 GM 權威特權覆蓋閘門與結局狀態重置一致性。"""
    import sqlite3
    from datetime import datetime

    from services.gm_auth import establish_gm_session

    team_id = "TEAM-GM-OVERRIDE"
    proto_key = "marah"
    now = datetime.now().isoformat()

    conn = sqlite3.connect(_test_db_path())
    conn.execute("DELETE FROM protagonist_trauma_log WHERE team_id = ?", (team_id,))
    conn.execute("DELETE FROM protagonist_states WHERE team_id = ?", (team_id,))
    conn.execute("DELETE FROM global_events WHERE created_by = 'GM-CHIEF-01'")
    conn.execute("DELETE FROM teams WHERE team_id = ?", (team_id,))
    conn.execute(
        """INSERT INTO teams (team_id, team_name, ending_type, created_at)
           VALUES (?, 'GM覆蓋隊', 'bad_ending', ?)""",
        (team_id, now),
    )
    conn.execute(
        """INSERT INTO protagonist_states
           (team_id, protagonist, hp, max_hp, sanity, trauma_count, is_active, last_updated)
           VALUES (?, ?, 100, 100, 100, 4, 1, ?)""",
        (team_id, proto_key, now),
    )
    conn.commit()
    conn.close()

    client = oikonomia.app.test_client()

    r403 = client.post(
        "/gm/api/override_trauma_ending",
        json={"team_id": team_id, "protagonist_key": proto_key, "target_trauma": 1},
    )
    ok("GM Override Gate: 非管理員登入遭遇 403 熔斷拒絕", r403.status_code == 403)

    with client.session_transaction() as sess:
        establish_gm_session(sess)

    r_no_op = client.post(
        "/gm/api/override_trauma_ending",
        json={
            "team_id": team_id,
            "protagonist_key": proto_key,
            "target_trauma": 0,
            "target_ending_type": "clear",
        },
    )
    ok(
        "GM Override Gate: 有效 GM session 但無 operator 身分遭 403",
        r_no_op.status_code == 403,
        str(r_no_op.status_code),
    )

    with client.session_transaction() as sess:
        establish_gm_session(sess)
        sess["squad_id"] = "GM-CHIEF-01"

    r_ok = client.post(
        "/gm/api/override_trauma_ending",
        json={
            "team_id": team_id,
            "protagonist_key": proto_key,
            "target_trauma": 0,
            "target_ending_type": "clear",
        },
    )
    body = r_ok.get_json() or {}
    ok(
        "GM Override Gate: 權威覆蓋指令發放成功",
        r_ok.status_code == 200 and body.get("success") is True,
        str(body)[:200],
    )

    conn = sqlite3.connect(_test_db_path())
    trauma = conn.execute(
        "SELECT trauma_count FROM protagonist_states WHERE team_id = ? AND protagonist = ?",
        (team_id, proto_key),
    ).fetchone()[0]
    ending = conn.execute(
        "SELECT ending_type FROM teams WHERE team_id = ?",
        (team_id,),
    ).fetchone()[0]
    log_exists = conn.execute(
        """SELECT COUNT(*) FROM protagonist_trauma_log
           WHERE team_id = ? AND reason LIKE '%GM_OVERRIDE%'""",
        (team_id,),
    ).fetchone()[0]
    event_exists = conn.execute(
        "SELECT COUNT(*) FROM global_events WHERE created_by = 'GM-CHIEF-01'",
    ).fetchone()[0]
    conn.close()

    ok("GM Override Gate: 實體表主角創傷已清零 SSOT", int(trauma) == 0)
    ok("GM Override Gate: 實體表團隊結局解鎖重置", ending is None)
    ok("GM Override Gate: 歷史審計日誌留痕合規", log_exists == 1)
    ok("GM Override Gate: 全營廣播通知發送成功", event_exists == 1)


def test_phase2_narrative_orchestrator_pipeline():
    """Phase 1.5 Step 3: 驗證全新戰後劇情管線強等冪性與背包熔斷防線。"""
    import sqlite3
    from datetime import datetime

    from services.narrative_orchestrator import execute_post_combat_success_pipeline

    team_id = "TEAM-NARRATIVE-V2"
    squad_id = "SQUAD-LEADER-V2"
    enc_id = "enc_iggy_01_leech"
    now = datetime.now().isoformat()

    conn = sqlite3.connect(_test_db_path())
    conn.execute(
        "DELETE FROM encounter_completions WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))",
        (team_id,),
    )
    conn.execute("DELETE FROM player_items WHERE squad_id = ?", (squad_id,))
    conn.execute("DELETE FROM squads WHERE squad_id = ?", (squad_id,))
    conn.execute("DELETE FROM teams WHERE team_id = ?", (team_id,))
    conn.execute(
        "INSERT INTO teams (team_id, team_name, created_at) VALUES (?, ?, ?)",
        (team_id, "NarrativeTest", now),
    )
    conn.execute(
        "INSERT INTO squads (squad_id, team_id, hp, max_hp, is_team_leader, display_name) "
        "VALUES (?, ?, 100, 100, 1, ?)",
        (squad_id, team_id, "Leader"),
    )
    conn.commit()
    conn.close()

    with patch("services.narrative_orchestrator.random.random", return_value=0.0):
        snap1 = execute_post_combat_success_pipeline(team_id, enc_id, squad_id)
    ok("Narrative V2: 首次結算管道成功執行", "通關" in snap1.log_message)

    conn = sqlite3.connect(_test_db_path())
    item_count = conn.execute(
        "SELECT COUNT(*) FROM player_items WHERE squad_id = ?",
        (squad_id,),
    ).fetchone()[0]
    completion_exists = conn.execute(
        """SELECT COUNT(*) FROM encounter_completions
           WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?)) AND encounter_id = ?""",
        (team_id, enc_id),
    ).fetchone()[0]
    conn.close()

    ok("Narrative V2: 獎勵物品成功發放至背包", item_count > 0)
    ok("Narrative V2: 遭遇通關誌成功存檔", completion_exists == 1)

    snap2 = execute_post_combat_success_pipeline(team_id, enc_id, squad_id)
    ok("Narrative V2: 強等冪閘門成功阻斷", "拒絕重複" in snap2.log_message)

    conn = sqlite3.connect(_test_db_path())
    item_count_after = conn.execute(
        "SELECT COUNT(*) FROM player_items WHERE squad_id = ?",
        (squad_id,),
    ).fetchone()[0]
    conn.close()
    ok("Narrative V2: 物品數量守恆，無重複發放漏洞", item_count == item_count_after)


def test_phase2_trauma_service_pipeline():
    """Phase 1.5 Step 2: 驗證全新中央創傷能帶管線與神學片段權威分發機制。"""
    import sqlite3
    from datetime import datetime

    from services.trauma_service import apply_protagonist_trauma_pipeline

    team_id = "TEAM-TRAUMA-V2"
    proto_key = "iggy"
    now = datetime.now().isoformat()

    conn = sqlite3.connect(_test_db_path())
    conn.execute("DELETE FROM protagonist_trauma_log WHERE team_id = ?", (team_id,))
    conn.execute("DELETE FROM protagonist_states WHERE team_id = ?", (team_id,))
    conn.execute("DELETE FROM teams WHERE team_id = ?", (team_id,))
    conn.execute(
        "INSERT INTO teams (team_id, team_name, created_at) VALUES (?, ?, ?)",
        (team_id, "測試隊伍", now),
    )
    conn.execute(
        """INSERT INTO protagonist_states
           (team_id, protagonist, hp, max_hp, sanity, trauma_count, is_active, last_updated)
           VALUES (?, ?, 100, 100, 100, 0, 1, ?)""",
        (team_id, proto_key, now),
    )
    conn.commit()
    conn.close()

    snap1 = apply_protagonist_trauma_pipeline(team_id, proto_key, 1, "測試低創傷原因")
    ok("Trauma V2: 創傷正確累加至 1", snap1.current_trauma == 1)
    ok("Trauma V2: 正確落入 low 能帶", snap1.trauma_band == "low")
    ok("Trauma V2: 盼望 fragment 包含恩典", "恩典" in snap1.narrative_fragment)
    ok("Trauma V2: 結局未鎖定", snap1.is_bad_ending_locked is False)

    snap2 = apply_protagonist_trauma_pipeline(team_id, proto_key, 3, "測試致命瀕死累積")
    ok("Trauma V2: 創傷穿透至 4 次", snap2.current_trauma == 4)
    ok("Trauma V2: 正確落入 high 能帶", snap2.trauma_band == "high")
    ok("Trauma V2: 盼望 fragment 包含基督能力", "基督" in snap2.narrative_fragment)
    ok("Trauma V2: 不可逆陰影結局成功鎖定", snap2.is_bad_ending_locked is True)

    conn = sqlite3.connect(_test_db_path())
    ending_type = conn.execute(
        "SELECT ending_type FROM teams WHERE team_id = ?",
        (team_id,),
    ).fetchone()[0]
    conn.close()
    ok("Trauma V2: DB 實體表寫入 bad_ending 完好合規", ending_type == "bad_ending")


def test_trauma_ending_thresholds():
    from models.protagonist import (
        TRAUMA_BAD_ENDING_LIMIT,
        check_ending_condition,
        get_team_ending_state,
        has_trauma_bad_ending,
        update_protagonist_state,
    )

    from models.protagonist import initialize_protagonist_for_team

    ok("trauma limit is 3", TRAUMA_BAD_ENDING_LIMIT == 3)
    team = "TEAM-TRAUMA-TEST"
    initialize_protagonist_for_team(team, "iggy")
    update_protagonist_state(team, "iggy", trauma_count=3, is_active=1)
    ok("3 trauma not bad ending", not has_trauma_bad_ending(team))
    ok("3 trauma normal ending", check_ending_condition(team) == "normal_ending")
    state3 = get_team_ending_state(team)
    ok("3 trauma until bad is 1", state3.get("trauma_until_bad") == 1)
    update_protagonist_state(team, "iggy", trauma_count=4)
    ok("4 trauma is bad ending", has_trauma_bad_ending(team))
    ok("4 trauma check_ending", check_ending_condition(team) == "bad_ending")


def test_trauma_bad_ending_victory(client, client2, team_id, leader_id, member_id):
    """Win combat with trauma > 3 → bad ending, no normal rewards narrative."""
    from models.protagonist import get_team_ending_type, update_protagonist_state

    prepare_test_encounter(client, team_id, TEST_ENCOUNTER_ID)
    update_protagonist_state(team_id, "iggy", trauma_count=4, is_active=0)

    r = client.post(
        "/combat/start",
        json={"encounter_id": TEST_ENCOUNTER_ID},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    if not combat_id:
        from models.combat import get_active_combat_for_team

        active = get_active_combat_for_team(team_id)
        combat_id = active.get("id") if active else None
    ok("trauma ending: have combat", combat_id, str(start))

    final, err = fight_until_victory(client, client2, combat_id)
    ok("trauma ending: fight completes", err is None, err or str(final)[:200])
    ok("trauma ending: still victory outcome", final.get("outcome") == "victory", str(final)[:200])
    ok("trauma ending: trauma_bad_ending flag", final.get("trauma_bad_ending") is True, str(final)[:200])
    ok("trauma ending: no reflection", not final.get("reflection_prompt"), str(final)[:200])
    ok("trauma ending: custom narrative", "心理創傷" in (final.get("narrative") or ""), str(final)[:200])

    st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
    ok("trauma ending: status has flag", st.get("trauma_bad_ending") is True, str(st)[:200])

    status = client.get("/status").get_json() or {}
    ending = status.get("ending") or {}
    ok("trauma ending: player status", ending.get("trauma_bad_ending") is True, str(ending))
    ok("trauma ending: team locked", get_team_ending_type(team_id) == "bad_ending")


def test_protagonist_player_control(client, client2, team_id, route="iggy"):
    """Encounter with protagonist_player_control: leader can submit as_protagonist."""
    from models.protagonist import protagonist_squad_id, update_protagonist_state

    update_protagonist_state(team_id, route, is_active=1)

    r = client.post(
        "/combat/start",
        json={"encounter_id": "test_protagonist_control"},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    if not combat_id:
        from models.combat import get_active_combat_for_team

        active = get_active_combat_for_team(team_id)
        combat_id = active.get("id") if active else None
    ok("pro control: start combat", combat_id, str(start))

    st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
    ok("pro control: flag enabled", st.get("protagonist_player_control") is True, str(st)[:200])
    pro_sid = protagonist_squad_id(team_id, route)
    ok(
        "pro control: controllable id",
        st.get("controllable_protagonist_id") == pro_sid,
        st.get("controllable_protagonist_id"),
    )

    r1 = client.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "attack", "as_protagonist": True},
        content_type="application/json",
    )
    d1 = r1.get_json() or {}
    ok("pro control: protagonist submit", d1.get("success") or d1.get("status"), str(d1)[:200])

    r2 = client2.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "attack"},
        content_type="application/json",
    )
    d2 = r2.get_json() or {}
    ok("pro control: teammate submit", d2.get("success") or d2.get("outcome"), str(d2)[:200])

    ok(
        "pro control: round resolved",
        d2.get("round_resolved") or d2.get("status") == "round_resolved" or d2.get("outcome"),
        str(d2)[:200],
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
    from models.protagonist import update_protagonist_state

    leader_team = (get_squad(leader_id) or {}).get("team_id")
    if leader_team:
        prepare_test_encounter(client, leader_team, TEST_ENCOUNTER_ID)

    update_squad(leader_id, resilience=10)
    update_squad(member_id, resilience=80)
    leader_team = (get_squad(leader_id) or {}).get("team_id")
    if leader_team:
        # Protagonist auto-attack can kill the test enemy before counter resolves.
        update_protagonist_state(leader_team, "iggy", is_active=0)

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


def test_enemy_hp_reconciled_from_logs(client, leader_id, team_id):
    """Status API must repair stale DB enemy_hp using log summaries (F5 refresh)."""
    from models.combat import build_enemy_combat_stats, create_combat_record, save_combat
    from models.encounter import load_encounter

    enc_id = "practice_iggy_01_quick"
    enc = load_encounter(enc_id)
    teardown_test_combat(team_id, enc_id)
    combat = create_combat_record(leader_id, enc_id, enc, initial_status="player_phase")
    combat_id = combat.get("id")
    start_hp = 48
    true_hp = 36
    logs = list(combat.get("logs") or [])
    logs.extend([
        {"type": "damage", "message": "Tester 攻擊對速戰殘影造成 12 點傷害"},
        {"type": "summary", "message": f"速戰殘影 受到共 12 點傷害，剩餘 HP {true_hp}"},
    ])
    save_combat(combat_id, enemy_hp=start_hp, logs=logs, status="player_phase")
    ok("reconcile test: seeded combat", combat_id, str(combat_id))

    st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
    payload_hp = int((st.get("enemy") or {}).get("hp") or -1)
    ok("reconcile test: status returns log HP", payload_hp == true_hp, f"{payload_hp} vs {true_hp}")

    repaired = combat_enemy_hp(get_combat(combat_id), default=start_hp)
    ok("reconcile test: DB repaired", repaired == true_hp, f"db={repaired}")

    stats = build_enemy_combat_stats(get_combat(combat_id) or {})
    ok("reconcile test: build_enemy stats", int(stats.get("hp") or -1) == true_hp, str(stats))

    teardown_test_combat(team_id, enc_id)


def test_enemy_hp_updates_after_round(client, client2, team_id):
    """Round resolve must persist enemy HP; round_resolved payload must reflect damage."""
    from models.protagonist import update_protagonist_state

    prepare_test_encounter(client, team_id, TEST_ENCOUNTER_ID)
    update_protagonist_state(team_id, "iggy", is_active=0)

    r = client.post(
        "/combat/start",
        json={"encounter_id": TEST_ENCOUNTER_ID},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    ok("enemy hp test: start combat", start.get("success") and combat_id, str(start))

    combat = get_combat(combat_id) if combat_id else None
    start_hp = int((combat or {}).get("enemy_hp") or 0)
    ok("enemy hp test: initial hp", start_hp > 0, str(start_hp))

    r1 = client.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "attack"},
        content_type="application/json",
    )
    ok(
        "enemy hp test: leader submits",
        (r1.get_json() or {}).get("status") == "waiting_for_teammates",
        str(r1.get_json())[:200],
    )

    # dice=1 keeps one round sub-lethal (dice=3 can one-shot the 55 HP test enemy).
    with patch("routes.combat.roll_combat_dice", return_value=1):
        r2 = client2.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "attack"},
            content_type="application/json",
        )
    phase = r2.get_json() or {}
    resolved = bool(
        phase.get("round_resolved")
        or phase.get("status") == "round_resolved"
        or phase.get("outcome") == "victory"
    )
    ok("enemy hp test: round resolves", resolved, str(phase)[:200])

    settlement = phase.get("round_settlement") or {}
    team_dealt = int(settlement.get("team_damage_dealt") or phase.get("round_enemy_damage") or 0)
    ok("enemy hp test: round_settlement team dealt", team_dealt > 0, str(settlement)[:200])
    ok(
        "enemy hp test: round_settlement enemy dealt present",
        "enemy_damage_dealt" in settlement,
        str(settlement)[:200],
    )

    db_hp = combat_enemy_hp(get_combat(combat_id), default=start_hp)
    if phase.get("outcome") == "victory":
        ok("enemy hp test: victory zeroes enemy hp", db_hp == 0, f"db={db_hp}")
    else:
        enemy_payload = phase.get("enemy") or {}
        payload_hp = (
            int(enemy_payload["hp"])
            if enemy_payload.get("hp") is not None
            else start_hp
        )
        ok(
            "enemy hp test: payload hp dropped",
            payload_hp < start_hp,
            f"{start_hp}->{payload_hp}",
        )
        ok(
            "enemy hp test: db hp matches payload",
            db_hp == payload_hp,
            f"db={db_hp}, payload={payload_hp}",
        )

    teardown_test_combat(team_id, TEST_ENCOUNTER_ID)
    clear_encounter_completion(team_id, TEST_ENCOUNTER_ID)
    update_protagonist_state(team_id, "iggy", is_active=1)


def test_solo_killing_blow_returns_victory(client, client2, team_id):
    """Final hit at enemy HP 1 must return victory, not another attackable player_phase."""
    from models.combat import combat_outcome_if_finished, get_active_combat_for_team, save_combat
    from models.encounter import load_encounter
    from models.protagonist import update_protagonist_state

    active = get_active_combat_for_team(team_id)
    if active:
        teardown_test_combat(team_id, active.get("encounter_id"))
    prepare_test_encounter(client, team_id, TEST_ENCOUNTER_ID)
    update_protagonist_state(team_id, "iggy", is_active=0)

    r = client.post(
        "/combat/start",
        json={"encounter_id": TEST_ENCOUNTER_ID},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    ok("killing blow: start combat", start.get("success") and combat_id, str(start))

    save_combat(combat_id, enemy_hp=1)
    with patch("routes.combat.roll_combat_dice", return_value=2):
        w = client.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "attack"},
            content_type="application/json",
        ).get_json() or {}
        ok("killing blow: leader waits", w.get("status") == "waiting_for_teammates", str(w)[:200])
        data = client2.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "attack"},
            content_type="application/json",
        ).get_json() or {}
    ok("killing blow: victory outcome", data.get("outcome") == "victory", str(data)[:240])
    settlement = data.get("round_settlement") or {}
    ok("killing blow: round_settlement on victory", bool(settlement), str(settlement)[:200])
    ok(
        "killing blow: enemy_hp_after zero",
        settlement.get("enemy_hp_after") == 0,
        str(settlement.get("enemy_hp_after")),
    )
    ok(
        "killing blow: combat ended in db",
        (get_combat(combat_id) or {}).get("status") == "ended",
        str(get_combat(combat_id))[:200],
    )

    zombie = dict(get_combat(combat_id) or {})
    zombie.update({"status": "player_phase", "enemy_hp": 0, "winner": None})
    finished = combat_outcome_if_finished(zombie, load_encounter(TEST_ENCOUNTER_ID), team_id=team_id)
    ok(
        "killing blow: zombie hp0 guard returns victory",
        finished and finished.get("outcome") == "victory",
        str(finished)[:200],
    )

    teardown_test_combat(team_id, TEST_ENCOUNTER_ID)
    clear_encounter_completion(team_id, TEST_ENCOUNTER_ID)
    update_protagonist_state(team_id, "iggy", is_active=1)


def test_solo_killing_blow_practice_quick():
    """Solo team + protagonist on practice_iggy_01_quick: one-round win includes settlement."""
    from models.protagonist import update_protagonist_state
    from models.squad import get_team_members, update_squad

    enc_id = "practice_iggy_01_quick"
    client = oikonomia.app.test_client()
    login(client, "QuickKillSolo")
    r = client.post("/team/create", data={"team_name": "QuickKillSolo"})
    team_id = (r.get_json() or {}).get("team_id")
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    update_protagonist_state(team_id, "iggy", is_active=1)
    for member in get_team_members(team_id):
        update_squad(member["squad_id"], power=12, intellect=12)

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    r = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    ok("quick kill: start", start.get("success") and combat_id, str(start)[:120])
    start_hp = combat_enemy_hp(get_combat(combat_id), default=-1)
    ok("quick kill: enemy hp ~48", 40 <= start_hp <= 55, str(start_hp))

    with patch("routes.combat.roll_combat_dice", return_value=1), patch(
        "models.combat.roll_combat_dice", return_value=1
    ):
        data = client.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "attack"},
            content_type="application/json",
        ).get_json() or {}

    ok("quick kill: victory outcome", data.get("outcome") == "victory", str(data)[:200])
    settlement = data.get("round_settlement") or {}
    ok("quick kill: round_settlement present", bool(settlement), str(settlement)[:200])
    ok(
        "quick kill: team_damage_dealt > 0",
        int(settlement.get("team_damage_dealt") or 0) > 0,
        str(settlement),
    )
    ok("quick kill: enemy_hp_after is 0", settlement.get("enemy_hp_after") == 0, str(settlement))
    payload_hp = (data.get("enemy") or {}).get("hp")
    ok(
        "quick kill: payload enemy hp 0",
        payload_hp is not None and int(payload_hp) == 0,
        str(data.get("enemy")),
    )
    ok("quick kill: log_entries present", len(data.get("log_entries") or []) > 0, "empty logs")
    ok("quick kill: db enemy_hp 0", combat_enemy_hp(get_combat(combat_id), default=-1) == 0, "db hp")
    ok(
        "quick kill: combat ended",
        (get_combat(combat_id) or {}).get("status") == "ended",
        str((get_combat(combat_id) or {}).get("status")),
    )

    teardown_test_combat(team_id, enc_id)


def test_escape_action_type_allowed():
    from models.combat import COMBAT_ACTION_TYPES

    ok("escape in COMBAT_ACTION_TYPES", "escape" in COMBAT_ACTION_TYPES)


def test_defeat_outcome_includes_dead_roster():
    from services.combat_outcomes import build_defeat_outcome_payload

    participants = [
        {"squad_id": "A", "display_name": "Alice", "hp": 0, "max_hp": 100},
        {"squad_id": "B", "display_name": "Bob", "hp": 80, "max_hp": 100},
    ]
    payload = build_defeat_outcome_payload({"failure": {"narrative": "fail"}}, participants=participants)
    ok("defeat outcome_type COMBAT_FAILED", payload.get("outcome_type") == "COMBAT_FAILED", str(payload))
    ok("defeat dead_squad_ids", payload.get("dead_squad_ids") == ["A"], str(payload))
    ok("defeat dead_squad_names", payload.get("dead_squad_names") == ["Alice"], str(payload))
    ok("defeat requires_gm", payload.get("requires_gm") is True, str(payload))


def test_select_enemy_counter_target_priority():
    from models.combat import select_enemy_counter_target

    participants = [
        {"squad_id": "A", "hp": 80, "max_hp": 100, "resilience": 5, "is_protagonist": False},
        {"squad_id": "B", "hp": 30, "max_hp": 100, "resilience": 3, "is_protagonist": False, "trauma_count": 0},
        {"squad_id": "P", "hp": 90, "max_hp": 100, "resilience": 10, "is_protagonist": True},
    ]
    actions = {"B": {"action_type": "escape"}}
    target = select_enemy_counter_target(participants, actions, enemy_base_damage=50)
    ok("escape target prefers escaper", target and target["squad_id"] == "B", str(target))


def test_escape_fail_mixed_settlement():
    """INV-E: escape fail still resolves combat actions with settlement metadata."""
    from models.protagonist import update_protagonist_state

    enc_id = "practice_iggy_01_quick"
    client = oikonomia.app.test_client()
    login(client, "EscapeFailSolo")
    client.post("/team/create", data={"team_name": "EscapeFail"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    conn.close()
    update_protagonist_state(team_id, "iggy", is_active=0)

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    start = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    ).get_json() or {}
    combat_id = start.get("combat_id")
    ok("escape fail: start", start.get("success") and combat_id, str(start)[:120])

    with patch("models.combat.random.random", return_value=0.99), patch(
        "models.combat.roll_combat_dice", return_value=2
    ):
        data = client.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "escape"},
            content_type="application/json",
        ).get_json() or {}

    ok("escape fail: not 400", data.get("success") is not False or data.get("round_resolved"), str(data)[:200])
    ok(
        "escape fail: round_resolved",
        data.get("round_resolved") or data.get("status") == "round_resolved",
        str(data)[:200],
    )
    settlement = data.get("round_settlement") or {}
    ok("escape fail: escape_triggered", settlement.get("escape_triggered") is True, str(settlement))
    ok("escape fail: escape_success false", settlement.get("escape_success") is False, str(settlement))
    ok(
        "escape fail: combat still active",
        (get_combat(combat_id) or {}).get("status") == "player_phase",
        str((get_combat(combat_id) or {}).get("status")),
    )

    teardown_test_combat(team_id, enc_id)


def test_use_item_combat_consumes_and_resolves():
    """P2-1: use_item consumes player_items row and resolves with damage."""
    from models.item import consume_squad_item_for_combat, grant_item_to_squad
    from models.protagonist import update_protagonist_state

    enc_id = "practice_iggy_01_quick"
    client = oikonomia.app.test_client()
    login(client, "UseItemSolo")
    client.post("/team/create", data={"team_name": "UseItem"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    squad_id = conn.execute(
        "SELECT squad_id FROM squads WHERE team_id = ? ORDER BY rowid LIMIT 1",
        (team_id,),
    ).fetchone()[0]
    conn.close()
    update_protagonist_state(team_id, "iggy", is_active=0)

    qr_value = f"test-combat-power-{os.getpid()}"
    conn = sqlite3.connect(_test_db_path())
    conn.execute("DELETE FROM player_items WHERE squad_id = ?", (squad_id,))
    conn.execute(
        """INSERT INTO items
           (name, description, icon, qr_code_value, has_ability, effect_type, effect_value, is_active)
           VALUES ('力量碎片', 'test', '💎', ?, 1, 'power_up', 5, 1)""",
        (qr_value,),
    )
    conn.commit()
    item_row = conn.execute(
        "SELECT id FROM items WHERE qr_code_value = ?", (qr_value,),
    ).fetchone()
    conn.close()
    item_id = item_row[0]

    granted, grant_msg, _ = grant_item_to_squad(squad_id, item_id, source="test")
    ok("use_item: grant power_up item", granted, grant_msg)

    r = client.get("/api/inventory")
    inv = r.get_json() or {}
    ok("use_item: /api/inventory lists item", inv.get("success") and any(
        i.get("item_id") == item_id for i in (inv.get("items") or [])
    ), str(inv)[:200])

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    start = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    ).get_json() or {}
    combat_id = start.get("combat_id")
    ok("use_item: start combat", start.get("success") and combat_id, str(start)[:120])

    with patch("routes.combat.roll_combat_dice", return_value=2):
        data = client.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "use_item", "item_id": item_id},
            content_type="application/json",
        ).get_json() or {}

    ok("use_item: submit resolves", data.get("round_resolved") or data.get("success"), str(data)[:200])
    settlement = data.get("round_settlement") or {}
    ok("use_item: team dealt damage", int(settlement.get("team_damage_dealt") or 0) > 0, str(settlement))

    conn = sqlite3.connect(_test_db_path())
    remaining = conn.execute(
        "SELECT COUNT(*) FROM player_items WHERE squad_id = ? AND item_id = ?",
        (squad_id, item_id),
    ).fetchone()[0]
    conn.close()
    ok("use_item: inventory row consumed", remaining == 0, str(remaining))

    ok_consume, _, err = consume_squad_item_for_combat(squad_id, item_id)
    ok("use_item: double consume blocked", not ok_consume and err, err)

    teardown_test_combat(team_id, enc_id)


def test_non_leader_as_protagonist_rejected():
    """P2-3: non-leader cannot submit with as_protagonist=true."""
    from models.protagonist import update_protagonist_state

    client = oikonomia.app.test_client()
    client2 = oikonomia.app.test_client()
    login(client, "ProLeader")
    login(client2, "ProMember")
    client.post("/team/create", data={"team_name": "ProGate"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})

    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    leader_id = conn.execute(
        "SELECT squad_id FROM squads WHERE team_id = ? AND is_team_leader = 1 LIMIT 1",
        (team_id,),
    ).fetchone()[0]
    conn.close()

    client2.post("/team/join", data={"team_id": team_id, "display_name": "ProMember"})

    update_protagonist_state(team_id, "iggy", is_active=1)

    enable_gm_session(client)
    teardown_test_combat(team_id, "test_protagonist_control")
    clear_encounter_completion(team_id, "test_protagonist_control")

    r = client.post(
        "/combat/start",
        json={"encounter_id": "test_protagonist_control"},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    ok("pro gate: start combat", combat_id, str(start)[:120])

    with client2.session_transaction() as sess:
        member_id = sess.get("squad_id")

    r403 = client2.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "attack", "as_protagonist": True},
        content_type="application/json",
    )
    ok("pro gate: member as_protagonist 403", r403.status_code == 403, str(r403.get_json()))
    body = r403.get_json() or {}
    ok(
        "pro gate: error message",
        "隊長" in (body.get("error") or ""),
        body.get("error"),
    )

    r_ok = client.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "attack", "as_protagonist": True},
        content_type="application/json",
    )
    d = r_ok.get_json() or {}
    ok("pro gate: leader as_protagonist ok", d.get("success") or d.get("status"), str(d)[:200])

    teardown_test_combat(team_id, "test_protagonist_control")


def test_use_item_hp_up_and_sanity_up_in_combat():
    """P2-4: hp_up / sanity_up items heal in combat without enemy damage."""
    from models.item import grant_item_to_squad
    from models.protagonist import update_protagonist_state

    enc_id = "practice_iggy_01_quick"
    client = oikonomia.app.test_client()
    login(client, "ItemExtendSolo")
    client.post("/team/create", data={"team_name": "ItemExtend"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    squad_id = conn.execute(
        "SELECT squad_id FROM squads WHERE team_id = ? ORDER BY rowid LIMIT 1",
        (team_id,),
    ).fetchone()[0]
    heal_qr = f"test-heal-{os.getpid()}"
    san_qr = f"test-san-{os.getpid()}"
    conn.execute("DELETE FROM player_items WHERE squad_id = ?", (squad_id,))
    conn.execute(
        """INSERT INTO items
           (name, description, icon, qr_code_value, has_ability, effect_type, effect_value, is_active)
           VALUES ('生命泉源', 'heal', '🧪', ?, 1, 'hp_up', 30, 1)""",
        (heal_qr,),
    )
    conn.execute(
        """INSERT INTO items
           (name, description, icon, qr_code_value, has_ability, effect_type, effect_value, is_active)
           VALUES ('安定情緒劑', 'sanity', '🔮', ?, 1, 'sanity_up', 25, 1)""",
        (san_qr,),
    )
    conn.commit()
    heal_item_id = conn.execute(
        "SELECT id FROM items WHERE qr_code_value = ?", (heal_qr,),
    ).fetchone()[0]
    san_item_id = conn.execute(
        "SELECT id FROM items WHERE qr_code_value = ?", (san_qr,),
    ).fetchone()[0]
    conn.close()

    update_protagonist_state(team_id, "iggy", is_active=0)

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    granted, _, _ = grant_item_to_squad(squad_id, heal_item_id, source="test")
    ok("P2-4: grant hp_up item", granted)

    start = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    ).get_json() or {}
    combat_id = start.get("combat_id")
    ok("P2-4: start combat (heal)", start.get("success") and combat_id, str(start)[:120])

    update_squad(squad_id, hp=40)
    hp_before = int((get_squad(squad_id) or {}).get("hp") or 0)
    max_hp = int((get_squad(squad_id) or {}).get("max_hp") or 100)

    data = client.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "use_item", "item_id": heal_item_id},
        content_type="application/json",
    ).get_json() or {}
    settlement = data.get("round_settlement") or {}
    squad_after_heal = get_squad(squad_id) or {}
    hp_after = int(squad_after_heal.get("hp") or 0)
    ok(
        "P2-4: hp_up increases HP vs baseline",
        hp_after > hp_before,
        f"before={hp_before} after={hp_after}",
    )
    ok("P2-4: hp_up deals no enemy damage", int(settlement.get("team_damage_dealt") or 0) == 0, str(settlement))
    logs = (get_combat(combat_id) or {}).get("logs") or []
    ok(
        "P2-4: hp_up combat log",
        any("生命值回復" in (e.get("message") if isinstance(e, dict) else str(e)) for e in logs),
        str(logs[-5:]),
    )

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    granted2, _, _ = grant_item_to_squad(squad_id, san_item_id, source="test")
    ok("P2-4: grant sanity_up item", granted2)

    start2 = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    ).get_json() or {}
    combat_id2 = start2.get("combat_id")
    ok("P2-4: start combat (sanity)", start2.get("success") and combat_id2, str(start2)[:120])

    update_squad(squad_id, sanity=50)
    san_before = int((get_squad(squad_id) or {}).get("sanity") or 0)

    data2 = client.post(
        "/combat/submit_action",
        json={"combat_id": combat_id2, "action_type": "use_item", "item_id": san_item_id},
        content_type="application/json",
    ).get_json() or {}
    settlement2 = data2.get("round_settlement") or {}
    squad_after_san = get_squad(squad_id) or {}
    san_after = int(squad_after_san.get("sanity") or 0)
    ok(
        "P2-4: sanity_up restores sanity SSOT",
        san_after == min(100, san_before + 25),
        f"before={san_before} after={san_after}",
    )
    ok("P2-4: sanity_up deals no enemy damage", int(settlement2.get("team_damage_dealt") or 0) == 0, str(settlement2))

    teardown_test_combat(team_id, enc_id)


def test_combat_summon_gm_creates_global_event():
    """P2-3/GM: summon_gm writes global_events row and combat log."""
    import sqlite3

    enc_id = "practice_iggy_01_quick"
    client = oikonomia.app.test_client()
    login(client, "SummonGmSolo")
    client.post("/team/create", data={"team_name": "SummonGm"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    squad_id = conn.execute(
        "SELECT squad_id FROM squads WHERE team_id = ? LIMIT 1", (team_id,)
    ).fetchone()[0]
    conn.close()

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    start = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    ).get_json() or {}
    combat_id = start.get("combat_id")
    ok("summon_gm: start combat", start.get("success") and combat_id, str(start)[:120])

    resp = client.post(
        "/combat/summon_gm",
        json={"combat_id": combat_id},
        content_type="application/json",
    ).get_json() or {}
    ok("summon_gm: success", resp.get("success"), str(resp))

    conn = sqlite3.connect(_test_db_path())
    row = conn.execute(
        "SELECT title, description FROM global_events ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    conn.close()
    ok("summon_gm: global_events row", row and "救援訊號" in (row[0] or ""), str(row))

    combat = get_combat(combat_id) or {}
    logs = combat.get("logs") or []
    ok(
        "summon_gm: combat log entry",
        any("求助" in (e.get("message") if isinstance(e, dict) else str(e)) for e in logs),
        str(logs[-3:]),
    )

    teardown_test_combat(team_id, enc_id)


def test_escape_success_ends_combat():
    """Escape success ends combat with outcome escaped."""
    from models.protagonist import update_protagonist_state

    enc_id = "practice_iggy_01_quick"
    client = oikonomia.app.test_client()
    login(client, "EscapeWinSolo")
    client.post("/team/create", data={"team_name": "EscapeWin"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    conn.close()
    update_protagonist_state(team_id, "iggy", is_active=0)

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    start = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    ).get_json() or {}
    combat_id = start.get("combat_id")
    ok("escape win: start", start.get("success") and combat_id, str(start)[:120])

    with patch("models.combat.random.random", return_value=0.01):
        data = client.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "escape"},
            content_type="application/json",
        ).get_json() or {}

    ok("escape win: outcome escaped", data.get("outcome") == "escaped", str(data)[:200])
    ok("escape win: winner escaped", data.get("winner") == "escaped", str(data)[:200])
    settlement = data.get("round_settlement") or {}
    ok("escape win: escape_success", settlement.get("escape_success") is True, str(settlement))
    ok(
        "escape win: combat ended",
        (get_combat(combat_id) or {}).get("winner") == "escaped",
        str(get_combat(combat_id)),
    )

    teardown_test_combat(team_id, enc_id)


def test_solo_multi_round_poll_hp_monotonic():
    """Solo multi-round: submit + poll must return decreasing enemy.hp (Henry scenario)."""
    from models.protagonist import update_protagonist_state

    enc_id = "practice_iggy_03_boundary"
    client = oikonomia.app.test_client()
    login(client, "SoloPollHp")
    client.post("/team/create", data={"team_name": "SoloPoll"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    conn.close()
    update_protagonist_state(team_id, "iggy", is_active=0)

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    r = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    )
    combat_id = (r.get_json() or {}).get("combat_id")
    start_hp = combat_enemy_hp(get_combat(combat_id), default=-1)
    ok("solo poll hp: start", start_hp > 0, str(start_hp))

    prev_payload_hp = start_hp
    prev_poll_hp = start_hp
    import models.combat as combat_model

    orig_auto = combat_model.choose_protagonist_auto_action
    combat_model.choose_protagonist_auto_action = lambda p, settings=None: {
        "action_type": "defend",
        "dice_result": 1,
    }
    try:
        for round_no in range(1, 4):
            with patch("routes.combat.roll_combat_dice", return_value=1):
                d = client.post(
                    "/combat/submit_action",
                    json={"combat_id": combat_id, "action_type": "attack"},
                    content_type="application/json",
                ).get_json() or {}
            if d.get("outcome"):
                ok("solo poll hp: skip victory", False, f"victory round {round_no}")
                break
            ok(
                f"solo poll hp: R{round_no} round_resolved",
                d.get("round_resolved") or d.get("status") == "round_resolved",
                str(d)[:160],
            )
            payload_hp_raw = (d.get("enemy") or {}).get("hp")
            payload_hp = int(payload_hp_raw) if payload_hp_raw is not None else None
            ok(
                f"solo poll hp: R{round_no} payload dropped",
                payload_hp is not None and payload_hp < prev_payload_hp,
                f"{prev_payload_hp}->{payload_hp}",
            )
            settlement = d.get("round_settlement") or {}
            ok(
                f"solo poll hp: R{round_no} settlement present",
                int(settlement.get("team_damage_dealt") or 0) > 0,
                str(settlement)[:120],
            )
            after = settlement.get("enemy_hp_after")
            ok(
                f"solo poll hp: R{round_no} after matches payload",
                after is not None and int(after) == payload_hp,
                f"after={after}, payload={payload_hp}",
            )

            st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
            poll_hp_raw = (st.get("enemy") or {}).get("hp")
            poll_hp = int(poll_hp_raw) if poll_hp_raw is not None else None
            ok(
                f"solo poll hp: R{round_no} poll matches payload",
                poll_hp == payload_hp,
                f"poll={poll_hp}, payload={payload_hp}",
            )
            ok(
                f"solo poll hp: R{round_no} poll monotonic",
                poll_hp is not None and poll_hp <= prev_poll_hp,
                f"{prev_poll_hp}->{poll_hp}",
            )
            ok(
                f"solo poll hp: R{round_no} db matches",
                combat_enemy_hp(get_combat(combat_id), default=-1) == payload_hp,
                "db mismatch",
            )
            prev_payload_hp = payload_hp
            prev_poll_hp = poll_hp
    finally:
        combat_model.choose_protagonist_auto_action = orig_auto

    teardown_test_combat(team_id, enc_id)


def test_zombie_hp_zero_status_poll_returns_victory():
    """Status poll must end combat when enemy HP is 0 but status still player_phase."""
    from models.protagonist import update_protagonist_state

    enc_id = "practice_iggy_03_boundary"
    client = oikonomia.app.test_client()
    login(client, "ZombieHpZero")
    client.post("/team/create", data={"team_name": "ZombieHp"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    conn.close()
    update_protagonist_state(team_id, "iggy", is_active=0)

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    r = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    )
    combat_id = (r.get_json() or {}).get("combat_id")
    ok("zombie hp0: start", bool(combat_id), str(r.get_json())[:120])

    from models.combat import append_combat_log, save_combat

    combat = get_combat(combat_id)
    combat = append_combat_log(
        combat,
        "練習・界線共生影 受到共 140 點傷害，剩餘 HP 0",
        log_type="summary",
    )
    save_combat(
        combat_id,
        status="player_phase",
        enemy_hp=4,
        logs=combat.get("logs"),
        winner=None,
    )

    st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
    ok("zombie hp0: poll returns victory", st.get("outcome") == "victory", str(st)[:200])
    ok("zombie hp0: poll inactive", st.get("active") is False, str(st.get("active")))
    ok(
        "zombie hp0: db ended",
        (get_combat(combat_id) or {}).get("status") == "ended",
        str((get_combat(combat_id) or {}).get("status")),
    )

    teardown_test_combat(team_id, enc_id)


def test_practice_combat_start_enemy_hp_full():
    """Fresh practice combat must start with full enemy HP (not 0 from stale reconcile)."""
    from models.protagonist import update_protagonist_state

    cases = (
        ("practice_iggy_01_quick", 48),
        ("practice_iggy_03_boundary", 140),
    )
    for enc_id, expected_hp in cases:
        client = oikonomia.app.test_client()
        login(client, f"StartHp_{enc_id[-6:]}")
        client.post("/team/create", data={"team_name": f"StartHp_{enc_id[-6:]}"})
        client.post("/set_team_route_by_leader", data={"route": "iggy"})
        import sqlite3

        conn = sqlite3.connect(_test_db_path())
        team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
        conn.close()
        update_protagonist_state(team_id, "iggy", is_active=0)
        teardown_test_combat(team_id, enc_id)
        clear_encounter_completion(team_id, enc_id)

        start = client.post(
            "/combat/start",
            json={"encounter_id": enc_id},
            content_type="application/json",
        ).get_json() or {}
        combat_id = start.get("combat_id")
        ok(f"start hp {enc_id}: created", bool(combat_id), str(start)[:120])
        db_hp = combat_enemy_hp(get_combat(combat_id), default=-1)
        ok(f"start hp {enc_id}: db", db_hp == expected_hp, f"db={db_hp}")

        st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
        payload_hp = (st.get("enemy") or {}).get("hp")
        ok(
            f"start hp {enc_id}: status poll",
            payload_hp is not None and int(payload_hp) == expected_hp,
            f"poll={payload_hp}",
        )
        ok(
            f"start hp {enc_id}: still active",
            st.get("active") is True and not st.get("outcome"),
            str(st)[:160],
        )
        teardown_test_combat(team_id, enc_id)


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


PRODUCTION_ENCOUNTERS = (
    "enc_iggy_01_leech",
    "enc_iggy_02_boundary",
    "enc_marah_01_whisper",
)


def test_near_death_rescue_security(client, leader_id, member_id):
    import sqlite3
    from datetime import datetime, timedelta

    from models.item import (
        get_item_by_qr_code_value,
        grant_item_to_squad,
        is_near_death_rescue_item,
    )

    until = (datetime.now() + timedelta(minutes=15)).isoformat()
    update_squad(member_id, near_death_until=until, hp=0)

    login(client, leader_id)
    rescuer_until = (datetime.now() + timedelta(minutes=15)).isoformat()
    update_squad(leader_id, near_death_until=rescuer_until, hp=0)
    r = client.post("/combat/rescue_near_death", json={"rescue_type": "prayer"})
    blocked = r.get_json() or {}
    ok(
        "rescuer near_death blocked",
        r.status_code == 400 and not blocked.get("success"),
        str(blocked),
    )
    update_squad(leader_id, near_death_until=None, hp=100)

    update_squad(leader_id, sanity=0)
    r = client.post("/combat/rescue_near_death", json={"rescue_type": "prayer"})
    sanity_blocked = r.get_json() or {}
    ok(
        "rescuer sanity collapse blocked",
        r.status_code == 400 and not sanity_blocked.get("success"),
        str(sanity_blocked),
    )
    update_squad(leader_id, sanity=50)

    r = client.post(
        "/combat/rescue_near_death",
        json={"rescue_type": "item", "item_id": 99999},
    )
    data = r.get_json() or {}
    ok("item rescue rejected without ownership", r.status_code == 400 and not data.get("success"))

    r = client.post("/combat/rescue_near_death", json={"rescue_type": "exploit"})
    ok("invalid rescue_type rejected", r.status_code == 400)

    qr_value = f"test-rescue-item-{os.getpid()}"
    db = os.path.join(TEST_DIR, "oikonomia.db")
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM player_items WHERE squad_id = ?", (leader_id,))
    conn.execute(
        """INSERT INTO items
           (name, description, icon, qr_code_value, has_ability, effect_type, effect_value, is_active)
           VALUES ('測試藥水', 'test', '💊', ?, 1, 'hp_up', 10, 1)""",
        (qr_value,),
    )
    conn.commit()
    conn.close()

    item = get_item_by_qr_code_value(qr_value)
    ok("rescue test item visible", item is not None, qr_value)
    ok("rescue test item eligible", is_near_death_rescue_item(item), str(item))
    item_id = item["id"]

    granted, grant_msg, _effect = grant_item_to_squad(leader_id, item_id, source="test")
    ok("grant rescue item", granted, grant_msg)
    r = client.post(
        "/combat/rescue_near_death",
        json={"rescue_type": "item", "item_id": item_id},
    )
    data = r.get_json() or {}
    ok("item rescue with hp_up consumes item", data.get("success") and data.get("rescued"), str(data))

    member = get_squad(member_id)
    ok("target revived hp=25", int(member.get("hp") or 0) == 25, str(member))
    ok("target near_death cleared", not member.get("near_death_until"))
    update_squad(member_id, near_death_until=None, hp=100)


def test_combat_start_rejects_body_squad_id_spoof(client, leader_id, member_id, team_id):
    """Body squad_id must not override session (IDOR prevention)."""
    from datetime import datetime

    from models.combat import clear_team_combat_id, get_combat, save_combat

    prepare_test_encounter(client, team_id, TEST_ENCOUNTER_ID)
    login(client, leader_id)

    r = client.post(
        "/combat/start",
        json={"encounter_id": TEST_ENCOUNTER_ID, "squad_id": member_id},
        content_type="application/json",
    )
    start = r.get_json() or {}
    ok("spoof start returns success", start.get("success"), str(start))
    combat_id = start.get("combat_id")
    combat = get_combat(combat_id) if combat_id else None
    ok(
        "combat owned by session squad not body",
        combat and combat.get("squad_id") == leader_id,
        f"expected {leader_id} got {(combat or {}).get('squad_id')}",
    )
    if combat_id:
        save_combat(combat_id, status="ended", winner="squad", ended_at=datetime.now().isoformat())
        clear_team_combat_id(team_id)


def test_rescue_near_death_target_squad_id(client, leader_id, member_id, team_id):
    """Explicit target_squad_id rescues the intended teammate when multiple are near death."""
    from datetime import datetime, timedelta

    client3 = oikonomia.app.test_client()
    p3 = login(client3, "TestMember2")
    ok("player3 login", p3 and p3.get("squad_id"))
    member2_id = p3.get("squad_id")
    join3 = client3.post("/team/join", data={"team_id": team_id}).get_json() or {}
    ok("player3 join team", join3.get("success"), str(join3))

    until_long = (datetime.now() + timedelta(minutes=30)).isoformat()
    until_short = (datetime.now() + timedelta(minutes=10)).isoformat()
    update_squad(member_id, near_death_until=until_long, hp=0)
    update_squad(member2_id, near_death_until=until_short, hp=0)

    login(client, leader_id)
    update_squad(leader_id, near_death_until=None, hp=100, sanity=50)

    r = client.post(
        "/combat/rescue_near_death",
        json={"rescue_type": "prayer", "target_squad_id": member2_id},
    )
    data = r.get_json() or {}
    ok("targeted rescue success", data.get("success"), str(data))

    m2 = get_squad(member2_id)
    m1 = get_squad(member_id)
    ok(
        "selected target deadline shortened",
        m2.get("near_death_until") and m2["near_death_until"] != until_short,
        f"until={m2.get('near_death_until')}",
    )
    ok(
        "non-target still near death",
        m1.get("near_death_until") == until_long,
        f"member1 until={m1.get('near_death_until')}",
    )

    update_squad(member_id, near_death_until=None, hp=100)
    update_squad(member2_id, near_death_until=None, hp=100)


def test_create_combat_record_active_guard(leader_id, team_id):
    from models.combat import (
        ActiveCombatExistsError,
        clear_team_combat_id,
        create_combat_record,
        get_active_combat_for_team,
        save_combat,
    )
    from models.encounter import load_encounter

    enc = load_encounter(TEST_ENCOUNTER_ID)
    active_before = get_active_combat_for_team(team_id)
    if active_before:
        save_combat(active_before["id"], status="ended", winner="squad")
        clear_team_combat_id(team_id)

    combat = create_combat_record(leader_id, TEST_ENCOUNTER_ID, enc, initial_status="player_phase")
    ok("create_combat_record opens combat", combat and combat.get("id"))
    duplicate = False
    try:
        create_combat_record(leader_id, TEST_ENCOUNTER_ID, enc, initial_status="player_phase")
    except ActiveCombatExistsError:
        duplicate = True
    ok("create_combat_record blocks duplicate team combat", duplicate)
    save_combat(combat["id"], status="ended", winner="squad")
    clear_team_combat_id(team_id)


def test_encounter_list_hides_test_for_players(client, team_id):
    """Non-GM players must not see trigger_type=test encounters in /encounters."""
    r = client.get("/encounters")
    data = r.get_json() or {}
    ok("encounter list API", data.get("success"), str(data)[:200])
    ids = [e.get("encounter_id") for e in (data.get("encounters") or [])]
    for hidden_id in (
        "test_combat_01",
        "test_undefeatable",
        "test_protagonist_control",
        "test_hard_win_item",
        "test_lose_trauma",
    ):
        ok(f"encounter list hides {hidden_id}", hidden_id not in ids, str(ids))
    ok(
        "encounter list shows first story encounter",
        "enc_iggy_01_leech" in ids,
        str(ids),
    )
    for practice_id in (
        "practice_iggy_01_quick",
        "practice_iggy_02_leech",
        "practice_iggy_03_boundary",
        "practice_iggy_04_marathon",
    ):
        ok(f"encounter list shows {practice_id}", practice_id in ids, str(ids))
    practice = next((e for e in (data.get("encounters") or []) if e.get("encounter_id") == "practice_iggy_01_quick"), {})
    ok("practice encounter is replayable", practice.get("replayable") is True, str(practice))
    ok("encounter list has progress hint", bool(data.get("progress_hint")), data.get("progress_hint"))


def test_encounters_reconcile_stale_active_combat(client, team_id, leader_id):
    """Finished combat with stale current_combat_id must not surface as active in lobby."""
    from models.combat import (
        clear_team_combat_id,
        create_combat_record,
        get_active_combat_for_team,
        save_combat,
        set_team_combat_id,
    )
    from models.encounter import load_encounter
    from models.squad import get_squad

    enc = load_encounter("practice_iggy_01_quick")
    clear_team_combat_id(team_id)
    combat = create_combat_record(
        leader_id, enc["encounter_id"], enc, initial_status="player_phase",
    )
    combat_id = combat["id"]

    save_combat(combat_id, status="player_phase", enemy_hp=0)
    set_team_combat_id(team_id, combat_id)

    r = client.get("/encounters")
    data = r.get_json() or {}
    ok("encounters reconcile: success", data.get("success"), str(data)[:200])
    ok("encounters reconcile: no stale active_combat", data.get("active_combat") is False, str(data))
    ok("encounters reconcile: active_combat_id cleared", not data.get("active_combat_id"), str(data))

    squad = get_squad(leader_id)
    ok(
        "encounters reconcile: squad current_combat_id cleared",
        not squad.get("current_combat_id"),
        str(squad),
    )
    ok(
        "encounters reconcile: get_active_combat_for_team empty",
        get_active_combat_for_team(team_id) is None,
        str(data),
    )

    save_combat(combat_id, status="ended", winner="squad")
    clear_team_combat_id(team_id)


def test_practice_boundary_settlement_enemy_hp(client, team_id):
    """Round settlement must include enemy_hp_after matching DB after damage."""
    from models.protagonist import update_protagonist_state

    update_protagonist_state(team_id, "iggy", is_active=0)
    enc_id = "practice_iggy_03_boundary"
    teardown_test_combat(team_id, enc_id)
    r = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    )
    combat_id = (r.get_json() or {}).get("combat_id")
    ok("boundary hp test: start", combat_id, str(r.get_json())[:120])
    start_hp = int((get_combat(combat_id) or {}).get("enemy_hp") or 0)

    with patch("routes.combat.roll_combat_dice", return_value=1):
        d = client.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "attack"},
            content_type="application/json",
        ).get_json() or {}
    if d.get("outcome"):
        ok("boundary hp test: skip one-shot", True, "victory in one round")
        teardown_test_combat(team_id, enc_id)
        return

    settlement = d.get("round_settlement") or {}
    payload_hp = int((d.get("enemy") or {}).get("hp") or -1)
    after = settlement.get("enemy_hp_after")
    db_hp = int((get_combat(combat_id) or {}).get("enemy_hp") or -1)
    ok("boundary hp test: team dealt damage", int(settlement.get("team_damage_dealt") or 0) > 0, str(settlement))
    breakdown = settlement.get("breakdown") or {}
    dealt = breakdown.get("dealt") or {}
    taken = breakdown.get("taken") or {}
    enemy_bd = breakdown.get("enemy") or {}
    ok("boundary hp test: breakdown dealt total", int(dealt.get("total") or 0) > 0, str(dealt))
    ok(
        "boundary hp test: breakdown enemy damage_taken",
        int(enemy_bd.get("damage_taken") or 0) == int(settlement.get("team_damage_dealt") or 0),
        str(enemy_bd),
    )
    ok(
        "boundary hp test: breakdown taken total",
        int(taken.get("total") or 0) == int(settlement.get("enemy_damage_dealt") or 0),
        str(taken),
    )
    ok("boundary hp test: player_hits have role", all(h.get("role") for h in settlement.get("player_hits") or []), str(settlement.get("player_hits")))
    ok("boundary hp test: enemy_hp_after present", after is not None, str(settlement))
    ok("boundary hp test: hp dropped", payload_hp < start_hp, f"{start_hp}->{payload_hp}")
    ok("boundary hp test: after matches payload", int(after) == payload_hp, f"{after} vs {payload_hp}")
    ok("boundary hp test: after matches db", int(after) == db_hp, f"{after} vs db {db_hp}")
    teardown_test_combat(team_id, enc_id)


def test_practice_encounter_replayable(client, team_id):
    """Practice fights can be started again after victory without new player."""
    from models.encounter import load_encounter
    from models.encounter_outcomes import encounter_already_completed, record_encounter_completion

    enc_id = "practice_iggy_01_quick"
    enc = load_encounter(enc_id)
    ok("practice encounter loads", enc is not None)
    record_encounter_completion(team_id, enc_id, "success", narrative="prior run")
    ok("practice marked completed in db", encounter_already_completed(team_id, enc_id))

    r = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    )
    data = r.get_json() or {}
    ok("practice replay start allowed", data.get("success") and data.get("combat_id"), str(data)[:200])

    from models.combat import clear_team_combat_id, get_active_combat_for_team, save_combat
    from datetime import datetime

    active = get_active_combat_for_team(team_id)
    if active:
        save_combat(active["id"], status="ended", winner="enemy", ended_at=datetime.now().isoformat())
        clear_team_combat_id(team_id)


def test_encounter_catalog():
    """Production encounter JSON must load with required fields."""
    from models.encounter import load_encounter

    required_enemy = ("name", "hp")
    for eid in PRODUCTION_ENCOUNTERS:
        enc = load_encounter(eid)
        ok(f"encounter loads: {eid}", enc is not None)
        if not enc:
            continue
        ok(f"{eid} encounter_id matches", enc.get("encounter_id") == eid)
        ok(f"{eid} has title", bool(enc.get("title")))
        ok(f"{eid} has route", bool(enc.get("route")))
        ok(f"{eid} has enemy", isinstance(enc.get("enemy"), dict))
        enemy = enc.get("enemy") or {}
        for key in required_enemy:
            ok(f"{eid} enemy.{key}", key in enemy and enemy[key] not in (None, ""))
        ok(f"{eid} success narrative", bool((enc.get("success") or {}).get("narrative")))
        ok(f"{eid} failure narrative", bool((enc.get("failure") or {}).get("narrative")))


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

    test_encounter_list_hides_test_for_players(client, team_id)
    test_encounters_reconcile_stale_active_combat(client, team_id, leader_id)
    test_practice_encounter_replayable(client, team_id)
    test_practice_boundary_settlement_enemy_hp(client, team_id)

    # --- 玩家 2：加入隊伍 ---
    client2 = oikonomia.app.test_client()
    p2 = login(client2, "TestMember")
    ok("玩家2 登入", p2 and p2.get("squad_id"))
    member_id = p2.get("squad_id")

    r2 = client2.post("/team/join", data={"team_id": team_id})
    join_data = r2.get_json()
    ok("玩家2 加入隊伍", join_data.get("success"), str(join_data))

    test_defend_team_buff_helpers()
    test_trauma_ending_thresholds()
    test_encounter_catalog()
    test_enemy_hp_updates_after_round(client, client2, team_id)
    test_enemy_hp_reconciled_from_logs(client, leader_id, team_id)

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
    test_near_death_rescue_security(client, leader_id, member_id)
    test_create_combat_record_active_guard(leader_id, team_id)
    test_trauma_bad_ending_victory(client, client2, team_id, leader_id, member_id)
    test_protagonist_player_control(client, client2, team_id, route="iggy")
    test_non_leader_as_protagonist_rejected()
    test_solo_killing_blow_returns_victory(client, client2, team_id)
    test_solo_killing_blow_practice_quick()
    test_escape_action_type_allowed()
    test_defeat_outcome_includes_dead_roster()
    test_select_enemy_counter_target_priority()
    test_escape_fail_mixed_settlement()
    test_use_item_combat_consumes_and_resolves()
    test_use_item_hp_up_and_sanity_up_in_combat()
    test_combat_summon_gm_creates_global_event()
    test_escape_success_ends_combat()
    test_solo_multi_round_poll_hp_monotonic()
    test_zombie_hp_zero_status_poll_returns_victory()
    test_practice_combat_start_enemy_hp_full()
    test_phase2_trauma_service_pipeline()
    test_phase2_narrative_orchestrator_pipeline()
    test_maybe_resolve_ready_claim_inside_tx()
    test_maybe_resolve_monotonic_phase_guard()
    test_phase2_gm_override_gateway()
    test_combat_start_rejects_body_squad_id_spoof(client, leader_id, member_id, team_id)
    test_rescue_near_death_target_squad_id(client, leader_id, member_id, team_id)

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
    ok("combat_v2_module marker", ver.get("markers", {}).get("combat_v2_module") is True)
    ok("player_max_hp marker", ver.get("markers", {}).get("player_max_hp") is True)
    ok("protagonist_combat marker", ver.get("markers", {}).get("protagonist_combat") is True)
    ok("trauma_ending marker", ver.get("markers", {}).get("trauma_ending") is True)
    ok("confirm_modal marker", ver.get("markers", {}).get("confirm_modal") is True)
    ok("combat_v2 marker key present", "combat_v2" in (ver.get("markers") or {}))
    ok("encounter_logs marker", ver.get("markers", {}).get("encounter_logs") is True)

    r = client.get("/encounter_logs")
    enc_logs = r.get_json() or {}
    ok("encounter_logs API", enc_logs.get("success") and enc_logs.get("has_team"), str(enc_logs)[:200])
    logs = enc_logs.get("logs") or []
    ok("encounter_logs has entries", len(logs) >= 1, f"count={len(logs)}")
    if logs:
        latest = logs[0]
        ok("encounter_log has outcome", bool(latest.get("outcome_label")), str(latest)[:200])
        ok("encounter_log has reward_lines", isinstance(latest.get("reward_lines"), list), str(latest)[:200])

    ok("version 正確", ver.get("version") == oikonomia.read_deploy_version())

    print(f"\n=== 結果：{PASS} 通過 / {FAIL} 失敗 ===\n")
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())