"""Combat persistence, resolution, preview, and status responses."""
import json
import math
import random
import re
import sqlite3
import time
from datetime import datetime, timedelta

from models.settings import settings
from models.encounter import load_encounter
from services.combat_engine import (
    COMBAT_ATTACK_BASE_DAMAGE,
    DEFEND_TEAM_DAMAGE_FACTOR,
    Combatant,
    calculate_incoming_damage as _engine_calculate_incoming_damage,
    count_team_defenders,
    dice_multiplier as _engine_dice_multiplier,
    select_enemy_counter_target,
    team_defend_damage_multiplier,
)
from services.combat_flow import normalize_failed_escape_actions
from services.combat_outcomes import (
    build_defeat_outcome_payload,
    build_victory_outcome_payload,
    resolve_combat_outcome,
)
from services.ending import judge_ending
from models.squad import (
    fetch_squads_by_ids,
    get_squad,
    get_team_members,
    row_to_squad,
    update_squad,
)
from models.protagonist import (
    apply_damage_to_protagonist,
    get_controllable_protagonist_squad_id,
    get_player_control_protagonist_ids,
    get_team_protagonist_trauma_total,
    get_team_story_stage,
    is_protagonist_participant,
    parse_protagonist_squad_id,
    protagonist_player_control_enabled,
    refresh_combat_participants,
    resolve_combat_protagonist_keys,
)
from models.team import get_team_by_id, get_team_protagonists, official_squad_route
from utils.db_tx import get_db_connection, immediate_transaction, with_db_retry
from utils.helpers import normalize_team_id


class ActiveCombatExistsError(Exception):
    """Raised when a team already has a non-ended combat."""

    def __init__(self, combat_id):
        self.combat_id = combat_id
        super().__init__(f"Team already has active combat {combat_id}")


def _db():
    return settings.db_path


def _combat_db_conn(*, row_factory=sqlite3.Row):
    return get_db_connection(_db(), row_factory=row_factory)


def _combat_is_finished_for_reconcile(combat):
    """Avoid sealing combats while resolve/poll is in flight (session restore)."""
    if not combat:
        return False
    status = combat.get("status")
    if status == "ended":
        return True
    if status in (COMBAT_STATUS_RESOLVING, "enemy_phase"):
        return False
    return int(combat.get("enemy_hp") or 0) <= 0


def _resolution_max_wait():
    try:
        return float(settings.combat_resolution_max_wait_seconds or 6.0)
    except (TypeError, ValueError):
        return 6.0


COMBAT_ACTION_TYPES = settings.combat_action_types
ATTACK_ACTION_TYPES = settings.attack_action_types
DICE_MULTIPLIERS = settings.dice_multipliers
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
    conn = _combat_db_conn()
    try:
        row = conn.execute("SELECT * FROM combats WHERE id = ?", (combat_id,)).fetchone()
    finally:
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
    conn = _combat_db_conn()
    try:
        row = conn.execute(
            """SELECT * FROM combats
               WHERE squad_id = ? AND status NOT IN ('ended')
               ORDER BY started_at DESC LIMIT 1""",
            (squad_id,),
        ).fetchone()
    finally:
        conn.close()
    return row_to_combat(row) if row else None

