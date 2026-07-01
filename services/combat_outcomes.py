"""Orchestrate post-combat rewards, trauma, and ending side effects."""
from models.protagonist import trauma_bad_ending_narrative
from services.ending import judge_ending
from utils.db_tx import with_db_retry


def _outcome_already_recorded(team_id, encounter_id):
    if not team_id or not encounter_id:
        return False
    from models.encounter_outcomes import encounter_already_completed

    return encounter_already_completed(team_id, encounter_id)


def resolve_combat_outcome(winner, team_id, encounter, starter_id, combat_id=None):
    """
    已重構：跨模組編排層管線 (INV-B/E 最終保障)
    透過中央原子 Transaction 鎖保護發放劇情獎勵與能帶更新。
    """
    from models.encounter_outcomes import (
        apply_encounter_failure,
        apply_encounter_failure_solo,
        apply_encounter_success_solo,
        apply_trauma_bad_ending_victory,
    )
    from services.narrative_orchestrator import execute_post_combat_success_pipeline

    result = {
        "winner": winner,
        "trauma_bad_ending": False,
        "log_messages": [],
        "ending": None,
        "applied_success": False,
        "applied_failure": False,
    }
    if not encounter or not winner:
        return result

    encounter_id = encounter.get("encounter_id")

    if winner == "escaped":
        result["log_messages"].append({
            "message": "全隊成功逃離戰場",
            "log_type": "escape_success",
        })
        return result

    if winner == "squad":

        def _apply_squad_outcome():
            squad_result = dict(result)
            ending = judge_ending(team_id) if team_id else {}
            squad_result["ending"] = ending
            trauma_total = int(ending.get("protagonist_trauma_total") or 0)
            already = _outcome_already_recorded(team_id, encounter_id)

            if team_id and ending.get("should_apply_bad_ending_victory"):
                if not already:
                    apply_trauma_bad_ending_victory(team_id, encounter)
                squad_result["trauma_bad_ending"] = True
                squad_result["log_messages"] = squad_result["log_messages"] + [{
                    "message": (
                        f"主角心理創傷過深（累計 {trauma_total}）——"
                        "勝利無法帶來真正救贖"
                    ),
                    "log_type": "trauma_ending",
                }]
            elif team_id:
                snap = execute_post_combat_success_pipeline(
                    team_id, encounter_id, starter_id,
                )
                squad_result["applied_success"] = "拒絕重複" not in snap.log_message
                squad_result["log_messages"] = squad_result["log_messages"] + [{
                    "message": snap.log_message,
                    "log_type": "story_progression",
                }]
            elif starter_id and not already:
                apply_encounter_success_solo(starter_id, encounter)
                squad_result["applied_success"] = True
            return squad_result

        return with_db_retry(_apply_squad_outcome)

    if winner == "enemy":

        def _apply_enemy_outcome():
            fail_result = dict(result)
            if team_id and not _outcome_already_recorded(team_id, encounter_id):
                apply_encounter_failure(team_id, encounter)
                fail_result["applied_failure"] = True
            elif starter_id:
                apply_encounter_failure_solo(starter_id, encounter)
                fail_result["applied_failure"] = True
            if team_id:
                fail_result["ending"] = judge_ending(team_id)
            return fail_result

        return with_db_retry(_apply_enemy_outcome)

    return result


def build_victory_outcome_payload(
    encounter,
    team_id=None,
    combat_id=None,
    current_round=0,
):
    """Build JSON payload for combat victory responses (INV-C monotonic fields)."""
    ending = judge_ending(team_id) if team_id else {}
    trauma_bad = bool(ending.get("trauma_bad_ending"))
    safe_combat_id = int(combat_id) if combat_id is not None else 0
    round_idx = max(0, int(current_round or 0))
    if round_idx > 0:
        settled_round_index = round_idx - 1
    else:
        settled_round_index = 0

    payload = {
        "success": True,
        "status": "ended",
        "outcome": "victory",
        "winner": "squad",
        "combat_id": safe_combat_id or None,
        "settled_round_index": settled_round_index,
        "settlement_id": f"{safe_combat_id}:{settled_round_index}",
        "narrative": (encounter or {}).get("success", {}).get("narrative"),
        "reflection_prompt": (encounter or {}).get("reflection_prompt"),
        "ending_condition": ending.get("ending_condition"),
        "protagonist_trauma_total": ending.get("protagonist_trauma_total", 0),
        "trauma_level": ending.get("trauma_level", "safe"),
    }
    if team_id:
        payload["ending"] = ending
        payload["ending_preview"] = ending.get("ending_preview")
    if trauma_bad:
        payload["trauma_bad_ending"] = True
        payload["narrative"] = trauma_bad_ending_narrative(encounter)
        payload["reflection_prompt"] = None
    return payload


def get_collapsed_combat_members(participants):
    """Squads that triggered INV-D (HP≤0 or active near-death)."""
    from models.squad import is_near_death_active

    collapsed = []
    for p in participants or []:
        if not p:
            continue
        if int(p.get("hp") or 0) <= 0 or is_near_death_active(p):
            collapsed.append(p)
    return collapsed


def build_defeat_outcome_payload(encounter, participants=None, team_id=None):
    dead = get_collapsed_combat_members(participants)
    if not dead and team_id:
        from models.squad import get_team_members

        dead = get_collapsed_combat_members(get_team_members(team_id))

    dead_ids = [m.get("squad_id") for m in dead if m.get("squad_id")]
    dead_names = [
        m.get("display_name") or m.get("squad_id")
        for m in dead
        if m.get("squad_id")
    ]
    failure = (encounter or {}).get("failure") or {}

    return {
        "success": True,
        "status": "ended",
        "outcome": "defeat",
        "outcome_type": "COMBAT_FAILED",
        "winner": "enemy",
        "narrative": failure.get("narrative"),
        "narrative_failure": failure.get("narrative")
        or failure.get("description")
        or "隊伍在西貢叢林中倒下了…",
        "requires_gm": True,
        "dead_squad_ids": dead_ids,
        "dead_squad_names": dead_names,
        "active": False,
    }