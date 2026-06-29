"""Combat API routes (migrated from app.py)."""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, session

from models.combat import (
    COMBAT_ACTION_TYPES,
    all_phase_actions_submitted,
    append_combat_log,
    build_combat_round_preview,
    build_combat_status_response,
    build_enemy_combat_stats,
    build_single_player_preview,
    clear_team_combat_id,
    combat_action_already_submitted,
    combat_phase_deadline,
    combat_phase_expired,
    create_combat_record,
    get_active_combat_for_team,
    get_active_combat_member_ids,
    get_combat,
    get_combat_by_squad,
    get_combat_participants,
    get_combat_phase_actions,
    get_phase_submit_required_ids,
    resolve_player_phase,
    roll_combat_dice,
    save_combat,
    upsert_combat_action,
    _build_full_preview_from_status,
    _build_round_resolved_response,
    _combat_outcome_json,
)
from models.encounter import (
    encounter_route_matches,
    evaluate_precheck_condition,
    load_encounter,
)
from models.encounter_outcomes import (
    apply_precheck_skip,
    encounter_already_completed,
)
from models.protagonist import get_controllable_protagonist_squad_id, get_team_story_stage
from models.squad import get_squad, get_team_members, update_squad

combat_bp = Blueprint("combat", __name__)


@combat_bp.route("/combat/start", methods=["POST"])
def combat_start_api(encounter_id=None):
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    body = request.json if request.is_json else {}
    squad_id = (body.get("squad_id") or session["squad_id"]).strip()
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

    team_id = squad["team_id"]
    if encounter_already_completed(team_id, encounter_id):
        return jsonify({"success": False, "error": "此 Encounter 已完成"}), 400

    existing = get_active_combat_for_team(team_id)
    if existing:
        if existing.get("status") == "precheck" and confirm in ("skip", "fight"):
            pass
        else:
            return jsonify({"success": False, "error": "已有進行中的戰鬥", "combat_id": existing["id"]}), 400

    route = squad.get("route")
    if not encounter_route_matches(encounter.get("route"), route):
        return jsonify({"success": False, "error": "此 Encounter 不屬於你嘅路線"}), 400

    precheck = encounter.get("precheck", {})
    precheck_passed = bool(
        precheck.get("condition") and evaluate_precheck_condition(precheck["condition"], team_id)
    )

    if existing and existing.get("status") == "precheck":
        combat = existing
    else:
        status = "precheck" if precheck_passed else "player_phase"
        combat = create_combat_record(squad_id, encounter_id, encounter, initial_status=status)

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

    return jsonify({
        "success": True,
        "combat_id": combat["id"],
        "status": combat.get("status"),
        "precheck_passed": precheck_passed,
        "can_skip": precheck_passed,
        "precheck_text": precheck.get("success_text") if precheck_passed else None,
        "enemy": build_enemy_combat_stats(combat, encounter),
        "encounter": {
            "encounter_id": encounter_id,
            "title": encounter.get("title"),
            "description": encounter.get("description"),
        },
    })

@combat_bp.route("/combat/status")
def combat_status_api():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

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
        squad = get_squad(session["squad_id"])
        team_id = squad.get("team_id") if squad else None
        if winner == "squad":
            outcome = _combat_outcome_json(winner, encounter, team_id=team_id)
            return jsonify({**outcome, "active": False})
        if winner == "enemy":
            return jsonify({
                "success": True,
                "active": False,
                "winner": winner,
                "outcome": "defeat",
                "narrative": (encounter or {}).get("failure", {}).get("narrative"),
            })
        return jsonify({"success": True, "active": False, "winner": winner})

    encounter = load_encounter(combat["encounter_id"])
    settings = (encounter or {}).get("combat_settings", {})

    round_just_resolved = False
    participants = None
    if combat.get("status") == "player_phase":
        participants = get_combat_participants(combat)
        should_resolve = (
            all_phase_actions_submitted(combat, participants)
            or combat_phase_expired(combat, settings)
        )
        if should_resolve:
            prev_phase = int(combat.get("current_phase") or 0)
            prev_log_len = len(combat.get("logs") or [])
            combat, winner = resolve_player_phase(combat["id"])
            actor = get_squad(session["squad_id"])
            outcome = _combat_outcome_json(
                winner, encounter, team_id=actor.get("team_id") if actor else None,
            )
            if outcome:
                return jsonify({**outcome, "active": False})
            combat = get_combat(combat["id"]) or combat
            participants = None
            round_just_resolved = (
                int(combat.get("current_phase") or 0) > prev_phase
                or len(combat.get("logs") or []) > prev_log_len
            )

    payload = build_combat_status_response(
        combat, encounter, session["squad_id"], participants=participants,
    )
    payload["active"] = combat.get("status") not in ("ended", "precheck")
    payload["in_precheck"] = combat.get("status") == "precheck"

    if round_just_resolved:
        payload["status"] = "round_resolved"
        payload["round_resolved"] = True
        payload["full_preview"] = _build_full_preview_from_status(payload)
    elif combat.get("status") == "player_phase":
        if participants is None:
            participants = get_combat_participants(combat)
        active_ids = get_active_combat_member_ids(participants)
        phase_actions = combat.get("phase_actions") or {}
        if session["squad_id"] in phase_actions and len(phase_actions) < len(active_ids):
            payload["waiting_for_teammates"] = True
            payload["submitted_count"] = len(phase_actions)
            payload["total_active"] = len(active_ids)

    return jsonify(payload)