def get_active_combat_for_team(team_id):
    if not team_id:
        return None

    conn = _combat_db_conn()
    try:
        row = conn.execute(
            """SELECT c.* FROM combats c
               JOIN squads s ON c.squad_id = s.squad_id
               WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?))
                 AND c.status NOT IN ('ended')
               ORDER BY c.started_at DESC LIMIT 1""",
            (team_id,),
        ).fetchone()
        return row_to_combat(row) if row else None
    finally:
        conn.close()

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
    conn = _combat_db_conn(row_factory=None)
    try:
        conn.execute(f"UPDATE combats SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    finally:
        conn.close()

def set_team_combat_id(team_id, combat_id):
    for member in get_team_members(team_id):
        update_squad(member["squad_id"], current_combat_id=combat_id)

def clear_team_combat_id(team_id):
    for member in get_team_members(team_id):
        update_squad(member["squad_id"], current_combat_id=None)


def purge_combat_actions(combat_id, *, conn=None):
    """Remove orphaned phase submissions when a combat room closes."""
    if not combat_id:
        return 0
    if conn is not None:
        cur = conn.execute(
            "DELETE FROM combat_actions WHERE combat_id = ?", (int(combat_id),),
        )
        return cur.rowcount
    with immediate_transaction(settings.db_path) as tx:
        cur = tx.execute(
            "DELETE FROM combat_actions WHERE combat_id = ?", (int(combat_id),),
        )
        return cur.rowcount


def reconcile_finished_active_combat(combat, team_id=None, squad_id=None):
    """
    SSOT heal on session restore: seal finished combats, purge orphan actions,
    and release squad current_combat_id inside one BEGIN IMMEDIATE transaction.
    """
    if not combat:
        return False, None, None

    combat_id = combat.get("id")
    enemy_hp = int(combat.get("enemy_hp") or 0)
    is_finished = _combat_is_finished_for_reconcile(combat)

    if not is_finished:
        return True, combat_id, combat.get("encounter_id")

    if not combat_id:
        return False, None, None

    now_str = datetime.now().isoformat()
    with immediate_transaction(settings.db_path) as conn:
        if combat.get("status") != "ended":
            conn.execute(
                """UPDATE combats SET status = 'ended', ended_at = ?, enemy_hp = ?
                   WHERE id = ?""",
                (
                    now_str,
                    0 if enemy_hp <= 0 else enemy_hp,
                    int(combat_id),
                ),
            )
        purge_combat_actions(combat_id, conn=conn)
        if team_id:
            conn.execute(
                "UPDATE squads SET current_combat_id = NULL WHERE team_id = ?",
                (team_id,),
            )
        elif squad_id:
            conn.execute(
                "UPDATE squads SET current_combat_id = NULL WHERE squad_id = ?",
                (squad_id,),
            )

    return False, None, None

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


def _combatant_from_squad(squad, item_bonus=0):
    return Combatant(
        id=str(squad.get("squad_id") or squad.get("id") or ""),
        power=get_effective_stat(squad, "power"),
        intellect=get_effective_stat(squad, "intellect"),
        resilience=get_effective_stat(squad, "resilience"),
        sanity=int(squad.get("sanity") or 100),
        item_bonus=int(item_bonus or 0),
    )


def calculate_attack_damage(player, enemy_resilience, multiplier=1.0, item_bonus=0,
                            base_damage=settings.combat_attack_base_damage):
    from services.combat_engine import calculate_attack_damage as _engine_calculate_attack_damage

    attacker = _combatant_from_squad(player, item_bonus=item_bonus)
    return _engine_calculate_attack_damage(
        attacker,
        enemy_resilience,
        multiplier=multiplier,
        item_bonus=item_bonus,
        base_damage=base_damage,
    )

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

def calculate_incoming_damage(
    enemy_base_damage,
    player_resilience,
    defending=False,
    team_defend_multiplier=None,
):
    return _engine_calculate_incoming_damage(
        enemy_base_damage,
        player_resilience,
        defending=defending,
        team_defend_multiplier=team_defend_multiplier,
    )


def dice_multiplier(dice_result):
    table = settings.dice_multipliers or None
    return _engine_dice_multiplier(dice_result, dice_multipliers=table)


def roll_combat_dice():
    """Server-authoritative combat dice (0=miss, 1=normal, 2=strong, 3=crit)."""
    return random.randint(0, 3)


def get_combat_phase_actions(combat_id, phase, json_fallback=None):
    conn = _combat_db_conn()
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
    conn = _combat_db_conn(row_factory=None)
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
        conn = _combat_db_conn(row_factory=None)
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

    conn = _combat_db_conn()
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
    if combat_settings.get("allow_zoo", True) and random.random() < 0.35:
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


def get_phase_active_member_ids(combat, participants):
    """
    INV-E: members active for current phase resolution.
    Escape submitters remain eligible until the round fully resolves.
    """
    active_ids = set(get_active_combat_member_ids(participants))
    if not combat or not combat.get("id"):
        return list(active_ids)

    phase = int(combat.get("current_phase") or 0)
    actions = get_combat_phase_actions(combat["id"], phase)
    if not actions:
        actions = (combat.get("phase_actions") or {})

    for sid, action in actions.items():
        action_type = (action.get("action_type") or action.get("action") or "")
        if action_type != "escape":
            continue
        participant = next((p for p in participants if p.get("squad_id") == sid), None)
        if participant and int(participant.get("hp") or 0) > 0:
            active_ids.add(sid)
    return list(active_ids)


def get_active_combat_members(participants):
    ids = set(get_active_combat_member_ids(participants))
    return [p for p in participants if p["squad_id"] in ids]


def _phase_player_control_context(combat, participants):
    """Split active combatants for player-controlled protagonist submit rules."""
    active = get_phase_active_member_ids(combat, participants)
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
            hp_row = conn.execute(
                "SELECT enemy_hp FROM combats WHERE id = ?",
                (combat_id,),
            ).fetchone()
            enemy_hp = int(hp_row[0] or 0) if hp_row else 0
            if enemy_hp <= 0:
                return
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


def _phase_actions_from_conn(conn, combat_id, phase, json_fallback=None):
    """Read phase actions using the caller's transaction connection (no nested locks)."""
    rows = conn.execute(
        """SELECT squad_id, action_type, dice_result, item_id
           FROM combat_actions WHERE combat_id = ? AND phase = ?""",
        (combat_id, phase),
    ).fetchall()
    if rows:
        return {
            row[0]: {
                "action_type": row[1],
                "dice_result": row[2],
                "item_id": row[3],
            }
            for row in rows
        }
    return dict(json_fallback or {})


def _claim_ready_player_phase_resolution(
    combat_id, combat_settings=None, cached_participants=None,
):
    """
    CAS claim player_phase -> resolving only when resolve preconditions hold.
    Participant assembly runs outside TX; phase_actions are re-read inside TX.
    """
    combat = get_combat(combat_id)
    if not combat or combat.get("status") != "player_phase":
        return False, None
    if cached_participants is not None:
        participants = cached_participants
    else:
        participants = get_combat_participants(combat) or []
    settings = combat_settings or {}

    with immediate_transaction() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM combats WHERE id = ?",
            (combat_id,),
        ).fetchone()
        if not row or row["status"] != "player_phase":
            return False, None
        cur = conn.execute(
            "UPDATE combats SET status = ? WHERE id = ? AND status = 'player_phase'",
            (COMBAT_STATUS_RESOLVING, combat_id),
        )
        if cur.rowcount == 0:
            return False, None

        fresh = row_to_combat(row)
        phase = int(fresh.get("current_phase") or 0)
        json_actions = fresh.get("phase_actions") or {}
        fresh["phase_actions"] = _phase_actions_from_conn(
            conn, combat_id, phase, json_fallback=json_actions
        )
        if not (
            all_phase_actions_submitted(fresh, participants)
            or combat_phase_expired(fresh, settings)
        ):
            conn.execute(
                "UPDATE combats SET status = 'player_phase' WHERE id = ? AND status = ?",
                (combat_id, COMBAT_STATUS_RESOLVING),
            )
            return False, fresh
        return True, fresh


def _release_player_phase_resolution(combat_id):
    combat = get_combat(combat_id)
    if combat and int(combat.get("enemy_hp") or 0) <= 0:
        return
    with immediate_transaction() as conn:
        conn.execute(
            "UPDATE combats SET status = 'player_phase' WHERE id = ? AND status = ?",
            (combat_id, COMBAT_STATUS_RESOLVING),
        )


def _wait_for_resolution_complete(combat_id, max_wait=None):
    if max_wait is None:
        max_wait = _resolution_max_wait()
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


def _escape_success_rate(combat_settings):
    try:
        rate = float((combat_settings or {}).get("escape_success_rate", 0.4))
    except (TypeError, ValueError):
        rate = 0.4
    return max(0.0, min(1.0, rate))


def _escape_meta_from_logs(logs, summary_idx=None):
    """Detect escape attempt outcome from combat logs for settlement enrichment."""
    entries = logs or []
    if summary_idx is None:
        summary_idx = _latest_team_summary_index(entries)
    start = 0
    if summary_idx is not None:
        prev = _latest_team_summary_index(entries[:summary_idx])
        start = (prev + 1) if prev is not None else 0
    scan = entries[start:summary_idx + 1] if summary_idx is not None else entries
    escape_triggered = False
    escape_success = False
    for entry in scan:
        if not isinstance(entry, dict):
            continue
        etype = entry.get("type")
        if etype in ("escape", "escape_failed"):
            escape_triggered = True
            escape_success = False
        elif etype == "escape_success":
            escape_triggered = True
            escape_success = True
    return escape_triggered, escape_success

