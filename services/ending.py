"""Central ending judgment, application, and player-facing previews."""
import os

from models.protagonist import (
    FINAL_STAGE_THRESHOLD,
    TRAUMA_BAD_ENDING_LIMIT,
    ProtagonistLifeState,
    check_ending_condition,
    get_protagonist_life_state,
    get_protagonist_state,
    get_team_ending_state,
    get_team_ending_type,
    get_team_protagonist_trauma_total,
    get_team_story_stage,
    has_trauma_bad_ending,
    record_team_ending,
)
from services.narrative import get_conditional_narrative_fragment


def is_ending_orchestrator_enabled():
    """Rollback switch: set OIKONOMIA_ENDING_ENABLED=0 to skip orchestrator side effects."""
    return os.environ.get("OIKONOMIA_ENDING_ENABLED", "1").lower() not in (
        "0", "false", "no", "off",
    )


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


def ending_narrative_key(team_id, level=None):
    """Map trauma/ending band to conditional narrative fragment id."""
    level = level or trauma_level_for_team(team_id)
    return {
        "locked": "bad_ending_locked",
        "critical": "trauma_critical",
        "caution": "trauma_caution",
        "safe": "weakness_grace",
    }.get(level, "weakness_grace")


def ending_type_label(team_id, state=None):
    """Player-facing ending bucket: bad | neutral | good (good reserved for Phase 3)."""
    state = state or get_team_ending_state(team_id)
    condition = state.get("ending_condition") or check_ending_condition(team_id)
    if condition == "bad_ending" or state.get("ending_type") == "bad_ending":
        return "bad"
    return "neutral"


def build_trauma_summary(team_id, state=None):
    """Compact trauma stats for /status (no spoilers)."""
    state = state or get_team_ending_state(team_id)
    total = int(state.get("protagonist_trauma_total") or 0)
    until_bad = int(state.get("trauma_until_bad") or 0)
    level = trauma_level_for_team(team_id)
    return {
        "total": total,
        "limit": TRAUMA_BAD_ENDING_LIMIT,
        "until_bad_ending": until_bad,
        "level": level,
        "narrative_key": ending_narrative_key(team_id, level),
        "theology_note": (
            "我的能力是在人的軟弱上顯得完全。"
            if level in ("safe", "caution")
            else "即使在陰影中，盼望仍可能被記念。"
        ),
    }


def build_ending_preview(team_id, state=None):
    """Short summary for /status (no GM spoilers)."""
    state = state or get_team_ending_state(team_id)
    level = trauma_level_for_team(team_id)
    condition = state.get("ending_condition") or check_ending_condition(team_id)
    total = int(state.get("protagonist_trauma_total") or 0)
    until_bad = int(state.get("trauma_until_bad") or 0)
    narrative_key = ending_narrative_key(team_id, level)

    if level == "locked" or condition == "bad_ending":
        fragment = get_conditional_narrative_fragment("bad_ending_locked", team_id)
        message = fragment.get("summary") if fragment else (
            "主角的心理創傷過深，故事走向陰影結局。"
        )
        return {
            "level": "locked",
            "condition": condition,
            "message": message,
            "narrative_key": narrative_key,
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
        "narrative_key": narrative_key,
        "theology_note": "我們可以帶著軟弱前行，恩典在彼此同行中顯明。",
    }


def preview_ending_for_players(team_id, state=None):
    """Alias for player-safe ending preview (GM uses /gm for full detail)."""
    return build_ending_preview(team_id, state=state)


def build_protagonist_control_status(team_id, route=None):
    """Story stage + per-protagonist control eligibility for /status."""
    if not team_id:
        return {
            "story_stage": 0,
            "player_control_unlocked": False,
            "active_route": route,
            "protagonists": {},
        }

    story_stage = get_team_story_stage(team_id)
    protagonists = {}
    for key in ("iggy", "marah"):
        state = get_protagonist_state(team_id, key, create=False)
        if not state:
            continue
        life = get_protagonist_life_state(team_id, key)
        protagonists[key] = {
            "is_active": bool(int(state.get("is_active") or 0)),
            "life_state": life.value if isinstance(life, ProtagonistLifeState) else life,
            "trauma_count": int(state.get("trauma_count") or 0),
            "near_death": bool(state.get("near_death_until")),
        }

    return {
        "story_stage": story_stage,
        "player_control_unlocked": story_stage >= FINAL_STAGE_THRESHOLD,
        "active_route": route,
        "protagonists": protagonists,
    }


def apply_ending(team_id, ending_type, source=None):
    """
    Persist irreversible ending on teams row.
    ending_type: bad_ending | bad (aliases) — good/neutral reserved for later phases.
    """
    if not is_ending_orchestrator_enabled():
        return {"applied": False, "reason": "orchestrator_disabled"}

    normalized = (ending_type or "").strip().lower()
    if normalized in ("bad", "bad_ending"):
        applied = record_team_ending(team_id, "bad_ending", source=source)
        return {
            "applied": applied,
            "ending_type": "bad_ending",
            "ending_type_label": "bad",
            "narrative_key": "bad_ending_locked",
        }

    return {"applied": False, "reason": "unsupported_ending_type", "ending_type": ending_type}


def judge_ending(team_id):
    """
    Single entry for ending evaluation after combat or status refresh.
    Returns enriched ending state for APIs and combat outcome JSON.
    """
    state = get_team_ending_state(team_id)
    if not team_id:
        return {
            **state,
            "ending_type_label": "neutral",
            "narrative_key": "weakness_grace",
            "trauma_level": "safe",
            "trauma_summary": build_trauma_summary(None, state),
            "ending_preview": build_ending_preview(None, state),
            "should_apply_bad_ending_victory": False,
            "orchestrator_enabled": is_ending_orchestrator_enabled(),
        }

    condition = state.get("ending_condition") or check_ending_condition(team_id)
    locked = get_team_ending_type(team_id)
    trauma_bad = bool(state.get("trauma_bad_ending")) or has_trauma_bad_ending(team_id)
    level = trauma_level_for_team(team_id)

    return {
        **state,
        "ending_condition": locked or condition,
        "ending_type_label": ending_type_label(team_id, state),
        "narrative_key": ending_narrative_key(team_id, level),
        "trauma_bad_ending": trauma_bad or condition == "bad_ending",
        "trauma_level": level,
        "trauma_summary": build_trauma_summary(team_id, state),
        "ending_preview": build_ending_preview(team_id, state),
        "should_apply_bad_ending_victory": (
            is_ending_orchestrator_enabled() and trauma_bad and not locked
        ),
        "is_ending_locked": locked == "bad_ending",
        "orchestrator_enabled": is_ending_orchestrator_enabled(),
    }