@combat_bp.route("/combat/preview_action", methods=["POST"])
def combat_preview_action_api():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

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

    preview = build_combat_round_preview(
        combat_id, session["squad_id"], action_type, dice_result, item_id,
    )
    if not preview:
        return jsonify({"success": False, "error": "無法預覽此回合"}), 400

    preview["is_estimate"] = True
    preview["preview_note"] = "此為估算（普通骰）；實際結果於提交後由系統擲骰決定"
    return jsonify({"success": True, "preview": preview})

@combat_bp.route("/combat/submit_action", methods=["POST"])
@combat_bp.route("/combat/action", methods=["POST"])
def combat_submit_action_api():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

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
    if not combat or combat.get("status") != "player_phase":
        return jsonify({"success": False, "error": "沒有進行中的 Player Phase"}), 400

    encounter = load_encounter(combat["encounter_id"])
    settings = (encounter or {}).get("combat_settings", {})
    story_stage = get_team_story_stage(squad["team_id"]) if squad.get("team_id") else 0
    as_protagonist = bool(body.get("as_protagonist"))
    if as_protagonist:
        acting_id = get_controllable_protagonist_squad_id(
            squad["team_id"], squad.get("route"), encounter, story_stage,
        )
        if not acting_id:
            return jsonify({"success": False, "error": "此階段不可代替主角行動"}), 400
    else:
        acting_id = session["squad_id"]

    participants = get_combat_participants(combat)
    actor_state = next(
        (p for p in participants if p["squad_id"] == acting_id),
        squad if acting_id == session["squad_id"] else None,
    )
    if not actor_state:
        return jsonify({"success": False, "error": "找不到行動者"}), 400

    if actor_state.get("near_death_until"):
        try:
            if datetime.now() < datetime.fromisoformat(actor_state["near_death_until"]):
                label = "主角" if as_protagonist else "你"
                return jsonify({"success": False, "error": f"{label}已陷入瀕死，等待救援"}), 400
        except ValueError:
            pass

    if action_type == "use_zoo" and not settings.get("allow_zoo", True):
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
    combat["phase_actions"] = phase_actions
    save_combat(combat_id, phase_actions=phase_actions)

    participants = get_combat_participants(combat)
    required_ids = get_phase_submit_required_ids(combat, participants)
    winner = None
    if all_phase_actions_submitted(combat, participants) or combat_phase_expired(combat, settings):
        combat, winner = resolve_player_phase(combat_id)

    outcome = _combat_outcome_json(winner, encounter, team_id=squad.get("team_id"))
    if outcome:
        return jsonify(outcome)

    combat = get_combat(combat_id)
    if len(required_ids) > 1 and len(phase_actions) < len(required_ids):
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
def combat_resolve_phase_api():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

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
def combat_rescue_near_death_api():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    body = request.json if request.is_json else request.form
    combat_id = body.get("combat_id")
    rescue_type = (body.get("rescue_type") or "prayer").strip()

    squad = get_squad(session["squad_id"])
    if not squad or not squad.get("team_id"):
        return jsonify({"success": False, "error": "請先加入 Team"}), 400

    participants = get_team_members(squad["team_id"])
    target = None
    for p in participants:
        if p.get("near_death_until"):
            try:
                if datetime.now() < datetime.fromisoformat(p["near_death_until"]):
                    target = p
                    break
            except ValueError:
                continue

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
    else:
        update_squad(target["squad_id"], near_death_until=None, hp=25)
        message = f"{rescuer_name} 使用道具救援 {target_name}，恢復至 25 生命值。"
        rescued = True

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