def resolve_player_phase(combat_id):
    """
    完整解析 Player Phase：
    - 攻擊傷害（max(力量, 智力)）+ dice multiplier
    - Zoo 加成（≥70/≥80/≥90/≥100 → 1.3x/1.4x/1.5x/1.8x；<70 為 1.0x，仍可發動）
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


def advance_combat_from_poll(combat_id, combat_settings=None):
    """
    Poll-side resolve gate — delegates to maybe_resolve_player_phase (CAS + TX).
    Returns (combat, winner, round_just_resolved, participants_cache).
    """
    combat = get_combat(combat_id)
    if not combat:
        return None, None, False, None

    if combat.get("status") == COMBAT_STATUS_RESOLVING:
        initial_phase = int(combat.get("current_phase") or 0)
        combat, winner = _wait_after_peer_resolve(combat_id, initial_phase)
        resolved = bool(
            winner
            or (combat and combat.get("status") == "ended")
            or (combat and int(combat.get("current_phase") or 0) > initial_phase)
        )
        return combat, winner, resolved, None

    if combat.get("status") != "player_phase":
        return combat, None, False, None

    settings = combat_settings or {}
    participants = get_combat_participants(combat) or []
    phase = int(combat.get("current_phase") or 0)
    fresh = dict(combat)
    fresh["phase_actions"] = get_combat_phase_actions(combat_id, phase)
    if not (
        all_phase_actions_submitted(fresh, participants)
        or combat_phase_expired(fresh, settings)
    ):
        return combat, None, False, participants

    prev_phase = phase
    prev_log_len = len(combat.get("logs") or [])
    combat, winner = maybe_resolve_player_phase(
        combat_id, settings, cached_participants=participants,
    )
    combat = get_combat(combat_id) or combat
    round_just_resolved = (
        int(combat.get("current_phase") or 0) > prev_phase
        or len(combat.get("logs") or []) > prev_log_len
    )
    return combat, winner, round_just_resolved, participants


def _wait_after_peer_resolve(combat_id, initial_phase, max_wait=None):
    if max_wait is None:
        max_wait = _resolution_max_wait()
    """
    Wait for in-flight resolve; if round already advanced, skip duplicate settlement.
    """
    waited, winner = _wait_for_resolution_complete(combat_id, max_wait=max_wait)
    if not waited:
        return None, None
    if int(waited.get("current_phase") or 0) > initial_phase:
        return waited, winner
    if waited.get("status") == "ended":
        return waited, winner
    fresh = get_combat(combat_id) or waited
    if fresh and int(fresh.get("current_phase") or 0) > initial_phase:
        return fresh, fresh.get("winner") if fresh.get("status") == "ended" else None
    return waited, winner


def maybe_resolve_player_phase(combat_id, combat_settings=None, cached_participants=None):
    """
    Authoritative resolve gate for routes: re-read DB snapshot, resolve at most once.
    Readiness is validated inside _claim_ready_player_phase_resolution (CAS + TX).
    Returns (combat, winner).
    """
    _recover_stale_resolving_combat(combat_id)
    combat = get_combat(combat_id)
    if not combat:
        return None, None

    initial_phase = int(combat.get("current_phase") or 0)
    status = combat.get("status")
    if status == "ended":
        return combat, combat.get("winner")
    if status == COMBAT_STATUS_RESOLVING:
        return _wait_after_peer_resolve(combat_id, initial_phase)
    if status != "player_phase":
        return combat, None

    encounter = load_encounter(combat.get("encounter_id") or "")
    settings = combat_settings or (encounter or {}).get("combat_settings", {})

    if cached_participants is None:
        cached_participants = get_combat_participants(combat) or []
    claimed, snapshot = _claim_ready_player_phase_resolution(
        combat_id, settings, cached_participants=cached_participants,
    )
    if not claimed:
        combat = get_combat(combat_id) or snapshot
        if combat and int(combat.get("current_phase") or 0) > initial_phase:
            return combat, combat.get("winner") if combat.get("status") == "ended" else None
        if combat and combat.get("status") == COMBAT_STATUS_RESOLVING:
            return _wait_after_peer_resolve(combat_id, initial_phase)
        return combat, None

    snap_phase = int((snapshot or {}).get("current_phase") or initial_phase)
    if snap_phase != initial_phase:
        _release_player_phase_resolution(combat_id)
        return get_combat(combat_id), None

    try:
        combat, winner = _resolve_player_phase_body(combat_id)
    except Exception:
        _release_player_phase_resolution(combat_id)
        raise
    if combat and combat.get("status") == COMBAT_STATUS_RESOLVING and winner is None:
        return _wait_after_peer_resolve(combat_id, initial_phase)
    return combat, winner


def _buffered_participant_hp(participant, squad_updates, protagonist_updates):
    sid = participant.get("squad_id")
    if is_protagonist_participant(sid):
        key, team_id = parse_protagonist_squad_id(sid)
        if team_id and key:
            buf = protagonist_updates.get((team_id, key), {})
            if "hp" in buf:
                return int(buf["hp"])
    else:
        buf = squad_updates.get(sid, {})
        if "hp" in buf:
            return int(buf["hp"])
    return int(participant.get("hp") or 0)


def _buffer_set_hp(squad_id, new_hp, squad_updates, protagonist_updates):
    if is_protagonist_participant(squad_id):
        key, team_id = parse_protagonist_squad_id(squad_id)
        if team_id and key:
            protagonist_updates.setdefault((team_id, key), {})["hp"] = int(new_hp)
    else:
        squad_updates.setdefault(squad_id, {})["hp"] = int(new_hp)


def _buffer_set_sanity(squad_id, new_san, squad_updates, protagonist_updates):
    if is_protagonist_participant(squad_id):
        key, team_id = parse_protagonist_squad_id(squad_id)
        if team_id and key:
            protagonist_updates.setdefault((team_id, key), {})["sanity"] = int(new_san)
    else:
        squad_updates.setdefault(squad_id, {})["sanity"] = int(new_san)


def _buffer_apply_damage(squad_id, damage, participant, squad_updates, protagonist_updates, trauma_events):
    participant = participant or {}
    if is_protagonist_participant(squad_id):
        key, team_id = parse_protagonist_squad_id(squad_id)
        if not key or not team_id:
            return int(participant.get("hp") or 0)
        buf = protagonist_updates.setdefault((team_id, key), {})
        curr = buf.get("hp", int(participant.get("hp") or 0))
        new_hp = max(0, curr - int(damage))
        buf["hp"] = new_hp
        if new_hp <= 0:
            buf["near_death_until"] = (
                datetime.now() + timedelta(minutes=settings.near_death_minutes)
            ).isoformat()
            prev_trauma = buf.get("trauma_count", int(participant.get("trauma_count") or 0))
            buf["trauma_count"] = prev_trauma + 1
            trauma_events.append((team_id, key, 1, "near_death_damage"))
        return new_hp

    buf = squad_updates.setdefault(squad_id, {})
    curr = buf.get("hp", int(participant.get("hp") or 0))
    new_hp = max(0, curr - int(damage))
    buf["hp"] = new_hp
    if new_hp <= 0 and not participant.get("near_death_until"):
        buf["near_death_until"] = (
            datetime.now() + timedelta(minutes=settings.near_death_minutes)
        ).isoformat()
    return new_hp


def _participants_with_buffers(participants, squad_updates, protagonist_updates):
    merged = []
    for p in participants:
        row = dict(p)
        sid = row.get("squad_id")
        if is_protagonist_participant(sid):
            key, team_id = parse_protagonist_squad_id(sid)
            buf = protagonist_updates.get((team_id, key), {}) if team_id and key else {}
        else:
            buf = squad_updates.get(sid, {})
        for field, val in buf.items():
            row[field] = val
        merged.append(row)
    return merged


def _team_defeated_from_participants(participants):
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


def _apply_resolve_phase_writes(
    conn,
    *,
    items_to_delete,
    squad_updates,
    protagonist_updates,
    trauma_events,
):
    for squad_id, item_id in items_to_delete:
        deleted = conn.execute(
            "DELETE FROM player_items WHERE squad_id = ? AND item_id = ?",
            (squad_id, item_id),
        )
        if deleted.rowcount != 1:
            raise RuntimeError(f"item consume failed: {squad_id}/{item_id}")

    for squad_id, fields in squad_updates.items():
        if "hp" in fields:
            conn.execute(
                "UPDATE squads SET hp = ? WHERE squad_id = ?",
                (fields["hp"], squad_id),
            )
        if "sanity" in fields:
            conn.execute(
                "UPDATE squads SET sanity = ? WHERE squad_id = ?",
                (fields["sanity"], squad_id),
            )
        if "near_death_until" in fields:
            nd = fields["near_death_until"]
            if nd is None:
                conn.execute(
                    "UPDATE squads SET near_death_until = NULL WHERE squad_id = ?",
                    (squad_id,),
                )
            else:
                conn.execute(
                    "UPDATE squads SET near_death_until = ? WHERE squad_id = ?",
                    (nd, squad_id),
                )

    for (team_id, protagonist_key), fields in protagonist_updates.items():
        updates = []
        params = []
        for col in ("hp", "max_hp", "sanity", "trauma_count"):
            if col in fields:
                updates.append(f"{col} = ?")
                params.append(fields[col])
        if "near_death_until" in fields:
            nd = fields["near_death_until"]
            if nd is None:
                updates.append("near_death_until = NULL")
            else:
                updates.append("near_death_until = ?")
                params.append(nd)
        if updates:
            updates.append("last_updated = ?")
            params.append(datetime.now().isoformat())
            params.extend([team_id, protagonist_key])
            conn.execute(
                f"UPDATE protagonist_states SET {', '.join(updates)} "
                "WHERE team_id = ? AND protagonist = ?",
                params,
            )

    now = datetime.now().isoformat()
    for team_id, protagonist_key, delta, reason in trauma_events:
        conn.execute(
            """INSERT INTO protagonist_trauma_log
               (team_id, protagonist, delta, reason, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (team_id, protagonist_key, int(delta), reason, now),
        )


