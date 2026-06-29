"""Orchestrate post-combat rewards, trauma, and ending side effects."""
from models.encounter_outcomes import (
    apply_encounter_failure,
    apply_encounter_failure_solo,
    apply_encounter_success,
    apply_encounter_success_solo,
    apply_trauma_bad_ending_victory,
)
from models.protagonist import trauma_bad_ending_narrative
from services.ending import judge_ending


def resolve_combat_outcome(winner, team_id, encounter, starter_id, combat_id=None):
    """
    Unified post-combat pipeline. Returns dict with flags for combat log / API.

    winner: 'squad' | 'enemy' | None
    """
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

    if winner == "squad":
        ending = judge_ending(team_id) if team_id else {}
        result["ending"] = ending
        trauma_total = int(ending.get("protagonist_trauma_total") or 0)

        if team_id and ending.get("should_apply_bad_ending_victory"):
            apply_trauma_bad_ending_victory(team_id, encounter)
            result["trauma_bad_ending"] = True
            result["log_messages"].append({
                "message": (
                    f"主角心理創傷過深（累計 {trauma_total}）——"
                    "勝利無法帶來真正救贖"
                ),
                "log_type": "trauma_ending",
            })
        elif team_id:
            apply_encounter_success(team_id, encounter, starter_id)
            result["applied_success"] = True
        elif starter_id:
            apply_encounter_success_solo(starter_id, encounter)
            result["applied_success"] = True

    elif winner == "enemy":
        if team_id:
            apply_encounter_failure(team_id, encounter)
            result["applied_failure"] = True
        elif starter_id:
            apply_encounter_failure_solo(starter_id, encounter)
            result["applied_failure"] = True
        if team_id:
            result["ending"] = judge_ending(team_id)

    return result


def build_victory_outcome_payload(encounter, team_id=None):
    """Build JSON payload for combat victory responses."""
    ending = judge_ending(team_id) if team_id else {}
    trauma_bad = bool(ending.get("trauma_bad_ending"))
    payload = {
        "success": True,
        "status": "ended",
        "outcome": "victory",
        "winner": "squad",
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


def build_defeat_outcome_payload(encounter):
    return {
        "success": True,
        "status": "ended",
        "outcome": "defeat",
        "winner": "enemy",
        "narrative": (encounter or {}).get("failure", {}).get("narrative"),
    }