#!/usr/bin/env python3
"""
PythonAnywhere 遠端戰鬥 smoke：單場戰鬥連續跑 N 回合結算驗證。

用法:
  ./venv/bin/python3 scripts/pa_combat_smoke_30.py
  PA_RUNS=30 PA_GM_PIN=gm2026 PA_BASE=https://takjai.pythonanywhere.com
"""
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    print("需要 requests：pip install requests")
    sys.exit(1)

PA_BASE = os.environ.get("PA_BASE", "https://takjai.pythonanywhere.com").rstrip("/")
PA_GM_PIN = os.environ.get("PA_GM_PIN", "gm2026")
PA_RUNS = int(os.environ.get("PA_RUNS", "30"))
# 高 HP 測試敵，可連續多回合；需 GM session 開啟 test route
ENCOUNTER_ID = os.environ.get("PA_ENCOUNTER_ID", "test_undefeatable")
_RUN_TAG = os.environ.get("PA_RUN_TAG", str(int(time.time()))[-6:])
LEADER_NAME = os.environ.get("PA_LEADER", f"PA30_{_RUN_TAG}_L")
MEMBER_NAME = os.environ.get("PA_MEMBER", f"PA30_{_RUN_TAG}_M")
TEAM_NAME = os.environ.get("PA_TEAM", f"PA30_{_RUN_TAG}")

PASS = 0
FAIL = 0
ERRORS = []


def ok(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
        return True
    FAIL += 1
    msg = f"{label}" + (f" — {detail}" if detail else "")
    ERRORS.append(msg)
    print(f"  ✗ {msg}")
    return False


def jshort(obj, n=180):
    try:
        return json.dumps(obj, ensure_ascii=False)[:n]
    except Exception:
        return str(obj)[:n]


class PaClient:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": "oikonomia-pa-smoke/1.0"})

    def login(self, squad_id):
        r = self.s.post(f"{PA_BASE}/login", data={"squad_id": squad_id}, timeout=30)
        data = r.json() if "json" in r.headers.get("content-type", "") else {}
        return r.status_code == 200 and bool(data.get("squad_id"))

    def gm_enable_test(self):
        r = self.s.post(f"{PA_BASE}/gm/login", data={"pin": PA_GM_PIN}, timeout=30)
        data = r.json() if "json" in r.headers.get("content-type", "") else {}
        return data.get("success"), jshort(data)

    def post_json(self, path, payload=None):
        r = self.s.post(
            f"{PA_BASE}{path}",
            json=payload or {},
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"raw": r.text[:300]}

    def post_form(self, path, payload=None):
        r = self.s.post(f"{PA_BASE}{path}", data=payload or {}, timeout=60)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"raw": r.text[:300]}

    def get_json(self, path):
        r = self.s.get(f"{PA_BASE}{path}", timeout=60)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"raw": r.text[:300]}


def ensure_team(leader: PaClient, member: PaClient):
    if not leader.login(LEADER_NAME):
        return None, "leader login failed"
    gm_ok, gm_detail = leader.gm_enable_test()
    if not gm_ok:
        return None, f"gm login failed: {gm_detail}"

    code, team_data = leader.post_form("/team/create", {"team_name": TEAM_NAME})
    team_id = team_data.get("team_id")
    if not team_id:
        code, st = leader.get_json("/status")
        team_id = st.get("team_id") or (st.get("team") or {}).get("team_id")
    if not team_id:
        return None, f"no team_id: {jshort(team_data)}"

    leader.post_form("/set_team_route_by_leader", {"route": "iggy"})

    if not member.login(MEMBER_NAME):
        return None, "member login failed"
    member.post_form("/team/join", {"team_id": team_id})
    return team_id, None


def start_fresh_combat(leader: PaClient):
    code, start = leader.post_json("/combat/start", {"encounter_id": ENCOUNTER_ID})
    if start.get("combat_id"):
        return start.get("combat_id"), None
    if start.get("error") and "已有進行中" in start.get("error", ""):
        return start.get("combat_id"), None
    return None, jshort(start)


def gm_heal_squads(leader: PaClient, squad_ids):
    for sid in squad_ids:
        if not sid:
            continue
        leader.post_form("/gm/adjust", {"squad_id": sid, "field": "hp", "value": "100"})