def _commit_resolve_phase_state(
    combat_id,
    *,
    items_to_delete,
    squad_updates,
    protagonist_updates,
    trauma_events,
    combat_fields,
):
    logs_json = json.dumps(combat_fields.get("logs") or [], ensure_ascii=False)
    with immediate_transaction(settings.db_path) as conn:
        _apply_resolve_phase_writes(
            conn,
            items_to_delete=items_to_delete,
            squad_updates=squad_updates,
            protagonist_updates=protagonist_updates,
            trauma_events=trauma_events,
        )
        allowed = {
            "status", "current_phase", "enemy_hp", "phase_actions", "logs",
            "phase_started_at", "phase_deadline",
        }
        updates = []
        params = []
        for key, val in combat_fields.items():
            if key not in allowed:
                continue
            if key == "logs":
                val = logs_json
            elif key == "phase_actions":
                val = json.dumps(val or {}, ensure_ascii=False)
            updates.append(f"{key} = ?")
            params.append(val)
        if updates:
            params.append(combat_id)
            conn.execute(
                f"UPDATE combats SET {', '.join(updates)} WHERE id = ?",
                params,
            )


def _resolve_player_phase_body(combat_id):
    combat = get_combat(combat_id)
    if not combat or combat.get("status") != COMBAT_STATUS_RESOLVING:
        _release_player_phase_resolution(combat_id)
        return combat, None

    from models.item import build_combat_item_consume_batch

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
    item_consume_batch = build_combat_item_consume_batch(actions)
    items_to_delete = []
    squad_updates = {}
    protagonist_updates = {}
    trauma_events = []

    enemy_hp = int(combat.get("enemy_hp") or 0)
    enemy_resilience = int(combat.get("enemy_resilience") or 0)
    enemy_sanity = int(combat.get("enemy_sanity") or 0)
    enemy_base_damage = int(combat.get("enemy_base_damage") or 0)
    enemy_name = combat.get("enemy_name") or "敵人"

    escape_triggered = any(
        (a.get("action_type") or a.get("action")) == "escape"
        for a in actions.values()
    )
    counter_target_actions = actions
    if escape_triggered:
        escape_rate = _escape_success_rate(combat_settings)
        if random.random() < escape_rate:
            combat = append_combat_log(
                combat,
                f"全隊逃跑成功！（成功率 {int(escape_rate * 100)}%）",
                log_type="escape_success",
            )
            save_combat(combat_id, logs=combat.get("logs"))
            return _end_combat(combat_id, "escaped", encounter), "escaped"
        combat = append_combat_log(
            combat,
            "全隊逃跑失敗，將繼續結算戰鬥行動",
            log_type="escape_failed",
        )
        actions = normalize_failed_escape_actions(
            actions,
            escape_triggered=True,
            escape_success=False,
        )
        counter_target_actions = actions

    total_damage_to_enemy = 0

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

        action_type = action_data.get("action_type") or action_data.get("action") or "pass"
        if action_type == "failed_escape":
            combat = append_combat_log(
                combat,
                f"{display} 由於逃跑失敗，本回合陷入破防僵直，無法輸出任何傷害。",
                log_type="failed_escape_stuck",
            )
            continue

        if is_berserk(sanity):
            if random.random() < 0.30:
                self_dmg = max(1, int(get_effective_attack_stat(player) * 0.3))
                _buffer_apply_damage(
                    player_squad_id, self_dmg, player,
                    squad_updates, protagonist_updates, trauma_events,
                )
                player["hp"] = _buffered_participant_hp(player, squad_updates, protagonist_updates)
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

        dice = action_data.get("dice_result", action_data.get("dice", 1))
        multiplier = dice_multiplier(dice)
        item_bonus = int(action_data.get("item_bonus") or 0)
        used_item_name = None
        item_effect_type = None
        item_effect_value = 0

        if action_type == "use_item" and action_data.get("item_id"):
            ok, item, err = item_consume_batch.consume_dry_run(
                player_squad_id, action_data["item_id"],
            )
            if not ok:
                combat = append_combat_log(
                    combat,
                    f"{display} 使用物品失敗：{err}",
                    log_type="item_fail",
                )
                continue
            used_item_name = item.get("name") or "物品"
            item_effect_type = item.get("effect_type")
            try:
                item_effect_value = int(item.get("effect_value") or 0)
            except (TypeError, ValueError):
                item_effect_value = 0
            items_to_delete.append((player_squad_id, action_data["item_id"]))

            if item_effect_type == "hp_up" and item_effect_value > 0:
                curr_hp = _buffered_participant_hp(player, squad_updates, protagonist_updates)
                max_hp = int(player.get("max_hp") or 100)
                new_hp = min(max_hp, curr_hp + item_effect_value)
                _buffer_set_hp(player_squad_id, new_hp, squad_updates, protagonist_updates)
                player["hp"] = new_hp
                combat = append_combat_log(
                    combat,
                    f"{display} 消耗了 [{used_item_name}]！❤️ 生命值回復 {item_effect_value} 點 (目前: {new_hp}/{max_hp})",
                    log_type="item_use",
                )
            elif item_effect_type == "sanity_up":
                curr_san = int(player.get("sanity") or 0)
                new_san = max(0, min(100, curr_san + item_effect_value))
                _buffer_set_sanity(player_squad_id, new_san, squad_updates, protagonist_updates)
                player["sanity"] = new_san
                san_label = "回復" if item_effect_value >= 0 else "扣除"
                combat = append_combat_log(
                    combat,
                    f"{display} 消耗了 [{used_item_name}]！🧠 神智值{san_label} {abs(item_effect_value)} 點 (目前: {new_san}/100)",
                    log_type="item_use",
                )
            elif item_effect_type == "power_up":
                item_bonus = abs(item_effect_value)
                combat = append_combat_log(
                    combat,
                    f"{display} 消耗了 [{used_item_name}]！💪 獲得臨時算力加成 +{item_bonus}",
                    log_type="item_use",
                )
            else:
                combat = append_combat_log(
                    combat,
                    f"{display} 消耗了 [{used_item_name}]！效果已生效",
                    log_type="item_use",
                )

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
        elif action_type == "escape":
            pro_tag = "（主角·自動）" if (
                player.get("is_protagonist")
                and player_squad_id not in (combat.get("phase_actions") or {})
            ) else ""
            combat = append_combat_log(
                combat,
                f"{display} 選擇逃跑{pro_tag}",
                log_type="escape",
            )
            continue
        elif action_type == "use_item":
            if item_effect_type in ("hp_up", "sanity_up"):
                continue
            stat_info = describe_attack_stat(player)
            dmg = calculate_attack_damage(
                player, enemy_resilience, multiplier=multiplier, item_bonus=item_bonus,
            )
            total_damage_to_enemy += dmg
            item_label = used_item_name or "物品"
            combat = append_combat_log(
                combat,
                f"{display} 使用「{item_label}」對{enemy_name}造成 {dmg} 點傷害"
                f"（{stat_info['label']} {stat_info['value']} · 骰 {dice}）",
                log_type="damage",
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
    write_buffers = dict(
        items_to_delete=items_to_delete,
        squad_updates=squad_updates,
        protagonist_updates=protagonist_updates,
        trauma_events=trauma_events,
    )

    if new_enemy_hp <= 0:
        _commit_resolve_phase_state(
            combat_id,
            **write_buffers,
            combat_fields={
                "enemy_hp": new_enemy_hp,
                "logs": combat.get("logs"),
                "phase_actions": {},
            },
        )
        return _end_combat(combat_id, "squad", encounter), "squad"

    fresh_participants = _participants_with_buffers(participants, squad_updates, protagonist_updates)
    target = (
        select_enemy_counter_target(
            fresh_participants, counter_target_actions, enemy_base_damage,
        )
        if escape_triggered
        else get_lowest_resilience_player(fresh_participants)
    )
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
            _buffer_apply_damage(
                target_id, incoming, target,
                squad_updates, protagonist_updates, trauma_events,
            )
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
            merged_target = _participants_with_buffers([target], squad_updates, protagonist_updates)[0]
            if merged_target.get("near_death_until"):
                trauma_note = ""
                if target.get("is_protagonist") and int(merged_target.get("trauma_count") or 0) > 0:
                    trauma_note = f"（心理創傷 +1，累計 {merged_target.get('trauma_count')}）"
                combat = append_combat_log(
                    combat,
                    f"{target.get('display_name', target_id)} 陷入瀕死！"
                    f"{settings.near_death_minutes} 分鐘內需救援{trauma_note}",
                    log_type="near_death",
                )

    write_buffers = dict(
        items_to_delete=items_to_delete,
        squad_updates=squad_updates,
        protagonist_updates=protagonist_updates,
        trauma_events=trauma_events,
    )
    defeated_participants = _participants_with_buffers(participants, squad_updates, protagonist_updates)
    if _team_defeated_from_participants(defeated_participants):
        _commit_resolve_phase_state(
            combat_id,
            **write_buffers,
            combat_fields={"logs": combat.get("logs")},
        )
        return _end_combat(combat_id, "enemy", encounter), "enemy"

    now = datetime.now().isoformat()
    limit = combat_settings.get("phase_time_limit_seconds", 180)
    _commit_resolve_phase_state(
        combat_id,
        **write_buffers,
        combat_fields={
            "status": "player_phase",
            "current_phase": int(combat.get("current_phase") or 0) + 1,
            "enemy_hp": new_enemy_hp,
            "logs": combat.get("logs"),
            "phase_started_at": now,
            "phase_deadline": combat_phase_deadline(now, limit),
            "phase_actions": {},
        },
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
    if not combat:
        return None

    squad = get_squad(combat["squad_id"])
    team_id = squad.get("team_id") if squad else None
    starter_id = combat.get("squad_id")
    now_str = datetime.now().isoformat()
    logs = list(combat.get("logs") or [])
    enemy_hp_val = 0 if winner == "squad" else combat.get("enemy_hp", 100)

    with immediate_transaction() as conn:
        row = conn.execute("SELECT 1 FROM combats WHERE id = ?", (combat_id,)).fetchone()
        if not row:
            return None
        conn.execute(
            """UPDATE combats SET status = 'ended', winner = ?, ended_at = ?, enemy_hp = ?
               WHERE id = ?""",
            (winner, now_str, enemy_hp_val, combat_id),
        )
        purge_combat_actions(combat_id, conn=conn)
        if team_id:
            conn.execute(
                "UPDATE squads SET current_combat_id = NULL WHERE team_id = ?",
                (team_id,),
            )
        else:
            conn.execute(
                "UPDATE squads SET current_combat_id = NULL WHERE squad_id = ?",
                (starter_id,),
            )

    outcome = resolve_combat_outcome(
        winner, team_id, encounter, starter_id, combat_id=combat_id,
    )
    log_messages = outcome.get("log_messages") or []
    if log_messages:
        for entry in log_messages:
            logs.append({
                "type": entry.get("log_type", "event"),
                "message": entry.get("message", ""),
                "timestamp": now_str,
                "at": now_str,
            })
        with immediate_transaction() as conn:
            conn.execute(
                "UPDATE combats SET logs = ? WHERE id = ?",
                (json.dumps(logs[-50:], ensure_ascii=False), combat_id),
            )

    return get_combat(combat_id)

def _enemy_hp_from_logs(logs):
    """Latest post-damage enemy HP parsed from round summary logs."""
    for entry in reversed(logs or []):
        if not isinstance(entry, dict) or entry.get("type") != "summary":
            continue
        msg = entry.get("message") or ""
        match = re.search(r"剩餘\s*HP\s*(\d+)", msg)
        if match:
            return int(match.group(1))
    return None


def reconcile_enemy_hp(combat, persist=False):
    """
    Align combat.enemy_hp with log summaries when DB snapshot is stale.
    Logs are written in the same resolve pass as damage; if stored HP is higher
    than the latest summary, trust the summary.
    """
    if not combat:
        return combat
    log_hp = _enemy_hp_from_logs(combat.get("logs"))
    if log_hp is None:
        return combat
    stored = combat.get("enemy_hp")
    if stored is not None and int(stored) <= log_hp:
        return combat
    combat = dict(combat)
    combat["enemy_hp"] = log_hp
    if persist and combat.get("id"):
        save_combat(combat["id"], enemy_hp=log_hp)
    return combat


def build_enemy_combat_stats(combat, encounter=None):
    """敵人 5 維數值（同玩家：生命值／神智／力量／智力／韌性）。"""
    combat = reconcile_enemy_hp(combat)
    enemy_def = (encounter or {}).get("enemy", {}) if encounter else {}
    log_hp = _enemy_hp_from_logs(combat.get("logs"))
    if log_hp is not None:
        hp = log_hp
    elif combat.get("enemy_hp") is not None:
        hp = int(combat.get("enemy_hp"))
    else:
        hp = int(enemy_def.get("hp") or 0)
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
    from models.item import combat_item_effect_display_label, get_items_by_ids

    if combat:
        combat = reconcile_enemy_hp(combat, persist=True)
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

    item_ids_for_status = [
        (submitted or {}).get("item_id")
        for submitted in phase_actions.values()
        if (submitted or {}).get("item_id") is not None
    ]
    item_catalog_by_id = get_items_by_ids(item_ids_for_status)

    member_states = {}
    for p in participants:
        sid = p["squad_id"]
        submitted = phase_actions.get(sid)
        item_id = (submitted or {}).get("item_id")
        item_effect_type = None
        item_effect_label = None
        if item_id:
            try:
                item_row = item_catalog_by_id.get(int(item_id))
            except (TypeError, ValueError):
                item_row = None
            if item_row:
                item_effect_type = item_row.get("effect_type")
                item_effect_label = combat_item_effect_display_label(item_effect_type)
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
            "is_team_leader": bool(p.get("is_team_leader")),
            "protagonist_key": p.get("protagonist_key"),
            "trauma_count": p.get("trauma_count"),
            "submitted": bool(submitted),
            "action_type": (submitted or {}).get("action_type"),
            "dice_result": (submitted or {}).get("dice_result"),
            "item_id": item_id,
            "item_effect_type": item_effect_type,
            "item_effect_label": item_effect_label,
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

    ending_state = judge_ending(team_id) if team_id else None

    payload = {
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
        "team_id": team_id,
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
        "ending": ending_state,
        "trauma_level": (ending_state or {}).get("trauma_level", "safe"),
    }
    _enrich_settlement_meta(payload, combat=combat)
    return payload

def _preview_action_enemy_damage(player, action_type, dice_result, item_id, enemy_resilience, enemy_sanity):
    """預估單一行動對敵人傷害（不含暴走隨機結果）"""
    from models.item import get_item_by_id

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
        if item:
            effect = item.get("effect_type")
            if effect == "power_up":
                item_bonus = abs(int(item.get("effect_value") or 0))
            elif effect in ("hp_up", "sanity_up"):
                return 0, meta

    if action_type in ATTACK_ACTION_TYPES or action_type == "use_item":
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
        "escape": "逃跑",
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
    elif base.get("action_label") == "逃跑":
        summary_parts.append("你選擇逃跑")
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


def _combat_outcome_json(winner, encounter, team_id=None, participants=None):
    if winner == "squad":
        return build_victory_outcome_payload(encounter, team_id=team_id)
    if winner == "enemy":
        return build_defeat_outcome_payload(
            encounter,
            participants=participants,
            team_id=team_id,
        )
    if winner == "escaped":
        escape_block = (encounter or {}).get("escape") or {}
        return {
            "success": True,
            "status": "ended",
            "outcome": "escaped",
            "winner": "escaped",
            "active": False,
            "narrative": escape_block.get("narrative") or "全隊成功脫離戰鬥。",
            "reflection_prompt": None,
        }
    return None


def build_escape_outcome_response(combat, encounter, squad_id, team_id=None):
    """Escape success JSON — combat ends without victory/defeat rewards."""
    payload = build_combat_status_response(combat, encounter, squad_id)
    meta = _combat_outcome_json("escaped", encounter, team_id=team_id) or {}
    payload.update(meta)
    payload["round_settlement"] = {
        "team_damage_dealt": 0,
        "enemy_damage_dealt": 0,
        "escape_triggered": True,
        "escape_success": True,
        "player_hits": [],
        "counter_hits": [],
        "breakdown": {},
    }
    _enrich_settlement_meta(payload, combat=combat)
    return payload


def build_victory_outcome_response(combat, encounter, squad_id, team_id=None):
    """
    Victory JSON that includes the final round settlement (logs, enemy.hp, round_settlement).
    Used on killing-blow so the client can sync HP and show the settlement modal before victory.
    """
    if not combat or not squad_id:
        return build_victory_outcome_payload(
            encounter,
            team_id=team_id,
            combat_id=(combat or {}).get("id"),
            current_round=(combat or {}).get("current_phase"),
        )
    round_payload = _build_round_resolved_response(combat, encounter, squad_id)
    meta = build_victory_outcome_payload(
        encounter,
        team_id=team_id,
        combat_id=combat.get("id"),
        current_round=combat.get("current_phase"),
    )
    payload = {**round_payload, **meta}
    payload["outcome"] = "victory"
    payload["winner"] = "squad"
    payload["status"] = "ended"
    payload["active"] = False
    payload["round_resolved"] = True
    enemy = dict(payload.get("enemy") or {})
    enemy["hp"] = 0
    payload["enemy"] = enemy
    settlement = dict(payload.get("round_settlement") or {})
    settlement["enemy_hp_after"] = 0
    payload["round_settlement"] = settlement
    payload["round_enemy_damage"] = settlement.get("team_damage_dealt") or payload.get("round_enemy_damage") or 0
    return payload


def combat_outcome_if_finished(combat, encounter, team_id=None, squad_id=None):
    """Return victory/defeat JSON when combat already ended or enemy HP is 0."""
    if not combat:
        return None
    squad_id = squad_id or combat.get("squad_id")
    if combat.get("status") == "ended":
        winner = combat.get("winner")
        if winner == "squad" and squad_id:
            return build_victory_outcome_response(combat, encounter, squad_id, team_id=team_id)
        if winner == "escaped" and squad_id:
            return build_escape_outcome_response(combat, encounter, squad_id, team_id=team_id)
        participants = get_combat_participants(combat) if combat else None
        return _combat_outcome_json(
            winner,
            encounter,
            team_id=team_id,
            participants=participants,
        )
    if int(combat.get("enemy_hp") or 0) <= 0:
        combat_id = combat.get("id")
        if combat_id:
            combat = _end_combat(combat_id, "squad", encounter)
        if squad_id:
            return build_victory_outcome_response(combat, encounter, squad_id, team_id=team_id)
        return _combat_outcome_json("squad", encounter, team_id=team_id)
    return None


def _build_full_preview_from_status(status_payload):
    return {
        "log_entries": status_payload.get("log_entries") or [],
        "log": status_payload.get("log") or [],
        "current_phase": status_payload.get("current_phase"),
        "enemy": status_payload.get("enemy"),
        "member_states": status_payload.get("member_states"),
        "round_settlement": status_payload.get("round_settlement"),
        "round_enemy_damage": status_payload.get("round_enemy_damage"),
        "round_player_damage": status_payload.get("round_player_damage"),
    }


def _round_enemy_damage_from_logs(logs):
    """Parse latest phase summary for UI feedback (e.g. high-HP test enemies)."""
    for entry in reversed(logs or []):
        if not isinstance(entry, dict) or entry.get("type") != "summary":
            continue
        msg = entry.get("message") or ""
        match = re.search(r"受到共\s*(\d+)\s*點傷害", msg)
        if match:
            return int(match.group(1))
    return 0


def _latest_team_summary_index(logs):
    for i in range(len(logs or []) - 1, -1, -1):
        entry = logs[i]
        if not isinstance(entry, dict) or entry.get("type") != "summary":
            continue
        msg = entry.get("message") or ""
        if re.search(r"受到共\s*(\d+)\s*點傷害", msg):
            return i
    return None


def _find_participant_by_display(participants, display_name):
    name = (display_name or "").strip()
    if not name:
        return None
    for participant in participants or []:
        if (participant.get("display_name") or "").strip() == name:
            return participant
        if (participant.get("squad_id") or "").strip() == name:
            return participant
    return None


def _participant_combat_role(participant, viewer_squad_id):
    if not participant:
        return "teammate"
    if participant.get("is_protagonist"):
        return "protagonist"
    sid = participant.get("squad_id")
    if viewer_squad_id and sid == viewer_squad_id:
        return "player"
    return "teammate"


def _build_settlement_role_breakdown(player_hits, counter_hits, team_dealt, enemy_dealt):
    dealt = {"player": 0, "protagonist": 0, "teammate": 0}
    taken = {"player": 0, "protagonist": 0, "teammate": 0}
    for hit in player_hits or []:
        role = hit.get("role") or "teammate"
        if role not in dealt:
            role = "teammate"
        dealt[role] += int(hit.get("damage") or 0)
    for hit in counter_hits or []:
        role = hit.get("role") or "teammate"
        if role not in taken:
            role = "teammate"
        taken[role] += int(hit.get("damage") or 0)
    return {
        "dealt": {
            **dealt,
            "total": int(team_dealt or 0) or sum(dealt.values()),
        },
        "taken": {
            **taken,
            "total": int(enemy_dealt or 0) or sum(taken.values()),
        },
        "enemy": {
            "damage_taken": int(team_dealt or 0) or sum(dealt.values()),
            "damage_dealt": int(enemy_dealt or 0) or sum(taken.values()),
        },
    }


def _round_settlement_from_logs(logs, participants=None, viewer_squad_id=None):
    """
    Parse the most recent completed round from combat logs.
    Returns team damage to enemy and enemy counter damage to squad.
    """
    entries = logs or []
    participants = participants or []
    summary_idx = _latest_team_summary_index(entries)
    team_dealt = _round_enemy_damage_from_logs(entries)
    enemy_dealt = 0
    counter_hits = []
    player_hits = []

    if summary_idx is None:
        breakdown = _build_settlement_role_breakdown(player_hits, counter_hits, team_dealt, enemy_dealt)
        escape_triggered, escape_success = _escape_meta_from_logs(entries)
        result = {
            "team_damage_dealt": team_dealt,
            "enemy_damage_dealt": enemy_dealt,
            "counter_hits": counter_hits,
            "player_hits": player_hits,
            "breakdown": breakdown,
        }
        if escape_triggered:
            result["escape_triggered"] = True
            result["escape_success"] = escape_success
        return result

    prev_summary_idx = _latest_team_summary_index(entries[:summary_idx])
    round_start = (prev_summary_idx + 1) if prev_summary_idx is not None else 0

    for entry in entries[round_start:summary_idx]:
        if not isinstance(entry, dict) or entry.get("type") != "damage":
            continue
        msg = entry.get("message") or ""
        match = re.search(r"^(.+?)\s+(?:攻擊|Zoo 能力)對.+造成\s*(\d+)\s*點傷害", msg)
        if match:
            display = match.group(1).strip()
            participant = _find_participant_by_display(participants, display)
            player_hits.append({
                "player": display,
                "damage": int(match.group(2)),
                "squad_id": participant.get("squad_id") if participant else None,
                "role": _participant_combat_role(participant, viewer_squad_id),
            })

    for entry in entries[summary_idx + 1:]:
        if not isinstance(entry, dict):
            continue
        etype = entry.get("type")
        if etype in ("near_death", "event", "incapacitated"):
            continue
        if etype != "enemy_attack":
            break
        msg = entry.get("message") or ""
        match = re.search(r"造成\s*(\d+)\s*點傷害", msg)
        if not match:
            continue
        dmg = int(match.group(1))
        enemy_dealt += dmg
        target_match = re.search(r"反擊\s*([^，]+)", msg)
        target_name = target_match.group(1).strip() if target_match else "?"
        participant = _find_participant_by_display(participants, target_name)
        counter_hits.append({
            "target": target_name,
            "damage": dmg,
            "squad_id": participant.get("squad_id") if participant else None,
            "role": _participant_combat_role(participant, viewer_squad_id),
        })

    summary_hp = None
    if summary_idx is not None:
        summary_msg = entries[summary_idx].get("message") or ""
        hp_match = re.search(r"剩餘\s*HP\s*(\d+)", summary_msg)
        if hp_match:
            summary_hp = int(hp_match.group(1))

    breakdown = _build_settlement_role_breakdown(player_hits, counter_hits, team_dealt, enemy_dealt)
    escape_triggered, escape_success = _escape_meta_from_logs(entries, summary_idx)
    result = {
        "team_damage_dealt": team_dealt,
        "enemy_damage_dealt": enemy_dealt,
        "counter_hits": counter_hits,
        "player_hits": player_hits,
        "enemy_hp_after": summary_hp,
        "breakdown": breakdown,
    }
    if escape_triggered:
        result["escape_triggered"] = True
        result["escape_success"] = escape_success
    return result


def _attach_round_settlement(payload, combat=None):
    logs = (combat or {}).get("logs") or payload.get("log_entries")
    participants = get_combat_participants(combat) if combat else []
    viewer_squad_id = payload.get("my_squad_id")
    settlement = _round_settlement_from_logs(
        logs,
        participants=participants,
        viewer_squad_id=viewer_squad_id,
    )
    enemy_hp = (payload.get("enemy") or {}).get("hp")
    if enemy_hp is None and combat is not None and combat.get("enemy_hp") is not None:
        enemy_hp = int(combat.get("enemy_hp"))
    if enemy_hp is not None:
        settlement["enemy_hp_after"] = int(enemy_hp)
    elif settlement.get("enemy_hp_after") is None:
        settlement["enemy_hp_after"] = _enemy_hp_from_logs(logs)
    payload["round_settlement"] = settlement
    payload["round_enemy_damage"] = settlement.get("team_damage_dealt") or 0
    payload["round_player_damage"] = settlement.get("enemy_damage_dealt") or 0
    return payload


def _enrich_settlement_meta(payload, combat=None):
    """Additive COMBAT_V2 fields: stable settlement progress on every status snapshot."""
    combat_id = payload.get("combat_id") or (combat or {}).get("id")
    if combat_id is None:
        return payload
    current_phase = int(
        (combat or {}).get("current_phase")
        if combat is not None
        else payload.get("current_phase") or 0
    )
    settled_round_index = max(0, current_phase - 1)
    payload["settled_round_index"] = settled_round_index
    payload["settlement_id"] = f"{combat_id}:{settled_round_index}"
    return payload


def _build_round_resolved_response(combat, encounter, squad_id):
    combat = reconcile_enemy_hp(combat, persist=True) if combat else combat
    payload = build_combat_status_response(combat, encounter, squad_id)
    payload["status"] = "round_resolved"
    payload["round_resolved"] = True
    payload["active"] = combat.get("status") not in ("ended", "precheck")
    _attach_round_settlement(payload, combat=combat)
    _enrich_settlement_meta(payload, combat=combat)
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
NEAR_DEATH_MINUTES = settings.near_death_minutes
