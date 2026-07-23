"""Orchestrate post-combat rewards, trauma, and ending side effects."""
from models.protagonist import trauma_bad_ending_narrative
from services.ending import judge_ending


def _outcome_already_recorded_team(team_id, encounter_id):
    if not team_id or not encounter_id:
        return False
    from models.encounter_outcomes import encounter_already_completed

    return encounter_already_completed(team_id, encounter_id)


def _outcome_already_recorded_solo(starter_id, encounter_id):
    if not starter_id or not encounter_id:
        return False
    from models.encounter_outcomes import encounter_already_completed_solo

    return encounter_already_completed_solo(starter_id, encounter_id)


def resolve_combat_outcome(winner, team_id, encounter, starter_id, combat_id=None):
    """
    Post-combat orchestration — idempotency enforced by encounter_completions SSOT.
    No outer with_db_retry: pipeline / completion checks must not race on dirty snapshots.
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

    def _post_combat_heal():
        """Every combat end restores 20% max HP for the party (+ protagonist)."""
        try:
            from models.squad import restore_party_hp_percent
            healed = restore_party_hp_percent(
                team_id=team_id,
                starter_id=starter_id,
                percent=20,
                include_protagonist=True,
            )
            if healed:
                result["hp_restored_percent"] = 20
                result["log_messages"].append({
                    "message": "戰鬥結束，全隊回復 20% 生命值",
                    "log_type": "hp_restore",
                })
        except Exception:
            pass

    if winner == "escaped":
        result["log_messages"].append({
            "message": "全隊成功逃離戰場",
            "log_type": "escape_success",
        })
        _post_combat_heal()
        return result

    if winner == "squad":
        ending = judge_ending(team_id) if team_id else {}
        result["ending"] = ending
        trauma_total = int(ending.get("protagonist_trauma_total") or 0)

        if team_id and ending.get("should_apply_bad_ending_victory"):
            if not _outcome_already_recorded_team(team_id, encounter_id):
                apply_trauma_bad_ending_victory(team_id, encounter)
                result["applied_success"] = True
            result["trauma_bad_ending"] = True
            result["log_messages"].append({
                "message": (
                    f"主角心理創傷過深（累計 {trauma_total}）——"
                    "勝利無法帶來真正救贖"
                ),
                "log_type": "trauma_ending",
            })
        elif team_id:
            try:
                snap = execute_post_combat_success_pipeline(
                    team_id, encounter_id, starter_id,
                )
                result["applied_success"] = "拒絕重複" not in snap.log_message
                result["log_messages"].append({
                    "message": snap.log_message,
                    "log_type": "story_progression",
                })
            except Exception as exc:
                result["log_messages"].append({
                    "message": f"劇情推進管線觸發等冪保護: {exc}",
                    "log_type": "idempotent_blocked",
                })
        elif starter_id and not _outcome_already_recorded_solo(starter_id, encounter_id):
            apply_encounter_success_solo(starter_id, encounter)
            result["applied_success"] = True

        # Queue post-combat story beats for team (progressive — one act beat at a time).
        unlock = (encounter or {}).get("success", {}).get("next_story_unlock")
        extra_unlocks = []
        try:
            from data.progression_gates import ENCOUNTER_STORY_UNLOCKS
            extra_unlocks = list(
                ENCOUNTER_STORY_UNLOCKS.get(
                    (encounter or {}).get("encounter_id") or "",
                    [],
                )
                or []
            )
        except Exception:
            extra_unlocks = []
        unlock_ids = []
        if unlock:
            unlock_ids.append(unlock)
        for u in extra_unlocks:
            if u and u not in unlock_ids:
                unlock_ids.append(u)
        if unlock_ids:
            result["next_story_unlock"] = unlock_ids[0]
            result["next_story_unlocks"] = unlock_ids
            try:
                from models.squad import get_team_members
                from services.story import grant_story_unlock
                members = (
                    get_team_members(team_id) if team_id else [{"squad_id": starter_id}]
                )
                for m in members or []:
                    sid = m.get("squad_id") if isinstance(m, dict) else None
                    if not sid:
                        continue
                    for u in unlock_ids:
                        grant_story_unlock(sid, u)
            except Exception:
                pass
        _post_combat_heal()
        return result

    if winner == "enemy":
        if team_id and not _outcome_already_recorded_team(team_id, encounter_id):
            apply_encounter_failure(team_id, encounter)
            result["applied_failure"] = True
        elif starter_id and not _outcome_already_recorded_solo(starter_id, encounter_id):
            apply_encounter_failure_solo(starter_id, encounter)
            result["applied_failure"] = True
        if team_id:
            result["ending"] = judge_ending(team_id)
        _post_combat_heal()
        return result

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
    settled_round_index = max(0, round_idx - 1)

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
        "next_story_unlock": (encounter or {}).get("success", {}).get("next_story_unlock"),
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
    """Squads that triggered INV-D (HP≤0 or active near-death while not revived)."""
    from models.squad import is_near_death_active

    collapsed = []
    for p in participants or []:
        if not p:
            continue
        try:
            hp = int(p.get("hp") or 0)
        except (TypeError, ValueError):
            hp = 0
        # is_near_death_active is false when HP>0 (revived / GM heal).
        if hp <= 0 or is_near_death_active(p):
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