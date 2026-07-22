"""Combat API routes (migrated from app.py)."""
import os
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, session

from models.combat import (
    COMBAT_ACTION_TYPES,
    COMBAT_STATUS_RESOLVING,
    ActiveCombatExistsError,
    append_combat_log,
    build_combat_round_preview,
    build_combat_status_response,
    build_enemy_combat_stats,
    build_single_player_preview,
    clear_team_combat_id,
    combat_action_already_submitted,
    combat_phase_deadline,
    create_combat_record,
    get_active_combat_for_team,
    get_active_combat_member_ids,
    get_combat,
    get_combat_by_squad,
    get_combat_participants,
    get_combat_phase_actions,
    get_phase_submit_required_ids,
    advance_combat_from_poll,
    maybe_resolve_player_phase,
    resolve_player_phase,
    roll_combat_dice,
    save_combat,
    upsert_combat_action,
    _build_full_preview_from_status,
    _build_round_resolved_response,
    _combat_outcome_json,
    _attach_round_settlement,
    _enrich_settlement_meta,
    build_escape_outcome_response,
    build_victory_outcome_response,
    combat_outcome_if_finished,
)
from models.encounter import (
    encounter_is_replayable,
    encounter_route_matches,
    encounter_visible_to_player,
    evaluate_precheck_condition,
    load_encounter,
)
from models.encounter_outcomes import (
    apply_precheck_skip,
    encounter_already_completed,
)
from models.protagonist import get_controllable_protagonist_squad_id, get_team_story_stage
from models.item import apply_near_death_item_rescue
from models.squad import get_squad, get_team_members, is_near_death_active, update_squad
from services.global_events import create_global_event
from utils.decorators import require_player

combat_bp = Blueprint("combat", __name__)


def _json_victory_outcome(combat, encounter, squad_id, team_id=None, **extra):
    """Victory JSON with round_settlement for V2 SETTLEMENT before VICTORY (killing blow)."""
    combat_id = (combat or {}).get("id")
    if combat_id:
        combat = get_combat(combat_id) or combat
    payload = build_victory_outcome_response(
        combat, encounter, squad_id, team_id=team_id,
    )
    _attach_round_settlement(payload, combat=combat)
    _enrich_settlement_meta(payload, combat=combat)
    payload.update(extra)
    return jsonify(payload)


_DYNAMIC_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@combat_bp.after_request
def combat_disable_http_cache(response):
    """Prevent browsers from caching combat GET polls (Chrome/Safari disk cache)."""
    for key, value in _DYNAMIC_NO_CACHE_HEADERS.items():
        response.headers[key] = value
    return response