def rescue_if_needed(member: PaClient, combat_id):
    member.post_json("/combat/rescue_near_death", {
        "combat_id": combat_id,
        "rescue_type": "prayer",
    })


def run_round(leader: PaClient, member: PaClient, combat_id, run_idx, leader_sid, member_sid):
    tag = f"round {run_idx}"

    code, d1 = leader.post_json("/combat/submit_action", {
        "combat_id": combat_id,
        "action_type": "attack",
    })
    if not ok(f"{tag}: leader waits", d1.get("status") == "waiting_for_teammates", jshort(d1)):
        return False, combat_id

    code, d2 = member.post_json("/combat/submit_action", {
        "combat_id": combat_id,
        "action_type": "attack",
    })

    if d2.get("outcome") in ("victory", "defeat"):
        ok(f"{tag}: unexpected combat end", False, d2.get("outcome"))
        return False, None

    if not ok(f"{tag}: round_resolved", d2.get("round_resolved") or d2.get("status") == "round_resolved", jshort(d2)):
        return False, combat_id

    settlement = d2.get("round_settlement") or {}
    team_dealt = int(settlement.get("team_damage_dealt") or d2.get("round_enemy_damage") or 0)
    ok(f"{tag}: round_settlement", bool(settlement), jshort(settlement))
    ok(f"{tag}: team_damage > 0", team_dealt > 0, str(team_dealt))
    ok(f"{tag}: enemy_damage field", "enemy_damage_dealt" in settlement, str(settlement.get("enemy_damage_dealt")))

    code, st = leader.get_json(f"/combat/status?combat_id={combat_id}")
    ok(f"{tag}: player_phase", st.get("status") == "player_phase", st.get("status"))
    ok(f"{tag}: ready next action", not (st.get("my_state") or {}).get("submitted"), "")
    pros = [m for m in (st.get("member_states") or {}).values() if m.get("is_protagonist")]
    ok(f"{tag}: protagonist present", len(pros) >= 1, str(len(pros)))

    gm_heal_squads(leader, [leader_sid, member_sid])
    rescue_if_needed(member, combat_id)

    return True, combat_id


def main():
    print(f"\n=== PA 戰鬥 Smoke × {PA_RUNS} 回合 ===")
    print(f"    base={PA_BASE}")
    print(f"    encounter={ENCOUNTER_ID}")

    probe = PaClient()
    code, ver = probe.get_json("/api/version")
    if not ok("PA online", code == 200 and ver.get("success"), jshort(ver)):
        return 1
    print(f"    version={ver.get('version')}")

    leader = PaClient()
    member = PaClient()
    team_id, err = ensure_team(leader, member)
    if not ok("setup team", team_id, err or ""):
        return 1
    print(f"    team_id={team_id}")

    code, lst = leader.get_json("/status")
    leader_sid = lst.get("squad_id")
    code, mst = member.get_json("/status")
    member_sid = mst.get("squad_id")
    gm_heal_squads(leader, [leader_sid, member_sid])

    combat_id, start_err = start_fresh_combat(leader)
    if not ok("start combat", combat_id, start_err or ""):
        return 1
    print(f"    combat_id={combat_id}")
    print(f"    leader={leader_sid} member={member_sid}")

    completed = 0
    for i in range(1, PA_RUNS + 1):
        print(f"\n--- 第 {i}/{PA_RUNS} 回合 ---")
        try:
            success, combat_id = run_round(leader, member, combat_id, i, leader_sid, member_sid)
            if success:
                completed += 1
            elif not combat_id:
                break
        except requests.RequestException as exc:
            ok(f"round {i}: network", False, str(exc))
            break
        time.sleep(0.12)

    print(f"\n=== 結果：{PASS} 通過 / {FAIL} 失敗（完成 {completed}/{PA_RUNS} 回合）===")
    if ERRORS:
        print("\n失敗摘要（最多 12 條）:")
        for e in ERRORS[:12]:
            print(f"  - {e}")
    return 0 if FAIL == 0 and completed == PA_RUNS else 1


if __name__ == "__main__":
    sys.exit(main())