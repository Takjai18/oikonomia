"""Combat persistence, resolution, preview, and status responses."""
import json
import math
import random
import sqlite3
import time
from datetime import datetime, timedelta

from models.settings import settings
from models.encounter import load_encounter
from models.encounter_outcomes import (
    apply_encounter_failure,
    apply_encounter_failure_solo,
    apply_encounter_success,
    apply_encounter_success_solo,
    apply_trauma_bad_ending_victory,
)
from models.item import get_item_by_id
from models.squad import (
    fetch_squads_by_ids,
    get_squad,
    get_team_members,
    row_to_squad,
    update_squad,
)
from models.protagonist import (
    apply_damage_to_protagonist,
    check_ending_condition,
    get_controllable_protagonist_squad_id,
    get_player_control_protagonist_ids,
    get_team_ending_state,
    get_team_protagonist_trauma_total,
    get_team_story_stage,
    has_trauma_bad_ending,
    is_protagonist_participant,
    parse_protagonist_squad_id,
    protagonist_player_control_enabled,
    refresh_combat_participants,
    resolve_combat_protagonist_keys,
    trauma_bad_ending_narrative,
)
from models.team import get_team_by_id, get_team_protagonists, official_squad_route
from utils.db_tx import immediate_transaction, with_db_retry
from utils.helpers import normalize_team_id


class ActiveCombatExistsError(Exception):
    """Raised when a team already has a non-ended combat."""

    def __init__(self, combat_id):
        self.combat_id = combat_id
        super().__init__(f"Team already has active combat {combat_id}")


def _db():
    return settings.db_path


COMBAT_ACTION_TYPES = settings.combat_action_types
ATTACK_ACTION_TYPES = settings.attack_action_types
DICE_MULTIPLIERS = settings.dice_multipliers
COMBAT_ATTACK_BASE_DAMAGE = settings.combat_attack_base_damage
COMBAT_STATUS_RESOLVING = "resolving"
RESOLVING_STALE_SECONDS = 45


def row_to_combat(row):
    data = dict(row)
    for field in ("phase_actions", "logs"):
        try:
            data[field] = json.loads(data.get(field) or ({} if field == "phase_actions" else []))
        except (json.JSONDecodeError, TypeError):
            data[field] = {} if field == "phase_actions" else []
    return data

def get_combat(combat_id):
    conn = sqlite3.connect(_db())
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM combats WHERE id = ?", (combat_id,)).fetchone()
    conn.close()
    if not row:
        return None
    combat = row_to_combat(row)
    phase = combat.get("current_phase", 0)
    json_actions = combat.get("phase_actions") or {}
    combat["phase_actions"] = get_combat_phase_actions(
        combat_id, phase, json_fallback=json_actions
    )
    return combat

def get_combat_by_squad(squad_id):
    squad = get_squad(squad_id)
    if not squad:
        return None
    combat_id = squad.get("current_combat_id")
    if combat_id:
        combat = get_combat(combat_id)
        if combat and combat.get("status") not in ("ended",):
            return combat
    conn = sqlite3.connect(_db())
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """SELECT * FROM combats
           WHERE squad_id = ? AND status NOT IN ('ended')
           ORDER BY started_at DESC LIMIT 1""",
        (squad_id,),
    ).fetchone()
    conn.close()
    return row_to_combat(row) if row else None

def get_active_combat_for_team(team_id):
    if not team_id:
        return None
    for member in get_team_members(team_id):
        combat = get_combat_by_squad(member["squad_id"])
        if combat:
            return combat
    return None