@combat_bp.route("/combat/start", methods=["POST"])
@require_player(response_style="combat")
def combat_start_api(encounter_id=None):
    body = request.json if request.is_json else {}
    is_e2e_mode = os.environ.get("COMBAT_E2E", "").lower() in ("1", "true", "yes")
    if is_e2e_mode and body.get("squad_id"):
        squad_id = str(body.get("squad_id")).strip()
    else:
        squad_id = session["squad_id"]
    encounter_id = encounter_id or body.get("encounter_id") or request.form.get("encounter_id")
    confirm = body.get("confirm") or request.form.get("confirm")

    if not encounter_id:
        return jsonify({"success": False, "error": "缺少 encounter_id"}), 400

    squad = get_squad(squad_id)
    if not squad or not squad.get("team_id"):
        return jsonify({"success": False, "error": "請先加入 Team 才能進行 Encounter"}), 400

    encounter = load_encounter(encounter_id)
    if not encounter:
        return jsonify({"success": False, "error": "Encounter 不存在"}), 404

    show_test = (
        session.get("is_gm")
        or os.environ.get("OIKONOMIA_SHOW_TEST_ENCOUNTERS", "").lower() in ("1", "true", "yes")
    )
    if not encounter_visible_to_player(encounter, show_test=show_test):
        return jsonify({"success": False, "error": "此 Encounter 僅供開發測試"}), 403

    team_id = squad["team_id"]
    if (
        not encounter_is_replayable(encounter)
        and encounter_already_completed(team_id, encounter_id)
    ):
        return jsonify({"success": False, "error": "此 Encounter 已完成"}), 400

    route = squad.get("route")
    if not encounter_route_matches(encounter.get("route"), route):
        return jsonify({"success": False, "error": "此 Encounter 不屬於你嘅路線"}), 400

    precheck = encounter.get("precheck", {})
    precheck_passed = bool(
        precheck.get("condition") and evaluate_precheck_condition(precheck["condition"], team_id)
    )

    status = "precheck" if precheck_passed else "player_phase"
    if encounter_is_replayable(encounter):
        stale = get_active_combat_for_team(team_id)
        if stale and int(stale.get("enemy_hp") or 0) <= 0:
            save_combat(
                stale["id"],
                status="ended",
                winner="squad",
                ended_at=datetime.now().isoformat(),
            )
            clear_team_combat_id(team_id)
    try:
        combat = create_combat_record(squad_id, encounter_id, encounter, initial_status=status)
    except ActiveCombatExistsError as exc:
        existing = get_combat(exc.combat_id)
        if existing and existing.get("status") == "precheck":
            combat = existing
        else:
            return jsonify({
                "success": False,
                "error": "已有進行中的戰鬥",
                "combat_id": exc.combat_id,
            }), 409 if existing else 400

    if confirm == "skip" and precheck_passed:
        apply_precheck_skip(team_id, encounter)
        save_combat(combat["id"], status="ended", winner="squad", ended_at=datetime.now().isoformat())
        clear_team_combat_id(team_id)
        return jsonify({
            "success": True,
            "skipped": True,
            "combat_id": combat["id"],
            "message": precheck.get("success_text", "成功避開戰鬥"),
            "narrative": precheck.get("skip_reward", {}).get("narrative"),
        })

    if confirm == "fight":
        if combat.get("status") == "precheck":
            now = datetime.now().isoformat()
            settings = encounter.get("combat_settings", {})
            save_combat(
                combat["id"],
                status="player_phase",
                current_phase=1,
                phase_started_at=now,
                phase_deadline=combat_phase_deadline(now, settings.get("phase_time_limit_seconds", 180)),
            )
            combat = get_combat(combat["id"])

    combat = get_combat(combat["id"]) or combat
    status_slice = build_combat_status_response(combat, encounter, squad_id)
    live_status = combat.get("status")
    combat_settings = (encounter or {}).get("combat_settings") or {}
    return jsonify({
        "success": True,
        "combat_id": combat["id"],
        "encounter_id": encounter_id,
        "status": live_status,
        "precheck_passed": precheck_passed,
        "can_skip": precheck_passed,
        "precheck_text": precheck.get("success_text") if precheck_passed else None,
        "active": live_status not in ("ended",),
        "round_resolved": False,
        "waiting_for_teammates": False,
        "outcome": None,
        "winner": None,
        "enemy": build_enemy_combat_stats(combat, encounter),
        "my_state": status_slice.get("my_state"),
        "member_states": status_slice.get("member_states"),
        "combat_settings": combat_settings,
        "tutorial_steps": combat_settings.get("tutorial_steps") or [],
        "encounter": {
            "encounter_id": encounter_id,
            "title": encounter.get("title"),
            "description": encounter.get("description"),
        },
    })

