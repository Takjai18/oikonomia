"""Central ending judgment and player-facing previews."""
from models.protagonist import (
    TRAUMA_BAD_ENDING_LIMIT,
    check_ending_condition,
    get_team_ending_state,
    get_team_ending_type,
    get_team_protagonist_trauma_total,
    has_trauma_bad_ending,
)
from services.narrative import get_conditional_narrative_fragment


def trauma_level_for_team(team_id):
    """
    Player-safe trauma band: safe | caution | critical | locked.
    locked = irreversible bad_ending on teams row.
    """
    if not team_id:
        return "safe"
    if get_team_ending_type(team_id) == "bad_ending":
        return "locked"
    total = get_team_protagonist_trauma_total(team_id)
    if total > TRAUMA_BAD_ENDING_LIMIT:
        return "critical"
    until_bad = max(0, TRAUMA_BAD_ENDING_LIMIT + 1 - total)
    if until_bad <= 1:
        return "critical"
    if until_bad <= 2 or total >= 2:
        return "caution"
    return "safe"


def build_ending_preview(team_id, state=None):
    """Short summary for /status (no GM spoilers)."""
    state = state or get_team_ending_state(team_id)
    level = trauma_level_for_team(team_id)
    condition = state.get("ending_condition") or check_ending_condition(team_id)
    total = int(state.get("protagonist_trauma_total") or 0)
    until_bad = int(state.get("trauma_until_bad") or 0)

    if level == "locked" or condition == "bad_ending":
        fragment = get_conditional_narrative_fragment("bad_ending_locked", team_id)
        message = fragment.get("summary") if fragment else (
            "主角的心理創傷過深，故事走向陰影結局。"
        )
        return {
            "level": "locked",
            "condition": condition,
            "message": message,
            "theology_note": "軟弱中仍可被記念，但救贖之路已偏離。",
        }

    if level == "critical":
        fragment = get_conditional_narrative_fragment("trauma_critical", team_id)
        message = fragment.get("summary") if fragment else (
            f"主角創傷累積 {total} 次，再承受多一次瀕死可能無法迎來真正結局。"
        )
    elif level == "caution":
        fragment = get_conditional_narrative_fragment("trauma_caution", team_id)
        message = fragment.get("summary") if fragment else (
            f"主角身上留有創傷（{total} 次）。記得彼此守望，在軟弱中互相扶持。"
        )
    else:
        fragment = get_conditional_narrative_fragment("weakness_grace", team_id)
        message = fragment.get("summary") if fragment else (
            "界線仍清晰，盼望仍在——「能力是在人的軟弱上顯得完全」。"
        )

    return {
        "level": level,
        "condition": condition,
        "message": message,
        "trauma_total": total,
        "trauma_until_bad": until_bad,
        "theology_note": "我們可以帶著軟弱前行，恩典在彼此同行中顯明。",
    }


def judge_ending(team_id):
    """
    Single entry for ending evaluation after combat or status refresh.
    Returns enriched ending state for APIs and combat outcome JSON.
    """
    state = get_team_ending_state(team_id)
    if not team_id:
        return {
            **state,
            "trauma_level": "safe",
            "ending_preview": build_ending_preview(None, state),
            "should_apply_bad_ending_victory": False,
        }

    condition = state.get("ending_condition") or check_ending_condition(team_id)
    locked = get_team_ending_type(team_id)
    trauma_bad = bool(state.get("trauma_bad_ending")) or has_trauma_bad_ending(team_id)

    return {
        **state,
        "ending_condition": locked or condition,
        "trauma_bad_ending": trauma_bad or condition == "bad_ending",
        "trauma_level": trauma_level_for_team(team_id),
        "ending_preview": build_ending_preview(team_id, state),
        "should_apply_bad_ending_victory": trauma_bad and not locked,
        "is_ending_locked": locked == "bad_ending",
    }