def save_combat(combat_id, **fields):
    allowed = {
        "status", "current_phase", "enemy_hp", "phase_actions", "logs",
        "phase_started_at", "phase_deadline", "ended_at", "winner",
    }
    updates, params = [], []
    for key, val in fields.items():
        if key not in allowed:
            continue
        if key in ("phase_actions", "logs"):
            val = json.dumps(val, ensure_ascii=False)
        updates.append(f"{key} = ?")
        params.append(val)
    if not updates:
        return
    params.append(combat_id)
    conn = sqlite3.connect(_db())
    conn.execute(f"UPDATE combats SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()

def set_team_combat_id(team_id, combat_id):
    for member in get_team_members(team_id):
        update_squad(member["squad_id"], current_combat_id=combat_id)

def clear_team_combat_id(team_id):
    for member in get_team_members(team_id):
        update_squad(member["squad_id"], current_combat_id=None)

def get_effective_stat(squad, stat):
    base = int(squad.get(stat) or 0)
    trauma_key = {
        "power": "trauma_power",
        "intellect": "trauma_intellect",
        "resilience": "trauma_resilience",
    }.get(stat)
    trauma = int(squad.get(trauma_key) or 0) if trauma_key else 0
    return max(0, base - trauma)

def get_effective_attack_stat(squad):
    return max(
        get_effective_stat(squad, "power"),
        get_effective_stat(squad, "intellect"),
    )

def describe_attack_stat(squad):
    power = get_effective_stat(squad, "power")
    intellect = get_effective_stat(squad, "intellect")
    if power > intellect:
        return {"stat": "power", "value": power, "label": "力量"}
    if intellect > power:
        return {"stat": "intellect", "value": intellect, "label": "智力"}
    return {"stat": "power", "value": power, "label": "力量/智力"}

def calculate_attack_damage(player, enemy_resilience, multiplier=1.0, item_bonus=0,
                            base_damage=settings.combat_attack_base_damage):
    if multiplier <= 0:
        return 0
    attack_stat = get_effective_attack_stat(player)
    raw = ((attack_stat * 1.5) + base_damage + item_bonus) * multiplier - (enemy_resilience * 0.8)
    return max(1, int(raw))

def calculate_damage_simple(attacker, target, base_damage=settings.combat_attack_base_damage,
                            multiplier=1.0, is_critical=False, apply_sanity_penalty=False,
                            item_bonus=0):
    """
    進階版傷害計算（可選機制模板，預設唔啟用暴擊/神智減益）。
    與 calculate_attack_damage 嘅分別：倍率/暴擊/神智係喺減防之後再疊加。
    啟用時建議：骰 3 → is_critical=True；神智 <50 → apply_sanity_penalty=True。
    target 可為敵人 dict（resilience）或整數防禦值。
    """
    if multiplier <= 0:
        return 0
    attack_power = get_effective_attack_stat(attacker)
    if isinstance(target, dict):
        defense = int(target.get("resilience") or 0)
    else:
        defense = int(target or 0)
    damage = (attack_power * 1.5) + base_damage + item_bonus - (defense * 0.8)
    damage *= multiplier
    if is_critical:
        damage *= 1.5
    if apply_sanity_penalty:
        sanity = int(attacker.get("sanity") or 100)
        if sanity < 50:
            damage *= 0.85
    return max(1, int(damage))

def calculate_damage(attacker_stat, multiplier, enemy_armor, item_bonus=0):
    """Legacy helper（暴走自傷等）；一般攻擊請用 calculate_attack_damage。"""
    base = (attacker_stat * 2.0) + item_bonus
    damage = math.floor(base * multiplier) - enemy_armor
    return max(0, damage)

DEFEND_TEAM_DAMAGE_FACTOR = 0.5


def count_team_defenders(actions):
    """Count players who chose Defend this phase (team-wide shield)."""
    if not actions:
        return 0
    return sum(
        1 for action_data in actions.values()
        if (action_data.get("action_type") or action_data.get("action")) == "defend"
    )


def team_defend_damage_multiplier(defender_count):
    if defender_count > 0:
        return DEFEND_TEAM_DAMAGE_FACTOR
    return 1.0


def calculate_incoming_damage(
    enemy_base_damage,
    player_resilience,
    defending=False,
    team_defend_multiplier=None,
):
    reduction = math.floor(player_resilience * 0.6)
    damage = max(0, enemy_base_damage - reduction)
    multiplier = team_defend_multiplier
    if multiplier is None:
        multiplier = DEFEND_TEAM_DAMAGE_FACTOR if defending else 1.0
    if multiplier < 1.0:
        damage = max(0, math.floor(damage * multiplier))
    return damage

def dice_multiplier(dice_result):
    try:
        dice = int(dice_result)
    except (TypeError, ValueError):
        dice = 2
    return settings.dice_multipliers.get(max(0, min(3, dice)), 1.0)


def roll_combat_dice():
    """Server-authoritative combat dice (0=miss, 1=normal, 2=strong, 3=crit)."""
    return random.randint(0, 3)


def get_combat_phase_actions(combat_id, phase, json_fallback=None):
    conn = sqlite3.connect(_db())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT squad_id, action_type, dice_result, item_id
               FROM combat_actions
               WHERE combat_id = ? AND phase = ?""",
            (combat_id, phase),
        ).fetchall()
        if rows:
            return {
                row["squad_id"]: {
                    "action_type": row["action_type"],
                    "dice_result": row["dice_result"],
                    "item_id": row["item_id"],
                }
                for row in rows
            }
    finally:
        conn.close()
    return dict(json_fallback or {})


def combat_action_already_submitted(combat_id, squad_id, phase):
    conn = sqlite3.connect(_db())
    try:
        row = conn.execute(
            """SELECT 1 FROM combat_actions
               WHERE combat_id = ? AND squad_id = ? AND phase = ?""",
            (combat_id, squad_id, phase),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def upsert_combat_action(combat_id, squad_id, phase, action_type, dice_result, item_id=None):
    def _write():
        conn = sqlite3.connect(_db())
        try:
            conn.execute(
                """INSERT INTO combat_actions
                   (combat_id, squad_id, phase, action_type, dice_result, item_id, submitted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(combat_id, squad_id, phase) DO UPDATE SET
                       action_type = excluded.action_type,
                       dice_result = excluded.dice_result,
                       item_id = excluded.item_id,
                       submitted_at = excluded.submitted_at""",
                (
                    combat_id,
                    squad_id,
                    phase,
                    action_type,
                    dice_result,
                    item_id,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    with_db_retry(_write)

def zoo_bonus_multiplier(sanity):
    sanity = int(sanity or 0)
    if sanity >= 100:
        return 1.8
    if sanity >= 90:
        return 1.5
    if sanity >= 80:
        return 1.4
    if sanity >= 70:
        return 1.3
    return 1.0

def berserk_probability(sanity):
    sanity = int(sanity or 0)
    if sanity < 10:
        return 0.90
    if sanity < 20:
        return 0.50
    if sanity < 40:
        return 0.20
    return 0.0

def is_berserk(sanity):
    sanity = int(sanity if isinstance(sanity, (int, float)) else (sanity or {}).get("sanity", 50))
    prob = berserk_probability(sanity)
    return prob > 0 and random.random() < prob

def combat_phase_deadline(phase_started_at, limit_seconds):
    started = datetime.fromisoformat(phase_started_at)
    return (started + timedelta(seconds=limit_seconds)).isoformat()

def combat_phase_expired(combat, settings):
    deadline = combat.get("phase_deadline")
    if not deadline:
        return False
    return datetime.now() >= datetime.fromisoformat(deadline)

def _combat_team_id(combat, participants=None):
    if participants:
        for p in participants:
            if p.get("team_id"):
                return p["team_id"]
    starter_id = (combat or {}).get("squad_id")
    if starter_id:
        starter = get_squad(starter_id)
        if starter and starter.get("team_id"):
            return starter["team_id"]
    return None


def get_combat_participants(combat):
    """Players + route/final-stage protagonists as combat participants."""
    if not combat:
        return []
    starter_id = combat.get("squad_id")
    if not starter_id:
        return []

    conn = sqlite3.connect(_db())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            WITH starter AS (
                SELECT squad_id, team_id FROM squads WHERE squad_id = ?
            )
            SELECT s.*
            FROM squads s
            CROSS JOIN starter st
            WHERE s.squad_id = st.squad_id
               OR (
                   st.team_id IS NOT NULL AND TRIM(st.team_id) != ''
                   AND UPPER(TRIM(s.team_id)) = UPPER(TRIM(st.team_id))
               )
            ORDER BY s.is_team_leader DESC, COALESCE(s.display_name, s.squad_id)
        """, (starter_id,)).fetchall()
        participants = []
        for row in rows:
            participant = row_to_squad(row)
            route = official_squad_route(participant)
            if route:
                participant["route"] = route
            participants.append(participant)
    finally:
        conn.close()

    team_id = _combat_team_id(combat, participants)
    if not team_id:
        return participants

    from models.protagonist import build_protagonist_participant

    encounter = load_encounter(combat.get("encounter_id"))
    story_stage = get_team_story_stage(team_id)
    for key in resolve_combat_protagonist_keys(team_id, encounter, story_stage):
        pro = build_protagonist_participant(team_id, key)
        if pro:
            participants.append(pro)
    return participants


def choose_protagonist_auto_action(participant, combat_settings=None):
    combat_settings = combat_settings or {}
    sanity = int(participant.get("sanity") or 50)
    dice = roll_combat_dice()
    if sanity < 30:
        return {"action_type": "defend", "dice_result": dice}
    if sanity >= 70 and combat_settings.get("allow_zoo", True):
        return {"action_type": "use_zoo", "dice_result": dice}
    if sanity < 40 and dice == 0:
        return {"action_type": "pass", "dice_result": dice}
    return {"action_type": "attack", "dice_result": dice}


def inject_protagonist_auto_actions(actions, participants, encounter, player_control_ids):
    merged = dict(actions or {})
    combat_settings = (encounter or {}).get("combat_settings") or {}
    player_control_ids = set(player_control_ids or [])
    active_ids = set(get_active_combat_member_ids(participants))
    for p in participants:
        if not p.get("is_protagonist"):
            continue
        sid = p["squad_id"]
        if sid not in active_ids or sid in merged:
            continue
        merged[sid] = choose_protagonist_auto_action(p, combat_settings)
    return merged


def apply_damage_to_combat_participant(squad_id, damage, participant=None):
    if is_protagonist_participant(squad_id):
        key, team_id = parse_protagonist_squad_id(squad_id)
        if key and team_id:
            return apply_damage_to_protagonist(team_id, key, damage, participant=participant)
        return None
    apply_damage_to_player(squad_id, damage, squad=participant)
    return None

def get_active_combat_member_ids(participants):
    """存活且可行動的隊員 squad_id（非瀕死）。"""
    active = []
    for p in participants:
        sid = p["squad_id"]
        if int(p.get("hp") or 0) <= 0:
            continue
        if p.get("near_death_until"):
            try:
                if datetime.now() < datetime.fromisoformat(p["near_death_until"]):
                    continue
            except ValueError:
                pass
        active.append(sid)
    return active


def get_active_combat_members(participants):
    ids = set(get_active_combat_member_ids(participants))
    return [p for p in participants if p["squad_id"] in ids]


def _phase_player_control_context(combat, participants):
    """Split active combatants for player-controlled protagonist submit rules."""
    active = get_active_combat_member_ids(participants)
    team_id = _combat_team_id(combat, participants)
    encounter = load_encounter(combat.get("encounter_id")) if combat else None
    story_stage = get_team_story_stage(team_id) if team_id else 0
    player_control_ids = set(
        get_player_control_protagonist_ids(team_id, encounter, story_stage, participants)
        if team_id else []
    )
    non_protagonist, player_control_protagonists = [], []
    for sid in active:
        p = next((x for x in participants if x["squad_id"] == sid), None)
        if p and p.get("is_protagonist"):
            if sid in player_control_ids:
                player_control_protagonists.append(sid)
            continue
        non_protagonist.append(sid)
    return {
        "non_protagonist": non_protagonist,
        "player_control_protagonists": player_control_protagonists,
    }


def get_phase_submit_required_ids(combat, participants):
    """Human players who must submit; protagonist may be manual or auto fallback."""
    ctx = _phase_player_control_context(combat, participants)
    return list(ctx["non_protagonist"])


def all_phase_actions_submitted(combat, participants):
    actions = combat.get("phase_actions") or {}
    ctx = _phase_player_control_context(combat, participants)
    non_pro = ctx["non_protagonist"]
    pro_control = ctx["player_control_protagonists"]
    if not non_pro and not pro_control:
        return True
    pro_submitted = any(sid in actions for sid in pro_control)
    non_pro_submitted = sum(1 for sid in non_pro if sid in actions)
    if pro_control:
        needed_players = max(0, len(non_pro) - (1 if pro_submitted else 0))
        return non_pro_submitted >= needed_players
    return non_pro_submitted >= len(non_pro)

def append_combat_log(combat, message, log_type="event"):
    logs = list(combat.get("logs") or [])
    now = datetime.now().isoformat()
    logs.append({
        "type": log_type,
        "message": message,
        "timestamp": now,
        "at": now,
    })
    combat["logs"] = logs[-50:]
    return combat

def apply_damage_to_player(squad_id, damage, squad=None):
    if squad is None:
        squad = get_squad(squad_id)
    if not squad:
        return
    current_hp = int(squad.get("hp") or 0)
    new_hp = max(0, current_hp - damage)
    updates = {"hp": new_hp}
    if new_hp <= 0 and current_hp > 0:
        updates["near_death_until"] = (
            datetime.now() + timedelta(minutes=settings.near_death_minutes)
        ).isoformat()
    elif new_hp <= 0 and not squad.get("near_death_until"):
        updates["near_death_until"] = (
            datetime.now() + timedelta(minutes=settings.near_death_minutes)
        ).isoformat()
    update_squad(squad_id, **updates)


def _recover_stale_resolving_combat(combat_id):
    with immediate_transaction() as conn:
        row = conn.execute(
            "SELECT status, phase_started_at FROM combats WHERE id = ?",
            (combat_id,),
        ).fetchone()
        if not row or row[0] != COMBAT_STATUS_RESOLVING:
            return
        started = row[1]
        stale = True
        if started:
            try:
                stale = (
                    datetime.now() - datetime.fromisoformat(started)
                ).total_seconds() > RESOLVING_STALE_SECONDS
            except ValueError:
                stale = True
        if stale:
            conn.execute(
                "UPDATE combats SET status = 'player_phase' WHERE id = ? AND status = ?",
                (combat_id, COMBAT_STATUS_RESOLVING),
            )


def _claim_player_phase_resolution(combat_id):
    with immediate_transaction() as conn:
        row = conn.execute(
            "SELECT status FROM combats WHERE id = ?",
            (combat_id,),
        ).fetchone()
        if not row or row[0] != "player_phase":
            return False
        cur = conn.execute(
            "UPDATE combats SET status = ? WHERE id = ? AND status = 'player_phase'",
            (COMBAT_STATUS_RESOLVING, combat_id),
        )
        return cur.rowcount > 0


def _release_player_phase_resolution(combat_id):
    with immediate_transaction() as conn:
        conn.execute(
            "UPDATE combats SET status = 'player_phase' WHERE id = ? AND status = ?",
            (combat_id, COMBAT_STATUS_RESOLVING),
        )


def _wait_for_resolution_complete(combat_id, max_wait=6.0):
    """Wait for another worker to finish resolve; avoids stale enemy HP snapshots."""
    deadline = time.time() + max_wait
    last = None
    while time.time() < deadline:
        combat = get_combat(combat_id)
        if not combat:
            return None, None
        last = combat
        status = combat.get("status")
        if status == "ended":
            return combat, combat.get("winner")
        if status not in (COMBAT_STATUS_RESOLVING, "enemy_phase"):
            return combat, None
        time.sleep(0.05)
    return last, None


def get_lowest_resilience_player(participants):
    best = None
    best_res = 999
    for p in participants:
        if p.get("near_death_until"):
            try:
                if datetime.now() < datetime.fromisoformat(p["near_death_until"]):
                    continue
            except ValueError:
                pass
        eff = get_effective_stat(p, "resilience")
        if eff < best_res:
            best_res = eff
            best = p
    return best or (participants[0] if participants else None)

def resolve_player_phase(combat_id):
    """
    完整解析 Player Phase：
    - 攻擊傷害（max(力量, 智力)）+ dice multiplier
    - Zoo 加成（70/80/90/100 → 1.3x–1.8x）
    - 暴走（指定機率 + 30% 自傷）
    - 敵人反擊（韌性最低者；任一同隊 Defend → 全隊減傷 50%）
    - 瀕死檢查、日誌、Phase 狀態更新
    回傳 (combat, winner)；winner 為 'squad' | 'enemy' | None
    """
    _recover_stale_resolving_combat(combat_id)
    if not _claim_player_phase_resolution(combat_id):
        combat = get_combat(combat_id)
        if not combat:
            return None, None
        if combat.get("status") in (COMBAT_STATUS_RESOLVING, "enemy_phase"):
            return _wait_for_resolution_complete(combat_id)
        if combat.get("status") == "ended":
            return combat, combat.get("winner")
        return combat, None

    try:
        return _resolve_player_phase_body(combat_id)
    except Exception:
        _release_player_phase_resolution(combat_id)
        raise


def _resolve_player_phase_body(combat_id):
    combat = get_combat(combat_id)
    if not combat or combat.get("status") != COMBAT_STATUS_RESOLVING:
        _release_player_phase_resolution(combat_id)
        return combat, None

    encounter = load_encounter(combat["encounter_id"])
    combat_settings = (encounter or {}).get("combat_settings", {})
    participants = get_combat_participants(combat)
    participant_by_id = {p["squad_id"]: p for p in participants}
    team_id = _combat_team_id(combat, participants)
    story_stage = get_team_story_stage(team_id) if team_id else 0
    player_control_ids = (
        get_player_control_protagonist_ids(team_id, encounter, story_stage, participants)
        if team_id else []
    )
    actions = inject_protagonist_auto_actions(
        combat.get("phase_actions") or {},
        participants,
        encounter,
        player_control_ids,
    )

    enemy_hp = int(combat.get("enemy_hp") or 0)
    enemy_resilience = int(combat.get("enemy_resilience") or 0)
    enemy_sanity = int(combat.get("enemy_sanity") or 0)
    enemy_base_damage = int(combat.get("enemy_base_damage") or 0)
    enemy_name = combat.get("enemy_name") or "敵人"

    total_damage_to_enemy = 0
    berserk_players = []

    for player_squad_id, action_data in actions.items():
        player = participant_by_id.get(player_squad_id)
        if not player:
            continue
        display = player.get("display_name") or player_squad_id
        sanity = int(player.get("sanity") or 0)

        if int(player.get("hp") or 0) <= 0:
            combat = append_combat_log(
                combat,
                f"{display} 已無法行動",
                log_type="incapacitated",
            )
            continue

        if is_berserk(sanity):
            berserk_players.append(player_squad_id)
            if random.random() < 0.30:
                self_dmg = max(1, int(get_effective_attack_stat(player) * 0.3))
                apply_damage_to_combat_participant(player_squad_id, self_dmg, participant=player)
                combat = append_combat_log(
                    combat,
                    f"{display} 暴走！攻擊自己，造成 {self_dmg} 點傷害",
                    log_type="berserk",
                )
            else:
                combat = append_combat_log(
                    combat,
                    f"{display} 神智不清，行動失控",
                    log_type="berserk",
                )
            continue

        action_type = action_data.get("action_type") or action_data.get("action") or "pass"
        dice = action_data.get("dice_result", action_data.get("dice", 1))
        multiplier = dice_multiplier(dice)
        item_bonus = int(action_data.get("item_bonus") or 0)

        if not item_bonus and action_type == "use_item" and action_data.get("item_id"):
            item = get_item_by_id(int(action_data["item_id"]))
            if item and item.get("effect_type") == "power_up":
                item_bonus = abs(int(item.get("effect_value") or 0))

        if action_type == "use_zoo":
            zoo_mult = zoo_bonus_multiplier(sanity)
            multiplier *= zoo_mult
            if zoo_mult > 1.0:
                combat = append_combat_log(
                    combat,
                    f"{display} 發動 Zoo 能力（×{zoo_mult}）",
                    log_type="zoo",
                )

        if action_type in ATTACK_ACTION_TYPES:
            stat_info = describe_attack_stat(player)
            dmg = calculate_attack_damage(
                player, enemy_resilience, multiplier=multiplier, item_bonus=item_bonus,
            )
            total_damage_to_enemy += dmg
            action_label = "Zoo 能力" if action_type == "use_zoo" else "攻擊"
            pro_tag = "（主角·自動）" if (
                player.get("is_protagonist")
                and player_squad_id not in (combat.get("phase_actions") or {})
            ) else ""
            combat = append_combat_log(
                combat,
                f"{display} {action_label}對{enemy_name}造成 {dmg} 點傷害"
                f"（{stat_info['label']} {stat_info['value']} · 骰 {dice}）{pro_tag}",
                log_type="damage",
            )
        elif action_type == "defend":
            pro_tag = "（主角·自動）" if (
                player.get("is_protagonist")
                and player_squad_id not in (combat.get("phase_actions") or {})
            ) else ""
            combat = append_combat_log(
                combat,
                f"{display} 為全隊堅守界線{pro_tag}",
                log_type="defend",
            )
        elif action_type == "pass":
            pro_tag = "（主角·自動）" if (
                player.get("is_protagonist")
                and player_squad_id not in (combat.get("phase_actions") or {})
            ) else ""
            combat = append_combat_log(
                combat,
                f"{display} 選擇觀望{pro_tag}",
                log_type="pass",
            )

    new_enemy_hp = max(0, enemy_hp - total_damage_to_enemy)
    if total_damage_to_enemy:
        combat = append_combat_log(
            combat,
            f"{enemy_name} 受到共 {total_damage_to_enemy} 點傷害，剩餘 HP {new_enemy_hp}",
            log_type="summary",
        )

    combat["enemy_hp"] = new_enemy_hp
    combat["phase_actions"] = {}

    if new_enemy_hp <= 0:
        save_combat(combat_id, enemy_hp=new_enemy_hp, logs=combat.get("logs"), phase_actions={})
        return _end_combat(combat_id, "squad", encounter), "squad"

    save_combat(
        combat_id,
        enemy_hp=new_enemy_hp,
        logs=combat.get("logs"),
        status="enemy_phase",
        phase_actions={},
    )
    combat["status"] = "enemy_phase"

    fresh_participants = refresh_combat_participants(participants)
    target = get_lowest_resilience_player(fresh_participants)
    if target:
        target_id = target["squad_id"]
        defender_count = count_team_defenders(actions)
        team_defend_mult = team_defend_damage_multiplier(defender_count)
        incoming = calculate_incoming_damage(
            enemy_base_damage,
            get_effective_stat(target, "resilience"),
            team_defend_multiplier=team_defend_mult,
        )
        if incoming > 0:
            apply_damage_to_combat_participant(target_id, incoming, participant=target)
            refreshed_list = refresh_combat_participants([target])
            refreshed = refreshed_list[0] if refreshed_list else target
            defend_note = ""
            if defender_count > 0:
                defend_note = (
                    f"（{defender_count} 人為全隊堅守界線，減半）"
                    if defender_count > 1
                    else "（全隊防禦，減半）"
                )
            pro_note = "（主角）" if target.get("is_protagonist") else ""
            combat = append_combat_log(
                combat,
                f"{enemy_name} 反擊 {target.get('display_name', target_id)}，造成 {incoming} 點傷害"
                + defend_note
                + pro_note,
                log_type="enemy_attack",
            )
            if refreshed and refreshed.get("near_death_until"):
                trauma_note = ""
                if target.get("is_protagonist") and int(refreshed.get("trauma_count") or 0) > 0:
                    trauma_note = f"（心理創傷 +1，累計 {refreshed.get('trauma_count')}）"
                combat = append_combat_log(
                    combat,
                    f"{target.get('display_name', target_id)} 陷入瀕死！"
                    f"{settings.near_death_minutes} 分鐘內需救援{trauma_note}",
                    log_type="near_death",
                )

    if _team_combat_defeated(combat):
        save_combat(combat_id, logs=combat.get("logs"))
        return _end_combat(combat_id, "enemy", encounter), "enemy"

    now = datetime.now().isoformat()
    limit = combat_settings.get("phase_time_limit_seconds", 180)
    save_combat(
        combat_id,
        status="player_phase",
        current_phase=int(combat.get("current_phase") or 0) + 1,
        logs=combat.get("logs"),
        phase_started_at=now,
        phase_deadline=combat_phase_deadline(now, limit),
        phase_actions={},
    )
    return get_combat(combat_id), None

def _team_combat_defeated(combat):
    participants = get_combat_participants(combat)
    alive = 0
    for p in participants:
        if int(p.get("hp") or 0) > 0:
            alive += 1
            continue
        if p.get("near_death_until"):
            try:
                if datetime.now() < datetime.fromisoformat(p["near_death_until"]):
                    alive += 1
            except ValueError:
                pass
    return alive == 0

def _end_combat(combat_id, winner, encounter):
    combat = get_combat(combat_id)
    squad = get_squad(combat["squad_id"])
    team_id = squad.get("team_id") if squad else None
    end_fields = {
        "status": "ended",
        "winner": winner,
        "ended_at": datetime.now().isoformat(),
        "logs": combat.get("logs"),
    }
    if winner == "squad":
        end_fields["enemy_hp"] = 0
    save_combat(combat_id, **end_fields)
    starter_id = combat.get("squad_id")
    if team_id:
        clear_team_combat_id(team_id)
    elif starter_id:
        update_squad(starter_id, current_combat_id=None)
    trauma_total = get_team_protagonist_trauma_total(team_id) if team_id else 0
    if winner == "squad" and encounter:
        if team_id and has_trauma_bad_ending(team_id):
            apply_trauma_bad_ending_victory(team_id, encounter)
            combat = append_combat_log(
                get_combat(combat_id),
                f"主角心理創傷過深（累計 {trauma_total}）——勝利無法帶來真正救贖",
                log_type="trauma_ending",
            )
            save_combat(combat_id, logs=combat.get("logs"))
        elif team_id:
            apply_encounter_success(team_id, encounter, starter_id)
        elif starter_id:
            apply_encounter_success_solo(starter_id, encounter)
    elif winner == "enemy" and encounter:
        if team_id:
            apply_encounter_failure(team_id, encounter)
        elif starter_id:
            apply_encounter_failure_solo(starter_id, encounter)
    return get_combat(combat_id)

def build_enemy_combat_stats(combat, encounter=None):
    """敵人 5 維數值（同玩家：生命值／神智／力量／智力／韌性）。"""
    enemy_def = (encounter or {}).get("enemy", {}) if encounter else {}
    hp = int(combat.get("enemy_hp") if combat.get("enemy_hp") is not None else enemy_def.get("hp") or 0)
    max_hp = int(combat.get("enemy_max_hp") if combat.get("enemy_max_hp") is not None else enemy_def.get("hp") or hp)
    sanity = int(
        combat.get("enemy_sanity") if combat.get("enemy_sanity") is not None
        else enemy_def.get("sanity") or 0
    )
    resilience = int(
        combat.get("enemy_resilience") if combat.get("enemy_resilience") is not None
        else enemy_def.get("resilience") or 0
    )
    base_damage = int(
        combat.get("enemy_base_damage") if combat.get("enemy_base_damage") is not None
        else enemy_def.get("base_damage") or 0
    )
    power = int(
        combat.get("enemy_power") if combat.get("enemy_power") is not None
        else enemy_def.get("power") or base_damage or max(resilience, 10)
    )
    intellect = int(
        combat.get("enemy_intellect") if combat.get("enemy_intellect") is not None
        else enemy_def.get("intellect") or sanity or max(int(resilience * 0.8), 10)
    )
    return {
        "name": combat.get("enemy_name") or enemy_def.get("name", "敵人"),
        "hp": hp,
        "max_hp": max_hp,
        "sanity": sanity,
        "power": power,
        "intellect": intellect,
        "resilience": resilience,
        "base_damage": base_damage,
    }


def build_combat_status_response(combat, encounter, squad_id, participants=None):
    combat_settings = (encounter or {}).get("combat_settings", {})
    if participants is None and combat:
        participants = get_combat_participants(combat)
    participants = participants or []
    participant_by_id = {p["squad_id"]: p for p in participants}

    me = participant_by_id.get(squad_id)
    if not me:
        me = fetch_squads_by_ids([squad_id]).get(squad_id) or {}

    team_id = me.get("team_id")
    if not team_id and combat:
        starter = participant_by_id.get(combat.get("squad_id"))
        if not starter and combat.get("squad_id"):
            starter = fetch_squads_by_ids([combat["squad_id"]]).get(combat["squad_id"])
        team_id = starter.get("team_id") if starter else None

    protagonists = get_team_protagonists(team_id) if team_id else {}
    team_route = protagonists.get("active_route") or me.get("route")
    if not team_route and team_id:
        team_row = get_team_by_id(team_id)
        team_route = (team_row or {}).get("route")
    phase_actions = (combat or {}).get("phase_actions") or {}
    berserk_hint = berserk_probability(me.get("sanity", 50)) > 0

    member_states = {}
    for p in participants:
        sid = p["squad_id"]
        submitted = phase_actions.get(sid)
        member_states[sid] = {
            "display_name": p.get("display_name") or sid,
            "avatar": p.get("avatar"),
            "hp": p.get("hp"),
            "max_hp": p.get("max_hp"),
            "sanity": p.get("sanity"),
            "power": p.get("power"),
            "intellect": p.get("intellect"),
            "resilience": get_effective_stat(p, "resilience"),
            "near_death_until": p.get("near_death_until"),
            "is_protagonist": bool(p.get("is_protagonist")),
            "protagonist_key": p.get("protagonist_key"),
            "trauma_count": p.get("trauma_count"),
            "submitted": bool(submitted),
            "action_type": (submitted or {}).get("action_type"),
            "dice_result": (submitted or {}).get("dice_result"),
        }

    logs = combat.get("logs") or []
    recent_logs = logs[-20:]
    log_messages = [
        entry.get("message") if isinstance(entry, dict) else str(entry)
        for entry in recent_logs
    ]
    log_entries = [
        {
            "type": entry.get("type", "event"),
            "message": entry.get("message", str(entry)),
        }
        if isinstance(entry, dict) else {"type": "event", "message": str(entry)}
        for entry in recent_logs
    ]

    return {
        "success": True,
        "combat_id": combat["id"],
        "encounter_id": combat["encounter_id"],
        "title": (encounter or {}).get("title"),
        "status": combat.get("status"),
        "current_phase": combat.get("current_phase", 0),
        "phase_started_at": combat.get("phase_started_at"),
        "phase_deadline": combat.get("phase_deadline"),
        "phase_expired": combat_phase_expired(combat, combat_settings),
        "remaining_seconds": max(
            0,
            int((datetime.fromisoformat(combat["phase_deadline"]) - datetime.now()).total_seconds())
        ) if combat.get("phase_deadline") else None,
        "enemy": build_enemy_combat_stats(combat, encounter),
        "member_states": member_states,
        "protagonists": protagonists,
        "my_state": {
            **member_states.get(squad_id, {}),
            "avatar": me.get("avatar"),
            "display_name": me.get("display_name") or squad_id,
            "power": me.get("power"),
            "intellect": me.get("intellect"),
            "hp": me.get("hp"),
            "max_hp": me.get("max_hp"),
            "sanity": me.get("sanity"),
            "resilience": get_effective_stat(me, "resilience"),
            "near_death_until": me.get("near_death_until"),
        },
        "berserk_warning": berserk_hint,
        "berserk_chance": round(berserk_probability(me.get("sanity", 50)) * 100),
        "log": log_messages,
        "log_entries": log_entries,
        "reflection_prompt": (encounter or {}).get("reflection_prompt"),
        "combat_settings": combat_settings,
        "available_actions": list(settings.combat_action_types),
        "winner": combat.get("winner"),
        "enemy_description": (encounter or {}).get("enemy", {}).get("description"),
        "route": team_route or (encounter or {}).get("route"),
        "max_phases": combat_settings.get("max_phases", 5),
        "my_squad_id": squad_id,
        "story_stage": get_team_story_stage(team_id) if team_id else 0,
        "protagonist_player_control": protagonist_player_control_enabled(
            encounter, get_team_story_stage(team_id) if team_id else 0
        ),
        "controllable_protagonist_id": (
            get_controllable_protagonist_squad_id(
                team_id,
                team_route,
                encounter,
                get_team_story_stage(team_id) if team_id else 0,
            )
            if team_id else None
        ),
        "protagonist_trauma_total": (
            get_team_protagonist_trauma_total(team_id) if team_id else 0
        ),
        "ending": get_team_ending_state(team_id) if team_id else None,
    }

def _preview_action_enemy_damage(player, action_type, dice_result, item_id, enemy_resilience, enemy_sanity):
    """預估單一行動對敵人傷害（不含暴走隨機結果）"""
    meta = {}
    sanity = int(player.get("sanity") or 0)
    berserk_chance = berserk_probability(sanity)
    if berserk_chance > 0:
        meta["berserk_risk"] = True
        meta["berserk_chance"] = round(berserk_chance * 100)

    try:
        dice = max(0, min(3, int(dice_result)))
    except (TypeError, ValueError):
        dice = 1
    multiplier = dice_multiplier(dice)
    item_bonus = 0
    if item_id:
        item = get_item_by_id(int(item_id))
        if item and item.get("effect_type") == "power_up":
            item_bonus = abs(int(item.get("effect_value") or 0))

    if action_type in ATTACK_ACTION_TYPES:
        if action_type == "use_zoo":
            multiplier *= zoo_bonus_multiplier(sanity)
        stat_info = describe_attack_stat(player)
        meta["attack_stat"] = stat_info["stat"]
        meta["attack_stat_value"] = stat_info["value"]
        meta["attack_stat_label"] = stat_info["label"]
        dmg = calculate_attack_damage(
            player, enemy_resilience, multiplier=multiplier, item_bonus=item_bonus,
        )
    else:
        dmg = 0

    if meta.get("berserk_risk"):
        meta["damage_if_normal"] = dmg
        meta["damage_note"] = "暴走時可能無法對敵輸出"
    return dmg, meta

def build_combat_round_preview(
    combat_id, squad_id, action_type, dice_result, item_id=None, as_protagonist=False,
):
    combat = get_combat(combat_id)
    if not combat or combat.get("status") != "player_phase":
        return None

    encounter = load_encounter(combat["encounter_id"])
    enemy_res = int(combat.get("enemy_resilience") or 0)
    enemy_san = int(combat.get("enemy_sanity") or 0)
    enemy_base = int(combat.get("enemy_base_damage") or 0)
    participants = get_combat_participants(combat)
    participant_by_id = {p["squad_id"]: p for p in participants}
    player = fetch_squads_by_ids([squad_id]).get(squad_id) or participant_by_id.get(squad_id)
    team_id = (player or {}).get("team_id")
    if as_protagonist and team_id:
        team_row = get_team_by_id(team_id) or {}
        story_stage = get_team_story_stage(team_id)
        acting_id = get_controllable_protagonist_squad_id(
            team_id, team_row.get("route"), encounter, story_stage,
        )
        if acting_id:
            squad_id = acting_id
    squad = participant_by_id.get(squad_id) or fetch_squads_by_ids([squad_id]).get(squad_id)
    if not squad:
        return None

    phase_actions = dict(combat.get("phase_actions") or {})

    my_dmg, my_meta = _preview_action_enemy_damage(
        squad, action_type, dice_result, item_id, enemy_res, enemy_san,
    )
    ally_damage = 0
    ally_count = 0
    for pid, ad in phase_actions.items():
        if pid == squad_id:
            continue
        player = participant_by_id.get(pid)
        if not player:
            continue
        d, _ = _preview_action_enemy_damage(
            player,
            ad.get("action_type"),
            ad.get("dice_result", 1),
            ad.get("item_id"),
            enemy_res,
            enemy_san,
        )
        ally_damage += d
        ally_count += 1

    hypo_actions = dict(phase_actions)
    hypo_actions[squad_id] = {
        "action_type": action_type,
        "dice_result": dice_result,
        "item_id": item_id,
    }

    active_participants = []
    for p in participants:
        sid = p["squad_id"]
        if p.get("near_death_until"):
            try:
                if datetime.now() < datetime.fromisoformat(p["near_death_until"]):
                    continue
            except ValueError:
                pass
        active_participants.append(p)

    all_submitted = all(hypo_actions.get(p["squad_id"]) for p in active_participants)
    pending_count = sum(1 for p in active_participants if not hypo_actions.get(p["squad_id"]))

    target = get_lowest_resilience_player(active_participants) or (participants[0] if participants else None)
    counter_damage = 0
    counter_target_name = None
    team_defend_count = count_team_defenders(hypo_actions)
    team_defend_mult = team_defend_damage_multiplier(team_defend_count)
    counter_defending = team_defend_count > 0
    if target:
        target_id = target["squad_id"]
        counter_damage = calculate_incoming_damage(
            enemy_base,
            get_effective_stat(target, "resilience"),
            team_defend_multiplier=team_defend_mult,
        )
        counter_target_name = target.get("display_name") or target_id

    risks = []
    if my_meta.get("berserk_risk"):
        risks.append({
            "level": "berserk",
            "message": f"你有 {my_meta['berserk_chance']}% 暴走機率，可能無法對敵造成傷害",
        })

    for p in active_participants:
        sid = p["squad_id"]
        name = p.get("display_name") or sid
        hp = int(p.get("hp") or 0)
        sanity = int(p.get("sanity") or 0)
        if target and sid == target["squad_id"] and counter_damage > 0:
            after_hp = hp - counter_damage
            if after_hp <= 0:
                risks.append({
                    "level": "critical",
                    "message": f"{name} 可能被反擊致命或陷入瀕死！",
                })
            elif after_hp < 20:
                risks.append({
                    "level": "hp",
                    "message": f"{name} 生命值將降至 {after_hp}（低於 20，瀕死風險）",
                })
        if sanity < 10:
            risks.append({
                "level": "sanity",
                "message": f"{name} 神智 {sanity}，暴走機率約 90%",
            })
        elif sanity < 20:
            risks.append({
                "level": "sanity",
                "message": f"{name} 神智 {sanity}，暴走機率約 50%",
            })
        elif sanity < 40:
            risks.append({
                "level": "sanity",
                "message": f"{name} 神智 {sanity}，仍有暴走風險（約 20%）",
            })

    action_labels = {
        "attack": "攻擊",
        "attack_physical": "攻擊",
        "attack_nonphysical": "攻擊",
        "defend": "堅守界線",
        "use_zoo": "Zoo 能力",
        "use_item": "使用物品",
        "pass": "觀望",
    }

    return {
        "action_type": action_type,
        "action_label": action_labels.get(action_type, action_type),
        "dice_result": dice_result,
        "my_damage_to_enemy": my_dmg,
        "ally_damage_to_enemy": ally_damage,
        "total_damage_to_enemy": my_dmg + ally_damage,
        "enemy_counter_damage": counter_damage,
        "counter_target_name": counter_target_name,
        "counter_defending": counter_defending,
        "team_defend_count": team_defend_count,
        "counter_pending": not all_submitted and len(active_participants) > 1,
        "pending_teammates": max(0, pending_count - 0) if not all_submitted else 0,
        "phase_resolves_now": all_submitted or len(active_participants) <= 1,
        "berserk_risk": my_meta.get("berserk_risk", False),
        "damage_if_normal": my_meta.get("damage_if_normal", my_dmg),
        "attack_stat_label": my_meta.get("attack_stat_label"),
        "attack_stat_value": my_meta.get("attack_stat_value"),
        "risks": risks,
    }


def build_single_player_preview(combat_id, squad_id, squad=None):
    """多人模式：只顯示該玩家自己相關的行動預覽。"""
    combat = get_combat(combat_id)
    if not squad:
        squad = fetch_squads_by_ids([squad_id]).get(squad_id)
    if not combat or not squad:
        return None

    action_data = (combat.get("phase_actions") or {}).get(squad_id)
    if not action_data:
        return None

    action_type = action_data.get("action_type") or action_data.get("action") or "pass"
    dice_result = action_data.get("dice_result", action_data.get("dice", 1))
    item_id = action_data.get("item_id")

    base = build_combat_round_preview(
        combat_id, squad_id, action_type, dice_result, item_id,
    )
    if not base:
        return None

    display_name = squad.get("display_name") or squad_id
    counter_target = base.get("counter_target_name") or ""
    me_is_target = counter_target == display_name or counter_target == squad_id
    counter_pending = bool(base.get("counter_pending"))
    damage_taken = 0
    if me_is_target and not counter_pending:
        damage_taken = int(base.get("enemy_counter_damage") or 0)

    team_id = squad.get("team_id")
    protagonists = get_team_protagonists(team_id) if team_id else {}
    active_route = protagonists.get("active_route") or squad.get("route")
    protagonist_name = None
    if active_route == "iggy":
        protagonist_name = (protagonists.get("iggy") or {}).get("name") or "Iggy"
    elif active_route == "marah":
        protagonist_name = (protagonists.get("marah") or {}).get("name") or "Marah"

    damage_dealt = int(base.get("my_damage_to_enemy") or 0)
    summary_parts = []
    if damage_dealt > 0:
        summary_parts.append(f"你對敵人造成 {damage_dealt} 點傷害")
    elif base.get("action_label") == "堅守界線":
        summary_parts.append("你為全隊堅守界線")
    elif base.get("action_label") == "觀望":
        summary_parts.append("你選擇觀望")
    else:
        summary_parts.append(f"你完成「{base.get('action_label', '行動')}」")

    if protagonist_name and damage_dealt > 0:
        summary_parts.append(f"（{protagonist_name} 路線加成已計入）")

    if counter_pending and me_is_target:
        est = int(base.get("enemy_counter_damage") or 0)
        summary_parts.append(f"敵人可能對你反擊約 {est} 點（待全隊提交後結算）")
    elif damage_taken > 0:
        summary_parts.append(f"你受到 {damage_taken} 點反擊傷害")

    return {
        "player_name": display_name,
        "action_type": base.get("action_type"),
        "action_label": base.get("action_label"),
        "dice_result": base.get("dice_result"),
        "damage_dealt": damage_dealt,
        "damage_taken": damage_taken,
        "damage_taken_pending": counter_pending and me_is_target,
        "estimated_counter_damage": int(base.get("enemy_counter_damage") or 0) if me_is_target else 0,
        "counter_pending": counter_pending,
        "protagonist_name": protagonist_name,
        "berserk_risk": base.get("berserk_risk", False),
        "damage_if_normal": base.get("damage_if_normal", damage_dealt),
        "attack_stat_label": base.get("attack_stat_label"),
        "attack_stat_value": base.get("attack_stat_value"),
        "summary": "，".join(summary_parts) + "。",
        "risks": base.get("risks") or [],
    }


def _combat_outcome_json(winner, encounter, team_id=None):
    if winner == "squad":
        ending = get_team_ending_state(team_id) if team_id else {}
        trauma_bad = bool(ending.get("trauma_bad_ending"))
        payload = {
            "success": True,
            "status": "ended",
            "outcome": "victory",
            "winner": "squad",
            "narrative": (encounter or {}).get("success", {}).get("narrative"),
            "reflection_prompt": (encounter or {}).get("reflection_prompt"),
            "ending_condition": ending.get("ending_condition") or check_ending_condition(team_id),
            "protagonist_trauma_total": ending.get("protagonist_trauma_total", 0),
        }
        if team_id:
            payload["ending"] = ending
        if trauma_bad:
            payload["trauma_bad_ending"] = True
            payload["narrative"] = trauma_bad_ending_narrative(encounter)
            payload["reflection_prompt"] = None
        return payload
    if winner == "enemy":
        return {
            "success": True,
            "status": "ended",
            "outcome": "defeat",
            "winner": "enemy",
            "narrative": (encounter or {}).get("failure", {}).get("narrative"),
        }
    return None


def _build_full_preview_from_status(status_payload):
    return {
        "log_entries": status_payload.get("log_entries") or [],
        "log": status_payload.get("log") or [],
        "current_phase": status_payload.get("current_phase"),
        "enemy": status_payload.get("enemy"),
        "member_states": status_payload.get("member_states"),
    }


def _build_round_resolved_response(combat, encounter, squad_id):
    payload = build_combat_status_response(combat, encounter, squad_id)
    payload["status"] = "round_resolved"
    payload["round_resolved"] = True
    payload["active"] = combat.get("status") not in ("ended", "precheck")
    payload["full_preview"] = _build_full_preview_from_status(payload)
    return payload


def create_combat_record(squad_id, encounter_id, encounter, initial_status="precheck"):
    squad = get_squad(squad_id)
    team_id = (squad or {}).get("team_id")
    clean_team_id = normalize_team_id(team_id) if team_id else None

    enemy = encounter.get("enemy", {})
    enemy_stats = build_enemy_combat_stats(
        {
            "enemy_name": enemy.get("name", "敵人"),
            "enemy_hp": enemy.get("hp", 100),
            "enemy_max_hp": enemy.get("hp", 100),
            "enemy_resilience": enemy.get("resilience", 0),
            "enemy_sanity": enemy.get("sanity", 0),
            "enemy_base_damage": enemy.get("base_damage", 10),
            "enemy_power": enemy.get("power"),
            "enemy_intellect": enemy.get("intellect"),
        },
        encounter,
    )
    combat_settings = encounter.get("combat_settings", {})
    now = datetime.now().isoformat()
    logs = [{"at": now, "message": f"遭遇戰開始：{encounter.get('title', encounter_id)}"}]
    phase_started = now if initial_status == "player_phase" else None
    phase_deadline = (
        combat_phase_deadline(now, combat_settings.get("phase_time_limit_seconds", 180))
        if initial_status == "player_phase" else None
    )

    with immediate_transaction() as conn:
        c = conn.cursor()
        if clean_team_id:
            row = c.execute(
                """
                SELECT c.id FROM combats c
                INNER JOIN squads s ON c.squad_id = s.squad_id
                WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?))
                  AND c.status NOT IN ('ended')
                ORDER BY c.started_at DESC
                LIMIT 1
                """,
                (clean_team_id,),
            ).fetchone()
            if row:
                raise ActiveCombatExistsError(row[0])

        c.execute(
            """INSERT INTO combats
               (squad_id, encounter_id, status, current_phase, enemy_name, enemy_hp, enemy_max_hp,
                enemy_resilience, enemy_sanity, enemy_base_damage, enemy_power, enemy_intellect,
                phase_actions, logs, phase_started_at, phase_deadline, started_at)
               VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?, ?, ?)""",
            (
                squad_id,
                encounter_id,
                initial_status,
                enemy_stats["name"],
                enemy_stats["hp"],
                enemy_stats["max_hp"],
                enemy_stats["resilience"],
                enemy_stats["sanity"],
                enemy_stats["base_damage"],
                enemy_stats["power"],
                enemy_stats["intellect"],
                json.dumps(logs, ensure_ascii=False),
                phase_started,
                phase_deadline,
                now,
            ),
        )
        combat_id = c.lastrowid
        if clean_team_id:
            c.execute(
                "UPDATE squads SET current_combat_id = ? WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))",
                (combat_id, clean_team_id),
            )

    return get_combat(combat_id)


# Public aliases for routes / templates
COMBAT_ACTION_TYPES = settings.combat_action_types
ATTACK_ACTION_TYPES = settings.attack_action_types
DICE_MULTIPLIERS = settings.dice_multipliers
COMBAT_ATTACK_BASE_DAMAGE = settings.combat_attack_base_damage
NEAR_DEATH_MINUTES = settings.near_death_minutes