@combat_bp.route("/combat/status")
@require_player(response_style="combat")
def combat_status_api():
    combat_id = request.args.get("combat_id", type=int)
    squad_id = request.args.get("squad_id") or session["squad_id"]

    if combat_id:
        combat = get_combat(combat_id)
    else:
        squad = get_squad(squad_id)
        if squad and squad.get("team_id"):
            combat = get_active_combat_for_team(squad["team_id"])
        else:
            combat = get_combat_by_squad(squad_id)

    if not combat:
        return jsonify({"success": True, "active": False})

    if combat.get("status") == "ended":
        encounter = load_encounter(combat["encounter_id"])
        winner = combat.get("winner")
        if winner is None and int(combat.get("enemy_hp") or 0) <= 0:
            winner = "squad"
        squad = get_squad(session["squad_id"])
        team_id = squad.get("team_id") if squad else None
        if winner == "squad":
            return _json_victory_outcome(
                combat, encounter, session["squad_id"], team_id=team_id,
            )
        if winner == "enemy":
            ended_participants = get_combat_participants(combat) if combat else None
            return jsonify(_combat_outcome_json(
                "enemy",
                encounter,
                team_id=team_id,
                participants=ended_participants,
            ))
        if winner == "escaped":
            return jsonify(build_escape_outcome_response(
                combat, encounter, session["squad_id"], team_id=team_id,
            ))
        return jsonify({"success": True, "active": False, "winner": winner})

    encounter = load_encounter(combat["encounter_id"])
    settings = (encounter or {}).get("combat_settings", {})

    round_just_resolved = False
    poll_participants = None
    if combat.get("status") in ("player_phase", COMBAT_STATUS_RESOLVING):
        combat, winner, round_just_resolved, poll_participants = advance_combat_from_poll(
            combat["id"], settings,
        )
        actor = get_squad(session["squad_id"])
        actor_team_id = actor.get("team_id") if actor else None
        if winner == "squad":
            combat = get_combat(combat["id"]) or combat
            return _json_victory_outcome(
                combat, encounter, session["squad_id"], team_id=actor_team_id,
            )
        if winner == "escaped":
            combat = get_combat(combat["id"]) or combat
            return jsonify(build_escape_outcome_response(
                combat, encounter, session["squad_id"], team_id=actor_team_id,
            ))
        if winner == "enemy":
            defeat_participants = get_combat_participants(combat) if combat else None
            return jsonify({
                **_combat_outcome_json(
                    "enemy",
                    encounter,
                    team_id=actor_team_id,
                    participants=defeat_participants,
                ),
                "active": False,
            })
        if combat:
            finished = combat_outcome_if_finished(
                combat,
                encounter,
                team_id=actor_team_id,
                squad_id=session["squad_id"],
            )
            if finished:
                return jsonify({**finished, "active": False})
    payload = build_combat_status_response(
        combat, encounter, session["squad_id"], participants=poll_participants,
    )
    _attach_round_settlement(payload, combat=combat)
    payload["active"] = combat.get("status") not in ("ended", "precheck")
    payload["in_precheck"] = combat.get("status") == "precheck"
    if combat.get("status") == "resolving":
        payload["resolving"] = True

    if round_just_resolved:
        payload["status"] = "round_resolved"
        payload["round_resolved"] = True
        _enrich_settlement_meta(payload, combat=combat)
        payload["full_preview"] = _build_full_preview_from_status(payload)
    elif combat.get("status") == "player_phase":
        participants = poll_participants or get_combat_participants(combat) or []
        active_ids = get_active_combat_member_ids(participants or [])
        phase_actions = combat.get("phase_actions") or {}
        if session["squad_id"] in phase_actions and len(phase_actions) < len(active_ids):
            payload["waiting_for_teammates"] = True
            payload["submitted_count"] = len(phase_actions)
            payload["total_active"] = len(active_ids)

    raw_enemy_hp = (payload.get("enemy") or {}).get("hp")
    enemy_hp = int(raw_enemy_hp) if raw_enemy_hp is not None else 1
    if payload.get("active") and enemy_hp <= 0:
        combat = get_combat(combat["id"]) or combat
        squad = get_squad(session["squad_id"])
        actor_team_id = squad.get("team_id") if squad else None
        finished = combat_outcome_if_finished(
            combat,
            encounter,
            team_id=actor_team_id,
            squad_id=session["squad_id"],
        )
        if finished:
            return jsonify({**finished, "active": False})

    return jsonify(payload)

@combat_bp.route("/combat/preview_action", methods=["POST"])
@require_player(response_style="combat")
def combat_preview_action_api():
    body = request.json if request.is_json else request.form.to_dict()
    combat_id = body.get("combat_id")
    try:
        combat_id = int(combat_id) if combat_id else None
    except (TypeError, ValueError):
        combat_id = None

    action_type = (body.get("action_type") or body.get("action") or "").strip()
    if action_type not in COMBAT_ACTION_TYPES:
        return jsonify({"success": False, "error": "無效行動"}), 400

    # Preview uses neutral dice=1; authoritative roll happens on submit.
    dice_result = 1

    item_id = body.get("item_id")
    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"success": False, "error": "玩家不存在"}), 400

    if not combat_id:
        active = None
        if squad.get("team_id"):
            active = get_active_combat_for_team(squad["team_id"])
        if not active:
            active = get_combat_by_squad(session["squad_id"])
        combat_id = active["id"] if active else None

    if not combat_id:
        return jsonify({"success": False, "error": "沒有進行中的戰鬥"}), 400

    as_protagonist = bool(body.get("as_protagonist"))
    preview = build_combat_round_preview(
        combat_id,
        session["squad_id"],
        action_type,
        dice_result,
        item_id,
        as_protagonist=as_protagonist,
    )
    if not preview:
        return jsonify({"success": False, "error": "無法預覽此回合"}), 400

    preview["is_estimate"] = True
    preview["preview_note"] = "此為估算（普通骰）；實際結果於提交後由系統擲骰決定"
    return jsonify({"success": True, "preview": preview})

@combat_bp.route("/combat/submit_action", methods=["POST"])
@combat_bp.route("/combat/action", methods=["POST"])
@require_player(response_style="combat")
def combat_submit_action_api():
    body = request.json if request.is_json else request.form.to_dict()
    combat_id = body.get("combat_id")
    try:
        combat_id = int(combat_id) if combat_id else None
    except (TypeError, ValueError):
        combat_id = None

    action_type = (body.get("action_type") or body.get("action") or "").strip()
    if action_type not in COMBAT_ACTION_TYPES:
        return jsonify({"success": False, "error": "無效行動"}), 400

    dice_result = roll_combat_dice()

    item_id = body.get("item_id")
    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"success": False, "error": "玩家不存在"}), 400

    if not combat_id:
        active = None
        if squad.get("team_id"):
            active = get_active_combat_for_team(squad["team_id"])
        if not active:
            active = get_combat_by_squad(session["squad_id"])
        combat_id = active["id"] if active else None
    combat = get_combat(combat_id) if combat_id else None
    if not combat or combat.get("status") not in ("player_phase",):
        if combat and combat.get("status") == "resolving":
            return jsonify({"success": False, "error": "回合結算中，請稍候"}), 409
        return jsonify({"success": False, "error": "沒有進行中的 Player Phase"}), 400

    encounter = load_encounter(combat["encounter_id"])
    settings = (encounter or {}).get("combat_settings", {})
    story_stage = get_team_story_stage(squad["team_id"]) if squad.get("team_id") else 0
    as_protagonist = bool(body.get("as_protagonist"))
    if as_protagonist:
        if not bool(squad.get("is_team_leader")):
            return jsonify({
                "success": False,
                "error": "只有隊長特權才能啟動主角代打模式",
            }), 403
        acting_id = get_controllable_protagonist_squad_id(
            squad["team_id"], squad.get("route"), encounter, story_stage,
        )
        if not acting_id:
            return jsonify({
                "success": False,
                "error": "此階段或此關卡不可代替主角行動",
            }), 400
    else:
        acting_id = session["squad_id"]

    participants = get_combat_participants(combat) or []
    actor_state = next(
        (p for p in participants if p["squad_id"] == acting_id),
        squad if acting_id == session["squad_id"] else None,
    )
    if not actor_state:
        return jsonify({"success": False, "error": "找不到行動者或該主角未參戰"}), 400

    # Use SSOT helper (HP>0 counts as revived even if timer string is stale).
    if is_near_death_active(actor_state):
        label = "AI 主角" if as_protagonist else "你"
        return jsonify({
            "success": False,
            "error": f"{label}已陷入瀕死，無法執行任何行動",
        }), 400

    if action_type == "use_zoo":
        from models.combat import apply_effective_combat_settings, is_zoo_unlocked_for_team

        team_for_zoo = squad.get("team_id")
        effective = apply_effective_combat_settings(
            team_for_zoo,
            encounter=encounter,
            story_stage=story_stage,
            combat_settings=settings,
        )
        if not effective.get("allow_zoo", True):
            if not is_zoo_unlocked_for_team(team_for_zoo, story_stage=story_stage):
                return jsonify({
                    "success": False,
                    "error": "Zoo 能力尚未解鎖（故事階段未達）",
                }), 400
            return jsonify({"success": False, "error": "此戰鬥不允許 Zoo 能力"}), 400
    if as_protagonist and action_type == "use_item":
        return jsonify({"success": False, "error": "主角不可使用玩家物品"}), 400

    current_phase = int(combat.get("current_phase") or 0)
    if combat_action_already_submitted(combat_id, acting_id, current_phase):
        return jsonify({"success": False, "error": "本回合行動已提交"}), 400

    upsert_combat_action(
        combat_id,
        acting_id,
        current_phase,
        action_type,
        dice_result,
        item_id,
    )
    phase_actions = get_combat_phase_actions(combat_id, current_phase)
    save_combat(combat_id, phase_actions=phase_actions)

    combat, winner = maybe_resolve_player_phase(combat_id, settings)
    combat = get_combat(combat_id) or combat
    participants = get_combat_participants(combat) or []
    required_ids = get_phase_submit_required_ids(combat, participants)
    resolved_phase = int(combat.get("current_phase") or current_phase)
    round_resolved_this_submit = resolved_phase > current_phase
    phase_actions = get_combat_phase_actions(combat_id, resolved_phase)

    if winner == "squad":
        combat = get_combat(combat_id) or combat
        return _json_victory_outcome(
            combat,
            encounter,
            session["squad_id"],
            team_id=squad.get("team_id"),
            dice_result=dice_result,
        )
    if winner == "escaped":
        combat = get_combat(combat_id) or combat
        payload = build_escape_outcome_response(
            combat, encounter, session["squad_id"], team_id=squad.get("team_id"),
        )
        payload["dice_result"] = dice_result
        return jsonify(payload)
    if winner == "enemy":
        return jsonify(_combat_outcome_json("enemy", encounter))

    combat = get_combat(combat_id)
    finished = combat_outcome_if_finished(
        combat,
        encounter,
        team_id=squad.get("team_id"),
        squad_id=session["squad_id"],
    )
    if finished:
        return jsonify(finished)

    if (
        not round_resolved_this_submit
        and len(required_ids) > 1
        and len(phase_actions) < len(required_ids)
    ):
        me = next(
            (p for p in participants if p["squad_id"] == session["squad_id"]),
            None,
        )
        single_preview = build_single_player_preview(
            combat_id, session["squad_id"], squad=me,
        )
        status = build_combat_status_response(
            combat, encounter, session["squad_id"], participants=participants,
        )
        return jsonify({
            "success": True,
            "status": "waiting_for_teammates",
            "dice_result": dice_result,
            "single_preview": single_preview,
            "submitted_count": len(phase_actions),
            "total_active": len(required_ids),
            "combat_id": combat_id,
            "current_phase": combat.get("current_phase", 0),
            "message": "行動已提交，等待其他隊友行動中...",
            "active": True,
            "my_state": status.get("my_state"),
            "member_states": status.get("member_states"),
            "enemy": status.get("enemy"),
            "title": status.get("title"),
            "log": status.get("log"),
            "log_entries": status.get("log_entries"),
        })

    payload = _build_round_resolved_response(combat, encounter, session["squad_id"])
    payload["dice_result"] = dice_result
    payload["message"] = f"本回合已結算：{action_type}（骰 {dice_result}）"
    return jsonify(payload)

@combat_bp.route("/combat/resolve_phase", methods=["POST"])
@require_player(response_style="combat")
def combat_resolve_phase_api():
    body = request.json if request.is_json else request.form
    combat_id = body.get("combat_id")
    if not combat_id:
        return jsonify({"success": False, "error": "缺少 combat_id"}), 400

    combat, winner = resolve_player_phase(int(combat_id))
    encounter = load_encounter(combat["encounter_id"]) if combat else None

    if winner == "squad":
        return jsonify({
            "success": True,
            "outcome": "victory",
            "narrative": (encounter or {}).get("success", {}).get("narrative"),
            "reflection_prompt": (encounter or {}).get("reflection_prompt"),
        })
    if winner == "escaped":
        escape_block = (encounter or {}).get("escape") or {}
        return jsonify({
            "success": True,
            "outcome": "escaped",
            "narrative": escape_block.get("narrative") or "全隊成功脫離戰鬥。",
        })
    if winner == "enemy":
        return jsonify({
            "success": True,
            "outcome": "defeat",
            "narrative": (encounter or {}).get("failure", {}).get("narrative"),
        })

    payload = build_combat_status_response(combat, encounter, session["squad_id"])
    payload["active"] = True
    return jsonify(payload)

@combat_bp.route("/combat/rescue_near_death", methods=["POST"])
@require_player(response_style="combat")
def combat_rescue_near_death_api():
    body = request.json if request.is_json else request.form
    combat_id = body.get("combat_id")
    rescue_type = (body.get("rescue_type") or "prayer").strip()

    squad = get_squad(session["squad_id"])
    if not squad or not squad.get("team_id"):
        return jsonify({"success": False, "error": "請先加入 Team"}), 400

    if is_near_death_active(squad):
        return jsonify({
            "success": False,
            "error": "你自身已陷入瀕死，無法救援隊友",
        }), 400
    if int(squad.get("sanity") or 0) <= 0:
        return jsonify({
            "success": False,
            "error": "你的神智已崩潰，無法救援隊友",
        }), 400

    participants = get_team_members(squad["team_id"])
    target_squad_id = (body.get("target_squad_id") or "").strip() or None
    target = None

    def _is_near_death_active_member(member):
        if not member or not member.get("near_death_until"):
            return False
        try:
            return datetime.now() < datetime.fromisoformat(member["near_death_until"])
        except ValueError:
            return False

    if target_squad_id:
        candidate = next(
            (p for p in participants if p.get("squad_id") == target_squad_id),
            None,
        )
        if not candidate:
            return jsonify({"success": False, "error": "指定隊友不在你的小隊"}), 400
        if not _is_near_death_active_member(candidate):
            return jsonify({"success": False, "error": "指定隊友目前不需要救援"}), 400
        target = candidate
    else:
        for p in participants:
            if _is_near_death_active_member(p):
                target = p
                break

    if not target:
        return jsonify({"success": False, "error": "沒有需要救援的隊友"}), 400

    if target["squad_id"] == session["squad_id"]:
        return jsonify({"success": False, "error": "無法救援自己"}), 400

    rescuer_name = squad.get("display_name") or session["squad_id"]
    target_name = target.get("display_name") or target["squad_id"]

    if rescue_type == "prayer":
        try:
            deadline = datetime.fromisoformat(target["near_death_until"])
            new_deadline = deadline - timedelta(minutes=5)
            if datetime.now() >= new_deadline:
                update_squad(target["squad_id"], near_death_until=None, hp=25)
                message = f"{rescuer_name} 禱告救援成功！{target_name} 恢復至 25 生命值。"
                rescued = True
            else:
                update_squad(target["squad_id"], near_death_until=new_deadline.isoformat())
                message = f"{rescuer_name} 為 {target_name} 禱告，瀕死時間縮短 5 分鐘。"
                rescued = False
        except ValueError:
            return jsonify({"success": False, "error": "瀕死時間資料錯誤"}), 400
    elif rescue_type == "item":
        item_id = body.get("item_id")
        if not item_id:
            return jsonify({"success": False, "error": "請指定救援道具"}), 400
        success, message, rescued = apply_near_death_item_rescue(
            session["squad_id"],
            target["squad_id"],
            item_id,
        )
        if not success:
            return jsonify({"success": False, "error": message}), 400
    else:
        return jsonify({"success": False, "error": "無效的救援方式"}), 400

    if combat_id:
        combat = get_combat(int(combat_id))
        if combat:
            combat = append_combat_log(combat, message)
            save_combat(combat["id"], logs=combat.get("logs"))

    return jsonify({
        "success": True,
        "rescued": rescued,
        "message": message,
        "target": target_name,
    })


@combat_bp.route("/combat/summon_gm", methods=["POST"])
@require_player()
def combat_summon_gm_api():
    """Broadcast GM help request to global_events and combat log."""
    body = request.json if request.is_json else {}
    combat_id = body.get("combat_id")
    if not combat_id:
        return jsonify({"success": False, "error": "缺少戰鬥編號"}), 400

    squad_id = session["squad_id"]
    squad = get_squad(squad_id)
    if not squad:
        return jsonify({"success": False, "error": "找不到隊伍"}), 404

    combat = get_combat(int(combat_id))
    if not combat:
        return jsonify({"success": False, "error": "無效的戰鬥編號"}), 404

    participants = get_combat_participants(combat)
    if squad_id not in {p.get("squad_id") for p in participants}:
        return jsonify({"success": False, "error": "你不在這場戰鬥中"}), 403

    display_name = squad.get("display_name") or squad_id
    team_id = squad.get("team_id") or "獨立隊員"

    # Staff-only: effect_type=gm_alert is filtered from player /announcements
    # and /global_events (see services.global_events.is_staff_only_event).
    create_global_event(
        title=f"🚨 戰場救援訊號：{display_name}",
        description=(
            f"Team [{team_id}] 在戰鬥 #{combat_id} 請求 GM 介入瀕死/崩潰狀態，"
            "需要工作人員手動重置或復活。"
        ),
        effect_type="gm_alert",
        effect_value=int(combat_id),
        created_by=squad_id,
    )

    combat = append_combat_log(
        combat,
        f"⚠️ [求助] {display_name} 已向 GM 發出緊急界線重建請求。",
        log_type="gm_alert",
    )
    save_combat(combat["id"], logs=combat.get("logs"))

    return jsonify({
        "success": True,
        "message": "GM 通訊網已建立，工作人員正在趕往現場。",
    })

