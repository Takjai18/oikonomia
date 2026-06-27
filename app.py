#!/usr/bin/env python3
"""
Oikonomia - Summer Camp 2026 Web App Prototype
Built by Grok Build
Priority: Beautiful Dashboard + GPS + Photo Upload
"""

from flask import Flask, render_template_string, request, jsonify, session, redirect, send_from_directory, send_file, abort
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import sqlite3
import json
import os
import shutil
import zipfile
import io
import re
from datetime import datetime, timedelta
import math
import time
import random

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "oikonomia-2026-prototype")
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get("RENDER") == "true" or os.environ.get("FLASK_ENV") == "production",
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_PATH="/",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)
RESTORE_TOKEN_MAX_AGE = int(timedelta(days=30).total_seconds())
_restore_serializer = None

_default_data_dir = "."
if os.environ.get("RENDER") == "true" and os.path.isdir("/data"):
    _default_data_dir = "/data"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
app.static_folder = os.path.join(PROJECT_DIR, "static")
AVATAR_DIR = os.path.join(app.static_folder, "avatars")
PORTRAIT_DIR = os.path.join(app.static_folder, "portraits")
PORTRAIT_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".svg")
os.makedirs(PORTRAIT_DIR, exist_ok=True)

def _list_image_files(directory, exclude=()):
    if not os.path.isdir(directory):
        return []
    skip = set(exclude)
    return sorted(
        name for name in os.listdir(directory)
        if name not in skip
        and not name.startswith(".")
        and os.path.isfile(os.path.join(directory, name))
        and name.lower().endswith(PORTRAIT_IMAGE_EXTS)
    )

def portrait_static_path(filename):
    """非玩家角色頭像 URL（static/portraits/）。"""
    safe = os.path.basename((filename or "").strip())
    if not safe:
        return "/static/avatars/default.png"
    return f"/static/portraits/{safe}"
DATA_DIR = os.environ.get("DATA_DIR", _default_data_dir)
os.makedirs(DATA_DIR, exist_ok=True)

# 上傳圖片固定放喺 project/uploads（PA 同 local 路徑一致，避免 data/uploads 分裂）
UPLOAD_FOLDER = os.path.join(PROJECT_DIR, "uploads")
LEGACY_UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "oikonomia.db")

def migrate_upload_files():
    """把舊版 data/uploads 的檔案搬到 project/uploads"""
    if not os.path.isdir(LEGACY_UPLOAD_FOLDER):
        return 0
    if os.path.abspath(LEGACY_UPLOAD_FOLDER) == os.path.abspath(UPLOAD_FOLDER):
        return 0
    moved = 0
    for name in os.listdir(LEGACY_UPLOAD_FOLDER):
        src = os.path.join(LEGACY_UPLOAD_FOLDER, name)
        dst = os.path.join(UPLOAD_FOLDER, name)
        if not os.path.isfile(src):
            continue
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
            moved += 1
    return moved

migrate_upload_files()

def read_deploy_version():
    version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".deploy-version")
    if os.path.isfile(version_file):
        with open(version_file, encoding="utf-8") as f:
            return f.read().strip()
    return "unknown"

def normalize_photo_url(photo_path):
    """Convert stored path to browser URL segment, e.g. uploads/foo.jpg"""
    if not photo_path:
        return None
    path = str(photo_path).replace("\\", "/")
    if path.startswith("uploads/"):
        return path
    return f"uploads/{os.path.basename(path)}"

def photo_public_url(photo_path):
    normalized = normalize_photo_url(photo_path)
    return f"/{normalized}" if normalized else None

def task_display_name(task_id):
    if not task_id:
        return "未知任務"
    return LOCATIONS.get(task_id, {}).get("name", task_id)

def safe_zip_arcname(*parts):
    name = "_".join(str(p or "unknown") for p in parts)
    return re.sub(r"[^\w\-.]", "_", name)

def resolve_upload_disk_path(filename):
    basename = os.path.basename(str(filename).replace("\\", "/"))
    if not basename:
        return None
    for folder in (UPLOAD_FOLDER, LEGACY_UPLOAD_FOLDER):
        if not folder or not os.path.isdir(folder):
            continue
        path = os.path.join(folder, basename)
        if os.path.isfile(path):
            return path
    return None

DEFAULT_PROTAGONIST = {"hp": 100, "sanity": 100, "power": 100, "intellect": 100, "resilience": 100}
SQUAD_ATTRIBUTES = ["hp", "sanity", "power", "intellect", "resilience"]
MAX_INVENTORY_SLOTS = 5

SAMPLE_ITEMS = [
    {
        "name": "裂縫碎片",
        "description": "來自界線的微小碎片，似乎還有溫度。",
        "icon": "🧩",
        "item_type": "story",
        "qr_code_value": "item-001",
        "has_ability": 0,
        "effect_type": None,
        "effect_value": 0,
        "image_path": "/static/images/items/item-001.svg",
    },
    {
        "name": "Judas 的信箋",
        "description": "上面有模糊的字跡，閱讀時 Sanity 會微微波動。",
        "icon": "📜",
        "item_type": "story",
        "qr_code_value": "item-002",
        "has_ability": 1,
        "effect_type": "sanity_up",
        "effect_value": -5,
        "image_path": "/static/images/items/item-002.svg",
    },
    {
        "name": "守護者徽章",
        "description": "掃描營地 QR 後獲得的證物，能強化你的 Resilience。",
        "icon": "🛡️",
        "item_type": "qr",
        "qr_code_value": "item-003",
        "has_ability": 1,
        "effect_type": "resilience_up",
        "effect_value": 8,
        "image_path": "/static/images/items/item-003.svg",
    },
    {
        "name": "記憶之瓶",
        "description": "裝住一段未完成的對話，觸碰時 Sanity 會回復。",
        "icon": "🫙",
        "item_type": "qr",
        "qr_code_value": "item-004",
        "has_ability": 1,
        "effect_type": "sanity_up",
        "effect_value": 5,
        "image_path": "/static/images/items/item-004.svg",
    },
    {
        "name": "界線之鑰",
        "description": "據說可以打開某扇隱藏的門，蘊含強大 Power。",
        "icon": "🗝️",
        "item_type": "special",
        "qr_code_value": "item-005",
        "has_ability": 1,
        "effect_type": "power_up",
        "effect_value": 10,
        "image_path": "/static/images/items/item-005.svg",
    },
]

ITEM_EFFECT_STAT_MAP = {
    "power_up": "power",
    "sanity_up": "sanity",
    "resilience_up": "resilience",
    "hp_up": "hp",
    "intellect_up": "intellect",
}

ITEM_EFFECT_LABELS = {
    "power_up": "力量",
    "sanity_up": "神智",
    "resilience_up": "韌性",
    "hp_up": "生命值",
    "intellect_up": "智力",
}

# ==================== Encounter / Combat ====================
ENCOUNTERS_DIR = os.path.join(PROJECT_DIR, "encounters")
NEAR_DEATH_MINUTES = 15
COMBAT_ACTION_TYPES = (
    "attack", "attack_physical", "attack_nonphysical",
    "defend", "use_item", "use_zoo", "pass",
)
COMBAT_ATTACK_BASE_DAMAGE = 10
ATTACK_ACTION_TYPES = frozenset({
    "attack", "attack_physical", "attack_nonphysical", "use_zoo",
})
DICE_MULTIPLIERS = {0: 0.0, 1: 1.0, 2: 1.5, 3: 2.0}
_encounter_cache = {}

def load_encounter(encounter_id):
    if encounter_id in _encounter_cache:
        return _encounter_cache[encounter_id]
    path = os.path.join(ENCOUNTERS_DIR, f"{encounter_id}.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _encounter_cache[encounter_id] = data
    return data

def list_encounter_ids():
    if not os.path.isdir(ENCOUNTERS_DIR):
        return []
    return sorted(
        name[:-5] for name in os.listdir(ENCOUNTERS_DIR)
        if name.endswith(".json")
    )

def load_all_encounters():
    return [load_encounter(eid) for eid in list_encounter_ids() if load_encounter(eid)]

def encounter_route_matches(encounter_route, squad_route):
    """route=test 的 encounter 對所有已選路線可見"""
    if not encounter_route or encounter_route == "test":
        return True
    if not squad_route:
        return False
    return encounter_route == squad_route

def get_team_members(team_id):
    if not team_id:
        return []
    clean_team_id = normalize_team_id(team_id)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))",
        (clean_team_id,),
    ).fetchall()
    conn.close()
    return [row_to_squad(r) for r in rows]

def get_team_average_stat(team_id, stat):
    members = get_team_members(team_id)
    if not members:
        return 0
    values = [int(m.get(stat) or 0) for m in members]
    return sum(values) / len(values)

def team_has_item_by_name(team_id, item_name):
    if not team_id or not item_name:
        return False
    clean_team_id = normalize_team_id(team_id)
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("""
        SELECT COUNT(*) FROM player_items pi
        JOIN squads s ON pi.squad_id = s.squad_id
        JOIN items i ON pi.item_id = i.id
        WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?)) AND i.name = ?
    """, (clean_team_id, item_name)).fetchone()
    conn.close()
    return row[0] > 0

def evaluate_precheck_condition(condition, team_id):
    if not condition:
        return False
    cond = condition.strip()
    parts = re.split(r"\s+OR\s+", cond, flags=re.I)
    return any(_evaluate_precheck_clause(p.strip(), team_id) for p in parts if p.strip())

def _evaluate_precheck_clause(clause, team_id):
    item_match = re.match(r"has_item\s+'([^']+)'", clause, re.I)
    if item_match:
        return team_has_item_by_name(team_id, item_match.group(1))
    stat_match = re.match(r"average_(\w+)\s*>=\s*(\d+)", clause, re.I)
    if stat_match:
        stat = stat_match.group(1).lower()
        threshold = int(stat_match.group(2))
        if stat not in SQUAD_ATTRIBUTES:
            return False
        return get_team_average_stat(team_id, stat) >= threshold
    return False

def parse_status_effects(raw):
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}

def serialize_status_effects(effects):
    return json.dumps(effects or {}, ensure_ascii=False)

def apply_status_debuff(squad_id, debuff_key):
    squad = get_squad(squad_id)
    if not squad:
        return
    effects = parse_status_effects(squad.get("status_effects"))
    effects[debuff_key] = {"applied_at": datetime.now().isoformat()}
    update_squad(squad_id, status_effects=serialize_status_effects(effects))
    if debuff_key == "resilience_-8_until_healed":
        apply_trauma_on_failure(squad_id, "resilience", 8)

def add_insight_fragments(team_id, amount):
    if not team_id or amount <= 0:
        return
    for member in get_team_members(team_id):
        squad = get_squad(member["squad_id"])
        if squad:
            update_squad(
                member["squad_id"],
                insight_fragments=int(squad.get("insight_fragments") or 0) + amount,
            )

def encounter_already_completed(team_id, encounter_id):
    if not team_id:
        return False
    clean_team_id = normalize_team_id(team_id)
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id FROM encounter_completions WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?)) AND encounter_id = ?",
        (clean_team_id, encounter_id),
    ).fetchone()
    conn.close()
    return bool(row)

def record_encounter_completion(team_id, encounter_id, outcome, unlocks=None, narrative=None):
    clean_team_id = normalize_team_id(team_id)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT OR REPLACE INTO encounter_completions
           (team_id, encounter_id, outcome, unlocks, narrative, completed_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            clean_team_id,
            encounter_id,
            outcome,
            json.dumps(unlocks or [], ensure_ascii=False),
            narrative,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()

def row_to_combat(row):
    data = dict(row)
    for field in ("phase_actions", "logs"):
        try:
            data[field] = json.loads(data.get(field) or ({} if field == "phase_actions" else []))
        except (json.JSONDecodeError, TypeError):
            data[field] = {} if field == "phase_actions" else []
    return data

def get_combat(combat_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM combats WHERE id = ?", (combat_id,)).fetchone()
    conn.close()
    return row_to_combat(row) if row else None

def get_combat_by_squad(squad_id):
    squad = get_squad(squad_id)
    if not squad:
        return None
    combat_id = squad.get("current_combat_id")
    if combat_id:
        combat = get_combat(combat_id)
        if combat and combat.get("status") not in ("ended",):
            return combat
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
                            base_damage=COMBAT_ATTACK_BASE_DAMAGE):
    if multiplier <= 0:
        return 0
    attack_stat = get_effective_attack_stat(player)
    raw = ((attack_stat * 1.5) + base_damage + item_bonus) * multiplier - (enemy_resilience * 0.8)
    return max(1, int(raw))

def calculate_damage_simple(attacker, target, base_damage=COMBAT_ATTACK_BASE_DAMAGE,
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

def calculate_incoming_damage(enemy_base_damage, player_resilience, defending=False):
    reduction = math.floor(player_resilience * 0.6)
    damage = max(0, enemy_base_damage - reduction)
    if defending:
        damage = max(0, math.floor(damage * 0.5))
    return damage

def dice_multiplier(dice_result):
    try:
        dice = int(dice_result)
    except (TypeError, ValueError):
        dice = 2
    return DICE_MULTIPLIERS.get(max(0, min(3, dice)), 1.0)

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

def get_combat_participants(combat):
    squad = get_squad(combat["squad_id"])
    if squad and squad.get("team_id"):
        return get_team_members(squad["team_id"])
    s = get_squad(combat["squad_id"])
    return [s] if s else []

def all_phase_actions_submitted(combat, participants):
    actions = combat.get("phase_actions") or {}
    active = []
    for p in participants:
        sid = p["squad_id"]
        if p.get("near_death_until"):
            try:
                if datetime.now() >= datetime.fromisoformat(p["near_death_until"]):
                    continue
            except ValueError:
                pass
        active.append(sid)
    if not active:
        return True
    return all(sid in actions for sid in active)

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

def apply_damage_to_player(squad_id, damage):
    squad = get_squad(squad_id)
    if not squad:
        return
    new_hp = max(0, int(squad.get("hp") or 0) - damage)
    updates = {"hp": new_hp}
    if new_hp <= 0:
        updates["near_death_until"] = (
            datetime.now() + timedelta(minutes=NEAR_DEATH_MINUTES)
        ).isoformat()
    update_squad(squad_id, **updates)

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
    - 敵人反擊（韌性最低者，Defend 減傷 50%）
    - 瀕死檢查、日誌、Phase 狀態更新
    回傳 (combat, winner)；winner 為 'squad' | 'enemy' | None
    """
    combat = get_combat(combat_id)
    if not combat or combat.get("status") != "player_phase":
        return combat, None

    encounter = load_encounter(combat["encounter_id"])
    settings = (encounter or {}).get("combat_settings", {})
    participants = get_combat_participants(combat)
    actions = combat.get("phase_actions") or {}

    enemy_hp = int(combat.get("enemy_hp") or 0)
    enemy_resilience = int(combat.get("enemy_resilience") or 0)
    enemy_sanity = int(combat.get("enemy_sanity") or 0)
    enemy_base_damage = int(combat.get("enemy_base_damage") or 0)
    enemy_name = combat.get("enemy_name") or "敵人"

    total_damage_to_enemy = 0
    berserk_players = []

    for player_squad_id, action_data in actions.items():
        player = get_squad(player_squad_id)
        if not player:
            continue
        display = player.get("display_name") or player_squad_id
        sanity = int(player.get("sanity") or 0)

        if is_berserk(sanity):
            berserk_players.append(player_squad_id)
            if random.random() < 0.30:
                self_dmg = max(1, int(get_effective_attack_stat(player) * 0.3))
                apply_damage_to_player(player_squad_id, self_dmg)
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
            combat = append_combat_log(
                combat,
                f"{display} {action_label}對{enemy_name}造成 {dmg} 點傷害"
                f"（{stat_info['label']} {stat_info['value']} · 骰 {dice}）",
                log_type="damage",
            )
        elif action_type == "defend":
            combat = append_combat_log(
                combat,
                f"{display} 進入防禦姿態",
                log_type="defend",
            )
        elif action_type == "pass":
            combat = append_combat_log(
                combat,
                f"{display} 選擇觀望",
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

    target = get_lowest_resilience_player(
        [get_squad(p["squad_id"]) or p for p in participants]
    )
    if target:
        target_id = target["squad_id"]
        defending = (actions.get(target_id) or {}).get("action_type") == "defend"
        incoming = calculate_incoming_damage(
            enemy_base_damage,
            get_effective_stat(target, "resilience"),
            defending=defending,
        )
        if incoming > 0:
            apply_damage_to_player(target_id, incoming)
            refreshed = get_squad(target_id)
            combat = append_combat_log(
                combat,
                f"{enemy_name} 反擊 {target.get('display_name', target_id)}，造成 {incoming} 點傷害"
                + ("（防禦減半）" if defending else ""),
                log_type="enemy_attack",
            )
            if refreshed and refreshed.get("near_death_until"):
                combat = append_combat_log(
                    combat,
                    f"{target.get('display_name', target_id)} 陷入瀕死！{NEAR_DEATH_MINUTES} 分鐘內需救援",
                    log_type="near_death",
                )

    if _team_combat_defeated(combat):
        save_combat(combat_id, logs=combat.get("logs"))
        return _end_combat(combat_id, "enemy", encounter), "enemy"

    now = datetime.now().isoformat()
    limit = settings.get("phase_time_limit_seconds", 180)
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
    save_combat(
        combat_id,
        status="ended",
        winner=winner,
        ended_at=datetime.now().isoformat(),
        logs=combat.get("logs"),
    )
    starter_id = combat.get("squad_id")
    if team_id:
        clear_team_combat_id(team_id)
    elif starter_id:
        update_squad(starter_id, current_combat_id=None)
    if winner == "squad" and encounter:
        if team_id:
            apply_encounter_success(team_id, encounter, starter_id)
        elif starter_id:
            apply_encounter_success_solo(starter_id, encounter)
    elif winner == "enemy" and encounter:
        if team_id:
            apply_encounter_failure(team_id, encounter)
        elif starter_id:
            apply_encounter_failure_solo(starter_id, encounter)
    return get_combat(combat_id)

def apply_trauma_on_failure(squad_id, stat, amount):
    trauma_key = {
        "resilience": "trauma_resilience",
        "power": "trauma_power",
        "intellect": "trauma_intellect",
    }.get(stat)
    if not trauma_key:
        return
    squad = get_squad(squad_id)
    if not squad:
        return
    new_trauma = int(squad.get(trauma_key) or 0) + amount
    update_squad(squad_id, **{trauma_key: new_trauma})

def apply_encounter_success(team_id, encounter, started_by):
    success = encounter.get("success", {})
    add_insight_fragments(team_id, success.get("insight_fragment", 0))
    unlocks = []
    if success.get("next_story_unlock"):
        unlocks.append(success["next_story_unlock"])
    for reward in success.get("rewards", []):
        if reward.get("type") == "item" and random.random() <= float(reward.get("chance", 1)):
            item = get_item_by_qr_code_value(reward.get("item_id"))
            if item and started_by:
                grant_item_to_squad(started_by, item["id"], source="encounter")
    record_encounter_completion(
        team_id,
        encounter["encounter_id"],
        "success",
        unlocks=unlocks,
        narrative=success.get("narrative"),
    )

def apply_failure_side_effects(squad_id, failure):
    """失敗附加效果：trauma、debuff、神智傷害、強制瀕死"""
    if not squad_id or not failure:
        return
    trauma = failure.get("trauma", {})
    stat = trauma.get("stat", "resilience")
    amount = int(trauma.get("amount", 0))
    if amount:
        apply_trauma_on_failure(squad_id, stat, amount)
    if failure.get("debuff"):
        apply_status_debuff(squad_id, failure["debuff"])
    sanity_dmg = int(failure.get("sanity_damage") or 0)
    if sanity_dmg:
        squad = get_squad(squad_id)
        if squad:
            new_sanity = max(0, int(squad.get("sanity") or 0) - sanity_dmg)
            update_squad(squad_id, sanity=new_sanity)
    if failure.get("force_near_death"):
        update_squad(
            squad_id,
            hp=0,
            near_death_until=(datetime.now() + timedelta(minutes=NEAR_DEATH_MINUTES)).isoformat(),
        )

def apply_encounter_failure(team_id, encounter):
    failure = encounter.get("failure", {})
    for member in get_team_members(team_id):
        apply_failure_side_effects(member["squad_id"], failure)
    record_encounter_completion(
        team_id,
        encounter["encounter_id"],
        "failure",
        narrative=failure.get("narrative"),
    )

def apply_encounter_success_solo(squad_id, encounter):
    success = encounter.get("success", {})
    squad = get_squad(squad_id)
    if squad:
        fragments = int(squad.get("insight_fragments") or 0) + int(success.get("insight_fragment", 0))
        update_squad(squad_id, insight_fragments=fragments)
    for reward in success.get("rewards", []):
        if reward.get("type") == "item" and random.random() <= float(reward.get("chance", 1)):
            item = get_item_by_qr_code_value(reward.get("item_id"))
            if item:
                grant_item_to_squad(squad_id, item["id"], source="encounter")

def apply_encounter_failure_solo(squad_id, encounter):
    apply_failure_side_effects(squad_id, encounter.get("failure", {}))

def apply_precheck_skip(team_id, encounter):
    skip = encounter.get("precheck", {}).get("skip_reward", {})
    add_insight_fragments(team_id, skip.get("insight_fragment", 0))
    record_encounter_completion(
        team_id,
        encounter["encounter_id"],
        "skipped_precheck",
        narrative=skip.get("narrative"),
    )

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


def build_combat_status_response(combat, encounter, squad_id):
    settings = (encounter or {}).get("combat_settings", {})
    me = get_squad(squad_id) or {}
    protagonists = get_team_protagonists(me["team_id"]) if me.get("team_id") else {}
    participants = get_combat_participants(combat) if combat else []
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
            "sanity": p.get("sanity"),
            "power": p.get("power"),
            "intellect": p.get("intellect"),
            "resilience": get_effective_stat(p, "resilience"),
            "near_death_until": p.get("near_death_until"),
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
        "phase_expired": combat_phase_expired(combat, settings),
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
            "sanity": me.get("sanity"),
            "resilience": get_effective_stat(me, "resilience"),
            "near_death_until": me.get("near_death_until"),
        },
        "berserk_warning": berserk_hint,
        "berserk_chance": round(berserk_probability(me.get("sanity", 50)) * 100),
        "log": log_messages,
        "log_entries": log_entries,
        "reflection_prompt": (encounter or {}).get("reflection_prompt"),
        "combat_settings": settings,
        "available_actions": list(COMBAT_ACTION_TYPES),
        "winner": combat.get("winner"),
        "enemy_description": (encounter or {}).get("enemy", {}).get("description"),
        "route": (encounter or {}).get("route"),
        "max_phases": settings.get("max_phases", 5),
        "my_squad_id": squad_id,
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

def build_combat_round_preview(combat_id, squad_id, action_type, dice_result, item_id=None):
    combat = get_combat(combat_id)
    if not combat or combat.get("status") != "player_phase":
        return None

    squad = get_squad(squad_id)
    if not squad:
        return None

    encounter = load_encounter(combat["encounter_id"])
    enemy_res = int(combat.get("enemy_resilience") or 0)
    enemy_san = int(combat.get("enemy_sanity") or 0)
    enemy_base = int(combat.get("enemy_base_damage") or 0)
    participants = get_combat_participants(combat)
    phase_actions = dict(combat.get("phase_actions") or {})

    my_dmg, my_meta = _preview_action_enemy_damage(
        squad, action_type, dice_result, item_id, enemy_res, enemy_san,
    )
    ally_damage = 0
    ally_count = 0
    for pid, ad in phase_actions.items():
        if pid == squad_id:
            continue
        player = get_squad(pid)
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
    counter_defending = False
    if target:
        target_id = target["squad_id"]
        counter_defending = (hypo_actions.get(target_id) or {}).get("action_type") == "defend"
        counter_damage = calculate_incoming_damage(
            enemy_base,
            get_effective_stat(target, "resilience"),
            defending=counter_defending,
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
        "counter_pending": not all_submitted and len(active_participants) > 1,
        "pending_teammates": max(0, pending_count - 0) if not all_submitted else 0,
        "phase_resolves_now": all_submitted or len(active_participants) <= 1,
        "berserk_risk": my_meta.get("berserk_risk", False),
        "damage_if_normal": my_meta.get("damage_if_normal", my_dmg),
        "attack_stat_label": my_meta.get("attack_stat_label"),
        "attack_stat_value": my_meta.get("attack_stat_value"),
        "risks": risks,
    }

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS squads (
        squad_id TEXT PRIMARY KEY,
        sanity INTEGER DEFAULT 50,
        hp INTEGER DEFAULT 100,
        resources INTEGER DEFAULT 0,
        zoo_skills TEXT DEFAULT '[]',
        last_update TEXT,
        power INTEGER DEFAULT 100,
        intellect INTEGER DEFAULT 100,
        resilience INTEGER DEFAULT 100,
        route TEXT,
        protagonist_stats TEXT,
        team_id TEXT,
        is_team_leader INTEGER DEFAULT 0,
        display_name TEXT,
        pin TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        squad_id TEXT,
        task_id TEXT,
        content TEXT,
        photo_path TEXT,
        timestamp TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS teams (
        team_id TEXT PRIMARY KEY,
        team_name TEXT NOT NULL,
        route TEXT,
        created_at TEXT,
        leader_squad_id TEXT,
        gm_notes TEXT DEFAULT ''
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS global_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        effect_type TEXT,
        effect_value INTEGER DEFAULT 0,
        created_by TEXT DEFAULT 'GM',
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        icon TEXT,
        qr_code_value TEXT UNIQUE,
        item_type TEXT DEFAULT 'normal',
        is_active INTEGER DEFAULT 1,
        is_one_time_use INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS qr_code_uses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL UNIQUE,
        squad_id TEXT NOT NULL,
        team_id TEXT,
        used_at TEXT DEFAULT CURRENT_TIMESTAMP,
        source TEXT,
        FOREIGN KEY (item_id) REFERENCES items(id),
        FOREIGN KEY (squad_id) REFERENCES squads(squad_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS player_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        squad_id TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        obtained_at TEXT DEFAULT CURRENT_TIMESTAMP,
        source TEXT,
        FOREIGN KEY (squad_id) REFERENCES squads(squad_id),
        FOREIGN KEY (item_id) REFERENCES items(id),
        UNIQUE(squad_id, item_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS encounter_completions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id TEXT NOT NULL,
        encounter_id TEXT NOT NULL,
        outcome TEXT NOT NULL,
        unlocks TEXT DEFAULT '[]',
        narrative TEXT,
        completed_at TEXT,
        UNIQUE(team_id, encounter_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS combats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        squad_id TEXT NOT NULL,
        encounter_id TEXT NOT NULL,
        status TEXT DEFAULT 'precheck',
        current_phase INTEGER DEFAULT 0,
        enemy_name TEXT,
        enemy_hp INTEGER,
        enemy_max_hp INTEGER,
        enemy_resilience INTEGER,
        enemy_sanity INTEGER,
        enemy_base_damage INTEGER,
        phase_actions TEXT DEFAULT '{}',
        logs TEXT DEFAULT '[]',
        phase_started_at TEXT,
        phase_deadline TEXT,
        started_at TEXT,
        ended_at TEXT,
        winner TEXT,
        FOREIGN KEY (squad_id) REFERENCES squads(squad_id)
    )''')

    conn.commit()
    conn.close()
    migrate_db()

def migrate_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("PRAGMA table_info(squads)")
    cols = {row[1] for row in c.fetchall()}
    squad_additions = {
        "power": "INTEGER DEFAULT 100",
        "intellect": "INTEGER DEFAULT 100",
        "resilience": "INTEGER DEFAULT 100",
        "route": "TEXT",
        "protagonist_stats": "TEXT",
        "team_id": "TEXT",
        "is_team_leader": "INTEGER DEFAULT 0",
    }
    for col, typedef in squad_additions.items():
        if col not in cols:
            try:
                c.execute(f"ALTER TABLE squads ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass
    if "display_name" not in cols:
        try:
            c.execute("ALTER TABLE squads ADD COLUMN display_name TEXT")
        except sqlite3.OperationalError:
            pass
    # === 新增 PIN 欄位 ===
    if "pin" not in cols:
        try:
            c.execute("ALTER TABLE squads ADD COLUMN pin TEXT")
        except sqlite3.OperationalError:
            pass
    if "avatar" not in cols:
        try:
            c.execute("ALTER TABLE squads ADD COLUMN avatar TEXT")
        except sqlite3.OperationalError:
            pass
    if "insight_fragments" not in cols:
        try:
            c.execute("ALTER TABLE squads ADD COLUMN insight_fragments INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
    if "status_effects" not in cols:
        try:
            c.execute("ALTER TABLE squads ADD COLUMN status_effects TEXT DEFAULT '{}'")
        except sqlite3.OperationalError:
            pass
    squad_trauma_cols = {
        "trauma_resilience": "INTEGER DEFAULT 0",
        "trauma_power": "INTEGER DEFAULT 0",
        "trauma_intellect": "INTEGER DEFAULT 0",
        "near_death_until": "TEXT",
        "current_combat_id": "INTEGER",
    }
    for col, typedef in squad_trauma_cols.items():
        if col not in cols:
            try:
                c.execute(f"ALTER TABLE squads ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass
    c.execute(
        "UPDATE squads SET protagonist_stats = ? WHERE protagonist_stats IS NULL",
        (json.dumps(DEFAULT_PROTAGONIST),),
    )

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='teams'")
    if not c.fetchone():
        c.execute('''CREATE TABLE teams (
            team_id TEXT PRIMARY KEY,
            team_name TEXT NOT NULL,
            route TEXT,
            created_at TEXT,
            leader_squad_id TEXT,
            gm_notes TEXT DEFAULT ''
        )''')

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='global_events'")
    if not c.fetchone():
        c.execute('''CREATE TABLE global_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            effect_type TEXT,
            effect_value INTEGER DEFAULT 0,
            created_by TEXT DEFAULT 'GM',
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
    else:
        c.execute("PRAGMA table_info(global_events)")
        ge_cols = {row[1] for row in c.fetchall()}
        if "title" not in ge_cols:
            c.execute('''CREATE TABLE global_events_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                effect_type TEXT,
                effect_value INTEGER DEFAULT 0,
                created_by TEXT,
                timestamp TEXT
            )''')
            if "message" in ge_cols:
                c.execute("""
                    INSERT INTO global_events_new
                        (title, description, effect_type, effect_value, created_by, timestamp)
                    SELECT message, message, event_type, 0, 'GM', timestamp
                    FROM global_events
                """)
            c.execute("DROP TABLE global_events")
            c.execute("ALTER TABLE global_events_new RENAME TO global_events")

    c.execute("PRAGMA table_info(teams)")
    team_cols = {row[1] for row in c.fetchall()}
    team_additions = {
        "leader_squad_id": "TEXT",
        "gm_notes": "TEXT DEFAULT ''",
    }
    for col, typedef in team_additions.items():
        if col not in team_cols:
            try:
                c.execute(f"ALTER TABLE teams ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
    if not c.fetchone():
        c.execute('''CREATE TABLE items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            icon TEXT,
            qr_code_value TEXT UNIQUE,
            item_type TEXT DEFAULT 'normal',
            is_active INTEGER DEFAULT 1,
            is_one_time_use INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

    c.execute("PRAGMA table_info(items)")
    item_cols = {row[1] for row in c.fetchall()}
    item_additions = {
        "qr_code_value": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "is_one_time_use": "INTEGER DEFAULT 1",
        "effect_type": "TEXT",
        "effect_value": "INTEGER DEFAULT 0",
        "has_ability": "INTEGER DEFAULT 0",
        "image_path": "TEXT",
    }
    for col, typedef in item_additions.items():
        if col not in item_cols:
            try:
                c.execute(f"ALTER TABLE items ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass

    missing_qr_rows = c.execute("""
        SELECT id FROM items
        WHERE qr_code_value IS NULL OR TRIM(qr_code_value) = ''
    """).fetchall()
    for row in missing_qr_rows:
        c.execute(
            "UPDATE items SET qr_code_value = ? WHERE id = ?",
            (f"item-{row[0]:03d}", row[0]),
        )

    try:
        c.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_items_qr_code_value
            ON items(qr_code_value)
            WHERE qr_code_value IS NOT NULL AND TRIM(qr_code_value) != ''
        """)
    except sqlite3.OperationalError:
        pass

    c.execute("UPDATE items SET is_active = 1 WHERE is_active IS NULL")
    c.execute("UPDATE items SET is_one_time_use = 1 WHERE is_one_time_use IS NULL")
    c.execute("UPDATE items SET is_one_time_use = 0 WHERE item_type = 'story'")

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='qr_code_uses'")
    if not c.fetchone():
        c.execute('''CREATE TABLE qr_code_uses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL UNIQUE,
            squad_id TEXT NOT NULL,
            team_id TEXT,
            used_at TEXT DEFAULT CURRENT_TIMESTAMP,
            source TEXT,
            FOREIGN KEY (item_id) REFERENCES items(id),
            FOREIGN KEY (squad_id) REFERENCES squads(squad_id)
        )''')

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='player_items'")
    if not c.fetchone():
        c.execute('''CREATE TABLE player_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            squad_id TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            obtained_at TEXT DEFAULT CURRENT_TIMESTAMP,
            source TEXT,
            FOREIGN KEY (squad_id) REFERENCES squads(squad_id),
            FOREIGN KEY (item_id) REFERENCES items(id),
            UNIQUE(squad_id, item_id)
        )''')

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='encounter_completions'")
    if not c.fetchone():
        c.execute('''CREATE TABLE encounter_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT NOT NULL,
            encounter_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            unlocks TEXT DEFAULT '[]',
            narrative TEXT,
            completed_at TEXT,
            UNIQUE(team_id, encounter_id)
        )''')

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='combats'")
    if not c.fetchone():
        c.execute('''CREATE TABLE combats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            squad_id TEXT NOT NULL,
            encounter_id TEXT NOT NULL,
            status TEXT DEFAULT 'precheck',
            current_phase INTEGER DEFAULT 0,
            enemy_name TEXT,
            enemy_hp INTEGER,
            enemy_max_hp INTEGER,
            enemy_resilience INTEGER,
            enemy_sanity INTEGER,
            enemy_base_damage INTEGER,
            phase_actions TEXT DEFAULT '{}',
            logs TEXT DEFAULT '[]',
            phase_started_at TEXT,
            phase_deadline TEXT,
            started_at TEXT,
            ended_at TEXT,
            winner TEXT,
            FOREIGN KEY (squad_id) REFERENCES squads(squad_id)
        )''')

    c.execute("PRAGMA table_info(combats)")
    combat_cols = {row[1] for row in c.fetchall()}
    for col, typedef in {
        "enemy_power": "INTEGER",
        "enemy_intellect": "INTEGER",
    }.items():
        if col not in combat_cols:
            try:
                c.execute(f"ALTER TABLE combats ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass

    item_count = c.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    if item_count == 0:
        now = datetime.now().isoformat()
        for entry in SAMPLE_ITEMS:
            is_one_time = 0 if entry["item_type"] == "story" else 1
            c.execute(
                """INSERT INTO items
                   (name, description, icon, item_type, qr_code_value, is_active,
                    is_one_time_use, has_ability, effect_type, effect_value,
                    image_path, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)""",
                (
                    entry["name"],
                    entry["description"],
                    entry["icon"],
                    entry["item_type"],
                    entry["qr_code_value"],
                    is_one_time,
                    entry.get("has_ability", 0),
                    entry.get("effect_type"),
                    entry.get("effect_value", 0),
                    entry.get("image_path"),
                    now,
                ),
            )
    else:
        for entry in SAMPLE_ITEMS:
            c.execute(
                """UPDATE items
                   SET has_ability = ?, effect_type = ?, effect_value = ?,
                       image_path = COALESCE(NULLIF(image_path, ''), ?),
                       description = ?
                   WHERE qr_code_value = ?""",
                (
                    entry.get("has_ability", 0),
                    entry.get("effect_type"),
                    entry.get("effect_value", 0),
                    entry.get("image_path"),
                    entry["description"],
                    entry["qr_code_value"],
                ),
            )

    conn.commit()
    conn.close()

init_db()

# ==================== 樣本資料（之後容易改） ====================
LOCATIONS = {
    "loc1": {
        "name": "裂縫起點",
        "hint": "籃球場旁邊嘅大樹下",
        "lat": 22.3850,
        "lng": 114.2700,
        "radius": 40,
        "task_type": "gps",
        "description": "Iggy 嘅第一段記憶似乎喺呢度。"
    },
    "loc2": {
        "name": "Judas 嘅低語",
        "hint": "室內活動室角落",
        "lat": 22.3845,
        "lng": 114.2695,
        "radius": 30,
        "task_type": "puzzle",
        "description": "Judas 留低嘅謎題。"
    },
    "loc3": {
        "name": "痛楚回音",
        "hint": "營地邊緣安靜位置",
        "lat": 22.3830,
        "lng": 114.2720,
        "radius": 50,
        "task_type": "photo",
        "description": "影一張代表「界線」嘅相。"
    }
}

# ==================== 故事階段設定（之後容易改） ====================
# 每個 Stage 解鎖所需「獨特已完成任務」最低數量（Stage 0 = 未達 Stage 1 門檻）
STORY_STAGE_THRESHOLDS = {
    1: 2,   # Stage 1：至少 N 個任務 — 可改
    2: 4,   # Stage 2：至少 N 個任務 — 可改
    3: 6,   # Stage 3（最終）：至少 N 個任務 — 可改
}

# 可選：特定任務 ID 解鎖階段（留空 = 只用上面數量門檻）
# 完成 listed 任務之一即可達到該 stage（與數量門檻取較高）
STORY_STAGE_REQUIRED_TASKS = {
    # 1: ["loc1"],
    # 2: ["loc2"],
    # 3: ["loc3"],
}

STORY_CONTENT = {
    "iggy": {
        0: {"title": "🔥 第一階段：裂縫的開端", "content": "你踏入了 Oikonomia 的世界，Iggy 的第一段記憶正喺度等待被找回。"},
        1: {"title": "🔥 第二階段：痛楚的回音", "content": "你開始感受到 Iggy 曾經承受過嘅界線與痛楚。Judas 的低語開始出現。"},
        2: {"title": "🔥 第三階段：界線的崩壞", "content": "Iggy 嘅世界開始出現裂痕。你必須決定係咪繼續陪佢走落去。"},
        3: {"title": "🔥 最終階段：救贖或崩壞", "content": "你已經深入 Iggy 嘅核心。最後嘅選擇將會決定一切。"},
    },
    "marah": {
        0: {"title": "🌊 第一階段：智慧的開端", "content": "你選擇了 Marah 路線，開始以智慧同韌性去面對界線。"},
        1: {"title": "🌊 第二階段：低語的解析", "content": "Judas 嘅謎題開始出現。你正試圖理解 Marah 背後嘅意義。"},
        2: {"title": "🌊 第三階段：韌性的考驗", "content": "你開始面對更深層嘅情緒勒索同界線問題。"},
        3: {"title": "🌊 最終階段：覺醒", "content": "你已經掌握足夠嘅資訊，準備迎接最後嘅真相。"},
    },
}

def count_team_distinct_tasks(squad_id, team_id):
    conn = sqlite3.connect(DB_PATH)
    if team_id:
        clean_team_id = normalize_team_id(team_id)
        count = conn.execute("""
            SELECT COUNT(DISTINCT task_id)
            FROM submissions
            WHERE squad_id IN (
                SELECT squad_id FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))
            )
        """, (clean_team_id,)).fetchone()[0]
        rows = conn.execute("""
            SELECT DISTINCT task_id
            FROM submissions
            WHERE squad_id IN (
                SELECT squad_id FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))
            )
        """, (clean_team_id,)).fetchall()
    else:
        count = conn.execute(
            "SELECT COUNT(DISTINCT task_id) FROM submissions WHERE squad_id = ?",
            (squad_id,),
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT DISTINCT task_id FROM submissions WHERE squad_id = ?",
            (squad_id,),
        ).fetchall()
    conn.close()
    return count, {row[0] for row in rows}

def resolve_story_stage(completed_count, completed_task_ids):
    stage = 0
    for target_stage, min_tasks in STORY_STAGE_THRESHOLDS.items():
        if completed_count >= min_tasks:
            stage = max(stage, target_stage)
    for target_stage, required_tasks in STORY_STAGE_REQUIRED_TASKS.items():
        if required_tasks and any(t in completed_task_ids for t in required_tasks):
            stage = max(stage, target_stage)
    return min(stage, max(STORY_STAGE_THRESHOLDS.keys(), default=0))

def get_story_for_route(route, stage):
    if not route:
        return {
            "title": "故事尚未開始",
            "content": "你尚未選擇路線。請先完成路線選擇，故事將會展開。",
        }
    route_stories = STORY_CONTENT.get(route, {})
    return route_stories.get(stage, route_stories.get(0, {"title": "故事進行中", "content": ""}))

def next_stage_threshold(current_stage):
    next_stage = current_stage + 1
    return STORY_STAGE_THRESHOLDS.get(next_stage)

def get_item_by_id(item_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM items WHERE id = ? AND COALESCE(is_active, 1) = 1",
        (item_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def get_item_by_qr_code_value(qr_code_value):
    if not qr_code_value:
        return None
    clean_value = str(qr_code_value).strip()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM items WHERE qr_code_value = ? AND COALESCE(is_active, 1) = 1",
        (clean_value,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def format_item_effect_text(effect_type, effect_value):
    if not effect_type or effect_type == "mixed":
        return None
    label = ITEM_EFFECT_LABELS.get(effect_type)
    if not label:
        return None
    try:
        value = int(effect_value)
    except (TypeError, ValueError):
        return None
    sign = "+" if value >= 0 else ""
    return f"{sign}{value} {label}"

def serialize_item_for_client(item):
    if not item:
        return None
    has_ability = bool(item.get("has_ability"))
    effect_type = item.get("effect_type")
    effect_value = item.get("effect_value")
    image_path = item.get("image_path") or "/static/images/default-item.svg"
    return {
        "id": item["id"],
        "name": item.get("name"),
        "description": item.get("description"),
        "icon": item.get("icon"),
        "image_path": image_path,
        "item_type": item.get("item_type"),
        "qr_code_value": item.get("qr_code_value"),
        "has_ability": has_ability,
        "effect_type": effect_type,
        "effect_value": effect_value,
        "effect_text": format_item_effect_text(effect_type, effect_value) if has_ability else None,
    }

def apply_item_effect_to_squad(squad_id, item):
    if not item or not item.get("has_ability") or not item.get("effect_type"):
        return None

    effect_type = item.get("effect_type")
    if effect_type == "mixed":
        return None

    stat = ITEM_EFFECT_STAT_MAP.get(effect_type)
    if not stat or stat not in SQUAD_ATTRIBUTES:
        return None

    try:
        delta = int(item.get("effect_value") or 0)
    except (TypeError, ValueError):
        return None
    if delta == 0:
        return None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        f"UPDATE squads SET {stat} = MAX(0, MIN(100, {stat} + ?)) WHERE squad_id = ?",
        (delta, squad_id),
    )
    row = c.execute(
        "SELECT hp, sanity, power, intellect, resilience FROM squads WHERE squad_id = ?",
        (squad_id,),
    ).fetchone()
    conn.commit()
    conn.close()

    if not row:
        return None

    return {
        "effect_type": effect_type,
        "effect_value": delta,
        "effect_text": format_item_effect_text(effect_type, delta),
        "stat": stat,
        "stats": dict(row),
    }

def build_item_qr_payload(item):
    if not item:
        return None
    return json.dumps({
        "type": "item",
        "id": item["id"],
        "qr": item.get("qr_code_value"),
        "v": 1,
    }, ensure_ascii=False)

def resolve_item_from_qr_payload(raw_payload):
    text = (raw_payload or "").strip()
    if not text:
        return None

    if text.startswith("{"):
        try:
            obj = json.loads(text)
            if obj.get("type") == "item":
                if obj.get("qr"):
                    item = get_item_by_qr_code_value(obj["qr"])
                    if item:
                        return item
                if obj.get("id") is not None:
                    return get_item_by_id(int(obj["id"]))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    claim_qr_match = re.search(r"/claim_qr/([^/?#]+)", text, re.I)
    if claim_qr_match:
        item = get_item_by_qr_code_value(claim_qr_match.group(1))
        if item:
            return item

    claim_id_match = re.search(r"/claim_item/(\d+)", text, re.I)
    if claim_id_match:
        return get_item_by_id(int(claim_id_match.group(1)))

    if re.match(r"^item-\d{3}$", text, re.I):
        return get_item_by_qr_code_value(text.lower())

    if text.lower().startswith("oiko-item-"):
        suffix = text.lower().replace("oiko-item-", "", 1)
        if suffix.isdigit():
            return get_item_by_qr_code_value(f"item-{int(suffix):03d}")
        return get_item_by_qr_code_value(text)

    direct = get_item_by_qr_code_value(text)
    if direct:
        return direct

    if text.isdigit():
        return get_item_by_id(int(text))

    return None

def team_has_item(team_id, item_id):
    if not team_id:
        return False
    clean_team_id = normalize_team_id(team_id)
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("""
        SELECT COUNT(*) FROM player_items pi
        JOIN squads s ON pi.squad_id = s.squad_id
        WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?)) AND pi.item_id = ?
    """, (clean_team_id, item_id)).fetchone()[0]
    conn.close()
    return count > 0

def qr_code_already_used(item_id):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT squad_id, team_id, used_at FROM qr_code_uses WHERE item_id = ?",
        (item_id,),
    ).fetchone()
    conn.close()
    return row

def grant_item_to_squad(squad_id, item_id, source="story"):
    squad = get_squad(squad_id)
    if not squad:
        return False, "找不到玩家", None

    item = get_item_by_id(item_id)
    if not item:
        return False, "物品不存在或已停用", None

    is_one_time = item.get("is_one_time_use", 1)
    enforce_qr_once = source == "qr" and is_one_time

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        if enforce_qr_once:
            used = c.execute(
                "SELECT squad_id FROM qr_code_uses WHERE item_id = ?",
                (item_id,),
            ).fetchone()
            if used:
                return False, "此 QR Code 已經被使用", None

        existing = c.execute(
            "SELECT id FROM player_items WHERE squad_id = ? AND item_id = ?",
            (squad_id, item_id),
        ).fetchone()
        if existing:
            return False, "你已經擁有此物品", None

        team_id = squad.get("team_id")
        if team_id:
            clean_team_id = normalize_team_id(team_id)
            team_dup = c.execute("""
                SELECT COUNT(*) FROM player_items pi
                JOIN squads s ON pi.squad_id = s.squad_id
                WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?)) AND pi.item_id = ?
            """, (clean_team_id, item_id)).fetchone()[0]
            if team_dup > 0:
                return False, "同一隊內已經有人擁有此物品", None

        owned_count = c.execute(
            "SELECT COUNT(*) FROM player_items WHERE squad_id = ?",
            (squad_id,),
        ).fetchone()[0]
        if owned_count >= MAX_INVENTORY_SLOTS:
            return False, f"你已經持有 {MAX_INVENTORY_SLOTS} 樣物品，請先丟棄", None

        now = datetime.now().isoformat()
        c.execute(
            "INSERT INTO player_items (squad_id, item_id, source, obtained_at) VALUES (?, ?, ?, ?)",
            (squad_id, item_id, source, now),
        )
        if enforce_qr_once:
            c.execute(
                """INSERT INTO qr_code_uses (item_id, squad_id, team_id, source, used_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    item_id,
                    squad_id,
                    normalize_team_id(team_id) if team_id else None,
                    source,
                    now,
                ),
            )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        return False, "此 QR Code 已經被使用", None
    finally:
        conn.close()

    applied_effect = apply_item_effect_to_squad(squad_id, item)
    return True, f"成功獲得物品：{item['name']}", applied_effect

def hkt_timestamp():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")

def apply_global_effect(effect_type, effect_value=0):
    if not effect_type or effect_type in ("announcement", "global_debuff"):
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if effect_type in ("adjust_sanity", "sanity_adjust"):
        c.execute(
            "UPDATE squads SET sanity = MAX(0, MIN(100, sanity + ?))",
            (effect_value,),
        )
    elif effect_type == "sanity_down":
        c.execute(
            "UPDATE squads SET sanity = MAX(0, MIN(100, sanity - ?))",
            (abs(effect_value),),
        )
    elif effect_type == "sanity_up":
        c.execute(
            "UPDATE squads SET sanity = MAX(0, MIN(100, sanity + ?))",
            (abs(effect_value),),
        )
    elif effect_type == "power_up":
        c.execute(
            "UPDATE squads SET power = MAX(0, MIN(100, power + ?))",
            (abs(effect_value),),
        )
    elif effect_type == "intellect_up":
        c.execute(
            "UPDATE squads SET intellect = MAX(0, MIN(100, intellect + ?))",
            (abs(effect_value),),
        )
    elif effect_type == "resilience_up":
        c.execute(
            "UPDATE squads SET resilience = MAX(0, MIN(100, resilience + ?))",
            (abs(effect_value),),
        )
    elif effect_type == "judas_strengthen":
        c.execute("UPDATE squads SET sanity = MAX(0, sanity - 8)")
    elif effect_type == "iggy_collapse":
        c.execute("UPDATE squads SET sanity = MAX(0, sanity - 12)")
    conn.commit()
    conn.close()

def create_global_event(title, description="", effect_type=None, effect_value=0, created_by="GM"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO global_events
           (title, description, effect_type, effect_value, created_by, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, description, effect_type, effect_value, created_by, hkt_timestamp()),
    )
    conn.commit()
    conn.close()

# ==================== 輔助函數 ====================
def normalize_team_id(team_id):
    if not team_id:
        return None
    return str(team_id).strip().upper()

def build_player_status(squad):
    if not squad:
        return None

    if not squad.get("team_id"):
        return {
            "success": True,
            **squad,
            "team": None,
            "protagonists": {},
            "route": squad.get("route"),
            "is_team_leader": 0,
        }

    team = get_team_by_id(squad["team_id"])
    protagonists = get_team_protagonists(squad["team_id"])
    route = (team or {}).get("route") or squad.get("route")

    return {
        "success": True,
        **squad,
        "route": route,
        "team": team,
        "protagonists": protagonists,
        "is_team_leader": squad.get("is_team_leader", 0),
    }

def row_to_squad(row):
    d = dict(row)
    protagonist = DEFAULT_PROTAGONIST.copy()
    if d.get("protagonist_stats"):
        try:
            protagonist = json.loads(d["protagonist_stats"])
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "squad_id": d["squad_id"],
        "display_name": d.get("display_name") or d["squad_id"],
        "sanity": d.get("sanity", 50),
        "hp": d.get("hp", 100),
        "power": d.get("power", 100),
        "intellect": d.get("intellect", 100),
        "resilience": d.get("resilience", 100),
        "resources": d.get("resources", 0),
        "zoo_skills": json.loads(d["zoo_skills"]) if d.get("zoo_skills") else [],
        "route": d.get("route"),
        "team_id": d.get("team_id"),
        "is_team_leader": 1 if d.get("is_team_leader") else 0,
        "has_pin": bool(d.get("pin")),
        "avatar": d.get("avatar"),
        "insight_fragments": d.get("insight_fragments") or 0,
        "status_effects": parse_status_effects(d.get("status_effects")),
        "trauma_resilience": d.get("trauma_resilience") or 0,
        "trauma_power": d.get("trauma_power") or 0,
        "trauma_intellect": d.get("trauma_intellect") or 0,
        "near_death_until": d.get("near_death_until"),
        "current_combat_id": d.get("current_combat_id"),
        "protagonist": protagonist,
    }

def get_squad(squad_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM squads WHERE squad_id = ?", (squad_id,)).fetchone()
    conn.close()

    if not row:
        return None

    squad = row_to_squad(row)

    if squad.get("team_id"):
        clean_team_id = normalize_team_id(squad["team_id"])
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        team_row = conn.execute(
            "SELECT route, leader_squad_id FROM teams WHERE team_id = ?",
            (clean_team_id,),
        ).fetchone()
        conn.close()

        if team_row:
            if team_row["route"]:
                squad["route"] = team_row["route"]
            if team_row["leader_squad_id"] == squad["squad_id"]:
                squad["is_team_leader"] = 1
            squad["protagonists"] = get_team_protagonists(clean_team_id)

    return squad

def get_team_protagonists(team_id):
    clean_team_id = normalize_team_id(team_id)
    if not clean_team_id:
        return {
            "iggy": DEFAULT_PROTAGONIST.copy(),
            "marah": DEFAULT_PROTAGONIST.copy(),
            "active_route": None,
        }

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    team_row = conn.execute(
        "SELECT route, leader_squad_id FROM teams WHERE team_id = ?", (clean_team_id,)
    ).fetchone()
    if not team_row:
        conn.close()
        return {
            "iggy": DEFAULT_PROTAGONIST.copy(),
            "marah": DEFAULT_PROTAGONIST.copy(),
            "active_route": None,
        }

    route = team_row["route"]
    leader_id = team_row["leader_squad_id"]
    if leader_id:
        squad_row = conn.execute(
            "SELECT protagonist_stats FROM squads WHERE squad_id = ?", (leader_id,)
        ).fetchone()
    else:
        squad_row = conn.execute(
            "SELECT protagonist_stats FROM squads WHERE team_id = ? LIMIT 1", (clean_team_id,)
        ).fetchone()
    conn.close()

    protagonist = DEFAULT_PROTAGONIST.copy()
    if squad_row and squad_row["protagonist_stats"]:
        try:
            protagonist = json.loads(squad_row["protagonist_stats"])
        except (json.JSONDecodeError, TypeError):
            pass

    iggy = DEFAULT_PROTAGONIST.copy()
    marah = DEFAULT_PROTAGONIST.copy()
    if route == "iggy":
        iggy = protagonist
    elif route == "marah":
        marah = protagonist

    return {"iggy": iggy, "marah": marah, "active_route": route}

def get_all_squads():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM squads ORDER BY squad_id").fetchall()
    conn.close()
    return [row_to_squad(r) for r in rows]

def update_squad(squad_id, **kwargs):
    allowed = {
        "sanity", "hp", "power", "intellect", "resilience", "resources", "route",
        "protagonist_stats", "team_id", "is_team_leader", "display_name", "pin",
        "avatar", "insight_fragments", "status_effects",
        "trauma_resilience", "trauma_power", "trauma_intellect",
        "near_death_until", "current_combat_id",
    }
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    updates = []
    params = []
    for key, val in kwargs.items():
        if key not in allowed:
            continue
        if key == "pin" and val is None:
            updates.append("pin = NULL")
        elif val is not None:
            updates.append(f"{key} = ?")
            params.append(val)
    if updates:
        updates.append("last_update = ?")
        params.append(datetime.now().isoformat())
        params.append(squad_id)
        c.execute(f"UPDATE squads SET {', '.join(updates)} WHERE squad_id = ?", params)
        conn.commit()
    conn.close()

def get_next_team_id():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT team_id FROM teams ORDER BY team_id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if not row:
        return "TEAM-01"
    num = int(row[0].split("-")[1]) + 1
    return f"TEAM-{num:02d}"

def get_team_by_id(team_id):
    if not team_id:
        return None

    clean_id = team_id.strip().upper()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM teams WHERE team_id = ?", (clean_id,)
    ).fetchone()

    if not row:
        conn.close()
        return None

    member_count = conn.execute(
        "SELECT COUNT(*) FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))", (clean_id,)
    ).fetchone()[0]
    conn.close()

    return {
        "team_id": row["team_id"],
        "team_name": row["team_name"],
        "route": row["route"],
        "created_at": row["created_at"],
        "member_count": member_count,
    }

def query_teams_list(current_team_id=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM teams ORDER BY created_at DESC").fetchall()

    teams = []
    for row in rows:
        member_count = conn.execute(
            "SELECT COUNT(*) FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))", (row["team_id"],)
        ).fetchone()[0]

        teams.append({
            "team_id": row["team_id"],
            "team_name": row["team_name"],
            "route": row["route"],
            "created_at": row["created_at"],
            "member_count": member_count,
            "is_joined": row["team_id"] == current_team_id,
        })

    conn.close()
    return teams

def get_all_teams_with_stats():
    return query_teams_list()

def build_teams_overview():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    team_rows = conn.execute("SELECT * FROM teams ORDER BY created_at DESC").fetchall()

    teams = []
    for team_row in team_rows:
        team_id = team_row["team_id"]
        clean_id = normalize_team_id(team_id)
        members = conn.execute(
            "SELECT * FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))",
            (clean_id,),
        ).fetchall()

        member_count = len(members)
        stat_fields = ["hp", "sanity", "power", "intellect", "resilience", "resources"]

        def team_avg(field):
            if not members:
                return 0
            return round(sum((m[field] or 0) for m in members) / member_count)

        leader_name = None
        leader_id = team_row["leader_squad_id"]
        if leader_id:
            leader = get_squad(leader_id)
            if leader:
                leader_name = leader.get("display_name") or leader["squad_id"]

        distinct_tasks, task_ids = count_team_distinct_tasks(None, clean_id)
        story_stage = resolve_story_stage(distinct_tasks, task_ids)

        sub_row = conn.execute("""
            SELECT COUNT(*) AS total, MAX(timestamp) AS last_ts
            FROM submissions
            WHERE squad_id IN (
                SELECT squad_id FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))
            )
        """, (clean_id,)).fetchone()

        route = team_row["route"]
        teams.append({
            "team_id": team_id,
            "team_name": team_row["team_name"],
            "route": route,
            "route_label": {"iggy": "🔥 Iggy", "marah": "🌊 Marah"}.get(route, "未選路線"),
            "leader_squad_id": leader_id,
            "leader_name": leader_name or "未設定",
            "member_count": member_count,
            "avg_hp": team_avg("hp"),
            "avg_sanity": team_avg("sanity"),
            "avg_power": team_avg("power"),
            "avg_intellect": team_avg("intellect"),
            "avg_resilience": team_avg("resilience"),
            "avg_resources": team_avg("resources"),
            "distinct_tasks": distinct_tasks,
            "story_stage": story_stage,
            "submission_count": sub_row["total"] if sub_row else 0,
            "last_submission": sub_row["last_ts"] if sub_row else None,
            "members": [
                {
                    "squad_id": m["squad_id"],
                    "display_name": m["display_name"] or m["squad_id"],
                    "hp": m["hp"],
                    "sanity": m["sanity"],
                    "power": m["power"],
                    "intellect": m["intellect"],
                    "resilience": m["resilience"],
                    "is_leader": 1 if leader_id and m["squad_id"] == leader_id else 0,
                }
                for m in members
            ],
        })

    solo_players = []
    unassigned_rows = conn.execute("""
        SELECT * FROM squads
        WHERE team_id IS NULL OR TRIM(team_id) = ''
        ORDER BY COALESCE(display_name, squad_id)
    """).fetchall()
    for row in unassigned_rows:
        distinct_tasks, task_ids = count_team_distinct_tasks(row["squad_id"], None)
        sub_row = conn.execute(
            "SELECT COUNT(*) AS total, MAX(timestamp) AS last_ts FROM submissions WHERE squad_id = ?",
            (row["squad_id"],),
        ).fetchone()
        solo_players.append({
            "squad_id": row["squad_id"],
            "display_name": row["display_name"] or row["squad_id"],
            "route": row["route"],
            "route_label": {"iggy": "🔥 Iggy", "marah": "🌊 Marah"}.get(row["route"], "未選路線"),
            "hp": row["hp"],
            "sanity": row["sanity"],
            "power": row["power"],
            "intellect": row["intellect"],
            "resilience": row["resilience"],
            "resources": row["resources"],
            "distinct_tasks": distinct_tasks,
            "story_stage": resolve_story_stage(distinct_tasks, task_ids),
            "submission_count": sub_row["total"] if sub_row else 0,
            "last_submission": sub_row["last_ts"] if sub_row else None,
        })

    conn.close()
    return {"teams": teams, "solo_players": solo_players}

def build_active_combats_overview():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM combats WHERE status NOT IN ('ended') ORDER BY id DESC"
    ).fetchall()
    conn.close()

    combats = []
    for row in rows:
        combat = row_to_combat(row)
        encounter = load_encounter(combat["encounter_id"])
        squad = get_squad(combat["squad_id"])
        team_id = squad.get("team_id") if squad else None
        team = get_team_by_id(team_id) if team_id else None
        participants = get_combat_participants(combat)
        phase_actions = combat.get("phase_actions") or {}

        combats.append({
            "combat_id": combat["id"],
            "encounter_id": combat["encounter_id"],
            "title": (encounter or {}).get("title", combat["encounter_id"]),
            "status": combat.get("status"),
            "current_phase": combat.get("current_phase", 0),
            "enemy_name": combat.get("enemy_name"),
            "enemy_hp": combat.get("enemy_hp"),
            "enemy_max_hp": combat.get("enemy_max_hp"),
            "team_id": team_id,
            "team_name": (team or {}).get("team_name"),
            "submitted_count": len(phase_actions),
            "participant_count": len(participants),
            "can_resolve": combat.get("status") == "player_phase",
            "phase_deadline": combat.get("phase_deadline"),
        })
    return combats

def get_restore_serializer():
    global _restore_serializer
    if _restore_serializer is None:
        _restore_serializer = URLSafeTimedSerializer(
            app.secret_key, salt="oikonomia-session-restore"
        )
    return _restore_serializer


def make_restore_token(squad_id):
    return get_restore_serializer().dumps({"sid": squad_id})


def verify_restore_token(token):
    if not token:
        return None
    try:
        payload = get_restore_serializer().loads(token, max_age=RESTORE_TOKEN_MAX_AGE)
        return payload.get("sid")
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None


def attach_restore_token(status_dict, squad_id):
    if status_dict and squad_id:
        status_dict["restore_token"] = make_restore_token(squad_id)
    return status_dict


def establish_player_session(squad_id):
    session.permanent = True
    session["squad_id"] = squad_id
    session.modified = True


# ==================== Routes ====================
@app.before_request
def refresh_player_session():
    if "squad_id" in session or session.get("is_gm"):
        session.permanent = True

@app.route("/api/version")
def api_version():
    upload_count = len([
        name for name in os.listdir(UPLOAD_FOLDER)
        if os.path.isfile(os.path.join(UPLOAD_FOLDER, name))
    ]) if os.path.isdir(UPLOAD_FOLDER) else 0
    avatar_count = len(_list_image_files(AVATAR_DIR, exclude=("default.png",)))
    portrait_count = len(_list_image_files(PORTRAIT_DIR, exclude=("default.png",)))
    return jsonify({
        "success": True,
        "version": read_deploy_version(),
        "markers": {
            "iggy_card": "iggy-card",
            "show_only_protagonist": "showOnlyProtagonistCard",
            "combat_system": callable(globals().get("resolve_player_phase")),
            "combat_preview": callable(globals().get("build_combat_round_preview")),
            "combat_modal": "combat-action-modal" in HTML_TEMPLATE,
        },
        "upload_folder": UPLOAD_FOLDER,
        "legacy_upload_folder": LEGACY_UPLOAD_FOLDER,
        "upload_file_count": upload_count,
        "avatar_dir": AVATAR_DIR,
        "avatar_count": avatar_count,
        "portrait_dir": PORTRAIT_DIR,
        "portrait_count": portrait_count,
    })

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/login", methods=["POST"])
def login():
    name = request.form.get("squad_id", "").strip()
    input_pin = request.form.get("pin", "").strip()

    if not name:
        return jsonify({"error": "請輸入名稱"}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        "SELECT * FROM squads WHERE squad_id = ? OR LOWER(TRIM(display_name)) = LOWER(TRIM(?))",
        (name, name),
    ).fetchone()

    if not row:
        internal_id = f"PLAYER-{int(time.time() * 1000) % 100000}"
        while get_squad(internal_id):
            internal_id = f"PLAYER-{(int(time.time() * 1000) + int(time.time() * 1000000) % 9999) % 100000}"
        c = conn.cursor()
        c.execute(
            "INSERT INTO squads (squad_id, display_name) VALUES (?, ?)",
            (internal_id, name),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM squads WHERE squad_id = ?", (internal_id,)).fetchone()

    has_pin = bool(row["pin"])

    if has_pin:
        if not input_pin:
            conn.close()
            return jsonify({
                "success": False,
                "require_pin": True,
                "message": "請輸入 PIN",
            })
        if input_pin != row["pin"]:
            conn.close()
            return jsonify({
                "success": False,
                "error": "PIN 錯誤",
            })

    establish_player_session(row["squad_id"])
    conn.close()

    squad = get_squad(row["squad_id"])
    status = build_player_status(squad)
    status["require_set_pin"] = not has_pin
    attach_restore_token(status, row["squad_id"])
    return jsonify(status)


@app.route("/session/restore", methods=["POST"])
def session_restore():
    """手機 Cookie 遺失時，用 localStorage 內嘅 restore_token 還原登入。"""
    body = request.json if request.is_json else {}
    token = (body.get("restore_token") or request.form.get("restore_token") or "").strip()
    squad_id = verify_restore_token(token)
    if not squad_id:
        return jsonify({"success": False, "error": "無效或已過期的裝置憑證"}), 401

    squad = get_squad(squad_id)
    if not squad:
        return jsonify({"success": False, "error": "帳號不存在"}), 401

    establish_player_session(squad_id)
    status = build_player_status(squad)
    attach_restore_token(status, squad_id)
    return jsonify(status)


@app.route("/set_pin", methods=["POST"])
def set_pin():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    new_pin = request.form.get("pin", "").strip()

    if not new_pin or len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({"success": False, "error": "請輸入 4 位數字 PIN"}), 400

    update_squad(session["squad_id"], pin=new_pin)

    return jsonify({"success": True, "message": "PIN 設定成功"})

@app.route("/my_submissions")
def my_submissions():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT task_id, content, photo_path, timestamp
        FROM submissions
        WHERE squad_id = ?
        ORDER BY timestamp DESC
    """, (session["squad_id"],)).fetchall()
    conn.close()

    submissions = []
    for row in rows:
        submissions.append({
            "task_id": row["task_id"],
            "content": row["content"],
            "photo_path": normalize_photo_url(row["photo_path"]),
            "photo_url": photo_public_url(row["photo_path"]),
            "timestamp": row["timestamp"],
        })

    return jsonify({"submissions": submissions})

@app.route("/team_task_logs")
def team_task_logs():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    team_id = squad.get("team_id") if squad else None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if team_id:
        rows = conn.execute("""
            SELECT
                s.id,
                s.task_id AS task_name,
                s.content AS description,
                s.photo_path,
                s.timestamp,
                sq.display_name,
                sq.squad_id
            FROM submissions s
            JOIN squads sq ON s.squad_id = sq.squad_id
            WHERE sq.team_id = ?
            ORDER BY s.timestamp DESC
        """, (team_id,)).fetchall()
        has_team = True
    else:
        rows = conn.execute("""
            SELECT
                s.id,
                s.task_id AS task_name,
                s.content AS description,
                s.photo_path,
                s.timestamp,
                sq.display_name,
                sq.squad_id
            FROM submissions s
            JOIN squads sq ON s.squad_id = sq.squad_id
            WHERE s.squad_id = ?
            ORDER BY s.timestamp DESC
        """, (session["squad_id"],)).fetchall()
        has_team = False
    conn.close()

    logs = []
    for row in rows:
        entry = dict(row)
        entry["status"] = "已完成"
        entry["display_name"] = entry.get("display_name") or entry.get("squad_id")
        entry["photo_path"] = normalize_photo_url(entry.get("photo_path"))
        entry["photo_url"] = photo_public_url(entry.get("photo_path"))
        logs.append(entry)

    return jsonify({"success": True, "logs": logs, "has_team": has_team})

@app.route("/global_events")
def get_global_events():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, title, description, effect_type, effect_value, created_by, timestamp
        FROM global_events
        ORDER BY timestamp DESC
        LIMIT 30
    """).fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "events": [dict(row) for row in rows],
    })

@app.route("/story_progress")
def story_progress():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"error": "玩家不存在"}), 404

    completed_count, completed_task_ids = count_team_distinct_tasks(
        session["squad_id"], squad.get("team_id")
    )
    stage = resolve_story_stage(completed_count, completed_task_ids)
    route = squad.get("route")
    story = get_story_for_route(route, stage)

    return jsonify({
        "stage": stage,
        "completed_tasks": completed_count,
        "route": route,
        "next_stage_at": next_stage_threshold(stage),
        "stage_thresholds": STORY_STAGE_THRESHOLDS,
        "story": story,
    })

@app.route("/encounters")
def list_encounters_api():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"error": "玩家不存在"}), 404

    team_id = squad.get("team_id")
    route = squad.get("route")
    completed_count, completed_task_ids = count_team_distinct_tasks(
        session["squad_id"], team_id
    )
    stage = resolve_story_stage(completed_count, completed_task_ids)
    if team_id:
        active_session = get_active_combat_for_team(team_id)
    else:
        active_session = get_combat_by_squad(session["squad_id"])

    encounters = []
    for enc in load_all_encounters():
        if not encounter_route_matches(enc.get("route"), route):
            continue
        if enc.get("story_stage", 0) > stage:
            continue
        completed = encounter_already_completed(team_id, enc["encounter_id"]) if team_id else False
        encounters.append({
            "encounter_id": enc["encounter_id"],
            "title": enc.get("title"),
            "description": enc.get("description"),
            "location_hint": enc.get("location_hint"),
            "story_stage": enc.get("story_stage"),
            "trigger_type": enc.get("trigger_type"),
            "completed": completed,
            "enemy_name": (enc.get("enemy") or {}).get("name"),
        })

    return jsonify({
        "success": True,
        "encounters": encounters,
        "active_combat": bool(active_session),
        "active_combat_id": active_session["id"] if active_session else None,
        "active_encounter_id": active_session["encounter_id"] if active_session else None,
    })

@app.route("/encounters/<encounter_id>")
def get_encounter_api(encounter_id):
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    encounter = load_encounter(encounter_id)
    if not encounter:
        return jsonify({"error": "Encounter 不存在"}), 404

    squad = get_squad(session["squad_id"])
    team_id = squad.get("team_id") if squad else None
    return jsonify({
        "success": True,
        "encounter": {
            "encounter_id": encounter["encounter_id"],
            "title": encounter.get("title"),
            "description": encounter.get("description"),
            "location_hint": encounter.get("location_hint"),
            "enemy": encounter.get("enemy"),
            "combat_settings": encounter.get("combat_settings"),
            "reflection_prompt": encounter.get("reflection_prompt"),
            "completed": encounter_already_completed(team_id, encounter_id) if team_id else False,
        },
    })

def _create_combat_record(squad_id, encounter_id, encounter, initial_status="precheck"):
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
    settings = encounter.get("combat_settings", {})
    now = datetime.now().isoformat()
    logs = [{"at": now, "message": f"遭遇戰開始：{encounter.get('title', encounter_id)}"}]
    phase_started = now if initial_status == "player_phase" else None
    phase_deadline = (
        combat_phase_deadline(now, settings.get("phase_time_limit_seconds", 180))
        if initial_status == "player_phase" else None
    )
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
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
    conn.commit()
    conn.close()
    squad = get_squad(squad_id)
    if squad and squad.get("team_id"):
        set_team_combat_id(squad["team_id"], combat_id)
    return get_combat(combat_id)

@app.route("/encounters/<encounter_id>/start", methods=["POST"])
def start_encounter_api(encounter_id):
    """Legacy alias → POST /combat/start"""
    return combat_start_api(encounter_id=encounter_id)

@app.route("/combat/start", methods=["POST"])
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
        combat = _create_combat_record(squad_id, encounter_id, encounter, initial_status=status)

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

@app.route("/combat/status")
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
        payload = {"success": True, "active": False, "winner": winner}
        if winner == "squad":
            payload["outcome"] = "victory"
            payload["narrative"] = (encounter or {}).get("success", {}).get("narrative")
            payload["reflection_prompt"] = (encounter or {}).get("reflection_prompt")
        elif winner == "enemy":
            payload["outcome"] = "defeat"
            payload["narrative"] = (encounter or {}).get("failure", {}).get("narrative")
        return jsonify(payload)

    encounter = load_encounter(combat["encounter_id"])
    settings = (encounter or {}).get("combat_settings", {})

    if combat.get("status") == "player_phase":
        participants = get_combat_participants(combat)
        should_resolve = (
            all_phase_actions_submitted(combat, participants)
            or combat_phase_expired(combat, settings)
        )
        if should_resolve:
            combat, winner = resolve_player_phase(combat["id"])
            if winner == "squad":
                return jsonify({
                    "success": True,
                    "active": False,
                    "outcome": "victory",
                    "winner": "squad",
                    "narrative": (encounter or {}).get("success", {}).get("narrative"),
                    "reflection_prompt": (encounter or {}).get("reflection_prompt"),
                })
            if winner == "enemy":
                return jsonify({
                    "success": True,
                    "active": False,
                    "outcome": "defeat",
                    "winner": "enemy",
                    "narrative": (encounter or {}).get("failure", {}).get("narrative"),
                })

    payload = build_combat_status_response(combat, encounter, session["squad_id"])
    payload["active"] = combat.get("status") not in ("ended", "precheck")
    payload["in_precheck"] = combat.get("status") == "precheck"
    return jsonify(payload)

@app.route("/combat/preview_action", methods=["POST"])
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

    try:
        dice_result = int(body.get("dice_result", body.get("dice", 1)))
    except (TypeError, ValueError):
        dice_result = 1
    dice_result = max(0, min(3, dice_result))

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

    return jsonify({"success": True, "preview": preview})

@app.route("/combat/submit_action", methods=["POST"])
@app.route("/combat/action", methods=["POST"])
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

    try:
        dice_result = int(body.get("dice_result", body.get("dice", 2)))
    except (TypeError, ValueError):
        dice_result = 2
    dice_result = max(0, min(3, dice_result))

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

    if squad.get("near_death_until"):
        try:
            if datetime.now() < datetime.fromisoformat(squad["near_death_until"]):
                return jsonify({"success": False, "error": "你已陷入瀕死，等待隊友救援"}), 400
        except ValueError:
            pass

    encounter = load_encounter(combat["encounter_id"])
    settings = (encounter or {}).get("combat_settings", {})
    if action_type == "use_zoo" and not settings.get("allow_zoo", True):
        return jsonify({"success": False, "error": "此戰鬥不允許 Zoo 能力"}), 400

    phase_actions = dict(combat.get("phase_actions") or {})
    if session["squad_id"] in phase_actions:
        return jsonify({"success": False, "error": "你已提交本回合行動"}), 400

    phase_actions[session["squad_id"]] = {
        "action_type": action_type,
        "dice_result": dice_result,
        "item_id": item_id,
    }
    save_combat(combat_id, phase_actions=phase_actions)
    combat["phase_actions"] = phase_actions

    participants = get_combat_participants(combat)
    winner = None
    if all_phase_actions_submitted(combat, participants) or combat_phase_expired(combat, settings):
        combat, winner = resolve_player_phase(combat_id)

    if winner == "squad":
        return jsonify({
            "success": True,
            "outcome": "victory",
            "winner": "squad",
            "narrative": (encounter or {}).get("success", {}).get("narrative"),
            "reflection_prompt": (encounter or {}).get("reflection_prompt"),
        })
    if winner == "enemy":
        return jsonify({
            "success": True,
            "outcome": "defeat",
            "winner": "enemy",
            "narrative": (encounter or {}).get("failure", {}).get("narrative"),
        })

    combat = get_combat(combat_id)
    payload = build_combat_status_response(combat, encounter, session["squad_id"])
    payload["active"] = True
    payload["message"] = f"已提交行動：{action_type}（骰 {dice_result}）"
    return jsonify(payload)

@app.route("/combat/resolve_phase", methods=["POST"])
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

@app.route("/combat/rescue_near_death", methods=["POST"])
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

@app.route("/status")
def get_status():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if not squad:
        session.clear()
        return jsonify({"success": False, "error": "未登入"}), 401

    status = build_player_status(squad)
    attach_restore_token(status, session["squad_id"])
    return jsonify(status)

@app.route("/team")
def get_team():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401
    return jsonify({"members": get_all_squads()})

@app.route("/my_team")
def my_team():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401
    squad = get_squad(session["squad_id"])
    if not squad or not squad.get("team_id"):
        return jsonify({
            "has_team": False,
            "route": squad.get("route") if squad else None,
        })
    clean_team_id = normalize_team_id(squad["team_id"])
    team = get_team_by_id(clean_team_id)
    if not team:
        return jsonify({
            "has_team": False,
            "route": squad.get("route"),
        })
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM squads
        WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))
        ORDER BY is_team_leader DESC, COALESCE(display_name, squad_id), squad_id
    """, (clean_team_id,)).fetchall()
    conn.close()
    members = []
    for row in rows:
        member = get_squad(row["squad_id"])
        if member:
            member["is_leader"] = member.get("is_team_leader") == 1
            members.append(member)
    protagonists = get_team_protagonists(squad["team_id"])
    return jsonify({
        "success": True,
        "has_team": True,
        "team": team,
        "route": team.get("route"),
        "members": members,
        "is_team_leader": squad.get("is_team_leader", 0),
        "current_squad_id": session["squad_id"],
        "protagonists": protagonists,
    })

@app.route("/available_teams")
def available_teams():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    current_team_id = squad.get("team_id") if squad else None
    has_team = bool(current_team_id and str(current_team_id).strip())
    clean_current_id = normalize_team_id(current_team_id) if has_team else None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM teams ORDER BY created_at DESC").fetchall()

    teams = []
    for row in rows:
        member_count = conn.execute(
            "SELECT COUNT(*) FROM squads WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))", (row["team_id"],)
        ).fetchone()[0]

        is_joined = bool(
            clean_current_id
            and normalize_team_id(row["team_id"]) == clean_current_id
        )

        teams.append({
            "team_id": row["team_id"],
            "team_name": row["team_name"],
            "route": row["route"],
            "member_count": member_count,
            "is_joined": is_joined,
        })

    conn.close()
    return jsonify({
        "success": True,
        "has_team": has_team,
        "current_team_id": clean_current_id,
        "teams": teams,
    })

@app.route("/team/join", methods=["POST"])
def join_team():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    team_id = request.form.get("team_id", "").strip()
    if not team_id:
        return jsonify({"success": False, "error": "請輸入 Team Code"}), 400

    team = get_team_by_id(team_id)
    if not team:
        print(f"[DEBUG] Join failed - team_id input: '{team_id}' not found in DB")
        return jsonify({"success": False, "error": "Team 不存在"}), 400

    squad = get_squad(session["squad_id"])
    if squad.get("team_id"):
        return jsonify({"success": False, "error": "你已加入 Team，無法重複加入"}), 400

    update_squad(session["squad_id"], team_id=normalize_team_id(team["team_id"]), is_team_leader=0)
    return jsonify({"success": True, "team": team})

@app.route("/team/create", methods=["POST"])
def create_player_team():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if squad.get("team_id"):
        return jsonify({"success": False, "error": "你已加入 Team，請先離開現有隊伍"}), 400

    team_name = request.form.get("team_name", "").strip() or "新小隊"
    team_id = get_next_team_id()
    created_at = datetime.now().isoformat()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO teams (team_id, team_name, route, created_at, leader_squad_id) VALUES (?, ?, ?, ?, ?)",
        (team_id, team_name, None, created_at, session["squad_id"]),
    )
    conn.commit()
    conn.close()

    update_squad(session["squad_id"], team_id=team_id, is_team_leader=1)
    return jsonify({"success": True, "team_id": team_id, "team_name": team_name})

@app.route("/team/update_name", methods=["POST"])
def team_update_name():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    new_name = request.form.get("team_name", "").strip()
    if not new_name:
        return jsonify({"success": False, "error": "隊名不能為空"}), 400
    if len(new_name) > 30:
        return jsonify({"success": False, "error": "隊名最長 30 個字"}), 400

    squad = get_squad(session["squad_id"])
    if not squad or squad.get("is_team_leader") != 1:
        return jsonify({"success": False, "error": "只有隊長可以改隊名"}), 403

    team_id = squad.get("team_id")
    if not team_id:
        return jsonify({"success": False, "error": "你未有隊伍"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE teams SET team_name = ? WHERE team_id = ?", (new_name, team_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "team_name": new_name})

@app.route("/team/transfer_leadership", methods=["POST"])
def transfer_leadership():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    data = request.get_json(silent=True) or {}
    target_squad_id = (data.get("target_squad_id") or "").strip()
    if not target_squad_id:
        return jsonify({"success": False, "error": "請選擇目標隊員"}), 400

    if target_squad_id == session["squad_id"]:
        return jsonify({"success": False, "error": "不能轉讓畀自己"}), 400

    current_squad = get_squad(session["squad_id"])
    if not current_squad or current_squad.get("is_team_leader") != 1:
        return jsonify({"success": False, "error": "只有隊長可以轉讓"}), 403

    team_id = normalize_team_id(current_squad.get("team_id"))
    if not team_id:
        return jsonify({"success": False, "error": "你未有隊伍"}), 400

    target_squad = get_squad(target_squad_id)
    if not target_squad:
        return jsonify({"success": False, "error": "找不到目標隊員"}), 404

    if normalize_team_id(target_squad.get("team_id")) != team_id:
        return jsonify({"success": False, "error": "目標隊員唔係同一個隊"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE squads SET is_team_leader = 0 WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))",
        (team_id,),
    )
    c.execute("UPDATE squads SET is_team_leader = 1 WHERE squad_id = ?", (target_squad_id,))
    c.execute("UPDATE teams SET leader_squad_id = ? WHERE team_id = ?", (target_squad_id, team_id))
    conn.commit()
    conn.close()

    updated = get_squad(session["squad_id"])
    return jsonify({
        "success": True,
        "message": "隊長已成功轉讓",
        "is_team_leader": updated.get("is_team_leader", 0),
    })

@app.route("/set_team_route_by_leader", methods=["POST"])
def set_team_route_by_leader():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad = get_squad(session["squad_id"])
    if not squad or squad.get("is_team_leader") != 1:
        return jsonify({"success": False, "error": "只有隊長可以設定路線"}), 403

    route = request.form.get("route", "").lower()
    if route not in ("iggy", "marah"):
        return jsonify({"success": False, "error": "無效路線"}), 400

    team_id = normalize_team_id(squad.get("team_id"))
    if not team_id:
        return jsonify({"success": False, "error": "你未加入任何 Team"}), 400

    team = get_team_by_id(team_id)
    if team and team.get("route"):
        return jsonify({"success": False, "error": "Team 已設定路線，無法更改"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE teams SET route = ? WHERE team_id = ?", (route, team_id))
    conn.commit()
    conn.close()

    updated = get_squad(session["squad_id"])
    status = build_player_status(updated)
    status["squad"] = updated
    return jsonify(status)

@app.route("/set_route", methods=["POST"])
def set_route():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    route = request.form.get("route", "").lower()
    if route not in ("iggy", "marah"):
        return jsonify({"error": "請選擇 Iggy 或 Marah 路線"}), 400

    squad = get_squad(session["squad_id"])
    if squad.get("route"):
        return jsonify({"error": "你已選擇路線，無法更改"}), 400

    update_squad(session["squad_id"], route=route)
    return jsonify(build_player_status(get_squad(session["squad_id"])))

@app.route("/locations")
def get_locations():
    return jsonify(LOCATIONS)

@app.route("/verify_gps", methods=["POST"])
def verify_gps():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    data = request.get_json()
    loc_id = data.get("loc_id")
    lat = float(data.get("lat"))
    lng = float(data.get("lng"))

    if loc_id not in LOCATIONS:
        return jsonify({"error": "無效地點"}), 400

    loc = LOCATIONS[loc_id]
    distance = math.sqrt((lat - loc["lat"])**2 + (lng - loc["lng"])**2) * 111000

    if distance <= loc["radius"]:
        return jsonify({
            "success": True,
            "message": "位置正確！",
            "task_type": loc["task_type"],
            "loc_name": loc["name"]
        })
    else:
        return jsonify({
            "success": False,
            "message": f"距離太遠（相差約 {int(distance)} 米）"
        })

@app.route("/submit_task", methods=["POST"])
def submit_task():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

    task_id = request.form.get("task_id", "unknown")
    content = request.form.get("content", "")

    squad = get_squad(session["squad_id"])
    team_id = squad.get("team_id")

    if not team_id:
        return jsonify({"error": "你未加入任何 Team，無法提交任務"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id FROM submissions
        WHERE task_id = ? AND squad_id IN (
            SELECT squad_id FROM squads WHERE team_id = ?
        )
    """, (task_id, team_id))
    already_submitted = c.fetchone()

    photo_path = None
    if "photo" in request.files:
        photo = request.files["photo"]
        if photo.filename:
            filename = f"{session['squad_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            photo.save(os.path.join(UPLOAD_FOLDER, filename))
            photo_path = f"uploads/{filename}"

    c.execute("""INSERT INTO submissions (squad_id, task_id, content, photo_path, timestamp)
                 VALUES (?, ?, ?, ?, ?)""",
              (session["squad_id"], task_id, content, photo_path, datetime.now().isoformat()))
    conn.commit()

    if not already_submitted:
        new_sanity = min(100, squad["sanity"] + 6)
        new_resources = squad["resources"] + 1
        update_squad(session["squad_id"], sanity=new_sanity, resources=new_resources)
        conn.close()
        return jsonify({
            "success": True,
            "message": "任務提交成功！+6 神智 +1 Resource（第一次提交）"
        })
    else:
        conn.close()
        return jsonify({
            "success": True,
            "message": "提交已記錄，但呢個任務已經計過分（只計一次）"
        })

@app.route("/update_display_name", methods=["POST"])
def update_display_name():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    new_name = request.form.get("display_name", "").strip()
    if not new_name:
        return jsonify({"success": False, "error": "名稱不能為空"}), 400
    if len(new_name) > 20:
        return jsonify({"success": False, "error": "名稱最長 20 個字"}), 400

    update_squad(session["squad_id"], display_name=new_name)
    return jsonify({"success": True, "display_name": new_name})

@app.route("/available_avatars")
def available_avatars():
    files = _list_image_files(AVATAR_DIR, exclude=("default.png",))
    return jsonify({"avatars": files, "avatar_dir": AVATAR_DIR})

@app.route("/available_portraits")
def available_portraits():
    files = _list_image_files(PORTRAIT_DIR, exclude=("default.png",))
    return jsonify({"portraits": files, "portrait_dir": PORTRAIT_DIR})

@app.route("/set_avatar", methods=["POST"])
def set_avatar():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    avatar_filename = os.path.basename(request.form.get("avatar", "").strip())
    if not avatar_filename:
        return jsonify({"success": False, "error": "請選擇頭像"}), 400

    avatar_path = os.path.join(AVATAR_DIR, avatar_filename)
    if not os.path.exists(avatar_path):
        return jsonify({"success": False, "error": "頭像不存在"}), 400

    update_squad(session["squad_id"], avatar=avatar_filename)
    return jsonify({"success": True, "avatar": avatar_filename})

@app.route("/my_items")
def my_items():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    squad_id = session["squad_id"]
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT pi.id, pi.item_id, i.name, i.description, i.icon, i.item_type,
               i.image_path, i.has_ability, i.effect_type, i.effect_value,
               pi.source, pi.obtained_at
        FROM player_items pi
        JOIN items i ON pi.item_id = i.id
        WHERE pi.squad_id = ?
        ORDER BY pi.obtained_at DESC
    """, (squad_id,)).fetchall()
    conn.close()

    items = []
    for row in rows:
        item = dict(row)
        item["has_ability"] = bool(item.get("has_ability"))
        item["image_path"] = item.get("image_path") or "/static/images/default-item.svg"
        item["effect_text"] = (
            format_item_effect_text(item.get("effect_type"), item.get("effect_value"))
            if item.get("has_ability") else None
        )
        items.append(item)
    return jsonify({
        "success": True,
        "items": items,
        "max_slots": MAX_INVENTORY_SLOTS,
        "current_count": len(items),
    })

@app.route("/add_item", methods=["POST"])
def add_item():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    data = request.get_json(silent=True) or {}
    source = (data.get("source") or "story").strip().lower() or "story"
    item = None

    if source == "qr":
        qr_payload = data.get("qr_payload") or data.get("qr_code_value") or ""
        if not str(qr_payload).strip():
            return jsonify({"success": False, "error": "無效的 QR Code"}), 400
        item = resolve_item_from_qr_payload(qr_payload)
        if not item:
            return jsonify({"success": False, "error": "QR Code 無效或物品已停用"}), 400
        item_id = item["id"]
    else:
        try:
            item_id = int(data.get("item_id"))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "無效物品 ID"}), 400
        item = get_item_by_id(item_id)
        if not item:
            return jsonify({"success": False, "error": "物品不存在或已停用"}), 400

    success, message, applied_effect = grant_item_to_squad(session["squad_id"], item_id, source)
    if not success:
        return jsonify({"success": False, "error": message}), 400

    response = {
        "success": True,
        "message": message,
        "item": serialize_item_for_client(item),
        "item_id": item_id,
        "item_name": item.get("name"),
        "qr_code_value": item.get("qr_code_value"),
    }
    if applied_effect:
        response["applied_effect"] = applied_effect
    return jsonify(response)

@app.route("/discard_item", methods=["POST"])
def discard_item():
    if "squad_id" not in session:
        return jsonify({"success": False, "error": "未登入"}), 401

    data = request.get_json(silent=True) or {}
    player_item_id = data.get("player_item_id")
    try:
        player_item_id = int(player_item_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "無效物品記錄"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "DELETE FROM player_items WHERE id = ? AND squad_id = ?",
        (player_item_id, session["squad_id"]),
    )
    deleted = c.rowcount
    conn.commit()
    conn.close()

    if deleted == 0:
        return jsonify({"success": False, "error": "找不到物品或無權限丟棄"}), 404

    return jsonify({"success": True, "message": "物品已丟棄"})

@app.route("/claim_item/<int:item_id>")
def claim_item_page(item_id):
    if "squad_id" not in session:
        return redirect(f"/?next=/claim_item/{item_id}")

    item = get_item_by_id(item_id)
    if not item:
        return "找不到此物品", 404

    return render_template_string(
        CLAIM_ITEM_HTML,
        item=item,
        qr_payload=build_item_qr_payload(item),
    )

@app.route("/claim_qr/<path:qr_value>")
def claim_qr_page(qr_value):
    if "squad_id" not in session:
        return redirect(f"/?next=/claim_qr/{qr_value}")

    item = get_item_by_qr_code_value(qr_value)
    if not item:
        return "找不到此物品", 404

    return render_template_string(
        CLAIM_ITEM_HTML,
        item=item,
        qr_payload=build_item_qr_payload(item),
    )

# ==================== GM Routes ====================

GM_PIN = "gm2026"  # GM 登入 PIN，你可以之後改

@app.route("/gm")
def gm_login_page():
    return render_template_string(GM_LOGIN_HTML)

@app.route("/gm/login", methods=["POST"])
def gm_login():
    pin = request.form.get("pin", "")
    if pin == GM_PIN:
        session.permanent = True
        session["is_gm"] = True
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "PIN 錯誤"})

@app.route("/gm/dashboard")
def gm_dashboard():
    if not session.get("is_gm"):
        return redirect("/gm")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    squad_list = []
    for s in get_all_squads():
        c.execute("SELECT COUNT(*) FROM submissions WHERE squad_id = ?", (s["squad_id"],))
        submission_count = c.fetchone()[0]
        squad_list.append({
            **s,
            "zoo_count": len(s["zoo_skills"]),
            "submission_count": submission_count,
            "route_label": {"iggy": "Iggy", "marah": "Marah"}.get(s.get("route"), "未選"),
        })
    
    last_update = datetime.now().strftime("%H:%M:%S")
    conn.close()
    
    return render_template_string(GM_DASHBOARD_HTML, squads=squad_list, last_update=last_update)

@app.route("/gm/squad/<squad_id>")
def gm_squad_detail(squad_id):
    if not session.get("is_gm"):
        return redirect("/gm")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    squad = get_squad(squad_id)
    if not squad:
        conn.close()
        return "找不到該小隊", 404
    squad["zoo_count"] = len(squad["zoo_skills"])
    squad["route_label"] = {"iggy": "Iggy 路線", "marah": "Marah 路線"}.get(squad.get("route"), "未選路線")
    
    # 取得提交記錄
    c.execute("""SELECT task_id, content, photo_path, timestamp 
                 FROM submissions 
                 WHERE squad_id = ? 
                 ORDER BY timestamp DESC""", (squad_id,))
    submissions_raw = c.fetchall()
    conn.close()
    
    submissions = []
    for sub in submissions_raw:
        submissions.append({
            "task_id": sub[0],
            "content": sub[1],
            "photo_path": normalize_photo_url(sub[2]),
            "photo_url": photo_public_url(sub[2]),
            "timestamp": sub[3]
        })
    
    return render_template_string(GM_SQUAD_DETAIL_HTML, squad=squad, submissions=submissions)

@app.route("/gm/adjust", methods=["POST"])
def gm_adjust():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未登入"}), 403

    squad_id = request.form.get("squad_id")
    field = request.form.get("field")          # hp, sanity, resources
    value = int(request.form.get("value", 0))

    if field not in ["hp", "sanity", "power", "intellect", "resilience", "resources"]:
        return jsonify({"success": False, "error": "無效欄位"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f"UPDATE squads SET {field} = ? WHERE squad_id = ?", (value, squad_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route("/gm/reset_pin", methods=["POST"])
def gm_reset_pin():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未登入 GM"}), 403

    squad_id = request.form.get("squad_id", "").strip()
    new_pin = request.form.get("new_pin", "").strip()

    if not squad_id:
        return jsonify({"success": False, "error": "請提供 Player ID"}), 400

    if not get_squad(squad_id):
        return jsonify({"success": False, "error": "玩家不存在"}), 404

    if not new_pin:
        new_pin = str(random.randint(1000, 9999))

    if len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({"success": False, "error": "PIN 必須係 4 位數字"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE squads SET pin = ? WHERE squad_id = ?", (new_pin, squad_id))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"已重置 {squad_id} 的 PIN",
        "new_pin": new_pin,
    })

@app.route("/gm/global_event", methods=["POST"])
def gm_global_event():
    if not session.get("is_gm"):
        return jsonify({"success": False}), 403

    event_type = request.form.get("event_type")
    value = int(request.form.get("value", 0))

    if event_type == "adjust_sanity":
        title = f"全營 Sanity {'+' if value > 0 else ''}{value}"
        description = f"GM 調整全營 Sanity {'+' if value > 0 else ''}{value}"
        effect_type = "adjust_sanity"
        effect_value = value
    elif event_type == "judas_strengthen":
        title = "Judas 加強"
        description = "Judas 加強！全營 Sanity -8"
        effect_type = "judas_strengthen"
        effect_value = -8
    elif event_type == "iggy_collapse":
        title = "Iggy 崩潰"
        description = "Iggy 開始崩潰！全營 Sanity -12"
        effect_type = "iggy_collapse"
        effect_value = -12
    else:
        return jsonify({"success": False, "error": "未知事件類型"})

    apply_global_effect(effect_type, effect_value)
    create_global_event(title, description, effect_type, effect_value, "GM")
    return jsonify({"success": True, "message": description})

@app.route("/gm/create_global_event", methods=["POST"])
def gm_create_global_event():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    data = request.get_json(silent=True) or request.form
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"success": False, "error": "標題不能為空"}), 400

    description = (data.get("description") or "").strip()
    effect_type = (data.get("effect_type") or "").strip() or None
    effect_value = int(data.get("effect_value", 0) or 0)

    apply_global_effect(effect_type, effect_value)
    create_global_event(title, description, effect_type, effect_value, "GM")
    return jsonify({"success": True, "message": "全球事件已建立"})

RESET_PASSWORD = "reset2026"  # 重置遊戲專用密碼

@app.route("/gm/reset_game", methods=["POST"])
def gm_reset_game():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未登入"}), 403

    password = request.form.get("password", "")
    if password != RESET_PASSWORD:
        return jsonify({"success": False, "error": "密碼錯誤"})

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. 清空提交記錄
    c.execute("DELETE FROM submissions")

    # 1b. 清空玩家物品
    c.execute("DELETE FROM player_items")

    # 1c. 清空 QR Code 使用記錄
    c.execute("DELETE FROM qr_code_uses")

    # 2. 清空所有 Team
    c.execute("DELETE FROM teams")

    # 3. 刪除所有玩家記錄（Squad = 獨立玩家ID）
    c.execute("DELETE FROM squads")

    # 4. 清空全球事件記錄
    c.execute("DELETE FROM global_events")

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "遊戲已完全重置（所有玩家ID、Team、提交記錄已清空）",
    })

@app.route("/gm/clear_all_images", methods=["POST"])
def gm_clear_all_images():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未登入"}), 403

    data = request.get_json(silent=True) or {}
    confirm = data.get("confirm", "")
    if confirm != "CLEAR_IMAGES":
        return jsonify({"success": False, "error": "確認碼錯誤"}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, photo_path FROM submissions
        WHERE photo_path IS NOT NULL AND TRIM(photo_path) != ''
    """)
    submissions = c.fetchall()

    deleted_count = 0
    cleared_count = 0
    for row in submissions:
        photo_path = row["photo_path"]
        disk_path = resolve_upload_disk_path(photo_path)
        if disk_path and os.path.isfile(disk_path):
            try:
                os.remove(disk_path)
                deleted_count += 1
            except OSError as e:
                print(f"刪除圖片失敗: {disk_path}, {e}")

        c.execute("UPDATE submissions SET photo_path = NULL WHERE id = ?", (row["id"],))
        cleared_count += 1

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"已成功刪除 {deleted_count} 張圖片（清空 {cleared_count} 筆提交記錄中的圖片欄位）",
        "deleted_files": deleted_count,
        "cleared_records": cleared_count,
    })

@app.route("/gm/teams_overview")
def gm_teams_overview():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    overview = build_teams_overview()
    return jsonify({"success": True, **overview})

@app.route("/gm/active_combats")
def gm_active_combats():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    return jsonify({"success": True, "combats": build_active_combats_overview()})

@app.route("/gm/combat/resolve_phase", methods=["POST"])
def gm_combat_resolve_phase():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    body = request.json if request.is_json else request.form
    combat_id = body.get("combat_id")
    if not combat_id:
        return jsonify({"success": False, "error": "缺少 combat_id"}), 400

    combat = get_combat(int(combat_id))
    if not combat:
        return jsonify({"success": False, "error": "戰鬥不存在"}), 404
    if combat.get("status") != "player_phase":
        return jsonify({
            "success": False,
            "error": f"目前狀態為 {combat.get('status')}，只能強制結算 player_phase",
        }), 400

    combat, winner = resolve_player_phase(int(combat_id))
    encounter = load_encounter(combat["encounter_id"]) if combat else None

    if winner == "squad":
        return jsonify({
            "success": True,
            "outcome": "victory",
            "winner": "squad",
            "combat_id": int(combat_id),
            "narrative": (encounter or {}).get("success", {}).get("narrative"),
        })
    if winner == "enemy":
        return jsonify({
            "success": True,
            "outcome": "defeat",
            "winner": "enemy",
            "combat_id": int(combat_id),
            "narrative": (encounter or {}).get("failure", {}).get("narrative"),
        })

    return jsonify({
        "success": True,
        "combat_id": int(combat_id),
        "status": combat.get("status") if combat else None,
        "current_phase": combat.get("current_phase") if combat else None,
        "enemy_hp": combat.get("enemy_hp") if combat else None,
        "message": "Phase 已強制結算，戰鬥繼續",
    })

@app.route("/gm/download_team_images/<team_id>")
def gm_download_team_images(team_id):
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    clean_id = normalize_team_id(team_id)
    team = get_team_by_id(clean_id)
    if not team:
        return jsonify({"success": False, "error": "找不到該隊伍"}), 404

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT s.id, s.photo_path, s.task_id, sq.display_name, sq.squad_id
        FROM submissions s
        JOIN squads sq ON s.squad_id = sq.squad_id
        WHERE UPPER(TRIM(sq.team_id)) = UPPER(TRIM(?))
          AND s.photo_path IS NOT NULL AND TRIM(s.photo_path) != ''
        ORDER BY s.timestamp
    """, (clean_id,)).fetchall()
    conn.close()

    if not rows:
        return jsonify({"success": False, "error": "該隊伍冇上傳過圖片"}), 404

    memory_file = io.BytesIO()
    added = 0
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            disk_path = resolve_upload_disk_path(row["photo_path"])
            if not disk_path or not os.path.isfile(disk_path):
                continue
            display_name = row["display_name"] or row["squad_id"]
            task_name = task_display_name(row["task_id"])
            filename = os.path.basename(disk_path)
            arcname = safe_zip_arcname(display_name, task_name, row["id"], filename)
            zf.write(disk_path, arcname=arcname)
            added += 1

    if added == 0:
        return jsonify({"success": False, "error": "圖片檔案已不存在於伺服器"}), 404

    memory_file.seek(0)
    zip_name = safe_zip_arcname(team.get("team_name") or clean_id, "images") + ".zip"
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_name,
    )

@app.route("/gm/player_logs/<squad_id>")
def gm_player_logs(squad_id):
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    squad = get_squad(squad_id)
    if not squad:
        return jsonify({"success": False, "error": "找不到玩家"}), 404

    team_info = get_team_by_id(squad.get("team_id")) if squad.get("team_id") else None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT s.id, s.task_id, s.content, s.photo_path, s.timestamp,
               sq.display_name, sq.squad_id, sq.team_id,
               t.team_name
        FROM submissions s
        JOIN squads sq ON s.squad_id = sq.squad_id
        LEFT JOIN teams t ON UPPER(TRIM(t.team_id)) = UPPER(TRIM(sq.team_id))
        WHERE s.squad_id = ?
        ORDER BY s.timestamp DESC
    """, (squad_id,)).fetchall()
    conn.close()

    logs = []
    for row in rows:
        task_id = row["task_id"]
        logs.append({
            "id": row["id"],
            "task_id": task_id,
            "task_name": task_display_name(task_id),
            "description": row["content"],
            "photo_path": normalize_photo_url(row["photo_path"]),
            "photo_url": photo_public_url(row["photo_path"]),
            "timestamp": row["timestamp"],
            "status": "已完成",
            "display_name": row["display_name"] or row["squad_id"],
            "team_name": row["team_name"],
        })

    return jsonify({
        "success": True,
        "player": {
            "squad_id": squad_id,
            "display_name": squad.get("display_name") or squad_id,
            "team_id": squad.get("team_id"),
            "team_name": team_info["team_name"] if team_info else None,
        },
        "logs": logs,
    })

# 公告歷史記錄（每條包含訊息 + 時間）
ANNOUNCEMENTS = []   # 格式: [{"message": "...", "timestamp": "..."}]

@app.route("/gm/announcement", methods=["POST"])
def gm_send_announcement():
    if not session.get("is_gm"):
        return jsonify({"success": False}), 403

    message = request.form.get("message", "").strip()
    if not message:
        return jsonify({"success": False, "error": "訊息不能為空"})

    timestamp = hkt_timestamp()

    ANNOUNCEMENTS.append({
        "message": message,
        "timestamp": timestamp
    })
    create_global_event("公告", message, "announcement", 0, "GM")

    return jsonify({"success": True, "message": "公告已發送"})

@app.route("/gm/teams")
def gm_teams():
    if not session.get("is_gm"):
        return jsonify({"error": "未授權"}), 403
    return jsonify({"teams": get_all_teams_with_stats()})

@app.route("/gm/team_members/<team_id>")
def gm_team_members(team_id):
    if not session.get("is_gm"):
        return jsonify({"error": "未授權"}), 403

    team = get_team_by_id(team_id)
    if not team:
        return jsonify({"error": "Team 不存在"}), 404

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM squads WHERE team_id = ? ORDER BY display_name, squad_id",
        (team_id,),
    ).fetchall()
    conn.close()

    members = [get_squad(row["squad_id"]) for row in rows]
    return jsonify({"team": team, "members": members})

@app.route("/gm/assignable_players")
def gm_assignable_players():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權", "players": []}), 403

    target_team_id = normalize_team_id(request.args.get("team_id", ""))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT squad_id, display_name, team_id
        FROM squads
        ORDER BY COALESCE(display_name, squad_id), squad_id
    """).fetchall()
    conn.close()

    players = []
    for row in rows:
        current_team_id = normalize_team_id(row["team_id"]) if row["team_id"] else None
        on_target_team = bool(target_team_id and current_team_id == target_team_id)

        label = row["display_name"] or row["squad_id"]
        if current_team_id:
            team_info = get_team_by_id(current_team_id)
            team_label = team_info["team_name"] if team_info else current_team_id
            label += f"（現於 {team_label}）"
        else:
            label += "（未入隊）"
        if on_target_team:
            label += "（已在目標隊）"

        players.append({
            "squad_id": row["squad_id"],
            "display_name": row["display_name"] or row["squad_id"],
            "current_team_id": current_team_id,
            "label": label,
            "on_target_team": on_target_team,
            "eligible": not on_target_team,
        })

    eligible = [player for player in players if player["eligible"]]
    return jsonify({
        "success": True,
        "players": eligible,
        "all_players": players,
        "count": len(eligible),
    })

@app.route("/gm/create_team", methods=["POST"])
def gm_create_team():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    team_name = request.form.get("team_name", "").strip() or "新小隊"
    team_id = get_next_team_id()
    created_at = datetime.now().isoformat()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO teams (team_id, team_name, route, created_at, leader_squad_id) VALUES (?, ?, ?, ?, ?)",
        (team_id, team_name, None, created_at, None),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "team_id": team_id, "team_name": team_name})

@app.route("/gm/assign_squad", methods=["POST"])
def gm_assign_squad():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    squad_id = request.form.get("squad_id", "").strip()
    new_team_id = request.form.get("team_id", "").strip().upper()

    if not squad_id:
        return jsonify({"success": False, "error": "請選擇玩家"}), 400

    squad = get_squad(squad_id)
    if not squad:
        if not squad_id.upper().startswith("FRAG-"):
            squad_id = squad_id.upper().replace(" ", "_")[:15]
        else:
            squad_id = squad_id.upper()
        squad = get_squad(squad_id)
    if not squad:
        return jsonify({"success": False, "error": "玩家不存在"}), 400

    new_team = get_team_by_id(new_team_id)
    if not new_team:
        return jsonify({"success": False, "error": "目標 Team 不存在"}), 400

    old_team_id = squad.get("team_id")
    old_team_name = None
    if old_team_id:
        old_team = get_team_by_id(old_team_id)
        if old_team:
            old_team_name = old_team["team_name"]

    is_leader = 0
    update_squad(squad_id, team_id=normalize_team_id(new_team_id), is_team_leader=is_leader)

    label = squad.get("display_name") or squad_id
    message = f"已將 {label} 分配到 {new_team['team_name']}"
    if old_team_name:
        message = f"已將 {label} 從「{old_team_name}」轉到「{new_team['team_name']}」"

    return jsonify({
        "success": True,
        "message": message,
        "old_team": old_team_name,
        "new_team": new_team["team_name"],
    })

@app.route("/gm/set_team_route", methods=["POST"])
def gm_set_team_route():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未授權"}), 403

    team_id = request.form.get("team_id", "").strip().upper()
    route = request.form.get("route", "").strip().lower()

    if route not in ("iggy", "marah"):
        return jsonify({"success": False, "error": "路線必須是 iggy 或 marah"}), 400
    if not get_team_by_id(team_id):
        return jsonify({"success": False, "error": "Team 不存在"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE teams SET route = ? WHERE team_id = ?", (route, team_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/gm/update_team_name", methods=["POST"])
def gm_update_team_name():
    if not session.get("is_gm"):
        return jsonify({"success": False, "error": "未登入 GM"}), 403

    team_id = request.form.get("team_id", "").strip().upper()
    new_name = request.form.get("new_name", "").strip()

    if not team_id or not new_name:
        return jsonify({"success": False, "error": "參數不完整"}), 400
    if not get_team_by_id(team_id):
        return jsonify({"success": False, "error": "Team 不存在"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE teams SET team_name = ? WHERE team_id = ?", (new_name, team_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "隊名已更新"})

@app.route("/debug/teams")
def debug_teams():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='teams'")
    exists = c.fetchone() is not None
    count = 0
    if exists:
        count = c.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    conn.close()
    return jsonify({"teams_table_exists": exists, "team_count": count})

@app.route("/announcements")
def get_announcements():
    return jsonify({"announcements": ANNOUNCEMENTS})

@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    disk_path = resolve_upload_disk_path(filename)
    if not disk_path:
        abort(404)
    return send_from_directory(os.path.dirname(disk_path), os.path.basename(disk_path))

# ==================== 漂亮嘅 HTML ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-HK">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oikonomia • 原型</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js" type="text/javascript"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        #qr-reader { min-height: 280px; background: #09090b; }
        #qr-reader video { border-radius: 0.75rem; }
        #item-reveal-modal { z-index: 110; }
        #item-reveal-modal .reveal-card {
            background: var(--card-bg);
            border: 2px solid var(--card-border);
            box-shadow: 0 0 40px rgba(251, 191, 36, 0.15);
            animation: reveal-pop 0.45s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        #item-reveal-modal.reveal-ability .reveal-card {
            border-color: #fbbf24;
            box-shadow: 0 0 50px rgba(251, 191, 36, 0.35);
        }
        #item-reveal-modal .reveal-image-wrap {
            position: relative;
            background: linear-gradient(180deg, rgba(0,0,0,0.2) 0%, rgba(0,0,0,0.6) 100%);
        }
        #item-reveal-modal .reveal-ability-badge {
            background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
            color: #18181b;
            box-shadow: 0 4px 14px rgba(251, 191, 36, 0.5);
            animation: badge-pulse 2s ease-in-out infinite;
        }
        #item-reveal-modal .reveal-effect-box {
            background: rgba(251, 191, 36, 0.1);
            border: 1px solid rgba(251, 191, 36, 0.35);
        }
        #item-reveal-modal .reveal-effect-text {
            color: #fbbf24;
            text-shadow: 0 0 20px rgba(251, 191, 36, 0.4);
        }
        @keyframes reveal-pop {
            0% { opacity: 0; transform: scale(0.85) translateY(20px); }
            100% { opacity: 1; transform: scale(1) translateY(0); }
        }
        @keyframes badge-pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }
        .inventory-ability-tag {
            background: rgba(251, 191, 36, 0.15);
            border: 1px solid rgba(251, 191, 36, 0.4);
            color: #fbbf24;
        }
        :root {
            --bg-main: #0D0D0D;
            --bg-color: #0D0D0D;
            --bg-gradient-start: #0D0D0D;
            --bg-gradient-mid: #141414;
            --bg-gradient-end: #141414;
            --bg-glow: transparent;
            --card-bg: #1F1F1F;
            --card-border: #555555;
            --text-primary: #FFFFFF;
            --text-secondary: #AAAAAA;
            --text-color: #FFFFFF;
            --text-muted: #AAAAAA;
            --accent-gold: #FFFFFF;
            --accent-orange: #888888;
            --accent-color: #FFFFFF;
            --accent-contrast: #0D0D0D;
            --accent-soft: rgba(255, 255, 255, 0.12);
            --progress-bg: #333333;
            --progress-track: #333333;
            --progress-color: #888888;
            --header-border: rgba(63, 63, 70, 0.8);
            --shadow-color: rgba(44, 62, 80, 0.6);
            --card-glow: none;
        }
        .theme-iggy {
            --bg-main: #0D0D0D;
            --bg-color: #0D0D0D;
            --bg-gradient-start: #3D1A2E;
            --bg-gradient-mid: #1a0f14;
            --bg-gradient-end: #0D0D0D;
            --bg-glow: rgba(212, 160, 23, 0.1);
            --card-bg: #4A1C2E;
            --card-border: #D4A017;
            --text-primary: #F5E8C7;
            --text-secondary: #C9A36A;
            --text-color: #F5E8C7;
            --text-muted: #C9A36A;
            --accent-gold: #D4A017;
            --accent-orange: #E07A5F;
            --accent-color: #D4A017;
            --accent-contrast: #1a0f14;
            --accent-soft: rgba(212, 160, 23, 0.22);
            --progress-bg: #3D1A2E;
            --progress-track: #3D1A2E;
            --progress-color: #E07A5F;
            --header-border: rgba(212, 160, 23, 0.45);
            --shadow-color: rgba(61, 26, 46, 0.85);
            --card-glow: 0 0 24px rgba(212, 160, 23, 0.18), inset 0 1px 0 rgba(212, 160, 23, 0.15);
        }
        .theme-marah {
            --bg-main: #0D0D0D;
            --bg-color: #0D0D0D;
            --bg-gradient-start: #152033;
            --bg-gradient-mid: #0f1a2e;
            --bg-gradient-end: #0D0D0D;
            --bg-glow: rgba(74, 144, 164, 0.08);
            --card-bg: #1E2A44;
            --card-border: #4A90A4;
            --text-primary: #E8E8E8;
            --text-secondary: #9ca8b8;
            --text-color: #E8E8E8;
            --text-muted: #9ca8b8;
            --accent-gold: #C0C0C0;
            --accent-orange: #4A90A4;
            --accent-color: #C0C0C0;
            --accent-contrast: #0f1520;
            --accent-soft: rgba(74, 144, 164, 0.28);
            --progress-bg: #152033;
            --progress-track: #152033;
            --progress-color: #4A90A4;
            --header-border: rgba(74, 144, 164, 0.38);
            --shadow-color: rgba(30, 42, 68, 0.75);
            --card-glow: 0 0 20px rgba(74, 144, 164, 0.12), inset 0 1px 0 rgba(192, 192, 192, 0.08);
        }
        body { font-family: 'Noto Sans TC', system-ui, sans-serif; }
        body.theme-body {
            background:
                radial-gradient(ellipse 110% 75% at 50% -8%, var(--bg-glow) 0%, transparent 52%),
                radial-gradient(ellipse 85% 55% at 8% 18%, color-mix(in srgb, var(--bg-gradient-start) 55%, transparent) 0%, transparent 48%),
                linear-gradient(165deg, var(--bg-gradient-start) 0%, var(--bg-gradient-mid) 38%, var(--bg-main) 100%);
            background-attachment: fixed;
            color: var(--text-color);
            min-height: 100vh;
        }
        .title-font { font-family: 'Playfair Display', Georgia, serif; }
        .theme-accent-bg { background-color: var(--accent-color); }
        .theme-accent-text { color: var(--accent-color); }
        .theme-muted-text { color: var(--text-muted); }
        .section-card {
            background: var(--card-bg);
            border: 1px solid var(--header-border);
        }
        .status-bar { transition: width 0.4s ease; }
        .stat-track { background-color: var(--progress-track); }
        .nav-active {
            background-color: var(--accent-soft);
            color: var(--accent-color);
            border-radius: 9999px;
        }
        .nav-btn {
            color: var(--text-muted);
            transition: all 0.2s;
        }
        .nav-btn:hover {
            color: var(--text-color);
            background-color: var(--accent-soft);
            border-radius: 9999px;
        }
        .app-header { border-color: var(--header-border) !important; }
        .cartoon-box {
            border: 2px solid var(--card-border);
            border-radius: 12px;
            background: var(--card-bg);
            box-shadow: var(--card-glow), 6px 6px 0px var(--shadow-color);
            color: var(--text-color);
        }
        body.theme-iggy .cartoon-box {
            border-width: 2px;
        }
        .theme-card-title {
            color: var(--accent-gold);
        }
        .ring-active-route {
            box-shadow: var(--card-glow), 0 0 0 2px var(--accent-gold), 6px 6px 0px var(--shadow-color);
        }
        .route-card {
            border: 3px solid #2C3E50;
            border-radius: 12px;
            padding: 1.25rem;
            cursor: pointer;
            transition: transform 0.1s ease, box-shadow 0.1s ease;
            box-shadow: 4px 4px 0px rgba(44, 62, 80, 0.5);
        }
        .route-card:hover { transform: translate(-2px, -2px); box-shadow: 6px 6px 0px rgba(44, 62, 80, 0.5); }
        .route-iggy { background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%); }
        .route-marah { background: linear-gradient(135deg, #1e3a5f 0%, #1e40af 100%); }
        /* Combat UI */
        .combat-accent-oikos { --combat-accent: #be123c; --combat-accent-soft: rgba(190, 18, 60, 0.22); }
        .combat-accent-polis { --combat-accent: #2563eb; --combat-accent-soft: rgba(37, 99, 235, 0.22); }
        .combat-accent-default { --combat-accent: #d97706; --combat-accent-soft: rgba(217, 119, 6, 0.2); }
        #combat-screen .combat-title { color: var(--combat-accent, #f59e0b); }
        .action-btn.selected { border-color: var(--combat-accent, #f59e0b) !important; background: var(--combat-accent-soft, rgba(245, 158, 11, 0.15)); }
        .dice-btn.selected { border-color: #f59e0b !important; background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
        .team-card-me { box-shadow: 0 0 0 2px var(--combat-accent, #f59e0b); }
        .team-card-berserk { animation: combat-pulse 1.5s ease-in-out infinite; }
        .combat-team-scroll { -webkit-overflow-scrolling: touch; scrollbar-width: none; }
        .combat-team-scroll::-webkit-scrollbar { display: none; }
        .combat-team-chip { flex: 0 0 auto; min-width: 4.5rem; }
        @media (max-width: 1023px) {
            #combat-screen .combat-action-btn { padding-top: 0.65rem; padding-bottom: 0.65rem; font-size: 0.8125rem; }
            #combat-log { max-height: 5.5rem; }
        }
        #available-teams-list .team-join-card {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            padding: 0.875rem 1rem;
            border-radius: 1rem;
            border: 1px solid var(--card-border, #3f3f46);
            background: rgba(24, 24, 27, 0.6);
        }
        @media (min-width: 640px) {
            #available-teams-list .team-join-card {
                flex-direction: row;
                align-items: center;
                justify-content: space-between;
            }
        }
        #available-teams-list .team-join-btn {
            min-height: 2.5rem;
            padding: 0.5rem 1.25rem;
            font-size: 0.875rem;
            font-weight: 600;
            border-radius: 0.75rem;
            width: 100%;
        }
        @media (min-width: 640px) {
            #available-teams-list .team-join-btn { width: auto; }
        }
        @keyframes combat-pulse {
            0%, 100% { box-shadow: 0 0 0 0 rgba(249, 115, 22, 0.4); }
            50% { box-shadow: 0 0 0 6px rgba(249, 115, 22, 0); }
        }
        @keyframes zoo-flash {
            0% { box-shadow: 0 0 0 0 rgba(251, 146, 60, 0.8); }
            100% { box-shadow: 0 0 24px 8px rgba(251, 146, 60, 0); }
        }
        .zoo-flash { animation: zoo-flash 0.6s ease-out; }
        .combat-action-btn.selected { border-color: var(--combat-accent, #f59e0b) !important; background: var(--combat-accent-soft, rgba(245, 158, 11, 0.15)); }
        #modal-dice-box.dice-crit {
            border-color: #facc15 !important;
            box-shadow: 0 0 28px rgba(234, 179, 8, 0.55);
        }
        .damage-number {
            position: absolute;
            font-weight: 700;
            font-size: 2rem;
            color: #f87171;
            text-shadow: 0 0 8px rgba(248, 113, 113, 0.6);
            pointer-events: none;
            z-index: 50;
            animation: damagePop 1.1s ease-out forwards;
            transform: translateX(-50%);
        }
        .damage-number.crit {
            color: #fbbf24;
            font-size: 2.5rem;
            text-shadow: 0 0 12px rgba(251, 191, 36, 0.8);
            animation: damagePopCrit 1.3s ease-out forwards;
        }
        @keyframes damagePop {
            0% { transform: translateX(-50%) translateY(0) scale(0.6); opacity: 1; }
            30% { transform: translateX(-50%) translateY(-25px) scale(1.1); }
            100% { transform: translateX(-50%) translateY(-60px) scale(0.9); opacity: 0; }
        }
        @keyframes damagePopCrit {
            0% { transform: translateX(-50%) translateY(0) scale(0.5); opacity: 1; }
            25% { transform: translateX(-50%) translateY(-35px) scale(1.3); }
            100% { transform: translateX(-50%) translateY(-75px) scale(0.85); opacity: 0; }
        }
        #combat-berserk-bar { background: linear-gradient(90deg, #9a3412, #ea580c); }
        #combat-berserk-bar.berserk-critical { background: linear-gradient(90deg, #7f1d1d, #dc2626); animation: combat-pulse 1s ease-in-out infinite; }
        #combat-near-death-overlay { background: rgba(69, 10, 10, 0.92); backdrop-filter: blur(4px); }
        #combat-precheck-modal { background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(6px); }
        #combat-berserk-overlay { background: rgba(127, 29, 29, 0.55); backdrop-filter: blur(2px); pointer-events: none; }
        /* Fallback（Tailwind CDN 載入失敗時仍可用） */
        .hidden { display: none; }
        .fixed { position: fixed; }
        .inset-0 { top: 0; right: 0; bottom: 0; left: 0; }
        /* 導航：桌面橫向 / 手機漢堡（唔用全局 .flex !important，避免蓋過響應式） */
        #nav-desktop { display: none; }
        @media (min-width: 768px) {
            #nav-desktop.nav-visible {
                display: flex !important;
                align-items: center;
                gap: 0.25rem;
            }
        }
        #hamburger-btn { display: none; }
        @media (max-width: 767px) {
            #hamburger-btn.nav-visible { display: block; }
        }
        #mobile-menu { display: none !important; }
        @media (max-width: 767px) {
            #mobile-menu.menu-open {
                display: flex !important;
                flex-direction: column;
            }
        }
        .location-card {
            cursor: pointer; padding: 1.25rem; border-radius: 1.5rem; margin-bottom: 1rem;
            background: var(--card-bg); border: 1px solid var(--header-border);
            color: var(--text-color);
        }
        .location-card:active { opacity: 0.85; }
        .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 50;
            display: flex; align-items: flex-end; justify-content: center; }
        .modal-box {
            background: var(--card-bg); color: var(--text-color);
            width: 100%; max-width: 480px; padding: 1.5rem;
            border-radius: 1.5rem 1.5rem 0 0; border-top: 1px solid var(--card-border);
        }
        #game-content .text-zinc-400 { color: var(--text-muted); }
        #game-content .border-zinc-700,
        #game-content .border-zinc-800 { border-color: var(--card-border); }
        .theme-btn-primary {
            background-color: var(--accent-color);
            color: var(--accent-contrast);
        }
        .theme-btn-primary:hover { filter: brightness(1.08); }
        @media (min-width: 768px) {
            .modal-overlay { align-items: center; }
            .modal-box { border-radius: 1.5rem; }
        }
    </style>
</head>
<body class="theme-body">
    <div class="max-w-4xl mx-auto">
        <!-- ==================== Header ==================== -->
        <div class="app-header flex items-center justify-between px-6 py-5 border-b border-zinc-800">
            <div class="flex items-center gap-x-3">
                <div class="w-9 h-9 theme-accent-bg rounded-2xl flex items-center justify-center">
                    <i class="fa-solid fa-link" style="color: var(--accent-contrast)"></i>
                </div>
                <span class="title-font text-3xl font-bold">Oikonomia</span>
            </div>

            <!-- 桌面版導航（≥768px 先顯示） -->
            <div id="nav-desktop" class="items-center gap-x-1 text-sm">
                <button onclick="showSection('dashboard')" class="px-5 py-2 nav-btn">Dashboard</button>
                <button onclick="showSection('explore')" class="px-5 py-2 nav-btn">探索</button>
                <button onclick="showSection('combat')" class="px-5 py-2 nav-btn">戰鬥</button>
                <button onclick="showSection('team')" class="px-5 py-2 nav-btn">Team</button>
                <button onclick="showSection('log')" class="px-5 py-2 nav-btn">日誌</button>
            </div>

            <!-- 手機版漢堡按鈕（<768px 先顯示） -->
            <button id="hamburger-btn" onclick="toggleMobileMenu()"
                    class="text-2xl text-zinc-300 hover:text-white px-2">
                <i class="fa-solid fa-bars"></i>
            </button>
        </div>

        <!-- 手機版彈出選單 -->
        <div id="mobile-menu" onclick="toggleMobileMenu()"
             class="fixed inset-0 bg-black/90 z-[60] pt-20 px-6">
            <div class="flex flex-col text-lg" onclick="event.stopPropagation()">
                <button onclick="showSection('dashboard'); toggleMobileMenu()" class="py-4 text-left border-b border-zinc-800">Dashboard</button>
                <button onclick="showSection('explore'); toggleMobileMenu()" class="py-4 text-left border-b border-zinc-800">探索</button>
                <button onclick="showSection('combat'); toggleMobileMenu()" class="py-4 text-left border-b border-zinc-800">戰鬥</button>
                <button onclick="showSection('team'); toggleMobileMenu()" class="py-4 text-left border-b border-zinc-800">Team</button>
                <button onclick="showSection('log'); toggleMobileMenu()" class="py-4 text-left">日誌</button>
            </div>
        </div>

        <!-- 恢復登入中 -->
        <div id="session-loading" class="max-w-md mx-auto px-6 py-24 text-center">
            <i class="fa-solid fa-circle-notch fa-spin text-4xl theme-accent-text mb-4"></i>
            <p class="text-zinc-400">正在恢復登入狀態...</p>
        </div>

        <!-- Login -->
        <div id="login-screen" class="hidden max-w-md mx-auto px-6 py-16">
            <div class="text-center mb-8">
                <i class="fa-solid fa-user-secret text-6xl theme-accent-text mb-4"></i>
                <h1 class="text-3xl font-bold">歡迎進入Oikonomia的世界</h1>
                <p class="text-zinc-400 mt-2">輸入名稱登入（首次無需 PIN）</p>
                <p id="login-restore-hint" class="hidden text-sm text-amber-400/90 mt-3"></p>
            </div>
            <form onsubmit="login(event)" class="section-card rounded-3xl p-8 space-y-4">
                <input type="text" id="squad_id" name="squad_id" placeholder="輸入你的名稱"
                       autocomplete="username" autocapitalize="off" autocorrect="off" spellcheck="false"
                       class="w-full bg-zinc-900 border border-zinc-700 focus:border-amber-500 rounded-2xl px-6 py-4 text-xl mb-3">
                <input type="password" id="login_pin" name="login_pin" placeholder="輸入 PIN（第一次登入可留空）" maxlength="4"
                       inputmode="numeric" pattern="[0-9]*" autocomplete="current-password"
                       class="w-full bg-zinc-900 border border-zinc-700 focus:border-amber-500 rounded-2xl px-6 py-4 text-xl tracking-widest text-center font-mono">
                <button type="submit" 
                        class="w-full theme-btn-primary font-semibold py-4 rounded-2xl">
                    進入 Oikonomia
                </button>
            </form>
        </div>

        <!-- Game Content -->
        <div id="game-content" class="hidden px-6 pb-12">
            <!-- Dashboard -->
            <div id="dashboard" class="section">
                <!-- Announcement History -->
                <div id="announcement-box" class="hidden mt-4 mb-10 bg-blue-900/30 border border-blue-500/30 rounded-3xl p-5">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-x-2">
                            <i class="fa-solid fa-bullhorn text-blue-400"></i>
                            <span class="font-medium text-blue-400">最新公告</span>
                        </div>
                        
                        <!-- 展開/收起按鈕 -->
                        <button id="toggle-announcement-btn" 
                                onclick="toggleAllAnnouncements()"
                                class="text-xs px-3 py-1 bg-blue-800 hover:bg-blue-700 rounded-full text-blue-200">
                            查看所有公告
                        </button>
                    </div>
                    
                    <!-- 最新一條公告 -->
                    <div id="latest-announcement"></div>
                    
                    <!-- 全部歷史公告（預設隱藏） -->
                    <div id="all-announcements" class="hidden mt-4 pt-4 border-t border-blue-700/50 space-y-3 text-sm"></div>
                </div>

                <div class="flex items-center gap-x-3 mb-6">
                    <img id="player-avatar"
                         src="/static/avatars/default.png"
                         class="w-16 h-16 rounded-full object-cover border-2 border-zinc-600 cursor-pointer"
                         onclick="showAvatarModal()">

                    <div>
                        <div class="flex items-center gap-x-2">
                            <div id="squad-name" class="text-4xl font-semibold"></div>
                            <button onclick="editDisplayName()"
                                    class="text-xs px-3 py-1 bg-zinc-700 hover:bg-zinc-600 rounded-xl flex items-center gap-x-1">
                                <i class="fa-solid fa-edit text-xs"></i>
                                <span>改名</span>
                            </button>
                        </div>
                        <div id="route-badge" class="hidden mt-2 text-sm"></div>
                        <div class="text-sm text-zinc-400 mt-1">點擊頭像更換角色頭像</div>
                    </div>
                </div>

                <!-- 路線選擇 -->
                <div id="route-picker" class="hidden mb-8 cartoon-box p-6">
                    <h3 class="text-lg font-bold mb-2">🔗 選擇你的路線</h3>
                    <p class="text-sm text-zinc-400 mb-4">A/B Line Unified Protocol — 選擇後無法更改</p>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div class="route-card route-iggy" onclick="selectRoute('iggy')">
                            <div class="text-xl font-bold">🔥 Iggy 路線</div>
                            <div class="text-sm mt-1 opacity-90">界線、力量、面對 Judas</div>
                        </div>
                        <div class="route-card route-marah" onclick="selectRoute('marah')">
                            <div class="text-xl font-bold">🌊 Marah 路線</div>
                            <div class="text-sm mt-1 opacity-90">智慧、韌性、深度連結</div>
                        </div>
                    </div>
                </div>

                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                    <!-- 玩家狀態（同戰鬥畫面風格） -->
                    <div id="player-status-card" class="cartoon-box p-5 bg-zinc-900/50 border border-zinc-700">
                        <div class="flex items-center gap-3 mb-5 pb-4 border-b border-zinc-700/80">
                            <img id="dashboard-player-avatar"
                                 src="/static/avatars/default.png"
                                 class="w-14 h-14 rounded-2xl object-cover border-2 border-amber-500 shrink-0 cursor-pointer"
                                 onclick="showAvatarModal()" alt="玩家頭像">
                            <div class="min-w-0">
                                <div id="dashboard-player-name" class="font-semibold text-lg truncate">—</div>
                                <div id="dashboard-attack-hint" class="text-xs text-amber-400/90 mt-0.5">攻擊力：—</div>
                            </div>
                        </div>
                        <h3 class="font-bold mb-3 flex items-center gap-2 text-sm text-zinc-400 uppercase tracking-wide">
                            <i class="fa-solid fa-shield-halved theme-accent-text"></i> 能力狀態
                        </h3>
                        <div class="space-y-3.5">
                            <div class="dashboard-stat-row" data-stat="hp">
                                <div class="flex justify-between text-sm mb-1">
                                    <span class="flex items-center gap-2"><span>❤️</span><span class="font-medium text-zinc-200">生命值</span></span>
                                    <span class="font-mono text-red-400">
                                        <span id="hp-value">— / 100</span>
                                        <span id="hp-pct" class="text-xs text-zinc-500 ml-1">(—)</span>
                                    </span>
                                </div>
                                <div class="h-2.5 bg-zinc-800 rounded-full overflow-hidden">
                                    <div id="hp-bar" class="h-2.5 bg-red-500 rounded-full transition-all duration-500" style="width:0%"></div>
                                </div>
                            </div>
                            <div class="dashboard-stat-row" data-stat="sanity">
                                <div class="flex justify-between text-sm mb-1">
                                    <span class="flex items-center gap-2"><span>🧠</span><span class="font-medium text-zinc-200">神智</span></span>
                                    <span class="font-mono text-purple-400">
                                        <span id="sanity-value">— / 100</span>
                                        <span id="sanity-pct" class="text-xs text-zinc-500 ml-1">(—)</span>
                                    </span>
                                </div>
                                <div class="h-2.5 bg-zinc-800 rounded-full overflow-hidden">
                                    <div id="sanity-bar" class="h-2.5 bg-purple-500 rounded-full transition-all duration-500" style="width:0%"></div>
                                </div>
                            </div>
                            <div class="flex justify-between items-center py-1.5 border-t border-zinc-800/80 mt-1 pt-3">
                                <span class="flex items-center gap-2 text-sm"><span>💪</span><span class="font-medium text-zinc-200">力量</span></span>
                                <span id="power-value" class="font-mono text-lg font-bold text-orange-400">—</span>
                            </div>
                            <div class="flex justify-between items-center py-1.5">
                                <span class="flex items-center gap-2 text-sm"><span>📘</span><span class="font-medium text-zinc-200">智力</span></span>
                                <span id="intellect-value" class="font-mono text-lg font-bold text-blue-400">—</span>
                            </div>
                            <div class="flex justify-between items-center py-1.5">
                                <span class="flex items-center gap-2 text-sm"><span>🛡️</span><span class="font-medium text-zinc-200">韌性</span></span>
                                <span id="resilience-value" class="font-mono text-lg font-bold text-emerald-400">—</span>
                            </div>
                        </div>
                        <div class="mt-4 pt-3 border-t border-zinc-700 space-y-2 text-sm">
                            <div class="flex justify-between">
                                <span><i class="fa-solid fa-gem text-purple-400 mr-1"></i>Resource</span>
                                <span id="resource-value" class="font-mono text-purple-400">0</span>
                            </div>
                            <div class="flex justify-between">
                                <span><i class="fa-solid fa-lightbulb text-amber-400 mr-1"></i>洞見碎片</span>
                                <span id="insight-value" class="font-mono text-amber-400">0</span>
                            </div>
                        </div>
                    </div>

                    <!-- Iggy 五維（已選 Iggy 路線時顯示） -->
                    <div id="iggy-card" class="cartoon-box p-5" style="display:none">
                        <h3 class="font-bold mb-4">🔥 Iggy</h3>
                        <div class="space-y-3">
                            <div><div class="flex justify-between text-sm mb-1"><span>❤️ 生命值</span><span id="iggy-hp-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="iggy-hp-bar" class="h-2.5 bg-red-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>🧠 神智</span><span id="iggy-sanity-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="iggy-sanity-bar" class="h-2.5 bg-purple-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>⚡ 力量</span><span id="iggy-power-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="iggy-power-bar" class="h-2.5 bg-orange-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>📖 智力</span><span id="iggy-intellect-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="iggy-intellect-bar" class="h-2.5 bg-blue-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>🛡️ 韌性</span><span id="iggy-resilience-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="iggy-resilience-bar" class="h-2.5 bg-emerald-500 rounded-full status-bar" style="width:100%"></div></div></div>
                        </div>
                    </div>

                    <!-- Marah 五維（已選 Marah 路線時顯示） -->
                    <div id="marah-card" class="cartoon-box p-5" style="display:none">
                        <h3 class="font-bold mb-4">🌊 Marah</h3>
                        <div class="space-y-3">
                            <div><div class="flex justify-between text-sm mb-1"><span>❤️ 生命值</span><span id="marah-hp-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="marah-hp-bar" class="h-2.5 bg-red-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>🧠 神智</span><span id="marah-sanity-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="marah-sanity-bar" class="h-2.5 bg-purple-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>⚡ 力量</span><span id="marah-power-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="marah-power-bar" class="h-2.5 bg-orange-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>📖 智力</span><span id="marah-intellect-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="marah-intellect-bar" class="h-2.5 bg-blue-500 rounded-full status-bar" style="width:100%"></div></div></div>
                            <div><div class="flex justify-between text-sm mb-1"><span>🛡️ 韌性</span><span id="marah-resilience-value" class="font-mono">100</span></div><div class="h-2.5 bg-zinc-800 rounded-full"><div id="marah-resilience-bar" class="h-2.5 bg-emerald-500 rounded-full status-bar" style="width:100%"></div></div></div>
                        </div>
                    </div>
                </div>

                <!-- 持有物品 -->
                <div class="cartoon-box p-5 mb-8">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="font-bold text-lg flex items-center gap-x-2 theme-card-title">
                            <i class="fa-solid fa-box-open theme-accent-text"></i>
                            <span>持有物品</span>
                            <span id="items-slot-label" class="text-xs font-normal theme-muted-text">(0/5)</span>
                        </h3>
                        <div class="flex items-center gap-2">
                            <button onclick="startQRScanner()"
                                    class="text-xs px-3 py-1.5 theme-btn-primary rounded-xl flex items-center gap-x-1 font-medium">
                                <i class="fa-solid fa-qrcode"></i>
                                <span>掃描 QR</span>
                            </button>
                            <button onclick="loadMyItems()"
                                    class="text-xs px-3 py-1 bg-zinc-700 hover:bg-zinc-600 rounded-xl">刷新</button>
                        </div>
                    </div>
                    <div id="my-items-list" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div class="text-sm text-zinc-400 col-span-full text-center py-4">載入中...</div>
                    </div>
                </div>

                <!-- Zoo Skills -->
                <div>
                    <div class="font-medium mb-3 flex items-center gap-x-2">
                        <i class="fa-solid fa-magic theme-accent-text"></i>
                        <span>Zoo 能力</span>
                    </div>
                    <div class="grid grid-cols-2 gap-3" id="zoo-list">
                        <div class="bg-zinc-800 border border-zinc-700 rounded-2xl p-4 text-sm">
                            <div class="text-amber-400 font-medium">溫柔之焰</div>
                            <div class="text-xs text-zinc-400 mt-1">幫助 Iggy 冷靜</div>
                        </div>
                        <div class="bg-zinc-800 border border-zinc-700 rounded-2xl p-4 text-sm">
                            <div class="text-amber-400 font-medium">界線共鳴</div>
                            <div class="text-xs text-zinc-400 mt-1">感受他人痛楚</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ==================== 日誌頁面 ==================== -->
            <div id="log" class="section hidden">
                <div class="mb-8 flex items-center gap-x-4">
                    <img id="log-player-avatar"
                         src="/static/avatars/default.png"
                         class="w-12 h-12 rounded-full object-cover border border-zinc-600">
                    <div>
                        <div class="text-sm theme-accent-text">LOG</div>
                        <div class="text-3xl font-semibold">故事與任務記錄</div>
                    </div>
                </div>

                <div class="cartoon-box p-6 mb-8">
                    <h3 class="font-bold text-xl mb-4 flex items-center gap-x-2">
                        <i class="fa-solid fa-book text-amber-400"></i>
                        <span>故事進度</span>
                    </h3>
                    <div id="story-log-content"></div>
                </div>

                <div class="cartoon-box p-6 mb-8">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="font-bold text-xl flex items-center gap-x-2">
                            <i class="fa-solid fa-tasks text-amber-400"></i>
                            <span id="team-task-logs-title">任務記錄</span>
                        </h3>
                        <button onclick="loadTeamTaskLogs()"
                                class="text-xs px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-2xl">
                            刷新記錄
                        </button>
                    </div>
                    <div id="team-task-logs" class="space-y-3"></div>
                </div>

                <!-- 全球事件記錄（日誌頁最底部） -->
                <div class="cartoon-box p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="font-bold text-xl flex items-center gap-x-2">
                            <i class="fa-solid fa-globe text-amber-400"></i>
                            <span>全球事件記錄</span>
                        </h3>
                        <button onclick="loadGlobalEvents()"
                                class="text-xs px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-2xl">
                            刷新
                        </button>
                    </div>
                    <div id="global-events-list" class="space-y-3"></div>
                </div>
            </div>

            <!-- Explore -->
            <div id="explore" class="section hidden">
                <h2 class="text-2xl font-semibold mb-4">探索地點</h2>
                <div id="location-list" class="space-y-4"></div>
            </div>

            <!-- Combat -->
            <div id="combat" class="section hidden">
                <!-- Encounter 列表（大廳） -->
                <div id="combat-lobby">
                    <div class="mb-6">
                        <div class="text-sm theme-accent-text">ENCOUNTER</div>
                        <div class="text-3xl font-semibold">戰鬥遭遇</div>
                    </div>
                    <div id="encounter-list" class="space-y-4 mb-8"></div>
                </div>

                <!-- 戰鬥主畫面（手機：敵人置頂 + compact；桌面：雙欄） -->
                <div id="combat-screen" class="hidden max-w-md lg:max-w-6xl mx-auto combat-accent-default relative px-1 sm:px-0">
                    <button onclick="exitCombatScreen()" class="mb-2 lg:mb-3 text-sm text-zinc-400 hover:text-zinc-200 flex items-center gap-1">
                        <i class="fa-solid fa-arrow-left"></i> 返回遭遇列表
                    </button>

                    <div class="flex justify-between items-center mb-3 lg:mb-4 gap-2">
                        <div class="min-w-0">
                            <h1 id="combat-title" class="combat-title text-lg lg:text-3xl font-bold truncate">戰鬥中</h1>
                            <p id="combat-subtitle" class="text-xs lg:text-sm text-zinc-400">第 <span id="current-phase">1</span> 回合</p>
                        </div>
                        <div class="text-right shrink-0">
                            <div id="phase-timer" class="text-2xl lg:text-4xl font-mono font-bold text-emerald-400">--:--</div>
                            <div id="phase-status-label" class="text-xs text-emerald-400">Player Phase</div>
                        </div>
                    </div>

                    <div id="combat-berserk-bar" class="hidden mb-3 lg:mb-4 px-3 py-1.5 lg:px-4 lg:py-2 rounded-xl text-xs lg:text-sm text-orange-100 font-medium">
                        ⚠️ <span id="combat-berserk-bar-text">神智偏低，暴走風險上升</span>
                    </div>

                    <div class="flex flex-col lg:grid lg:grid-cols-2 gap-3 lg:gap-6">
                        <!-- 敵人（手機 order-1 置頂；5 維同玩家） -->
                        <div id="enemy-panel" class="order-1 lg:order-2 bg-zinc-900 border border-red-500/40 lg:border-zinc-700 rounded-2xl lg:rounded-3xl p-3 lg:p-6 relative overflow-hidden">
                            <div class="flex items-center gap-x-3 mb-3">
                                <img id="combat-enemy-avatar" src="/static/images/enemies/parasite_shadow.svg"
                                     class="w-11 h-11 lg:w-20 lg:h-20 rounded-xl lg:rounded-2xl border-2 border-red-500 object-cover bg-zinc-950 shrink-0" alt="敵人">
                                <div class="flex-1 min-w-0">
                                    <div id="enemy-name" class="font-semibold lg:text-xl text-red-400 truncate">敵人</div>
                                    <div class="hidden lg:block text-sm text-zinc-400">Enemy</div>
                                    <div class="flex items-center gap-x-2 mt-1.5">
                                        <div class="flex-1 h-2.5 bg-zinc-800 rounded-full overflow-hidden">
                                            <div id="enemy-hp-bar" class="h-2.5 bg-gradient-to-r from-red-700 to-red-400 transition-all duration-500" style="width:100%"></div>
                                        </div>
                                        <div class="font-mono text-xs lg:text-sm text-red-400 whitespace-nowrap">
                                            <span id="enemy-hp-current">0</span>/<span id="enemy-hp-max">0</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="grid grid-cols-5 gap-1 text-center">
                                <div>
                                    <div class="text-red-400 text-[10px] lg:text-xs">生命值</div>
                                    <div id="enemy-stat-hp" class="font-mono text-sm lg:text-lg text-red-400">—</div>
                                </div>
                                <div>
                                    <div class="text-purple-400 text-[10px] lg:text-xs">神智</div>
                                    <div id="enemy-stat-sanity" class="font-mono text-sm lg:text-lg text-purple-400">—</div>
                                </div>
                                <div>
                                    <div class="text-orange-400 text-[10px] lg:text-xs">力量</div>
                                    <div id="enemy-stat-power" class="font-mono text-sm lg:text-lg text-orange-400">—</div>
                                </div>
                                <div>
                                    <div class="text-blue-400 text-[10px] lg:text-xs">智力</div>
                                    <div id="enemy-stat-intellect" class="font-mono text-sm lg:text-lg text-blue-400">—</div>
                                </div>
                                <div>
                                    <div class="text-emerald-400 text-[10px] lg:text-xs">韌性</div>
                                    <div id="enemy-stat-resilience" class="font-mono text-sm lg:text-lg text-emerald-400">—</div>
                                </div>
                            </div>
                            <div id="enemy-quote" class="hidden lg:block text-sm text-zinc-300 leading-relaxed mt-4"></div>
                        </div>

                        <!-- 玩家 + 行動（手機 order-2） -->
                        <div id="player-panel" class="order-2 lg:order-1 bg-zinc-900 border border-zinc-700 rounded-2xl lg:rounded-3xl p-3 lg:p-6 relative overflow-hidden">
                            <div id="combat-berserk-overlay" class="hidden absolute inset-0 z-10 rounded-2xl lg:rounded-3xl flex items-center justify-center bg-zinc-950/80">
                                <div class="text-center text-red-200 font-bold text-base lg:text-lg px-4">神智不清，能力失控</div>
                            </div>

                            <!-- 手機：名 + HP + 神智 同一行 -->
                            <div class="flex items-center justify-between gap-2 mb-3 lg:mb-5">
                                <div class="flex items-center gap-x-2 lg:gap-x-4 min-w-0">
                                    <img id="combat-player-avatar" src="/static/avatars/default.png"
                                         class="w-9 h-9 lg:w-20 lg:h-20 rounded-full lg:rounded-2xl border-2 border-amber-500 object-cover shrink-0" alt="玩家">
                                    <div class="min-w-0">
                                        <div id="combat-player-name" class="font-semibold lg:text-xl truncate">你</div>
                                        <div id="combat-player-team" class="hidden lg:block text-sm text-zinc-400 truncate">—</div>
                                    </div>
                                </div>
                                <div class="lg:hidden flex items-center gap-x-4 text-sm shrink-0">
                                    <div class="flex items-center gap-x-1">
                                        <span class="text-red-400">❤️</span>
                                        <span class="font-mono" id="combat-player-hp">—</span>
                                    </div>
                                    <div class="flex items-center gap-x-1">
                                        <span class="text-purple-400">🧠</span>
                                        <span class="font-mono" id="combat-player-sanity">—</span>
                                    </div>
                                </div>
                            </div>

                            <!-- 手機：力量／智力／韌性 單行 -->
                            <div class="lg:hidden flex justify-between items-center text-xs mb-3 px-0.5 border-t border-zinc-800/80 pt-2">
                                <div class="flex items-center gap-x-1"><span>💪</span><span id="combat-m-power" class="font-mono text-orange-400">—</span></div>
                                <div class="flex items-center gap-x-1"><span>📘</span><span id="combat-m-intellect" class="font-mono text-blue-400">—</span></div>
                                <div class="flex items-center gap-x-1"><span>🛡️</span><span id="combat-m-resilience" class="font-mono text-emerald-400">—</span></div>
                            </div>

                            <!-- 桌面：完整屬性 -->
                            <div class="hidden lg:block space-y-3.5 mb-6">
                                <div>
                                    <div class="flex justify-between text-sm mb-1">
                                        <span class="flex items-center gap-2"><span>❤️</span><span class="font-medium text-zinc-200">生命值</span></span>
                                        <span class="font-mono text-red-400">
                                            <span id="combat-hp-value">— / 100</span>
                                            <span id="combat-hp-pct" class="text-xs text-zinc-500 ml-1">(—)</span>
                                        </span>
                                    </div>
                                    <div class="h-2.5 bg-zinc-800 rounded-full overflow-hidden">
                                        <div id="combat-hp-bar" class="h-2.5 bg-red-500 rounded-full transition-all duration-500" style="width:0%"></div>
                                    </div>
                                </div>
                                <div>
                                    <div class="flex justify-between text-sm mb-1">
                                        <span class="flex items-center gap-2"><span>🧠</span><span class="font-medium text-zinc-200">神智</span></span>
                                        <span class="font-mono text-purple-400">
                                            <span id="combat-sanity-value">— / 100</span>
                                            <span id="combat-sanity-pct" class="text-xs text-zinc-500 ml-1">(—)</span>
                                        </span>
                                    </div>
                                    <div class="h-2.5 bg-zinc-800 rounded-full overflow-hidden">
                                        <div id="combat-sanity-bar" class="h-2.5 bg-purple-500 rounded-full transition-all duration-500" style="width:0%"></div>
                                    </div>
                                </div>
                                <div class="flex justify-between items-center py-1.5 border-t border-zinc-800/80 mt-1 pt-3">
                                    <span class="flex items-center gap-2 text-sm"><span>💪</span><span class="font-medium text-zinc-200">力量</span></span>
                                    <span id="combat-power-value" class="font-mono text-lg font-bold text-orange-400">—</span>
                                </div>
                                <div class="flex justify-between items-center py-1.5">
                                    <span class="flex items-center gap-2 text-sm"><span>📘</span><span class="font-medium text-zinc-200">智力</span></span>
                                    <span id="combat-intellect-value" class="font-mono text-lg font-bold text-blue-400">—</span>
                                </div>
                                <div class="flex justify-between items-center py-1.5">
                                    <span class="flex items-center gap-2 text-sm"><span>🛡️</span><span class="font-medium text-zinc-200">韌性</span></span>
                                    <span id="combat-resilience-value" class="font-mono text-lg font-bold text-emerald-400">—</span>
                                </div>
                            </div>

                            <div class="text-xs text-zinc-400 mb-2 px-0.5 lg:hidden">選擇行動</div>
                            <div class="grid grid-cols-2 lg:grid-cols-1 gap-2 lg:gap-3" id="combat-action-buttons">
                                <button type="button" data-action="attack" id="attack-action-btn"
                                        class="combat-action-btn py-2.5 lg:py-3 bg-zinc-800 hover:bg-zinc-700 border border-zinc-600 rounded-xl lg:rounded-2xl flex items-center justify-center gap-x-2 lg:gap-x-3">
                                    <span class="text-lg lg:text-xl">⚔️</span>
                                    <span class="flex flex-col items-start leading-tight">
                                        <span>攻擊</span>
                                        <span id="attack-stat-hint" class="hidden lg:inline text-[10px] text-amber-400 font-normal">自動取力量／智力較高者</span>
                                    </span>
                                </button>
                                <button type="button" data-action="defend"
                                        class="combat-action-btn py-2.5 lg:py-3 bg-zinc-800 hover:bg-zinc-700 border border-zinc-600 rounded-xl lg:rounded-2xl flex items-center justify-center gap-x-2">
                                    <span>🛡️</span><span class="lg:hidden">防禦</span><span class="hidden lg:inline">Defend（堅守界線）</span>
                                </button>
                                <button type="button" data-action="use_zoo" id="zoo-action-btn"
                                        class="combat-action-btn py-2.5 lg:py-3 bg-orange-900/30 hover:bg-orange-900/50 border border-orange-700 rounded-xl lg:rounded-2xl flex flex-col items-center justify-center gap-y-0.5">
                                    <span class="flex items-center gap-x-2"><span>🔥</span><span class="lg:hidden">Zoo</span><span class="hidden lg:inline">Use Zoo（高神智有加成）</span></span>
                                    <span id="zoo-hint" class="text-[10px] text-orange-400">神智 ≥70 有加成</span>
                                </button>
                                <button type="button" data-action="pass"
                                        class="combat-action-btn py-2.5 lg:py-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 rounded-xl text-sm text-zinc-400 flex items-center justify-center gap-x-2">
                                    <span>⏭️</span><span>觀望</span>
                                </button>
                                <div class="col-span-2 lg:col-span-1">
                                    <div class="text-xs text-zinc-400 mb-1 px-1">可用物品</div>
                                    <div id="combat-item-list" class="space-y-1.5 lg:space-y-2">
                                        <div class="text-xs text-zinc-500 py-2 text-center">載入物品中…</div>
                                    </div>
                                </div>
                            </div>
                            <div class="mt-3 lg:mt-4 flex justify-end">
                                <button type="button" onclick="rescueNearDeath()"
                                        class="text-[10px] lg:text-xs px-3 lg:px-4 py-1.5 lg:py-2 bg-emerald-900/50 hover:bg-emerald-800 border border-emerald-700 rounded-xl">
                                    🤝 禱告救援瀕死隊友
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- 隊友 + 主角（水平 scroll） -->
                    <div id="combat-team-strip" class="mt-3 lg:mt-4 bg-zinc-900 border border-zinc-700 rounded-2xl lg:rounded-3xl p-3">
                        <div class="text-xs text-zinc-400 mb-2 px-1">隊友與主角狀態</div>
                        <div id="team-status-row" class="flex gap-x-4 overflow-x-auto combat-team-scroll pb-1"></div>
                    </div>

                    <p id="combat-submit-hint" class="text-[10px] lg:text-xs text-zinc-500 text-center mt-3 lg:mt-4"></p>

                    <div class="mt-3 lg:mt-6 bg-zinc-950 border border-zinc-800 rounded-2xl lg:rounded-3xl p-3 lg:p-4 max-h-48 overflow-y-auto text-xs lg:text-sm text-zinc-300" id="combat-log"></div>
                    <span id="max-phase" class="hidden"></span>
                </div>

                <!-- 瀕死全屏 -->
                <div id="combat-near-death-overlay" class="hidden fixed inset-0 z-[70] flex items-center justify-center p-6">
                    <div class="text-center max-w-sm">
                        <div class="text-5xl mb-4">💔</div>
                        <h2 class="text-2xl font-bold text-red-300 mb-2">正在癒合…</h2>
                        <p id="near-death-countdown" class="text-4xl font-mono text-red-400 mb-4">15:00</p>
                        <p class="text-sm text-zinc-300 mb-6">隊友可發起「界線重建」禱告救援</p>
                        <button onclick="rescueNearDeath()" class="px-6 py-3 bg-emerald-700 hover:bg-emerald-600 rounded-2xl font-medium">
                            🤝 為隊友禱告（非瀕死者）
                        </button>
                    </div>
                </div>

                <!-- Precheck Modal -->
                <div id="combat-precheck-modal" class="hidden fixed inset-0 z-[65] flex items-center justify-center p-6">
                    <div class="bg-zinc-900 border border-amber-600/40 rounded-3xl p-6 max-w-md w-full shadow-2xl">
                        <div class="text-amber-400 text-sm mb-1">洞察力判定</div>
                        <h3 class="text-xl font-bold mb-3" id="precheck-modal-title">前置判定</h3>
                        <p id="combat-precheck-text" class="text-zinc-300 text-sm leading-relaxed mb-6"></p>
                        <div class="flex flex-col sm:flex-row gap-3">
                            <button onclick="confirmPrecheck('skip')" class="flex-1 py-3 bg-emerald-700 hover:bg-emerald-600 rounded-2xl font-medium">跳過戰鬥</button>
                            <button onclick="confirmPrecheck('fight')" class="flex-1 py-3 bg-red-800 hover:bg-red-700 rounded-2xl font-medium">進入戰鬥</button>
                        </div>
                    </div>
                </div>

                <!-- 戰鬥結果 + 神學反思 -->
                <div id="combat-result-panel" class="hidden cartoon-box p-6 max-w-4xl mx-auto">
                    <h3 id="combat-result-title" class="text-xl font-bold mb-3"></h3>
                    <p id="combat-result-narrative" class="text-zinc-300 mb-4 leading-relaxed"></p>
                    <div id="combat-reflection" class="hidden border-t border-zinc-700 pt-4 mt-4">
                        <h4 class="font-bold text-amber-400 mb-1" id="combat-reflection-title">界線反思</h4>
                        <p id="combat-reflection-theology" class="text-xs text-zinc-500 mb-3 italic"></p>
                        <ul id="combat-reflection-questions" class="text-sm text-zinc-300 space-y-3 list-none"></ul>
                    </div>
                    <button onclick="exitCombatScreen()" class="mt-6 px-5 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-xl text-sm">返回遭遇列表</button>
                </div>
            </div>

            <!-- Team 區塊 -->
            <div id="team" class="section hidden">
                <div class="mb-4">
                    <div class="text-sm theme-accent-text">TEAM</div>
                    <div class="text-2xl lg:text-3xl font-semibold">你的小隊</div>
                </div>

                <!-- 可加入隊伍（置頂，手機一開就見到） -->
                <div id="available-teams-panel" class="cartoon-box p-4 mb-4">
                    <div class="flex items-center justify-between gap-2 mb-3">
                        <div class="min-w-0">
                            <div class="font-semibold text-base">可加入的隊伍</div>
                            <div class="text-xs text-zinc-400 mt-0.5">揀一隊加入，或往下建立新隊</div>
                        </div>
                        <button onclick="loadAvailableTeams()"
                                class="shrink-0 text-xs px-3 py-1.5 bg-zinc-700 hover:bg-zinc-600 rounded-xl flex items-center gap-x-1">
                            <i class="fa-solid fa-sync text-xs"></i>
                            <span>刷新</span>
                        </button>
                    </div>
                    <div id="available-teams-list" class="space-y-2 max-h-[50vh] sm:max-h-[320px] overflow-y-auto pr-1 -webkit-overflow-scrolling-touch"></div>
                </div>

                <!-- 未有 Team 時顯示 -->
                <div id="no-team-box" class="hidden cartoon-box p-5 sm:p-8 mb-4">
                    <div class="text-center mb-5">
                        <i class="fa-solid fa-users text-4xl sm:text-5xl text-zinc-600 mb-3"></i>
                        <h3 class="text-lg sm:text-xl font-bold mb-1">你尚未加入任何 Team</h3>
                        <p class="text-sm text-zinc-400">從上面列表加入，或建立新隊</p>
                    </div>

                    <div class="border-t border-zinc-700 pt-4">
                        <div class="text-sm text-zinc-400 mb-2 px-1">建立新隊</div>
                        <div class="flex flex-col sm:flex-row gap-2">
                            <input type="text" id="create-team-name" placeholder="輸入隊名（例如：界線守護者）"
                                   class="flex-1 bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-3 text-sm">
                            <button onclick="createMyTeam()"
                                    class="px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-2xl">
                                建立新隊
                            </button>
                        </div>
                    </div>
                </div>

                <!-- 已有 Team 時顯示 -->
                <div id="has-team-box" class="hidden">
                    <div class="cartoon-box p-6 mb-6">
                        <div class="flex justify-between items-center">
                            <div>
                                <div class="text-xs text-emerald-400">TEAM NAME</div>
                                <div id="my-team-name" class="text-2xl font-bold"></div>
                                <div id="my-team-id" class="font-mono text-xs text-zinc-500"></div>
                            </div>
                            <div id="my-team-route-badge"></div>
                        </div>
                    </div>

                    <div class="mb-4 flex items-center justify-between">
                        <div class="font-semibold">隊友列表</div>
                        <button onclick="loadMyTeam()" class="text-xs px-3 py-1 bg-zinc-700 rounded-xl">刷新</button>
                    </div>
                    <div id="team-protagonists-section" class="hidden grid grid-cols-1 md:grid-cols-2 gap-4 mb-6"></div>

                    <div id="team-members-list" class="grid grid-cols-1 md:grid-cols-2 gap-4"></div>

                    <div class="cartoon-box p-5 mt-6">
                        <div class="flex items-center justify-between mb-4">
                            <h3 class="font-bold flex items-center gap-x-2">
                                <i class="fa-solid fa-clipboard-list text-amber-400"></i>
                                <span>全隊任務日誌</span>
                            </h3>
                            <button onclick="loadTeamTaskLogs()"
                                    class="text-xs px-3 py-1 bg-zinc-700 hover:bg-zinc-600 rounded-xl">
                                刷新
                            </button>
                        </div>
                        <div id="team-task-logs-list" class="space-y-3 max-h-[400px] overflow-auto pr-1"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentSquad = null;

        function setVisible(el, visible) {
            if (!el) return;
            el.classList.toggle('hidden', !visible);
            el.style.display = visible ? '' : 'none';
        }

        function toggleMobileMenu() {
            const menu = document.getElementById('mobile-menu');
            if (menu) menu.classList.toggle('menu-open');
        }

        function showNavAfterLogin() {
            document.getElementById('nav-desktop')?.classList.add('nav-visible');
            document.getElementById('hamburger-btn')?.classList.add('nav-visible');
        }

        function showSection(id) {
            document.querySelectorAll('.section').forEach(s => setVisible(s, false));
            setVisible(document.getElementById(id), true);
            if (id === 'explore') loadLocations();
            if (id === 'dashboard') loadMyItems();
            if (id === 'combat') loadCombatPage();
            if (id === 'team') {
                loadMyTeam();
                loadAvailableTeams();
            }
            if (id === 'log') {
                loadStoryLog();
                loadTeamTaskLogs();
                loadGlobalEvents();
            }
        }

        let combatPollTimer = null;
        let combatPhaseTimer = null;
        let currentCombatId = null;
        let pendingEncounterId = null;
        let selectedAction = 'attack';
        let selectedItemId = null;
        let selectedDice = null;
        let actionModalRolling = false;
        let actionModalRollTimer = null;
        let actionModalPauseTimer = null;
        const DICE_RESULT_PAUSE_MS = 1150;
        const DICE_RESULT_DESCRIPTIONS = {
            0: '失手 (0%)',
            1: '普通攻擊 (100%)',
            2: '強力攻擊 (150%)',
            3: '爆擊！(200%)',
        };
        let combatItemsLoaded = false;
        let lastDicePhase = 0;
        let lastCombatLogCount = 0;
        let lastCombatStatus = null;
        const COMBAT_ACTION_LABELS = {
            attack: '攻擊',
            attack_physical: '攻擊',
            attack_nonphysical: '攻擊',
            defend: '堅守界線',
            use_zoo: 'Zoo 能力',
            use_item: '使用物品',
            pass: '觀望',
        };
        const ROUTE_SUBTITLES = { iggy: 'Iggy 線', marah: 'Marah 線' };
        const COMBAT_DICE_ACTIONS = new Set(['attack', 'use_zoo']);
        const COMBAT_ATTACK_BASE_DAMAGE = 10;
        const COMBAT_DICE_MULTIPLIERS = {0: 0, 1: 1, 2: 1.5, 3: 2};

        function stopCombatPolling() {
            if (combatPollTimer) {
                clearInterval(combatPollTimer);
                combatPollTimer = null;
            }
            if (combatPhaseTimer) {
                clearInterval(combatPhaseTimer);
                combatPhaseTimer = null;
            }
        }

        function startCombatPolling() {
            stopCombatPolling();
            combatPollTimer = setInterval(() => loadCombatStatus(false), 8000);
        }

        function formatTimerDisplay(totalSeconds) {
            const s = Math.max(0, totalSeconds);
            const m = Math.floor(s / 60);
            const sec = s % 60;
            return `${m}:${String(sec).padStart(2, '0')}`;
        }

        function startPhaseCountdown(deadlineIso) {
            if (combatPhaseTimer) clearInterval(combatPhaseTimer);
            const timerEl = document.getElementById('phase-timer');
            if (!deadlineIso || !timerEl) return;
            const tick = () => {
                const remaining = Math.max(0, Math.floor((new Date(deadlineIso) - Date.now()) / 1000));
                timerEl.textContent = formatTimerDisplay(remaining);
                if (remaining <= 0 && combatPhaseTimer) {
                    clearInterval(combatPhaseTimer);
                    combatPhaseTimer = null;
                    timerEl.textContent = '0:00';
                    timerEl.classList.add('text-amber-400');
                }
            };
            tick();
            combatPhaseTimer = setInterval(tick, 1000);
        }

        function applyCombatAccent(route) {
            const screen = document.getElementById('combat-screen');
            if (!screen) return;
            screen.classList.remove('combat-accent-oikos', 'combat-accent-polis', 'combat-accent-default');
            if (route === 'iggy') screen.classList.add('combat-accent-oikos');
            else if (route === 'marah') screen.classList.add('combat-accent-polis');
            else screen.classList.add('combat-accent-default');
        }

        function showDamageNumber(targetId, amount, isCrit = false) {
            const target = document.getElementById(targetId);
            if (!target || !amount) return;

            const damageEl = document.createElement('div');
            damageEl.className = `damage-number${isCrit ? ' crit' : ''}`;
            damageEl.textContent = `-${amount}`;

            const offsetX = Math.random() * 40 - 20;
            damageEl.style.left = `calc(50% + ${offsetX}px)`;
            damageEl.style.top = '30%';

            target.appendChild(damageEl);
            setTimeout(() => damageEl.remove(), isCrit ? 1300 : 1100);
        }

        function parseLogDamageEvent(entry, myDisplayName) {
            const msg = entry.message || '';
            const type = entry.type || 'event';
            const dmgMatch = msg.match(/造成\\s*(\\d+)\\s*點傷害/);
            if (!dmgMatch) return null;
            const amount = parseInt(dmgMatch[1], 10);
            const crit = /骰\\s*3[）)]/.test(msg);

            if (type === 'damage') {
                return { target: 'enemy-panel', amount, crit };
            }
            if (type === 'summary' && msg.includes('受到共')) {
                return { target: 'enemy-panel', amount, crit: false, total: true };
            }
            if (type === 'enemy_attack' && myDisplayName && msg.includes(myDisplayName)) {
                return { target: 'player-panel', amount, crit: false };
            }
            if (type === 'berserk' && msg.includes('攻擊自己')) {
                return { target: 'player-panel', amount, crit: false };
            }
            return null;
        }

        function processCombatDamageAnimations(data, delayMs = 300, initOnly = false) {
            const entries = data.log_entries || [];
            if (entries.length < lastCombatLogCount) lastCombatLogCount = 0;
            if (initOnly) {
                lastCombatLogCount = entries.length;
                return;
            }
            const newEntries = entries.slice(lastCombatLogCount);
            lastCombatLogCount = entries.length;
            if (!newEntries.length) return;

            const myName = currentSquad?.display_name || data.my_state?.display_name || '';
            const hasDamageLine = newEntries.some(e => e.type === 'damage');

            newEntries.forEach((entry, index) => {
                const hit = parseLogDamageEvent(entry, myName);
                if (!hit) return;
                if (hit.total && hasDamageLine) return;
                setTimeout(() => {
                    showDamageNumber(hit.target, hit.amount, hit.crit);
                }, delayMs + index * 180);
            });
        }

        function flashEnemyHpBar() {
            const bar = document.getElementById('enemy-hp-bar');
            if (!bar) return;
            bar.classList.add('brightness-150');
            setTimeout(() => bar.classList.remove('brightness-150'), 400);
        }

        function highlightCombatAction(action, opts = {}) {
            document.querySelectorAll('.combat-action-btn').forEach(btn => {
                const match = btn.dataset.action === action
                    && (action !== 'use_item' || String(btn.dataset.itemId) === String(opts.item_id));
                btn.classList.toggle('selected', match);
            });
            document.querySelectorAll('.combat-item-btn').forEach(btn => {
                btn.classList.toggle('selected', String(btn.dataset.itemId) === String(opts.item_id));
            });
        }

        function getActionDisplayName(type) {
            return COMBAT_ACTION_LABELS[type] || type;
        }

        function getEffectiveAttackStatFromUi() {
            const power = parseStatText('combat-power-value', currentSquad?.power);
            const intellect = parseStatText('combat-intellect-value', currentSquad?.intellect);
            return { power, intellect, value: Math.max(power, intellect) };
        }

        function describeAttackStatFromUi() {
            const { power, intellect, value } = getEffectiveAttackStatFromUi();
            if (power > intellect) return { label: '力量', value, stat: 'power' };
            if (intellect > power) return { label: '智力', value, stat: 'intellect' };
            return { label: '力量/智力', value, stat: 'power' };
        }

        function updateAttackButtonHint() {
            const hint = document.getElementById('attack-stat-hint');
            if (!hint) return;
            const info = describeAttackStatFromUi();
            hint.textContent = `使用${info.label} ${info.value}（自動取較高屬性）`;
        }

        function calcClientAttackDamage(multiplier, itemBonus = 0) {
            const info = describeAttackStatFromUi();
            const enemyRes = lastCombatStatus?.enemy?.resilience || 0;
            if (multiplier <= 0) return 0;
            const raw = ((info.value * 1.5) + COMBAT_ATTACK_BASE_DAMAGE + itemBonus) * multiplier - (enemyRes * 0.8);
            return Math.max(1, Math.floor(raw));
        }

        function isCombatModalOpen() {
            const modal = document.getElementById('combat-action-modal');
            return modal && !modal.classList.contains('hidden');
        }

        function clearActionModalRollTimer() {
            if (actionModalRollTimer) {
                clearInterval(actionModalRollTimer);
                actionModalRollTimer = null;
            }
            if (actionModalPauseTimer) {
                clearTimeout(actionModalPauseTimer);
                actionModalPauseTimer = null;
            }
        }

        function setCombatModalControlsLocked(locked) {
            ['modal-close-btn', 'modal-cancel-btn'].forEach(id => {
                const el = document.getElementById(id);
                if (!el) return;
                el.toggleAttribute('disabled', locked);
                el.classList.toggle('opacity-40', locked);
                el.classList.toggle('pointer-events-none', locked);
            });
        }

        function showCombatModalPanel(id, visible) {
            const el = document.getElementById(id);
            if (!el) return;
            el.classList.toggle('hidden', !visible);
            el.style.display = visible ? '' : 'none';
        }

        function resetCombatModalUi() {
            clearActionModalRollTimer();
            actionModalRolling = false;
            setCombatModalControlsLocked(false);
            showCombatModalPanel('modal-dice-area', true);
            showCombatModalPanel('modal-preview-area', false);
            showCombatModalPanel('modal-confirm-btn', false);
            const diceValue = document.getElementById('modal-dice-value');
            const diceBox = document.getElementById('modal-dice-box');
            if (diceValue) diceValue.textContent = '?';
            if (diceBox) {
                diceBox.style.transform = 'scale(1)';
                diceBox.classList.remove('animate-pulse', 'dice-crit');
            }
            document.getElementById('modal-dice-final')?.classList.add('hidden');
            const diceDesc = document.getElementById('modal-dice-desc');
            if (diceDesc) {
                diceDesc.textContent = '';
                diceDesc.classList.remove('text-yellow-400', 'font-bold');
            }
            document.getElementById('preview-warning')?.replaceChildren();
            const confirmBtn = document.getElementById('modal-confirm-btn');
            if (confirmBtn) confirmBtn.disabled = false;
        }

        function openCombatModal() {
            const modal = document.getElementById('combat-action-modal');
            if (!modal) return;
            resetCombatModalUi();
            modal.classList.remove('hidden');
            modal.classList.add('flex', 'items-center', 'justify-center');
            document.getElementById('modal-action-title').textContent = getActionDisplayName(selectedAction);
            document.getElementById('modal-status-hint').textContent = '系統正在擲骰…';
        }

        function hideCombatModal() {
            const modal = document.getElementById('combat-action-modal');
            if (!modal) return;
            modal.classList.add('hidden');
            modal.classList.remove('flex', 'items-center', 'justify-center');
        }

        function resetCombatDiceUi() {
            selectedDice = null;
            hideCombatModal();
            resetCombatModalUi();
        }

        function closeCombatModal() {
            if (actionModalRolling) return;
            hideCombatModal();
            resetCombatModalUi();
            selectedDice = null;
        }

        function rollDiceInModal() {
            if (actionModalRolling) return;
            const diceBox = document.getElementById('modal-dice-box');
            const diceValue = document.getElementById('modal-dice-value');
            const finalContainer = document.getElementById('modal-dice-final');
            const diceNumber = document.getElementById('modal-dice-number');
            const diceDesc = document.getElementById('modal-dice-desc');
            if (!diceBox || !diceValue) return;

            actionModalRolling = true;
            setCombatModalControlsLocked(true);
            document.querySelectorAll('.combat-action-btn, .combat-item-btn').forEach(el => { el.disabled = true; });

            diceBox.classList.remove('dice-crit');
            diceBox.classList.add('animate-pulse');
            finalContainer?.classList.add('hidden');
            if (diceDesc) {
                diceDesc.textContent = '';
                diceDesc.classList.remove('text-yellow-400', 'font-bold');
            }
            document.getElementById('modal-status-hint').textContent = '系統正在擲骰…';

            let rollCount = 0;
            const maxRolls = 14;
            clearActionModalRollTimer();
            actionModalRollTimer = setInterval(() => {
                diceValue.textContent = String(Math.floor(Math.random() * 4));
                diceBox.style.transform = `scale(${0.95 + Math.random() * 0.1})`;
                rollCount += 1;
                if (rollCount < maxRolls) return;

                clearInterval(actionModalRollTimer);
                actionModalRollTimer = null;

                const result = Math.floor(Math.random() * 4);
                selectedDice = result;
                diceValue.textContent = String(result);
                diceBox.style.transform = 'scale(1)';
                diceBox.classList.remove('animate-pulse', 'dice-crit');

                const description = DICE_RESULT_DESCRIPTIONS[result] || '';
                const isCrit = result === 3;
                if (isCrit) diceBox.classList.add('dice-crit');
                if (diceNumber) diceNumber.textContent = String(result);
                if (diceDesc) {
                    diceDesc.textContent = description;
                    diceDesc.classList.toggle('text-yellow-400', isCrit);
                    diceDesc.classList.toggle('font-bold', isCrit);
                }
                finalContainer?.classList.remove('hidden');

                document.getElementById('modal-status-hint').textContent =
                    `擲出 ${result} — ${description}`;

                actionModalRolling = false;
                setCombatModalControlsLocked(false);
                document.querySelectorAll('.combat-action-btn, .combat-item-btn').forEach(el => {
                    const canAct = lastCombatStatus?.status === 'player_phase' && !lastCombatStatus?.my_state?.submitted;
                    el.disabled = !canAct;
                });

                actionModalPauseTimer = setTimeout(() => {
                    actionModalPauseTimer = null;
                    fetchAndShowCombatPreview();
                }, DICE_RESULT_PAUSE_MS);
            }, 75);
        }

        function zooBonusMultiplier(sanity) {
            const s = parseInt(sanity, 10) || 0;
            if (s >= 100) return 1.8;
            if (s >= 90) return 1.5;
            if (s >= 80) return 1.4;
            if (s >= 70) return 1.3;
            return 1;
        }

        function parseStatText(id, fallback) {
            const raw = document.getElementById(id)?.textContent;
            const n = parseInt(raw, 10);
            return Number.isFinite(n) ? n : (fallback ?? 0);
        }

        function buildClientPreviewFallback(apiError) {
            const dice = selectedDice ?? 1;
            let multiplier = COMBAT_DICE_MULTIPLIERS[dice] ?? 1;
            const me = lastCombatStatus?.my_state || {};
            const enemy = lastCombatStatus?.enemy || {};
            const squad = currentSquad || {};
            const sanity = me.sanity ?? squad.sanity ?? 50;

            if (selectedAction === 'use_zoo') {
                multiplier *= zooBonusMultiplier(sanity);
            }

            const myDmg = ['attack', 'attack_physical', 'attack_nonphysical', 'use_zoo'].includes(selectedAction)
                ? calcClientAttackDamage(multiplier)
                : 0;
            const attackInfo = describeAttackStatFromUi();
            const resilience = me.resilience ?? parseStatText('combat-resilience-value', squad.resilience);
            const defending = selectedAction === 'defend';
            let counter = Math.max(0, (enemy.base_damage || 0) - Math.floor(resilience * 0.6));
            if (defending) counter = Math.max(0, Math.floor(counter * 0.5));

            const risks = [];
            if (apiError) {
                risks.push({ level: 'sanity', message: `${apiError}（以下為本地估算，仍可確認提交）` });
            }
            const hp = me.hp ?? parseStatText('combat-hp-value', squad.hp);
            if (counter > 0 && hp - counter < 20) {
                risks.push({
                    level: hp - counter <= 0 ? 'critical' : 'hp',
                    message: hp - counter <= 0
                        ? '反擊可能令你陷入瀕死或致命！'
                        : `反擊後生命值約 ${hp - counter}（低於 20）`,
                });
            }
            if (sanity < 20) {
                risks.push({ level: 'berserk', message: `神智 ${sanity}，暴走風險偏高` });
            }

            return {
                action_label: getActionDisplayName(selectedAction),
                dice_result: dice,
                attack_stat_label: attackInfo.label,
                attack_stat_value: attackInfo.value,
                my_damage_to_enemy: myDmg,
                ally_damage_to_enemy: 0,
                total_damage_to_enemy: myDmg,
                enemy_counter_damage: counter,
                counter_target_name: me.display_name || squad.display_name || '你',
                counter_defending: defending,
                counter_pending: false,
                phase_resolves_now: true,
                berserk_risk: sanity < 40,
                damage_if_normal: myDmg,
                risks,
                _fallback: true,
            };
        }

        function renderPreviewWarnings(risks) {
            const container = document.getElementById('preview-warning');
            if (!container) return;
            container.innerHTML = '';
            if (!risks || !risks.length) {
                container.innerHTML = '<div class="text-zinc-500">暫無額外危險提示</div>';
                return;
            }
            const styles = {
                critical: 'text-red-400 bg-red-900/30 border border-red-600',
                hp: 'text-red-300 bg-red-900/20 border border-red-700',
                sanity: 'text-orange-400 bg-orange-900/30 border border-orange-600',
                berserk: 'text-orange-300 bg-orange-900/40 border border-orange-500',
            };
            risks.forEach(r => {
                const div = document.createElement('div');
                div.className = `px-3 py-1.5 rounded-xl ${styles[r.level] || 'bg-zinc-800 text-zinc-300'}`;
                div.textContent = `⚠️ ${r.message}`;
                container.appendChild(div);
            });
        }

        function showPreviewInModal(preview) {
            if (!preview) return;
            const labels = ['失手', '普通', '良好', '爆擊'];
            const diceLabel = labels[preview.dice_result] ?? '';
            document.getElementById('modal-preview-summary').textContent =
                `${preview.action_label || ''} · 骰 ${preview.dice_result}（${diceLabel}）`;
            document.getElementById('modal-status-hint').textContent =
                `擲出 ${preview.dice_result}（${diceLabel}）· 請確認後結束本回合`;
            document.getElementById('preview-damage-enemy').textContent = preview.total_damage_to_enemy ?? 0;
            document.getElementById('preview-damage-player').textContent = preview.enemy_counter_damage ?? 0;

            const myNote = document.getElementById('modal-my-damage-note');
            if (myNote) {
                let note = `你造成 ${preview.my_damage_to_enemy ?? 0}`;
                if (preview.attack_stat_label && preview.attack_stat_value != null) {
                    note += `（${preview.attack_stat_label} ${preview.attack_stat_value}）`;
                }
                if (preview.ally_damage_to_enemy > 0) note += `，隊友已提交 ${preview.ally_damage_to_enemy}`;
                if (preview.berserk_risk) note += `（正常 ${preview.damage_if_normal ?? 0}；暴走可能 0）`;
                myNote.textContent = note;
            }

            const counterNote = document.getElementById('modal-counter-note');
            if (counterNote) {
                let note = preview.counter_target_name
                    ? `反擊目標：${preview.counter_target_name}`
                    : '預計對我方造成傷害';
                if (preview.counter_defending) note += '（防禦減半）';
                if (preview.counter_pending) note += ' · 待全隊提交';
                else if (preview.phase_resolves_now) note += ' · 本回合將結算';
                counterNote.textContent = note;
            }

            renderPreviewWarnings(preview.risks);
            if (COMBAT_DICE_ACTIONS.has(selectedAction)) {
                showCombatModalPanel('modal-dice-area', false);
            }
            showCombatModalPanel('modal-preview-area', true);
            showCombatModalPanel('modal-confirm-btn', true);

            const hint = document.getElementById('combat-submit-hint');
            if (hint) hint.textContent = '請於彈窗內確認並結束本回合';
        }

        async function fetchAndShowCombatPreview() {
            showCombatModalPanel('modal-preview-area', false);
            showCombatModalPanel('modal-confirm-btn', false);
            document.getElementById('modal-status-hint').textContent = '計算戰況預覽中…';

            const combatId = currentCombatId || lastCombatStatus?.combat_id;
            const payload = {
                combat_id: combatId,
                action_type: selectedAction,
                dice_result: selectedDice ?? 1,
            };
            if (selectedAction === 'use_item' && selectedItemId) {
                payload.item_id = selectedItemId;
            }

            let preview = null;
            let apiError = null;
            try {
                const res = await fetch('/combat/preview_action', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                const text = await res.text();
                let data = null;
                try {
                    data = JSON.parse(text);
                } catch (parseErr) {
                    apiError = res.status === 404
                        ? '伺服器尚未更新預覽 API'
                        : `預覽服務回應異常（HTTP ${res.status}）`;
                }
                if (data?.success && data.preview) {
                    preview = data.preview;
                } else if (!apiError) {
                    apiError = data?.error || `無法預覽戰況（HTTP ${res.status}）`;
                }
            } catch (e) {
                apiError = '無法連接預覽服務';
            }

            if (!preview) {
                preview = buildClientPreviewFallback(apiError);
            }
            showPreviewInModal(preview);
        }

        function confirmRound() {
            const btn = document.getElementById('modal-confirm-btn');
            if (btn?.disabled || actionModalRolling) return;
            btn.disabled = true;
            hideCombatModal();
            submitAction();
        }

        function performAction(action, opts = {}) {
            if (actionModalRolling || isCombatModalOpen()) return;
            const me = lastCombatStatus?.my_state || {};
            const inNearDeath = me.near_death_until && new Date(me.near_death_until) > new Date();
            if (lastCombatStatus?.status !== 'player_phase' || me.submitted || inNearDeath) return;

            selectedAction = action;
            if (action === 'use_item') {
                selectedItemId = opts.item_id != null ? opts.item_id : null;
                if (!selectedItemId) {
                    highlightCombatAction(action, opts);
                    return;
                }
            } else {
                selectedItemId = null;
            }
            highlightCombatAction(action, opts);
            openCombatModal();

            if (action === 'use_zoo') {
                const zooBtn = document.getElementById('zoo-action-btn');
                zooBtn?.classList.add('zoo-flash');
                setTimeout(() => zooBtn?.classList.remove('zoo-flash'), 600);
            }

            if (COMBAT_DICE_ACTIONS.has(action)) {
                rollDiceInModal();
                return;
            }

            selectedDice = 1;
            document.getElementById('modal-status-hint').textContent = '本回合戰況預覽';
            showCombatModalPanel('modal-dice-area', false);
            fetchAndShowCombatPreview();
        }

        async function loadCombatItems() {
            const listEl = document.getElementById('combat-item-list');
            if (!listEl) return;
            try {
                const res = await fetch('/my_items', { credentials: 'same-origin' });
                const data = await res.json();
                if (!data.success || !data.items || data.items.length === 0) {
                    listEl.innerHTML = '<div class="text-xs text-zinc-500 py-2 text-center">暫無可用物品</div>';
                    return;
                }
                listEl.innerHTML = data.items.map(item => `
                    <button type="button"
                            class="combat-item-btn combat-action-btn w-full py-2.5 bg-purple-900/30 hover:bg-purple-900/50 border border-purple-700 rounded-2xl text-sm text-left px-4 flex items-center gap-3"
                            data-action="use_item"
                            data-item-id="${item.item_id}"
                            onclick="performAction('use_item', {item_id: ${item.item_id}})">
                        <img src="${item.image_path || '/static/images/default-item.svg'}" class="w-8 h-8 rounded-lg object-cover shrink-0" alt="">
                        <span>使用「${escapeHtml(item.name)}」${item.effect_text ? `<span class="text-zinc-500 text-xs">（${escapeHtml(item.effect_text)}）</span>` : ''}</span>
                    </button>
                `).join('');
                combatItemsLoaded = true;
            } catch (e) {
                listEl.innerHTML = '<div class="text-xs text-red-400 py-2 text-center">物品載入失敗</div>';
            }
        }

        function exitCombatScreen() {
            setVisible(document.getElementById('combat-screen'), false);
            setVisible(document.getElementById('combat-result-panel'), false);
            setVisible(document.getElementById('combat-precheck-modal'), false);
            setVisible(document.getElementById('combat-near-death-overlay'), false);
            setVisible(document.getElementById('combat-lobby'), true);
            stopCombatPolling();
            resetCombatDiceUi();
            lastDicePhase = 0;
            lastCombatLogCount = 0;
            loadEncounters();
        }

        async function showCombatScreen() {
            setVisible(document.getElementById('combat-lobby'), false);
            setVisible(document.getElementById('combat-screen'), true);
            setVisible(document.getElementById('combat-result-panel'), false);
            document.querySelectorAll('.combat-action-btn[data-action]').forEach(btn => {
                if (btn.dataset.action !== 'use_item') {
                    btn.onclick = () => performAction(btn.dataset.action);
                }
            });
            if (!combatItemsLoaded) await loadCombatItems();
            resetCombatDiceUi();
            const me = lastCombatStatus?.my_state;
            const canAct = lastCombatStatus?.status === 'player_phase'
                && !(me?.near_death_until && new Date(me.near_death_until) > new Date())
                && !me?.submitted;
            const hint = document.getElementById('combat-submit-hint');
            if (hint) {
                hint.textContent = canAct ? '選擇行動後將彈出戰況預覽' : '';
            }
        }

        async function ensureCurrentSquadProfile() {
            if (currentSquad?.avatar) return;
            try {
                const res = await fetch('/status', { credentials: 'same-origin' });
                const data = await res.json();
                if (data && data.success !== false && data.squad_id) {
                    currentSquad = data;
                    initPlayerAvatar();
                }
            } catch (e) {
                console.warn('無法載入玩家資料', e);
            }
        }

        async function loadCombatPage() {
            stopCombatPolling();
            setVisible(document.getElementById('combat-lobby'), true);
            setVisible(document.getElementById('combat-screen'), false);
            await ensureCurrentSquadProfile();
            await loadEncounters();
            await loadCombatStatus(true);
        }

        async function loadEncounters() {
            const container = document.getElementById('encounter-list');
            if (!container) return;
            container.innerHTML = '<div class="text-zinc-400">載入 Encounter...</div>';

            try {
                const res = await fetch('/encounters', { credentials: 'same-origin' });
                const data = await res.json();
                if (!data.success) {
                    container.innerHTML = '<div class="text-red-400">載入失敗</div>';
                    return;
                }

                if (!data.encounters || data.encounters.length === 0) {
                    container.innerHTML = '<div class="text-zinc-400 cartoon-box p-6 text-center">暫無可用 Encounter（需達故事階段並選擇路線）</div>';
                    return;
                }

                container.innerHTML = '';
                data.encounters.forEach(enc => {
                    const card = document.createElement('div');
                    card.className = 'cartoon-box p-5';
                    const completed = enc.completed ? '<span class="text-xs px-2 py-1 bg-emerald-900/50 text-emerald-400 rounded-full">已完成</span>' : '';
                    const btn = enc.completed
                        ? ''
                        : `<button onclick="startEncounter('${enc.encounter_id}')" class="mt-3 px-4 py-2 theme-btn-primary rounded-xl text-sm font-medium">開始 Encounter</button>`;
                    card.innerHTML = `
                        <div class="flex items-start justify-between gap-3 mb-2">
                            <div class="font-bold text-lg">${enc.title || enc.encounter_id}</div>
                            ${completed}
                        </div>
                        <div class="text-xs text-zinc-500 mb-2">${enc.location_hint || ''}</div>
                        <p class="text-sm text-zinc-300">${enc.description || ''}</p>
                        ${enc.enemy_name ? `<div class="text-xs text-red-400/80 mt-2">敵人：${enc.enemy_name}</div>` : ''}
                        ${btn}
                    `;
                    container.appendChild(card);
                });

                if (data.active_combat) {
                    const hint = document.createElement('div');
                    hint.className = 'text-sm text-amber-400 cartoon-box p-4 cursor-pointer';
                    hint.innerHTML = '⚔️ 進行中的戰鬥 — <span class="underline">點擊繼續</span>';
                    hint.onclick = () => { showCombatScreen(); loadCombatStatus(true); };
                    container.prepend(hint);
                }
            } catch (e) {
                container.innerHTML = '<div class="text-red-400">載入失敗</div>';
            }
        }

        async function startEncounter(encounterId) {
            if (!confirm('確定開始此 Encounter？')) return;
            pendingEncounterId = encounterId;
            const res = await fetch('/combat/start', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ encounter_id: encounterId }),
            });
            const data = await res.json();
            if (!data.success) {
                alert(data.error || '無法開始');
                return;
            }
            currentCombatId = data.combat_id;
            showSection('combat');
            if (data.can_skip && data.status === 'precheck') {
                document.getElementById('precheck-modal-title').textContent = data.encounter?.title || '前置判定';
                document.getElementById('combat-precheck-text').textContent =
                    data.precheck_text || '你們有足夠洞察力看穿這是情緒勒索的扭曲模式。';
                setVisible(document.getElementById('combat-precheck-modal'), true);
                return;
            }
            showCombatScreen();
            updateCombatUI(data);
            await loadCombatStatus(true);
        }

        async function confirmPrecheck(choice) {
            const res = await fetch('/combat/start', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    encounter_id: pendingEncounterId,
                    confirm: choice,
                }),
            });
            const data = await res.json();
            if (!data.success) {
                alert(data.error || '操作失敗');
                return;
            }
            setVisible(document.getElementById('combat-precheck-modal'), false);
            if (data.skipped) {
                showCombatResult({ outcome: 'victory', narrative: data.narrative, reflection_prompt: data.reflection_prompt });
                const statusRes = await fetch('/status', { credentials: 'same-origin' });
                updateDashboard(await statusRes.json());
                return;
            }
            currentCombatId = data.combat_id;
            showCombatScreen();
            await loadCombatStatus(true);
        }

        function showCombatResult(data) {
            stopCombatPolling();
            setVisible(document.getElementById('combat-screen'), false);
            setVisible(document.getElementById('combat-near-death-overlay'), false);
            setVisible(document.getElementById('combat-precheck-modal'), false);
            setVisible(document.getElementById('combat-lobby'), false);
            setVisible(document.getElementById('combat-result-panel'), true);
            const victory = data.outcome === 'victory';
            document.getElementById('combat-result-title').textContent = victory ? '🎉 戰鬥勝利' : '💀 戰鬥失敗';
            document.getElementById('combat-result-narrative').textContent = data.narrative || '';
            const reflection = data.reflection_prompt;
            const reflectionBox = document.getElementById('combat-reflection');
            if (reflection) {
                setVisible(reflectionBox, true);
                document.getElementById('combat-reflection-title').textContent = reflection.title || '界線反思';
                document.getElementById('combat-reflection-theology').textContent = reflection.theological_tie || '';
                document.getElementById('combat-reflection-questions').innerHTML =
                    (reflection.questions || []).map((q, i) =>
                        `<li class="pl-3 border-l-2 border-amber-600/50"><span class="text-amber-500/80 text-xs">Q${i + 1}</span><br>${q}</li>`
                    ).join('');
            } else {
                setVisible(reflectionBox, false);
            }
        }

        function updateNearDeathOverlay(me) {
            const overlay = document.getElementById('combat-near-death-overlay');
            const countdownEl = document.getElementById('near-death-countdown');
            const inNearDeath = me?.near_death_until && new Date(me.near_death_until) > new Date();
            setVisible(overlay, !!inNearDeath);
            if (inNearDeath && countdownEl) {
                const remaining = Math.max(0, Math.floor((new Date(me.near_death_until) - Date.now()) / 1000));
                countdownEl.textContent = formatTimerDisplay(remaining);
            }
        }

        function updateCombatUI(data, options = {}) {
            if (!data) return;
            lastCombatStatus = data;
            setVisible(document.getElementById('combat-result-panel'), false);

            if (data.in_precheck) {
                setVisible(document.getElementById('combat-precheck-modal'), true);
                return;
            }

            const combatLive = data.active === true
                || ['player_phase', 'enemy_phase'].includes(data.status);
            if (!combatLive) {
                if (data.outcome) showCombatResult(data);
                return;
            }

            currentCombatId = data.combat_id || currentCombatId;
            showCombatScreen();
            applyCombatAccent(data.route);

            document.getElementById('combat-title').textContent = data.title || '戰鬥中';
            const routeLabel = ROUTE_SUBTITLES[data.route] || 'Encounter';
            const phaseNum = data.current_phase || 1;
            document.getElementById('combat-subtitle').textContent = `${routeLabel} · 第 ${phaseNum} 回合`;
            document.getElementById('current-phase').textContent = phaseNum;
            document.getElementById('max-phase').textContent = data.max_phases || 5;

            const phaseLabels = {
                player_phase: { text: 'Player Phase', color: 'text-emerald-400' },
                enemy_phase: { text: 'Enemy Phase', color: 'text-red-400' },
            };
            const pl = phaseLabels[data.status] || { text: data.status, color: 'text-zinc-400' };
            const phaseLabelEl = document.getElementById('phase-status-label');
            phaseLabelEl.textContent = pl.text;
            phaseLabelEl.className = `text-xs ${pl.color}`;

            updateEnemyCombatStats(data.enemy || {}, data.enemy_description || '');

            const me = data.my_state || {};
            const squad = currentSquad || {};
            updateCombatPlayerAvatar(me);
            document.getElementById('combat-player-name').textContent =
                me.display_name || squad.display_name || '你';
            document.getElementById('combat-player-team').textContent = squad.team?.team_name || squad.team_name || '單人';
            updateCombatPlayerStats(me, squad);
            updateAttackButtonHint();
            renderCombatTeamRow(data);

            const sanity = me.sanity ?? 100;
            const berserkBar = document.getElementById('combat-berserk-bar');
            const berserkChance = data.berserk_chance || 0;
            if (sanity < 40) {
                setVisible(berserkBar, true);
                let berserkMsg;
                if (sanity < 10) {
                    berserkMsg = `神智崩潰邊緣！暴走機率 ${berserkChance}% — 極高風險`;
                } else if (sanity < 20) {
                    berserkMsg = `神智危險！暴走機率 ${berserkChance}% — 提交前請確認`;
                } else {
                    berserkMsg = `神智偏低（${sanity}），暴走風險 ${berserkChance}%`;
                }
                document.getElementById('combat-berserk-bar-text').textContent = berserkMsg;
                berserkBar.classList.toggle('berserk-critical', sanity < 10);
            } else {
                setVisible(berserkBar, false);
                berserkBar.classList.remove('berserk-critical');
            }

            setVisible(document.getElementById('combat-berserk-overlay'),
                sanity < 10 && data.status === 'player_phase' && !me.submitted);

            const zooHint = document.getElementById('zoo-hint');
            if (zooHint) {
                if (sanity >= 100) zooHint.textContent = 'Zoo 加成 ×1.8';
                else if (sanity >= 90) zooHint.textContent = 'Zoo 加成 ×1.5';
                else if (sanity >= 80) zooHint.textContent = 'Zoo 加成 ×1.4';
                else if (sanity >= 70) zooHint.textContent = 'Zoo 加成 ×1.3 ✓';
                else zooHint.textContent = `神智 ${sanity}，需 ≥70`;
                zooHint.className = sanity >= 70 ? 'text-[10px] text-orange-300 font-medium' : 'text-[10px] text-zinc-500';
            }

            if (data.phase_deadline && data.status === 'player_phase') {
                startPhaseCountdown(data.phase_deadline);
            } else if (data.phase_expired) {
                document.getElementById('phase-timer').textContent = '0:00';
            }

            const logEl = document.getElementById('combat-log');
            logEl.innerHTML = (data.log || []).map(line => `<div class="py-0.5">• ${line}</div>`).join('')
                || '<div class="text-zinc-500">尚無戰鬥記錄</div>';
            logEl.scrollTop = logEl.scrollHeight;
            processCombatDamageAnimations(
                data,
                options.damageDelay ?? 0,
                !!options.initLogsOnly,
            );

            const inNearDeath = me.near_death_until && new Date(me.near_death_until) > new Date();
            updateNearDeathOverlay(me);

            const hintEl = document.getElementById('combat-submit-hint');
            const actionContainer = document.getElementById('player-panel');
            const canAct = data.status === 'player_phase' && !inNearDeath && !me.submitted;
            if (actionContainer) actionContainer.style.opacity = canAct ? '1' : '0.55';
            document.querySelectorAll('.combat-action-btn, .combat-item-btn').forEach(el => {
                el.disabled = !canAct || actionModalRolling;
            });
            if (canAct && phaseNum !== lastDicePhase) {
                lastDicePhase = phaseNum;
                resetCombatDiceUi();
            } else if (me.submitted || !canAct) {
                hideCombatModal();
            }
            if (hintEl) {
                if (inNearDeath) hintEl.textContent = '你已瀕死，等待隊友救援';
                else if (me.submitted) hintEl.textContent = `已提交：${COMBAT_ACTION_LABELS[me.action_type] || me.action_type}（骰 ${me.dice_result ?? '?' }），等待隊友…`;
                else if (data.status !== 'player_phase') hintEl.textContent = '敵人回合結算中…';
                else if (actionModalRolling) hintEl.textContent = '系統擲骰中，請稍候…';
                else if (isCombatModalOpen()) hintEl.textContent = '請於彈窗內確認並結束本回合';
                else if (selectedAction === 'use_item' && !selectedItemId) hintEl.textContent = '請選擇要使用的物品';
                else hintEl.textContent = '選擇行動後將彈出戰況預覽';
            }
        }

        async function loadCombatStatus(showLoading) {
            try {
                const url = currentCombatId
                    ? `/combat/status?combat_id=${currentCombatId}`
                    : '/combat/status';
                const res = await fetch(url, { credentials: 'same-origin' });
                const data = await res.json();
                if (!data.success) return;
                if (data.outcome) {
                    showCombatResult(data);
                    const statusRes = await fetch('/status', { credentials: 'same-origin' });
                    updateDashboard(await statusRes.json());
                    return;
                }
                if (data.active) {
                    setVisible(document.getElementById('combat-lobby'), false);
                }
                updateCombatUI(data, showLoading ? { initLogsOnly: true } : {});
                if (data.active || data.in_precheck) startCombatPolling();
                else stopCombatPolling();
            } catch (e) {
                if (showLoading) console.error('載入戰鬥狀態失敗', e);
            }
        }

        async function submitAction() {
            if (selectedAction === 'use_item' && !selectedItemId) {
                alert('請先選擇要使用的物品');
                return;
            }
            if (COMBAT_DICE_ACTIONS.has(selectedAction) && selectedDice === null) {
                alert('請先選擇攻擊行動並完成擲骰');
                return;
            }
            if (selectedDice === null) selectedDice = 1;

            const confirmBtn = document.getElementById('modal-confirm-btn');
            if (confirmBtn) confirmBtn.disabled = true;

            const payload = {
                combat_id: currentCombatId,
                action_type: selectedAction,
                dice_result: selectedDice,
            };
            if (selectedAction === 'use_item' && selectedItemId) payload.item_id = selectedItemId;

            let data;
            try {
                const res = await fetch('/combat/submit_action', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                data = await res.json();
            } catch (e) {
                if (confirmBtn) confirmBtn.disabled = false;
                alert('提交失敗，請稍後再試');
                return;
            }
            if (!data.success && data.error) {
                if (confirmBtn) confirmBtn.disabled = false;
                alert(data.error);
                return;
            }
            if (data.outcome) {
                if (data.log_entries?.length) {
                    processCombatDamageAnimations(data, 200);
                }
                showCombatResult(data);
                const statusRes = await fetch('/status', { credentials: 'same-origin' });
                updateDashboard(await statusRes.json());
                combatItemsLoaded = false;
                return;
            }
            resetCombatDiceUi();
            lastDicePhase = 0;
            updateCombatUI({ ...data, active: true }, { damageDelay: 350 });
        }

        async function rescueNearDeath() {
            if (!confirm('為瀕死隊友發起禱告救援？（每次縮短 5 分鐘）')) return;
            const res = await fetch('/combat/rescue_near_death', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ combat_id: currentCombatId, rescue_type: 'prayer' }),
            });
            const data = await res.json();
            if (!data.success) {
                alert(data.error || '救援失敗');
                return;
            }
            if (data.rescued) setVisible(document.getElementById('combat-near-death-overlay'), false);
            const logEl = document.getElementById('combat-log');
            if (logEl && data.message) {
                const line = document.createElement('div');
                line.className = 'py-0.5 text-emerald-400';
                line.textContent = `• ${data.message}`;
                logEl.appendChild(line);
                logEl.scrollTop = logEl.scrollHeight;
            }
            await loadCombatStatus(false);
        }

        async function loadStoryLog() {
            const container = document.getElementById('story-log-content');
            container.innerHTML = '<div class="text-zinc-400">載入故事中...</div>';

            try {
                const res = await fetch('/story_progress', { credentials: 'same-origin' });
                const data = await res.json();

                const stage = data.stage || 0;
                const completed = data.completed_tasks || 0;
                const story = data.story || {};
                const title = story.title || '故事進行中';
                const content = story.content || '';

                let progressHint = '';
                if (data.next_stage_at != null) {
                    const remaining = Math.max(0, data.next_stage_at - completed);
                    progressHint = `<div class="text-xs text-zinc-500 mt-3">距離下一階段還需 ${remaining} 個新任務（門檻：${data.next_stage_at} 個）</div>`;
                } else if (stage >= 3) {
                    progressHint = `<div class="text-xs text-amber-400/80 mt-3">你已達最終故事階段</div>`;
                }

                let encounterHint = '';
                try {
                    const encRes = await fetch('/encounters', { credentials: 'same-origin' });
                    const encData = await encRes.json();
                    const available = (encData.encounters || []).filter(e => !e.completed);
                    if (available.length) {
                        encounterHint = `
                            <div class="mt-4 p-4 bg-red-900/20 border border-red-700/40 rounded-2xl">
                                <div class="text-sm font-medium text-red-300 mb-2">⚔️ 可進行 Encounter</div>
                                ${available.map(e => `
                                    <div class="text-sm text-zinc-300 mb-2">${e.title}</div>
                                    <button onclick="showSection('combat')" class="text-xs px-3 py-1 bg-red-800/60 hover:bg-red-700 rounded-xl">前往戰鬥</button>
                                `).join('')}
                            </div>`;
                    }
                } catch (_) {}

                container.innerHTML = `
                    <div class="mb-3 flex flex-wrap gap-2">
                        <div class="inline-block px-3 py-1 bg-zinc-700 rounded-full text-xs">
                            已完成任務：${completed} 個
                        </div>
                        <div class="inline-block px-3 py-1 bg-zinc-800 border border-zinc-600 rounded-full text-xs">
                            故事階段：Stage ${stage}
                        </div>
                    </div>
                    <div class="text-xl font-bold mb-2">${title}</div>
                    <div class="text-zinc-300 leading-relaxed">${content}</div>
                    ${progressHint}
                    ${encounterHint}
                `;

            } catch (e) {
                container.innerHTML = '<div class="text-red-400">載入故事失敗</div>';
            }
        }

        function renderTeamTaskLogEntries(container, logs, options = {}) {
            const { showPlayer = false, emptyText = '暫無任務記錄' } = options;

            if (!logs || logs.length === 0) {
                container.innerHTML = `<div class="text-zinc-400 py-6 text-center">${emptyText}</div>`;
                return;
            }

            container.innerHTML = '';
            logs.forEach(log => {
                const taskName = log.task_name || log.task_id || '未知任務';
                const description = log.description || log.content || '';
                const status = log.status || '已完成';
                const el = document.createElement('div');
                el.className = 'log-item bg-zinc-800 border border-zinc-700 rounded-2xl p-4';
                el.innerHTML = `
                    <div class="flex justify-between items-start gap-x-3 mb-2">
                        <div>
                            ${showPlayer ? `<strong class="text-zinc-100">${log.display_name}</strong>` : ''}
                            <span class="text-xs px-2 py-0.5 bg-emerald-900/50 text-emerald-400 rounded-full ml-1">${status}</span>
                        </div>
                        <div class="text-xs text-zinc-500 whitespace-nowrap">${log.timestamp}</div>
                    </div>
                    <div class="text-sm">
                        <strong class="text-zinc-300">任務：</strong>
                        <span class="font-mono text-amber-400">${taskName}</span>
                    </div>
                    ${description ? `<div class="text-zinc-400 text-sm mt-1">${description}</div>` : ''}
                    ${(log.photo_url || log.photo_path) ? `
                        <div class="mt-2">
                            <img src="${log.photo_url || '/' + log.photo_path}" class="max-h-48 rounded-xl border border-zinc-700">
                        </div>
                    ` : ''}
                `;
                container.appendChild(el);
            });
        }

        async function loadTeamTaskLogs() {
            const logPageContainer = document.getElementById('team-task-logs');
            const teamPageContainer = document.getElementById('team-task-logs-list');
            const titleEl = document.getElementById('team-task-logs-title');

            if (!logPageContainer && !teamPageContainer) return;

            if (logPageContainer) logPageContainer.innerHTML = '<div class="text-zinc-400">載入中...</div>';
            if (teamPageContainer) teamPageContainer.innerHTML = '<div class="text-zinc-400">載入中...</div>';

            try {
                const res = await fetch('/team_task_logs', { credentials: 'same-origin' });
                const data = await res.json();

                if (logPageContainer) {
                    if (titleEl) {
                        titleEl.textContent = data.has_team ? '👥 全隊任務日誌' : '📋 個人任務日誌';
                    }
                    renderTeamTaskLogEntries(logPageContainer, data.logs, {
                        showPlayer: !!data.has_team,
                        emptyText: data.has_team ? '全隊尚未有任務記錄' : '暫無任務記錄',
                    });
                }

                if (teamPageContainer) {
                    if (!data.has_team) {
                        teamPageContainer.innerHTML = '<div class="text-zinc-400 py-4 text-center">你尚未加入 Team</div>';
                    } else {
                        renderTeamTaskLogEntries(teamPageContainer, data.logs, {
                            showPlayer: true,
                            emptyText: '全隊尚未有任務記錄',
                        });
                    }
                }
            } catch (e) {
                console.error('載入任務日誌失敗', e);
                if (logPageContainer) logPageContainer.innerHTML = '<div class="text-red-400">載入失敗</div>';
                if (teamPageContainer) teamPageContainer.innerHTML = '<div class="text-red-400">載入失敗</div>';
            }
        }

        function formatGlobalEffect(ev) {
            if (!ev.effect_type || ev.effect_type === 'announcement') return '';
            const labels = {
                adjust_sanity: '神智調整',
                sanity_adjust: '神智調整',
                sanity_down: '神智下降',
                sanity_up: '神智上升',
                power_up: '力量上升',
                intellect_up: '智力上升',
                resilience_up: '韌性上升',
                judas_strengthen: 'Judas 加強',
                iggy_collapse: 'Iggy 崩潰',
                global_debuff: '全球減益',
            };
            const label = labels[ev.effect_type] || ev.effect_type;
            if (ev.effect_value) {
                const sign = ev.effect_value > 0 ? '+' : '';
                return `${label} ${sign}${ev.effect_value}`;
            }
            return label;
        }

        async function loadGlobalEvents() {
            const container = document.getElementById('global-events-list');
            if (!container) return;
            container.innerHTML = '<div class="text-zinc-400">載入中...</div>';

            const eventIcons = {
                adjust_sanity: '🧠',
                sanity_adjust: '🧠',
                sanity_down: '🧠',
                sanity_up: '🧠',
                power_up: '⚡',
                intellect_up: '📚',
                resilience_up: '🛡️',
                judas_strengthen: '⚔️',
                iggy_collapse: '🔥',
                announcement: '📢',
                global_debuff: '💀',
            };

            try {
                const res = await fetch('/global_events', { credentials: 'same-origin' });
                const data = await res.json();

                if (!data.events || data.events.length === 0) {
                    container.innerHTML = '<div class="text-zinc-400 py-4 text-center">暫無全球事件</div>';
                    return;
                }

                container.innerHTML = '';
                data.events.forEach(event => {
                    const icon = eventIcons[event.effect_type] || '🌍';
                    const effectText = formatGlobalEffect(event);
                    const el = document.createElement('div');
                    el.className = 'global-event-item bg-zinc-800 border border-zinc-700 rounded-2xl p-4';
                    el.innerHTML = `
                        <div class="flex justify-between items-start gap-x-3">
                            <div class="flex gap-x-2 min-w-0">
                                <span class="text-lg shrink-0">${icon}</span>
                                <div class="min-w-0">
                                    <div class="font-semibold text-red-400">${event.title}</div>
                                    ${event.description ? `<div class="text-zinc-300 text-sm mt-1 leading-relaxed">${event.description}</div>` : ''}
                                    ${event.effect_type ? `
                                        <div class="mt-2 flex flex-wrap items-center gap-2 text-xs">
                                            <span class="px-2 py-0.5 bg-zinc-700 rounded-full text-zinc-300">${event.effect_type}</span>
                                            <span class="text-zinc-400">數值: ${event.effect_value ?? 0}</span>
                                            ${effectText ? `<span class="text-amber-400">${effectText}</span>` : ''}
                                        </div>
                                    ` : ''}
                                    ${event.created_by ? `<div class="text-xs text-zinc-500 mt-1">由 ${event.created_by} 觸發</div>` : ''}
                                </div>
                            </div>
                            <div class="text-xs text-zinc-500 whitespace-nowrap shrink-0">${event.timestamp}</div>
                        </div>
                    `;
                    container.appendChild(el);
                });
            } catch (e) {
                container.innerHTML = '<div class="text-red-400">載入失敗</div>';
            }
        }

        function closeModal(el) {
            const modal = el?.closest?.('.modal-overlay') || el?.closest?.('.fixed');
            if (modal) modal.remove();
        }

        const CAPPED_SQUAD_STATS = new Set(['hp', 'sanity']);
        const SQUAD_CAP_MAX = { hp: 100, sanity: 100 };
        const DASHBOARD_STAT_META = {
            hp: { text: 'text-red-400', bar: 'bg-red-500' },
            sanity: { text: 'text-purple-400', bar: 'bg-purple-500' },
            power: { text: 'text-orange-400' },
            intellect: { text: 'text-blue-400' },
            resilience: { text: 'text-emerald-400' },
        };

        function setStatBar(prefix, stat, value, options = {}) {
            const meta = DASHBOARD_STAT_META[stat] || {};
            const el = document.getElementById(prefix + stat + '-value');
            const raw = Number(value) || 0;
            const showRatio = options.showRatio ?? !prefix;

            if (!CAPPED_SQUAD_STATS.has(stat)) {
                if (el) {
                    el.textContent = String(raw);
                    if (!prefix) {
                        el.className = `font-mono text-lg font-bold ${meta.text || 'text-zinc-300'}`;
                    }
                }
                return;
            }

            const max = SQUAD_CAP_MAX[stat] || 100;
            const v = Math.max(0, Math.min(max, raw));
            const pct = Math.round((v / max) * 100);
            const bar = document.getElementById(prefix + stat + '-bar');
            const pctEl = document.getElementById(prefix + stat + '-pct');
            if (el) {
                el.textContent = showRatio ? `${v} / ${max}` : String(v);
            }
            if (pctEl) pctEl.textContent = `(${pct}%)`;
            if (bar) bar.style.width = `${pct}%`;
        }

        function updateCombatPlayerStats(me, squad) {
            const stats = {
                hp: me.hp ?? squad.hp ?? 100,
                sanity: me.sanity ?? squad.sanity ?? 100,
                power: me.power ?? squad.power ?? 0,
                intellect: me.intellect ?? squad.intellect ?? 0,
                resilience: me.resilience ?? squad.resilience ?? 0,
            };
            ['hp', 'sanity', 'power', 'intellect', 'resilience'].forEach(s => {
                setStatBar('combat-', s, stats[s], { showRatio: true });
            });
            const setTextIf = (id, value) => {
                const el = document.getElementById(id);
                if (el) el.textContent = value ?? '—';
            };
            setTextIf('combat-player-hp', stats.hp);
            setTextIf('combat-player-sanity', stats.sanity);
            setTextIf('combat-m-power', stats.power);
            setTextIf('combat-m-intellect', stats.intellect);
            setTextIf('combat-m-resilience', stats.resilience);
        }

        function updateEnemyCombatStats(enemy, description) {
            const setTextIf = (id, value) => {
                const el = document.getElementById(id);
                if (el) el.textContent = value ?? '—';
            };
            setTextIf('enemy-name', enemy.name || '敵人');
            const quoteEl = document.getElementById('enemy-quote');
            if (quoteEl) quoteEl.textContent = description || '';
            const hp = enemy.hp ?? 0;
            const maxHp = enemy.max_hp || enemy.hp || 1;
            setTextIf('enemy-hp-current', hp);
            setTextIf('enemy-hp-max', maxHp);
            setTextIf('enemy-stat-hp', hp);
            setTextIf('enemy-stat-sanity', enemy.sanity);
            setTextIf('enemy-stat-power', enemy.power);
            setTextIf('enemy-stat-intellect', enemy.intellect);
            setTextIf('enemy-stat-resilience', enemy.resilience);
            const enemyHpBar = document.getElementById('enemy-hp-bar');
            const prevEnemyHp = lastCombatStatus?.enemy?.hp;
            if (enemyHpBar) {
                enemyHpBar.style.width =
                    `${Math.max(0, Math.min(100, Math.round((hp || 0) / maxHp * 100)))}%`;
                if (prevEnemyHp != null && hp != null && hp < prevEnemyHp) {
                    flashEnemyHpBar();
                }
            }
        }

        function renderCombatTeamRow(data) {
            const container = document.getElementById('team-status-row');
            const teamStrip = document.getElementById('combat-team-strip');
            if (!container) return;

            const myId = data.my_squad_id || currentSquad?.squad_id;
            const members = data.member_states || {};
            const route = data.route || currentSquad?.route;
            const protagonists = data.protagonists || currentSquad?.protagonists || {};
            const chips = [];

            Object.entries(members).forEach(([sid, m]) => {
                const isMe = sid === myId;
                const label = isMe ? '你' : (m.display_name || sid);
                const avatarSrc = m.avatar ? `/static/avatars/${m.avatar}` : '/static/avatars/default.png';
                chips.push(`
                    <div class="combat-team-chip flex-shrink-0 text-center min-w-[52px] ${isMe ? 'team-card-me rounded-xl px-1' : ''}">
                        <img src="${avatarSrc}" class="w-8 h-8 rounded-full border border-zinc-600 mx-auto mb-0.5 object-cover" alt="">
                        <div class="text-[10px] text-zinc-300 truncate max-w-[64px]">${label}</div>
                        <div class="text-[10px] font-mono text-zinc-400">❤️${m.hp ?? '?'} 🧠${m.sanity ?? '?'}</div>
                    </div>
                `);
            });

            [
                { key: 'iggy', label: '🔥 Iggy', accent: 'text-red-400' },
                { key: 'marah', label: '🌊 Marah', accent: 'text-blue-400' },
            ].forEach(({ key, label, accent }) => {
                const p = protagonists[key];
                if (!p) return;
                const active = route === key;
                chips.push(`
                    <div class="combat-team-chip flex-shrink-0 text-center min-w-[52px] border-l border-zinc-700 pl-3 ${active ? '' : 'opacity-60'}">
                        <div class="w-8 h-8 rounded-full border border-amber-600/50 mx-auto mb-0.5 flex items-center justify-center text-xs">${key === 'iggy' ? '🔥' : '🌊'}</div>
                        <div class="text-[10px] ${accent}">${label}${active ? '（主角）' : ''}</div>
                        <div class="text-[10px] font-mono text-zinc-400">❤️${p.hp ?? '?'} 🧠${p.sanity ?? '?'}</div>
                    </div>
                `);
            });

            container.innerHTML = chips.length
                ? chips.join('')
                : '<div class="text-[10px] text-zinc-500 py-1">暫無隊友資料</div>';
            if (teamStrip) setVisible(teamStrip, true);
        }

        function updateDashboardAttackHint(squad) {
            const hint = document.getElementById('dashboard-attack-hint');
            if (!hint) return;
            const power = Number(squad?.power) || 0;
            const intellect = Number(squad?.intellect) || 0;
            const attack = Math.max(power, intellect);
            if (power > intellect) hint.textContent = `攻擊力：力量 ${attack}`;
            else if (intellect > power) hint.textContent = `攻擊力：智力 ${attack}`;
            else hint.textContent = `攻擊力：${attack}（力量／智力相同）`;
        }

        function setText(id, value) {
            const el = document.getElementById(id);
            if (el) el.textContent = value ?? 0;
        }

        async function editDisplayName() {
            const current = currentSquad.display_name || currentSquad.squad_id;
            const newName = prompt('輸入新顯示名稱（最多 20 字）', current);
            if (!newName || newName.trim() === current) return;

            const res = await fetch('/update_display_name', {
                method: 'POST',
                credentials: 'same-origin',
                body: new URLSearchParams({display_name: newName.trim()})
            });
            const data = await res.json();

            if (data.success) {
                currentSquad.display_name = data.display_name;
                document.getElementById('squad-name').textContent = data.display_name;
                alert('名稱已更新！');
            } else {
                alert(data.error || '更新失敗');
            }
        }

        async function editTeamName(teamId, currentName) {
            const newName = prompt('輸入新隊名（最多 30 字）', currentName);
            if (!newName || newName.trim() === currentName) return;

            const res = await fetch('/team/update_name', {
                method: 'POST',
                credentials: 'same-origin',
                body: new URLSearchParams({ team_name: newName.trim() })
            });

            const data = await res.json();

            if (data.success) {
                document.getElementById('my-team-name').textContent = data.team_name;
                loadAvailableTeams();
                alert('隊名已更新！');
            } else {
                alert(data.error || '更新失敗');
            }
        }

        function renderProtagonistStats(prefix, stats) {
            ['hp', 'sanity', 'power', 'intellect', 'resilience'].forEach(s => {
                setStatBar(prefix, s, stats?.[s] ?? 100);
            });
        }

        function showOnlyProtagonistCard(route, protagonists) {
            const iggyCard = document.getElementById('iggy-card');
            const marahCard = document.getElementById('marah-card');
            if (!iggyCard || !marahCard) return;

            iggyCard.style.display = 'none';
            marahCard.style.display = 'none';
            iggyCard.classList.remove('ring-2', 'ring-amber-500/50');
            marahCard.classList.remove('ring-2', 'ring-amber-500/50');

            const iggy = protagonists?.iggy || {};
            const marah = protagonists?.marah || {};

            if (route === 'iggy') {
                iggyCard.style.display = 'block';
                iggyCard.classList.add('ring-2', 'ring-amber-500/50');
                renderProtagonistStats('iggy-', iggy);
            } else if (route === 'marah') {
                marahCard.style.display = 'block';
                marahCard.classList.add('ring-2', 'ring-amber-500/50');
                renderProtagonistStats('marah-', marah);
            }
        }

        function buildProtagonistCardHtml(title, prefix, stats, isActive) {
            const ring = isActive ? 'ring-active-route' : '';
            const statsList = ['hp', 'sanity', 'power', 'intellect', 'resilience'];
            const labels = {hp: '❤️ 生命值', sanity: '🧠 神智', power: '⚡ 力量', intellect: '📖 智力', resilience: '🛡️ 韌性'};
            const colors = {hp: 'text-red-400', sanity: 'text-purple-400', power: 'text-orange-400', intellect: 'text-blue-400', resilience: 'text-emerald-400'};
            const barColors = {hp: 'bg-red-500', sanity: 'bg-purple-500', power: 'bg-orange-500', intellect: 'bg-blue-500', resilience: 'bg-emerald-500'};
            const rows = statsList.map(s => `
                <div>
                    <div class="flex justify-between text-xs mb-1"><span>${labels[s]}</span><span class="font-mono ${colors[s]}">${stats?.[s] ?? 100}</span></div>
                    <div class="h-2 stat-track rounded-full"><div class="h-2 rounded-full status-bar ${barColors[s]}" style="width:${stats?.[s] ?? 100}%"></div></div>
                </div>
            `).join('');
            return `
                <div class="cartoon-box p-5 ${ring}">
                    <h3 class="font-bold mb-4 theme-card-title">${title}${isActive ? ' <span class="text-xs theme-accent-text">(使用中)</span>' : ''}</h3>
                    <div class="space-y-2">${rows}</div>
                </div>
            `;
        }

        function renderTeamProtagonists(protagonists) {
            const section = document.getElementById('team-protagonists-section');
            if (!section) return;
            const route = protagonists?.active_route;
            if (!protagonists || !route) {
                section.classList.add('hidden');
                section.innerHTML = '';
                return;
            }
            section.classList.remove('hidden');
            if (route === 'iggy') {
                section.innerHTML = buildProtagonistCardHtml('🔥 Iggy', 'iggy', protagonists.iggy, true);
            } else if (route === 'marah') {
                section.innerHTML = buildProtagonistCardHtml('🌊 Marah', 'marah', protagonists.marah, true);
            } else {
                section.classList.add('hidden');
                section.innerHTML = '';
            }
        }

        const THEME_VARS = {
            default: {
                '--bg-main': '#0D0D0D',
                '--bg-color': '#0D0D0D',
                '--bg-gradient-start': '#0D0D0D',
                '--bg-gradient-mid': '#141414',
                '--bg-gradient-end': '#141414',
                '--bg-glow': 'transparent',
                '--card-bg': '#1F1F1F',
                '--card-border': '#555555',
                '--text-primary': '#FFFFFF',
                '--text-secondary': '#AAAAAA',
                '--text-color': '#FFFFFF',
                '--text-muted': '#AAAAAA',
                '--accent-gold': '#FFFFFF',
                '--accent-orange': '#888888',
                '--accent-color': '#FFFFFF',
                '--accent-contrast': '#0D0D0D',
                '--accent-soft': 'rgba(255, 255, 255, 0.12)',
                '--progress-bg': '#333333',
                '--progress-track': '#333333',
                '--progress-color': '#888888',
                '--header-border': 'rgba(63, 63, 70, 0.8)',
                '--shadow-color': 'rgba(44, 62, 80, 0.6)',
                '--card-glow': 'none',
            },
            iggy: {
                '--bg-main': '#0D0D0D',
                '--bg-color': '#0D0D0D',
                '--bg-gradient-start': '#3D1A2E',
                '--bg-gradient-mid': '#1a0f14',
                '--bg-gradient-end': '#0D0D0D',
                '--bg-glow': 'rgba(212, 160, 23, 0.1)',
                '--card-bg': '#4A1C2E',
                '--card-border': '#D4A017',
                '--text-primary': '#F5E8C7',
                '--text-secondary': '#C9A36A',
                '--text-color': '#F5E8C7',
                '--text-muted': '#C9A36A',
                '--accent-gold': '#D4A017',
                '--accent-orange': '#E07A5F',
                '--accent-color': '#D4A017',
                '--accent-contrast': '#1a0f14',
                '--accent-soft': 'rgba(212, 160, 23, 0.22)',
                '--progress-bg': '#3D1A2E',
                '--progress-track': '#3D1A2E',
                '--progress-color': '#E07A5F',
                '--header-border': 'rgba(212, 160, 23, 0.45)',
                '--shadow-color': 'rgba(61, 26, 46, 0.85)',
                '--card-glow': '0 0 24px rgba(212, 160, 23, 0.18), inset 0 1px 0 rgba(212, 160, 23, 0.15)',
            },
            marah: {
                '--bg-main': '#0D0D0D',
                '--bg-color': '#0D0D0D',
                '--bg-gradient-start': '#152033',
                '--bg-gradient-mid': '#0f1a2e',
                '--bg-gradient-end': '#0D0D0D',
                '--bg-glow': 'rgba(74, 144, 164, 0.08)',
                '--card-bg': '#1E2A44',
                '--card-border': '#4A90A4',
                '--text-primary': '#E8E8E8',
                '--text-secondary': '#9ca8b8',
                '--text-color': '#E8E8E8',
                '--text-muted': '#9ca8b8',
                '--accent-gold': '#C0C0C0',
                '--accent-orange': '#4A90A4',
                '--accent-color': '#C0C0C0',
                '--accent-contrast': '#0f1520',
                '--accent-soft': 'rgba(74, 144, 164, 0.28)',
                '--progress-bg': '#152033',
                '--progress-track': '#152033',
                '--progress-color': '#4A90A4',
                '--header-border': 'rgba(74, 144, 164, 0.38)',
                '--shadow-color': 'rgba(30, 42, 68, 0.75)',
                '--card-glow': '0 0 20px rgba(74, 144, 164, 0.12), inset 0 1px 0 rgba(192, 192, 192, 0.08)',
            },
        };

        function applyThemeVars(themeName) {
            const root = document.documentElement;
            const vars = THEME_VARS[themeName] || THEME_VARS.default;
            Object.entries(vars).forEach(([key, value]) => {
                root.style.setProperty(key, value);
            });
        }

        function applyDefaultTheme() {
            applyThemeVars('default');
        }

        function applyIggyTheme() {
            applyThemeVars('iggy');
        }

        function applyMarahTheme() {
            applyThemeVars('marah');
        }

        function applyRouteTheme(route) {
            const body = document.body;
            body.classList.remove('theme-iggy', 'theme-marah');
            if (route === 'iggy') {
                body.classList.add('theme-iggy');
                applyIggyTheme();
            } else if (route === 'marah') {
                body.classList.add('theme-marah');
                applyMarahTheme();
            } else {
                applyDefaultTheme();
            }
        }

        function updateDashboard(data) {
            const squad = data.squad_id ? data : (data.squad || data);
            const protagonists = data.protagonists || squad.protagonists;
            const route = data.route || data.team?.route || squad.route;

            applyRouteTheme(route);

            ['hp','sanity','power','intellect','resilience'].forEach(s => setStatBar('', s, squad[s] ?? 100));
            document.getElementById('resource-value').textContent = squad.resources || 0;
            const insightEl = document.getElementById('insight-value');
            if (insightEl) insightEl.textContent = squad.insight_fragments || 0;
            const displayName = squad.display_name || squad.squad_id;
            document.getElementById('squad-name').textContent = displayName;
            const dashName = document.getElementById('dashboard-player-name');
            if (dashName) dashName.textContent = displayName;
            updateDashboardAttackHint(squad);

            const routePicker = document.getElementById('route-picker');
            const routeBadge = document.getElementById('route-badge');
            const isLeader = squad.is_team_leader === 1;
            const inTeam = !!(squad.team_id || data.team);

            showOnlyProtagonistCard(route, protagonists || {});

            if (routePicker) setVisible(routePicker, !route && (!inTeam || isLeader));

            if (routeBadge) {
                if (route === 'iggy') {
                    setVisible(routeBadge, true);
                    routeBadge.innerHTML = `<span class="inline-flex items-center gap-x-1 px-3 py-1 bg-red-900/60 text-red-400 rounded-full text-xs font-medium">🔥 Iggy 路線</span>`;
                } else if (route === 'marah') {
                    setVisible(routeBadge, true);
                    routeBadge.innerHTML = `<span class="inline-flex items-center gap-x-1 px-3 py-1 bg-blue-900/60 text-blue-400 rounded-full text-xs font-medium">🌊 Marah 路線</span>`;
                } else if (inTeam && !isLeader) {
                    setVisible(routeBadge, true);
                    routeBadge.innerHTML = `<span class="text-xs text-zinc-400">等待隊長選擇路線...</span>`;
                } else {
                    setVisible(routeBadge, true);
                    routeBadge.innerHTML = `<span class="text-xs text-zinc-500">未選擇路線</span>`;
                }
            }

            if (currentSquad) {
                Object.assign(currentSquad, squad);
                if (protagonists) currentSquad.protagonists = protagonists;
                if (route) currentSquad.route = route;
                if (data.team) currentSquad.team = data.team;
            }
            initPlayerAvatar();
        }

        async function selectRoute(route) {
            if (!confirm(route === 'iggy' ? '確認選擇 Iggy 路線？' : '確認選擇 Marah 路線？')) return;

            const useTeamRoute = currentSquad && currentSquad.is_team_leader === 1 && currentSquad.team_id;
            const endpoint = useTeamRoute ? '/set_team_route_by_leader' : '/set_route';

            const res = await fetch(endpoint, {
                method: 'POST',
                credentials: 'same-origin',
                body: new URLSearchParams({route})
            });
            const data = await res.json();

            if (!data.success) {
                alert(data.error || '選擇失敗');
                return;
            }

            if (data.squad_id) {
                currentSquad = data;
            } else if (data.squad) {
                currentSquad = { ...data.squad, route: data.route, team: data.team, protagonists: data.protagonists };
            } else {
                const statusRes = await fetch('/status', { credentials: 'same-origin' });
                currentSquad = await statusRes.json();
            }
            updateDashboard(currentSquad);

            const picker = document.getElementById('route-picker');
            if (picker) setVisible(picker, false);
        }

        async function loadMyTeam() {
            const noBox = document.getElementById('no-team-box');
            const hasBox = document.getElementById('has-team-box');
            try {
                const res = await fetch('/my_team', { credentials: 'same-origin' });
                const data = await res.json();

                if (!data.has_team) {
                    setVisible(noBox, true);
                    setVisible(hasBox, false);
                    applyRouteTheme(data.route || (currentSquad && currentSquad.route));
                } else {
                    setVisible(noBox, false);
                    setVisible(hasBox, true);
                    applyRouteTheme(data.route || data.team?.route);
                    if (currentSquad && data.route) currentSquad.route = data.route;
                }

                if (!data.has_team) {
                    loadAvailableTeams();
                    return;
                }

                const team = data.team;
                const isLeader = data.is_team_leader === 1;
                if (currentSquad) currentSquad.is_team_leader = data.is_team_leader;
                const safeTeamName = (team.team_name || '').replace(/'/g, "\\'");
                const currentSquadId = data.current_squad_id;

                let teamNameHTML = `
                    <div class="flex items-center gap-x-2">
                        <div id="my-team-name" class="text-2xl font-bold">${team.team_name}</div>
                `;

                if (isLeader) {
                    teamNameHTML += `
                        <button onclick="editTeamName('${team.team_id}', '${safeTeamName}')"
                                class="text-xs px-3 py-1 bg-zinc-700 hover:bg-zinc-600 rounded-xl flex items-center gap-x-1">
                            <i class="fa-solid fa-edit"></i>
                            <span>改名</span>
                        </button>
                    `;
                }

                teamNameHTML += `</div>`;

                document.querySelector('#has-team-box .cartoon-box').innerHTML = `
                    <div class="flex justify-between items-center">
                        <div>
                            <div class="text-xs text-emerald-400">TEAM NAME</div>
                            ${teamNameHTML}
                            <div id="my-team-id" class="font-mono text-xs text-zinc-500">${team.team_id}</div>
                        </div>
                        <div id="my-team-route-badge"></div>
                    </div>
                `;

                const routeBadge = document.getElementById('my-team-route-badge');
                if (team.route === 'iggy') {
                    routeBadge.innerHTML = '<div class="text-xs px-3 py-1 rounded-full bg-red-900/50 text-red-300">🔥 Iggy 線</div>';
                } else if (team.route === 'marah') {
                    routeBadge.innerHTML = '<div class="text-xs px-3 py-1 rounded-full bg-blue-900/50 text-blue-300">🌊 Marah 線</div>';
                } else {
                    routeBadge.innerHTML = '<div class="text-xs px-3 py-1 rounded-full bg-zinc-700 text-zinc-400">未設定路線</div>';
                }

                renderTeamProtagonists(data.protagonists);

                const list = document.getElementById('team-members-list');
                list.innerHTML = '';
                const members = data.members || [];
                if (members.length === 0) {
                    list.innerHTML = '<div class="text-zinc-400 col-span-2 text-center py-6">暫無隊友</div>';
                } else {
                members.forEach(m => {
                    const isYou = currentSquadId && m.squad_id === currentSquadId;
                    const isMemberLeader = m.is_leader || m.is_team_leader === 1;
                    const el = document.createElement('div');
                    el.className = 'cartoon-box p-4' + (isYou ? ' ring-2 ring-amber-500/50' : '');

                    const displayName = m.display_name || m.squad_id;
                    const leaderBadge = isMemberLeader
                        ? '<span class="ml-2 text-xs px-2 py-0.5 bg-amber-500 text-zinc-950 rounded-full font-medium">👑 隊長</span>'
                        : '';
                    const transferBtn = (isYou && isMemberLeader && isLeader)
                        ? `<button onclick="showTransferModal()"
                                   class="text-xs px-3 py-1 bg-amber-600 hover:bg-amber-700 text-zinc-950 rounded-xl font-medium shrink-0">
                               轉讓隊長
                           </button>`
                        : '';

                    el.innerHTML = `
                        <div class="flex items-center gap-x-3">
                            <img src="${avatarSrc(m.avatar)}"
                                 class="w-12 h-12 rounded-full object-cover border border-zinc-600 shrink-0">
                            <div class="flex-1 min-w-0">
                                <div class="font-semibold text-lg flex flex-wrap items-center gap-x-1">
                                    <span>${displayName}</span>
                                    ${leaderBadge}
                                    ${isYou ? '<span class="text-xs text-amber-400">(你)</span>' : ''}
                                </div>
                            </div>
                            ${transferBtn}
                        </div>

                        <div class="grid grid-cols-5 gap-1 mt-3 text-center text-xs">
                            <div>
                                <div class="text-red-400 font-mono">${m.hp}</div>
                                <div class="text-zinc-500">生命值</div>
                            </div>
                            <div>
                                <div class="text-purple-400 font-mono">${m.sanity}</div>
                                <div class="text-zinc-500">神智</div>
                            </div>
                            <div>
                                <div class="text-orange-400 font-mono">${m.power}</div>
                                <div class="text-zinc-500">力量</div>
                            </div>
                            <div>
                                <div class="text-blue-400 font-mono">${m.intellect}</div>
                                <div class="text-zinc-500">智力</div>
                            </div>
                            <div>
                                <div class="text-emerald-400 font-mono">${m.resilience}</div>
                                <div class="text-zinc-500">韌性</div>
                            </div>
                        </div>
                    `;
                    list.appendChild(el);
                });
                }
                loadTeamTaskLogs();
                loadAvailableTeams();
            } catch (e) {
                console.error('loadMyTeam failed', e);
                setVisible(noBox, true);
                setVisible(hasBox, false);
                loadAvailableTeams();
            }
        }

        async function showTransferModal() {
            const modal = document.getElementById('transfer-modal');
            const select = document.getElementById('transfer-target');
            if (!modal || !select) return;

            select.innerHTML = '<option value="">載入中...</option>';
            modal.classList.remove('hidden');
            modal.classList.add('flex');

            try {
                const res = await fetch('/my_team', { credentials: 'same-origin' });
                const data = await res.json();
                select.innerHTML = '';

                const currentId = data.current_squad_id;
                const others = (data.members || []).filter(m => m.squad_id !== currentId);

                if (others.length === 0) {
                    select.innerHTML = '<option value="">（隊內無其他隊員）</option>';
                    return;
                }

                others.forEach(member => {
                    const option = document.createElement('option');
                    option.value = member.squad_id;
                    option.textContent = member.display_name || member.squad_id;
                    select.appendChild(option);
                });
            } catch (e) {
                select.innerHTML = '<option value="">載入失敗</option>';
            }
        }

        function hideTransferModal() {
            const modal = document.getElementById('transfer-modal');
            if (!modal) return;
            modal.classList.remove('flex');
            modal.classList.add('hidden');
            const select = document.getElementById('transfer-target');
            if (select) select.innerHTML = '';
        }

        async function transferLeadership() {
            const select = document.getElementById('transfer-target');
            const targetSquadId = select ? select.value : '';
            if (!targetSquadId) {
                alert('請選擇要轉讓的隊員');
                return;
            }

            if (!confirm('確定要將隊長轉讓畀呢位隊員嗎？')) return;

            try {
                const res = await fetch('/team/transfer_leadership', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ target_squad_id: targetSquadId })
                });
                const result = await res.json();

                if (result.success) {
                    alert(result.message || '隊長已成功轉讓！');
                    hideTransferModal();
                    const statusRes = await fetch('/status', { credentials: 'same-origin' });
                    if (statusRes.ok) {
                        currentSquad = await statusRes.json();
                        updateDashboard(currentSquad);
                    }
                    loadMyTeam();
                } else {
                    alert(result.error || '轉讓失敗');
                }
            } catch (e) {
                alert('轉讓失敗，請重試');
            }
        }

        function teamRouteBadge(route) {
            if (route === 'iggy') return '<span class="text-[10px] px-2 py-0.5 rounded-full bg-red-900/40 text-red-300">🔥 Iggy</span>';
            if (route === 'marah') return '<span class="text-[10px] px-2 py-0.5 rounded-full bg-blue-900/40 text-blue-300">🌊 Marah</span>';
            return '<span class="text-[10px] px-2 py-0.5 rounded-full bg-zinc-700 text-zinc-400">未選路線</span>';
        }

        async function loadAvailableTeams() {
            const container = document.getElementById('available-teams-list');
            if (!container) return;
            container.innerHTML = '<div class="text-zinc-400 text-sm py-4 text-center">載入中...</div>';

            try {
                const res = await fetch('/available_teams', { credentials: 'same-origin' });
                const data = await res.json();

                if (!res.ok) {
                    container.innerHTML = `<div class="text-red-400 text-sm py-4 text-center">${data.error || '請先登入'}</div>`;
                    return;
                }

                if (!data.teams || data.teams.length === 0) {
                    container.innerHTML = '<div class="text-zinc-400 text-sm py-6 text-center">暫時冇隊伍 — 你可以往下建立新隊</div>';
                    return;
                }

                container.innerHTML = '';
                const hasTeam = Boolean(data.has_team);
                data.teams.forEach(team => {
                    const el = document.createElement('div');
                    el.className = 'team-join-card';

                    let actionHtml = '';
                    if (team.is_joined) {
                        actionHtml = `<span class="team-join-btn inline-flex items-center justify-center bg-emerald-900/50 text-emerald-300">✓ 已加入</span>`;
                    } else if (hasTeam) {
                        actionHtml = `<span class="team-join-btn inline-flex items-center justify-center bg-zinc-700 text-zinc-400">已屬其他隊</span>`;
                    } else {
                        actionHtml = `<button type="button" class="team-join-btn bg-amber-500 hover:bg-amber-600 text-zinc-950">加入此隊</button>`;
                    }

                    el.innerHTML = `
                        <div class="min-w-0 flex-1">
                            <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                                <div class="font-semibold text-base truncate">${team.team_name || team.team_id}</div>
                                ${teamRouteBadge(team.route)}
                            </div>
                            <div class="font-mono text-emerald-400/90 text-xs mt-0.5">${team.team_id}</div>
                            <div class="text-xs text-zinc-400 mt-1">${team.member_count} 位隊員</div>
                        </div>
                        <div class="shrink-0 w-full sm:w-auto">${actionHtml}</div>
                    `;

                    const btn = el.querySelector('button');
                    if (btn) {
                        btn.onclick = () => joinTeamDirectly(team.team_id);
                    }
                    container.appendChild(el);
                });
            } catch (e) {
                console.error('loadAvailableTeams failed', e);
                container.innerHTML = '<div class="text-red-400 text-sm py-4 text-center">載入失敗，請下拉刷新重試</div>';
            }
        }

        async function joinTeamDirectly(teamId) {
            const res = await fetch('/team/join', {
                method: 'POST',
                credentials: 'same-origin',
                body: new URLSearchParams({team_id: teamId})
            });
            const data = await res.json();
            if (data.success) {
                alert('成功加入 Team！');
                if (currentSquad) {
                    currentSquad.team_id = data.team.team_id;
                    const statusRes = await fetch('/status', { credentials: 'same-origin' });
                    currentSquad = await statusRes.json();
                    updateDashboard(currentSquad);
                }
                loadMyTeam();
                loadAvailableTeams();
            } else {
                alert(data.error || '加入失敗');
            }
        }

        async function createMyTeam() {
            const name = document.getElementById('create-team-name').value.trim() || '新小隊';
            const res = await fetch('/team/create', {
                method: 'POST',
                credentials: 'same-origin',
                body: new URLSearchParams({team_name: name})
            });
            const data = await res.json();
            if (data.success) {
                alert(`Team ${data.team_id} 已建立！`);
                document.getElementById('create-team-name').value = '';
                loadMyTeam();
                loadAvailableTeams();
            } else {
                alert(data.error || '建立失敗');
            }
        }

        const OIKONOMIA_STORAGE_KEY = 'oikonomia_session_v1';

        function saveLocalSession(data) {
            if (!data?.squad_id) return;
            try {
                localStorage.setItem(OIKONOMIA_STORAGE_KEY, JSON.stringify({
                    squad_id: data.squad_id,
                    display_name: data.display_name || data.squad_id,
                    restore_token: data.restore_token || null,
                    has_pin: !!data.has_pin,
                    saved_at: Date.now(),
                }));
            } catch (e) {
                console.warn('localStorage save failed', e);
            }
        }

        function loadLocalSession() {
            try {
                const raw = localStorage.getItem(OIKONOMIA_STORAGE_KEY);
                return raw ? JSON.parse(raw) : null;
            } catch (e) {
                return null;
            }
        }

        function clearLocalSession() {
            try { localStorage.removeItem(OIKONOMIA_STORAGE_KEY); } catch (e) { /* ignore */ }
        }

        async function tryRestoreWithToken(stored) {
            if (!stored?.restore_token) return null;
            const res = await fetch('/session/restore', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ restore_token: stored.restore_token }),
            });
            if (!res.ok) return null;
            const data = await res.json();
            if (data?.success && data.squad_id) {
                saveLocalSession(data);
                return data;
            }
            return null;
        }

        async function restoreSession() {
            const loading = document.getElementById('session-loading');
            const loginScreen = document.getElementById('login-screen');

            for (let attempt = 0; attempt < 3; attempt++) {
                try {
                    const res = await fetch('/status', { credentials: 'same-origin' });
                    if (res.ok) {
                        const squad = await res.json();
                        if (squad && squad.squad_id && squad.success !== false && !squad.error) {
                            saveLocalSession(squad);
                            if (loading) setVisible(loading, false);
                            await completeLogin({ ...squad, require_set_pin: false, skip_team_prompt: true });
                            return;
                        }
                    }
                } catch (e) {
                    console.log('session restore attempt failed', attempt + 1);
                }
                if (attempt < 2) {
                    await new Promise(r => setTimeout(r, 1200));
                }
            }

            const stored = loadLocalSession();
            if (stored) {
                try {
                    const restored = await tryRestoreWithToken(stored);
                    if (restored) {
                        if (loading) setVisible(loading, false);
                        await completeLogin({ ...restored, require_set_pin: false, skip_team_prompt: true });
                        return;
                    }
                } catch (e) {
                    console.warn('token restore failed', e);
                }
            }

            if (loading) setVisible(loading, false);
            if (loginScreen) setVisible(loginScreen, true);
            const nameEl = document.getElementById('squad_id');
            if (nameEl && stored?.display_name && !nameEl.value) {
                nameEl.value = stored.display_name;
            }
            if (stored?.has_pin) {
                const hint = document.getElementById('login-restore-hint');
                if (hint) {
                    hint.textContent = '偵測到先前帳號，請輸入 PIN 登入（進度已保存）';
                    setVisible(hint, true);
                }
            }
        }

        async function completeLogin(data) {
            currentSquad = data.squad_id ? data : (data.squad || data);
            saveLocalSession({
                ...currentSquad,
                restore_token: data.restore_token || currentSquad.restore_token,
            });
            setVisible(document.getElementById('login-screen'), false);
            setVisible(document.getElementById('game-content'), true);
            showNavAfterLogin();

            document.getElementById('squad-name').textContent =
                currentSquad.display_name || currentSquad.squad_id;

            if (data.require_set_pin) {
                setTimeout(() => {
                    const pin = prompt('請設定你的 4 位數 PIN（之後登入要用）');
                    if (pin && pin.length === 4 && /^\\d+$/.test(pin)) {
                        fetch('/set_pin', {
                            method: 'POST',
                            credentials: 'same-origin',
                            body: new URLSearchParams({pin: pin})
                        }).then(r => r.json()).then(res => {
                            if (res.success) {
                                alert('PIN 設定成功！請記住。');
                                currentSquad.has_pin = true;
                            } else {
                                alert(res.error || 'PIN 設定失敗');
                            }
                        });
                    } else if (pin) {
                        alert('PIN 設定失敗，請之後再設定。');
                    }
                }, 800);
            }

            showSection('dashboard');
            updateDashboard(currentSquad);
            initPlayerAvatar();
            loadMyItems();
            loadAnnouncements();

            setTimeout(() => {
                const picker = document.getElementById('route-picker');
                if (!picker) return;
                if (currentSquad.route) {
                    setVisible(picker, false);
                } else if (currentSquad.is_team_leader !== 1) {
                    setVisible(picker, false);
                }
            }, 400);

            if (!data.skip_team_prompt) {
                try {
                    const teamRes = await fetch('/my_team', { credentials: 'same-origin' });
                    const teamData = await teamRes.json();
                    if (!teamData.has_team) {
                        setTimeout(() => {
                            if (confirm('你尚未加入任何 Team。\\n是否立即建立或加入一個 Team？')) {
                                showSection('team');
                            }
                        }, 1200);
                    }
                } catch (teamErr) {
                    console.error('team check failed', teamErr);
                }
            }
        }

        async function loginWithPin(name, pin) {
            const res = await fetch('/login', {
                method: 'POST',
                credentials: 'same-origin',
                body: new URLSearchParams({squad_id: name, pin: pin})
            });
            const data = await res.json();
            if (data.success) {
                await completeLogin(data);
            } else {
                alert(data.error || 'PIN 錯誤');
            }
        }

        async function login(e) {
            e.preventDefault();
            try {
                const name = document.getElementById('squad_id').value.trim();
                const pin = document.getElementById('login_pin').value.trim();
                const res = await fetch('/login', {
                    method: 'POST',
                    credentials: 'same-origin',
                    body: new URLSearchParams({squad_id: name, pin: pin})
                });
                const data = await res.json();

                if (data.success) {
                    await completeLogin(data);
                } else {
                    if (data.require_pin) {
                        const inputPin = prompt('請輸入你的 4 位數 PIN');
                        if (inputPin) {
                            await loginWithPin(name, inputPin);
                        }
                    } else {
                        alert(data.error || data.message || '登入失敗');
                    }
                }
            } catch (err) {
                console.error('login failed', err);
                alert('登入失敗，請重試或檢查網絡連線');
            }
        }

        let showAllAnnouncements = false;

        async function loadAnnouncements() {
            try {
                const res = await fetch('/announcements');
                const data = await res.json();
                
                if (!data.announcements || data.announcements.length === 0) {
                    document.getElementById('announcement-box').classList.add('hidden');
                    return;
                }

                const reversed = [...data.announcements].reverse(); // 由新到舊
                
                // 顯示最新一條
                const latest = reversed[0];
                document.getElementById('latest-announcement').innerHTML = `
                    <div class="bg-blue-950/50 rounded-2xl p-3">
                        <div class="flex justify-between text-xs mb-1">
                            <span class="text-blue-300">${latest.timestamp}</span>
                        </div>
                        <div class="text-blue-100">${latest.message}</div>
                    </div>
                `;
                
                // 顯示全部歷史（如果已展開）
                const allContainer = document.getElementById('all-announcements');
                allContainer.innerHTML = '';
                
                reversed.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'bg-blue-950/50 rounded-2xl p-3';
                    div.innerHTML = `
                        <div class="flex justify-between text-xs mb-1">
                            <span class="text-blue-300">${item.timestamp}</span>
                        </div>
                        <div class="text-blue-100">${item.message}</div>
                    `;
                    allContainer.appendChild(div);
                });
                
                document.getElementById('announcement-box').classList.remove('hidden');
                
            } catch(e) {
                console.log("載入公告失敗");
            }
        }

        // 切換顯示全部公告
        function toggleAllAnnouncements() {
            const allContainer = document.getElementById('all-announcements');
            const btn = document.getElementById('toggle-announcement-btn');
            
            showAllAnnouncements = !showAllAnnouncements;
            
            if (showAllAnnouncements) {
                allContainer.classList.remove('hidden');
                btn.textContent = '收起';
            } else {
                allContainer.classList.add('hidden');
                btn.textContent = '查看所有公告';
            }
        }

        const fetchOpts = { credentials: 'same-origin' };

        async function loadLocations() {
            const container = document.getElementById('location-list');
            container.innerHTML = '<div class="text-zinc-400 text-sm py-4">載入地點中…</div>';
            try {
                const res = await fetch('/locations', fetchOpts);
                if (!res.ok) throw new Error('HTTP ' + res.status);
                const locs = await res.json();
                container.innerHTML = '';
                const keys = Object.keys(locs);
                if (keys.length === 0) {
                    container.innerHTML = '<div class="text-zinc-400 text-sm py-4">暫無地點</div>';
                    return;
                }
                keys.forEach(key => {
                    const loc = locs[key];
                    const el = document.createElement('div');
                    el.className = 'section-card rounded-3xl p-5 location-card';
                    el.innerHTML = `<div class="font-semibold">${loc.name}</div><div class="text-xs text-amber-400">${loc.hint}</div>`;
                    el.addEventListener('click', () => openLocation(key, loc));
                    container.appendChild(el);
                });
            } catch (e) {
                console.error('loadLocations failed', e);
                container.innerHTML = '<div class="text-red-400 text-sm py-4">載入失敗，<button onclick="loadLocations()" class="underline">按此重試</button></div>';
            }
        }

        function openLocation(id, loc) {
            currentLocation = { id: id, ...loc };

            // 建立簡單 Modal
            const modal = document.createElement('div');
            modal.className = 'modal-overlay fixed inset-0 bg-black/70 flex items-end md:items-center justify-center z-50';
            modal.innerHTML = `
                <div class="modal-box bg-zinc-900 w-full md:w-[480px] md:rounded-t-3xl md:rounded-b-3xl rounded-t-3xl p-6 border-t border-zinc-700">
                    <div class="flex justify-between items-start mb-4">
                        <div>
                            <div class="font-semibold text-2xl">${loc.name}</div>
                            <div class="text-sm text-amber-400 mt-0.5">${loc.hint}</div>
                        </div>
                        <button type="button" class="text-3xl leading-none text-zinc-400 hover:text-white" onclick="closeModal(this)">×</button>
                    </div>

                    <div class="text-zinc-300 mb-6">${loc.description}</div>

                    <div id="action-area">
                        ${loc.task_type === 'gps' ? `
                            <button onclick="verifyCurrentLocation('${id}')" 
                                    class="w-full py-4 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl flex items-center justify-center gap-x-3">
                                <i class="fa-solid fa-location-arrow"></i>
                                <span>驗證目前位置</span>
                            </button>
                        ` : ''}

                        ${loc.task_type === 'photo' ? `
                            <div class="space-y-3">
                                <input type="file" id="photo-input" accept="image/*" capture="environment" class="hidden">
                                <button onclick="document.getElementById('photo-input').click()" 
                                        class="w-full py-4 bg-zinc-700 hover:bg-zinc-600 rounded-2xl font-medium flex items-center justify-center gap-x-3">
                                    <i class="fa-solid fa-camera"></i>
                                    <span>影相上傳</span>
                                </button>
                                <button onclick="submitPhotoTask('${id}', this)" 
                                        class="w-full py-3.5 text-sm border border-zinc-700 rounded-2xl hover:bg-zinc-800">
                                    直接提交任務（唔影相）
                                </button>
                            </div>
                        ` : ''}

                        ${loc.task_type === 'puzzle' ? `
                            <button onclick="startPuzzle('${id}', this)" 
                                    class="w-full py-4 bg-zinc-700 hover:bg-zinc-600 rounded-2xl font-medium flex items-center justify-center gap-x-3">
                                <i class="fa-solid fa-question-circle"></i>
                                <span>開始解謎</span>
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
            document.body.appendChild(modal);

            // 處理影相選擇
            setTimeout(() => {
                const input = document.getElementById('photo-input');
                if (input) {
                    input.onchange = () => {
                        if (input.files.length > 0) {
                            submitPhotoWithFile(id, input.files[0], modal);
                        }
                    };
                }
            }, 100);
        }

        let currentLocation = null;

        async function verifyCurrentLocation(locId) {
            if (!navigator.geolocation) {
                showLocationError("你的手機唔支援定位功能");
                return;
            }

            navigator.geolocation.getCurrentPosition(
                async (position) => {
                    const res = await fetch('/verify_gps', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            loc_id: locId,
                            lat: position.coords.latitude,
                            lng: position.coords.longitude
                        })
                    });
                    const data = await res.json();
                    alert(data.message || (data.error ? '錯誤：' + data.error : '驗證失敗'));
                    if (data.success) closeModal(document.querySelector('.modal-overlay'));
                },
                (error) => {
                    let message = "無法取得定位";
                    if (error.code === error.PERMISSION_DENIED) {
                        message = "你已拒絕定位權限";
                        showLocationPermissionGuide();
                    } else if (error.code === error.POSITION_UNAVAILABLE) {
                        message = "暫時無法取得定位";
                    } else if (error.code === error.TIMEOUT) {
                        message = "定位超時";
                    }
                    showLocationError(message);
                }
            );
        }

        function showLocationError(msg) {
            alert(msg);
        }

        function detectBrowser() {
            const ua = navigator.userAgent;
            const isIOS = /iPad|iPhone|iPod/.test(ua)
                || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
            const isAndroid = /Android/.test(ua);

            let browser = 'other';
            if (/CriOS/.test(ua)) browser = 'chrome-ios';
            else if (/FxiOS/.test(ua)) browser = 'firefox-ios';
            else if (/EdgiOS/.test(ua)) browser = 'edge-ios';
            else if (/OPiOS/.test(ua)) browser = 'opera-ios';
            else if (isIOS && /Safari/.test(ua)) browser = 'safari-ios';
            else if (/SamsungBrowser/.test(ua)) browser = 'samsung';
            else if (/EdgA/.test(ua)) browser = 'edge-android';
            else if (/Firefox/.test(ua)) browser = 'firefox';
            else if (/Chrome/.test(ua)) browser = 'chrome';
            else if (isIOS) browser = 'safari-ios';

            const names = {
                'safari-ios': 'Safari',
                'chrome-ios': 'Chrome',
                'firefox-ios': 'Firefox',
                'edge-ios': 'Edge',
                'opera-ios': 'Opera',
                'chrome': 'Chrome',
                'firefox': 'Firefox',
                'edge-android': 'Edge',
                'samsung': 'Samsung 瀏覽器',
                'other': '你的瀏覽器',
            };

            return { isIOS, isAndroid, browser, browserName: names[browser] || names.other };
        }

        function getLocationPermissionGuide() {
            const { isIOS, isAndroid, browser, browserName } = detectBrowser();

            const guides = {
                'safari-ios': `
                    <strong>Safari（iPhone / iPad）：</strong><br>
                    1. 喺 Safari 網址列左邊點 <strong>aA</strong> →「網站設定」→ 位置 → <strong>允許</strong><br>
                    2. 或者：設定 → Safari → 進階 → 網站資料 → 搵 oikonomia → 位置 → 允許<br>
                    3. 確保：設定 → 私隱與保安 → 定位服務 → <strong>開啟</strong>
                `,
                'chrome-ios': `
                    <strong>Chrome（iPhone / iPad）：</strong><br>
                    1. 設定 → Chrome → 位置 → <strong>使用 App 期間</strong><br>
                    2. 返回 Chrome，點網址列左邊圖示 → 網站設定 → 位置 → <strong>允許</strong><br>
                    3. 確保：設定 → 私隱與保安 → 定位服務 → <strong>開啟</strong>
                `,
                'firefox-ios': `
                    <strong>Firefox（iPhone / iPad）：</strong><br>
                    1. 設定 → Firefox → 位置 → <strong>使用 App 期間</strong><br>
                    2. 返回 Firefox，重新整理頁面，彈出提示時選 <strong>允許</strong><br>
                    3. 確保：設定 → 私隱與保安 → 定位服務 → <strong>開啟</strong>
                `,
                'edge-ios': `
                    <strong>Edge（iPhone / iPad）：</strong><br>
                    1. 設定 → Edge → 位置 → <strong>使用 App 期間</strong><br>
                    2. 返回 Edge，點網址列圖示 → 網站權限 → 位置 → <strong>允許</strong>
                `,
                'chrome': `
                    <strong>Chrome（Android）：</strong><br>
                    1. 點網址列左邊 <strong>鎖頭／圖示</strong> → 權限 → 位置 → <strong>允許</strong><br>
                    2. 或者：設定 → 應用程式 → Chrome → 權限 → 位置 → <strong>允許</strong>
                `,
                'samsung': `
                    <strong>Samsung 瀏覽器（Android）：</strong><br>
                    1. 點網址列左邊圖示 → 權限 → 位置 → <strong>允許</strong><br>
                    2. 或者：設定 → 應用程式 → Samsung 瀏覽器 → 權限 → 位置 → <strong>允許</strong>
                `,
                'firefox': `
                    <strong>Firefox（Android）：</strong><br>
                    1. 點網址列左邊圖示 → 權限 → 位置 → <strong>允許</strong><br>
                    2. 或者：設定 → 應用程式 → Firefox → 權限 → 位置 → <strong>允許</strong>
                `,
                'edge-android': `
                    <strong>Edge（Android）：</strong><br>
                    1. 點網址列左邊圖示 → 權限 → 位置 → <strong>允許</strong><br>
                    2. 或者：設定 → 應用程式 → Edge → 權限 → 位置 → <strong>允許</strong>
                `,
            };

            if (isIOS) {
                return {
                    intro: `Oikonomia 係網頁，定位權限要畀 <strong>${browserName}</strong>，唔係 Oikonomia 本身。`,
                    steps: guides[browser] || guides['safari-ios'],
                };
            }
            if (isAndroid) {
                return {
                    intro: `Oikonomia 係網頁，定位權限要畀 <strong>${browserName}</strong>，唔係 Oikonomia 本身。`,
                    steps: guides[browser] || guides['chrome'],
                };
            }
            return {
                intro: '請喺瀏覽器允許此網站使用定位，先至可以用到探索功能。',
                steps: `
                    <strong>桌面瀏覽器：</strong><br>
                    點網址列左邊嘅鎖頭／圖示 → 網站設定 → 位置 → <strong>允許</strong>，然後重新整理頁面。
                `,
            };
        }

        function showLocationPermissionGuide() {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100] px-4';

            const guide = getLocationPermissionGuide();

            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-md rounded-3xl p-6 border border-zinc-700 max-h-[90vh] overflow-auto">
                    <div class="text-xl font-bold mb-4">需要開啟定位權限</div>

                    <div class="text-zinc-300 mb-4 leading-relaxed text-sm">
                        ${guide.intro}
                    </div>

                    <div class="space-y-3">
                        <div class="bg-zinc-800 p-4 rounded-2xl text-sm leading-relaxed">
                            ${guide.steps}
                        </div>

                        <button onclick="this.closest('.fixed').remove()"
                                class="w-full py-3 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl">
                            我已開啟，重新嘗試
                        </button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);
        }

        async function submitPhotoWithFile(locId, file, modal) {
            const formData = new FormData();
            formData.append('task_id', locId);
            formData.append('photo', file);

            const res = await fetch('/submit_task', { method: 'POST', credentials: 'same-origin', body: formData });
            const data = await res.json();
            alert(data.message || (data.error ? '錯誤：' + data.error : '提交失敗'));
            if (modal) modal.remove();
        }

        async function submitPhotoTask(locId, btn) {
            btn.disabled = true;
            btn.textContent = '提交中...';

            const formData = new FormData();
            formData.append('task_id', locId);

            const res = await fetch('/submit_task', { method: 'POST', credentials: 'same-origin', body: formData });
            const data = await res.json();
            alert(data.message);
            closeModal(btn);
        }

        async function startPuzzle(locId, btn) {
            const answer = prompt('請輸入答案：');
            if (!answer) return;

            // 簡單示範，之後可以改做真實後端驗證
            if (answer.toLowerCase() === 'iggy') {
                alert('正確！獲得神智 +8');
                closeModal(btn);
            } else {
                alert('唔正確');
            }
        }

        // 自動更新公告
        setInterval(() => {
            loadAnnouncements();
        }, 10000);

        // 每 12 秒自動更新狀態
        setInterval(() => {
            if (currentSquad) {
                fetch('/status', { credentials: 'same-origin' })
                    .then(r => r.ok ? r.json() : null)
                    .then(d => {
                        if (d && d.squad_id && d.success !== false) {
                            currentSquad = d;
                            updateDashboard(d);
                        }
                    });
            }
        }, 12000);

        let currentAvatar = null;

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text ?? '';
            return div.innerHTML;
        }

        const ITEM_SOURCE_LABELS = { story: '劇情', qr: 'QR', event: '事件', special: '特殊' };
        const ITEM_EFFECT_LABELS = {
            power_up: '力量',
            sanity_up: '神智',
            resilience_up: '韌性',
            hp_up: '生命值',
            intellect_up: '智力',
        };

        let currentObtainedItem = null;
        let pendingAppliedEffect = null;

        function formatItemEffectText(item) {
            if (item.effect_text) return item.effect_text;
            if (!item.has_ability || !item.effect_type) return '';
            const label = ITEM_EFFECT_LABELS[item.effect_type];
            if (!label) return '';
            const value = Number(item.effect_value) || 0;
            const sign = value >= 0 ? '+' : '';
            return `${sign}${value} ${label}`;
        }

        function showItemReveal(item, appliedEffect) {
            currentObtainedItem = item;
            pendingAppliedEffect = appliedEffect || null;

            const modal = document.getElementById('item-reveal-modal');
            const imageEl = document.getElementById('reveal-item-image');
            const effectBox = document.getElementById('reveal-effect-box');
            const abilityBadge = document.getElementById('reveal-ability-badge');

            imageEl.src = item.image_path || '/static/images/default-item.svg';
            imageEl.onerror = () => { imageEl.src = '/static/images/default-item.svg'; };
            document.getElementById('reveal-item-name').textContent = item.name || '未知物品';
            document.getElementById('reveal-item-desc').textContent = item.description || '';

            const effectText = formatItemEffectText(item);
            if (item.has_ability && effectText) {
                effectBox.classList.remove('hidden');
                abilityBadge.classList.remove('hidden');
                document.getElementById('reveal-effect-text').textContent = effectText;
                modal.classList.add('reveal-ability');
            } else {
                effectBox.classList.add('hidden');
                abilityBadge.classList.add('hidden');
                modal.classList.remove('reveal-ability');
            }

            modal.classList.remove('hidden');
            modal.classList.add('flex');
        }

        async function confirmObtainItem() {
            const modal = document.getElementById('item-reveal-modal');
            modal.classList.add('hidden');
            modal.classList.remove('flex', 'reveal-ability');

            await loadMyItems();

            if (pendingAppliedEffect && pendingAppliedEffect.stats) {
                updateDashboard({ ...currentSquad, ...pendingAppliedEffect.stats });
            } else {
                try {
                    const res = await fetch('/status', { credentials: 'same-origin' });
                    if (res.ok) {
                        const data = await res.json();
                        if (data && data.squad_id) {
                            currentSquad = data;
                            updateDashboard(data);
                        }
                    }
                } catch (e) {
                    console.error(e);
                }
            }

            currentObtainedItem = null;
            pendingAppliedEffect = null;
        }

        async function loadMyItems() {
            const container = document.getElementById('my-items-list');
            const slotLabel = document.getElementById('items-slot-label');
            if (!container) return;

            try {
                const res = await fetch('/my_items', { credentials: 'same-origin' });
                const data = await res.json();

                if (!res.ok || !data.success) {
                    container.innerHTML = '<div class="text-red-400 text-sm col-span-full text-center py-4">載入失敗</div>';
                    return;
                }

                if (slotLabel) {
                    slotLabel.textContent = `(${data.current_count || 0}/${data.max_slots || 5})`;
                }

                const items = data.items || [];
                if (items.length === 0) {
                    container.innerHTML = '<div class="text-sm text-zinc-400 col-span-full text-center py-6">暫無物品 — 完成劇情或掃描 QR 可獲得</div>';
                    return;
                }

                container.innerHTML = '';
                items.forEach(item => {
                    const div = document.createElement('div');
                    const isAbility = item.has_ability && item.effect_type;
                    div.className = 'bg-zinc-800/80 border rounded-2xl p-4 overflow-hidden'
                        + (isAbility ? ' border-amber-500/40 ring-1 ring-amber-500/20' : ' border-zinc-700');
                    const sourceLabel = ITEM_SOURCE_LABELS[item.source] || item.source || '未知';
                    const imagePath = item.image_path || '/static/images/default-item.svg';
                    const thumb = `<img src="${escapeHtml(imagePath)}" class="w-14 h-14 object-cover rounded-xl border border-zinc-600" alt="" onerror="this.src='/static/images/default-item.svg'">`;
                    const effectText = formatItemEffectText(item);
                    const abilityTag = isAbility && effectText
                        ? `<span class="inventory-ability-tag text-xs px-2 py-0.5 rounded-full font-medium inline-flex items-center gap-1 mt-1"><i class="fa-solid fa-bolt text-[10px]"></i>${escapeHtml(effectText)}</span>`
                        : '';
                    div.innerHTML = `
                        <div class="flex gap-3">
                            <div class="shrink-0">${thumb}</div>
                            <div class="flex-1 min-w-0">
                                <div class="font-semibold flex items-center gap-2 flex-wrap">
                                    <span>${escapeHtml(item.name)}</span>
                                    ${isAbility ? '<span class="text-[10px] px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded font-bold">能力</span>' : ''}
                                </div>
                                <div class="text-xs text-zinc-400 mt-0.5 line-clamp-2">${escapeHtml(item.description || '')}</div>
                                <div class="text-xs text-zinc-500 mt-1">${escapeHtml(sourceLabel)}</div>
                                ${abilityTag}
                            </div>
                            <button onclick="discardItem(${item.id})"
                                    class="text-xs px-2 py-1 h-fit bg-red-900/50 hover:bg-red-800 text-red-300 rounded-lg shrink-0">
                                丟棄
                            </button>
                        </div>
                    `;
                    container.appendChild(div);
                });
            } catch (e) {
                container.innerHTML = '<div class="text-red-400 text-sm col-span-full text-center py-4">載入失敗</div>';
            }
        }

        async function discardItem(playerItemId) {
            if (!confirm('確定要丟棄此物品嗎？')) return;

            const res = await fetch('/discard_item', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ player_item_id: playerItemId })
            });
            const result = await res.json();

            if (result.success) {
                loadMyItems();
            } else {
                alert(result.error || '丟棄失敗');
            }
        }

        async function claimItemFromStory(itemId) {
            try {
                const res = await fetch('/add_item', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ item_id: itemId, source: 'story' })
                });
                const result = await res.json();
                if (result.success && result.item) {
                    showItemReveal(result.item, result.applied_effect);
                    return true;
                }
                alert(result.error || '獲取失敗');
                return false;
            } catch (err) {
                alert('網絡錯誤，請稍後再試');
                return false;
            }
        }

        async function claimItemFromQrPayload(qrPayload) {
            try {
                const res = await fetch('/add_item', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ qr_payload: qrPayload, source: 'qr' })
                });
                const result = await res.json();
                if (result.success && result.item) {
                    showItemReveal(result.item, result.applied_effect);
                    return true;
                }
                alert(result.error || '獲取失敗');
                return false;
            } catch (err) {
                alert('網絡錯誤，請稍後再試');
                return false;
            }
        }

        let html5QrCode = null;
        let qrScannerRunning = false;
        let qrClaimInProgress = false;

        async function stopQRScanner() {
            const modal = document.getElementById('qr-scanner-modal');
            if (modal) {
                modal.classList.remove('flex');
                modal.classList.add('hidden');
            }
            if (html5QrCode && qrScannerRunning) {
                try {
                    await html5QrCode.stop();
                    html5QrCode.clear();
                } catch (e) {
                    console.error(e);
                }
            }
            html5QrCode = null;
            qrScannerRunning = false;
        }

        async function startQRScanner() {
            if (typeof Html5Qrcode === 'undefined') {
                alert('QR 掃描庫載入失敗，請重新整理頁面');
                return;
            }

            const modal = document.getElementById('qr-scanner-modal');
            const status = document.getElementById('qr-status');
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            if (status) status.textContent = '正在啟動相機...';

            await stopQRScanner();
            html5QrCode = new Html5Qrcode('qr-reader');
            const config = { fps: 10, qrbox: { width: 250, height: 250 } };

            const onScanFailure = () => {};

            async function tryStartCamera(facingMode, label) {
                await html5QrCode.start(
                    { facingMode },
                    config,
                    onScanSuccess,
                    onScanFailure
                );
                qrScannerRunning = true;
                if (status) status.textContent = label;
            }

            try {
                await tryStartCamera('environment', '請對準 QR Code');
            } catch (err) {
                console.error('後置相機失敗:', err);
                try {
                    html5QrCode = new Html5Qrcode('qr-reader');
                    await tryStartCamera('user', '請對準 QR Code（前鏡頭）');
                } catch (err2) {
                    console.error('前鏡頭失敗:', err2);
                    if (status) status.textContent = '無法啟動相機，請檢查瀏覽器權限';
                }
            }
        }

        async function onScanSuccess(decodedText) {
            if (qrClaimInProgress) return;
            const payload = (decodedText || '').trim();
            if (!payload) {
                const status = document.getElementById('qr-status');
                if (status) status.textContent = 'QR Code 內容為空';
                return;
            }

            qrClaimInProgress = true;
            const status = document.getElementById('qr-status');
            if (status) status.textContent = '掃描成功，正在領取物品...';

            await stopQRScanner();
            await claimItemFromQrPayload(payload);
            qrClaimInProgress = false;
        }

        function avatarSrc(filename) {
            return `/static/avatars/${filename || 'default.png'}`;
        }

        function setAvatarImage(img, filename) {
            if (!img) return;
            img.onerror = () => {
                img.onerror = null;
                img.src = avatarSrc(null);
            };
            img.src = avatarSrc(filename);
        }

        function updateCombatPlayerAvatar(info) {
            const filename = info?.avatar || currentSquad?.avatar || null;
            setAvatarImage(document.getElementById('combat-player-avatar'), filename);
        }

        function showAvatarModal() {
            const modal = document.getElementById('avatar-modal');
            const grid = document.getElementById('avatar-grid');
            grid.innerHTML = '<div class="col-span-full text-center py-8 text-zinc-400">載入中...</div>';
            modal.classList.remove('hidden');
            modal.classList.add('flex');

            fetch('/available_avatars', { credentials: 'same-origin' })
                .then(res => res.json())
                .then(data => {
                    grid.innerHTML = '';

                    if (!data.avatars || data.avatars.length === 0) {
                        grid.innerHTML = '<div class="col-span-full text-center text-zinc-400 py-8">暫無可用頭像</div>';
                        return;
                    }

                    data.avatars.forEach(filename => {
                        const div = document.createElement('div');
                        div.className = `cursor-pointer rounded-2xl overflow-hidden border-2 transition-all hover:scale-105 ${currentAvatar === filename ? 'border-amber-500' : 'border-zinc-700'}`;

                        div.innerHTML = `
                            <img src="/static/avatars/${filename}"
                                 class="w-full aspect-square object-cover">
                        `;

                        div.onclick = () => selectAvatar(filename, div);
                        grid.appendChild(div);
                    });
                })
                .catch(() => {
                    grid.innerHTML = '<div class="col-span-full text-center text-red-400 py-8">載入失敗</div>';
                });
        }

        function hideAvatarModal() {
            const modal = document.getElementById('avatar-modal');
            modal.classList.remove('flex');
            modal.classList.add('hidden');
        }

        function selectAvatar(filename, element) {
            document.querySelectorAll('#avatar-grid > div').forEach(el => {
                el.classList.remove('border-amber-500');
                el.classList.add('border-zinc-700');
            });

            element.classList.remove('border-zinc-700');
            element.classList.add('border-amber-500');

            fetch('/set_avatar', {
                method: 'POST',
                credentials: 'same-origin',
                body: new URLSearchParams({ avatar: filename })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    currentAvatar = filename;
                    if (currentSquad) currentSquad.avatar = filename;
                    initPlayerAvatar();

                    setTimeout(() => {
                        hideAvatarModal();
                        alert('頭像已更新！');
                    }, 300);
                } else {
                    alert(data.error || '更新失敗');
                }
            });
        }

        function initPlayerAvatar() {
            const filename = currentSquad?.avatar || null;
            currentAvatar = filename;
            ['player-avatar', 'log-player-avatar', 'combat-player-avatar', 'dashboard-player-avatar'].forEach(id => {
                setAvatarImage(document.getElementById(id), filename);
            });
        }

        // 頁面載入時還原登入狀態（Render 冷啟動會重試）
        restoreSession();
    </script>

    <!-- 轉讓隊長 Modal -->
    <div id="transfer-modal" onclick="if (event.target.id === 'transfer-modal') hideTransferModal()"
         class="hidden fixed inset-0 bg-black/80 items-center justify-center z-[100]">
        <div onclick="event.stopImmediatePropagation()"
             class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-zinc-700">
            <div class="text-xl font-bold mb-1">轉讓隊長</div>
            <div class="text-sm text-zinc-400 mb-4">選擇隊內另一位隊員成為新隊長</div>
            <select id="transfer-target"
                    class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-3 text-sm mb-4">
            </select>
            <div class="flex gap-x-3">
                <button onclick="hideTransferModal()"
                        class="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm">取消</button>
                <button onclick="transferLeadership()"
                        class="flex-1 py-3 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl text-sm">
                    確認轉讓
                </button>
            </div>
        </div>
    </div>

    <!-- 物品 Reveal Modal -->
    <div id="item-reveal-modal"
         class="hidden fixed inset-0 bg-black/85 items-center justify-center">
        <div class="reveal-card rounded-3xl w-full max-w-sm mx-4 overflow-hidden">
            <div class="reveal-image-wrap">
                <img id="reveal-item-image" class="w-full h-64 object-cover" alt="Item Image">
                <div id="reveal-ability-badge"
                     class="reveal-ability-badge hidden absolute top-4 right-4 px-3 py-1 rounded-full text-sm font-bold flex items-center gap-1">
                    <i class="fa-solid fa-bolt"></i>
                    <span>能力物品</span>
                </div>
            </div>
            <div class="p-5">
                <h2 id="reveal-item-name" class="text-2xl font-bold mb-2"></h2>
                <p id="reveal-item-desc" class="text-sm theme-muted-text mb-4"></p>
                <div id="reveal-effect-box" class="reveal-effect-box hidden p-4 rounded-2xl mb-4">
                    <div class="text-xs theme-muted-text mb-1 flex items-center gap-1">
                        <i class="fa-solid fa-sparkles text-amber-400"></i>
                        <span>獲得效果</span>
                    </div>
                    <div id="reveal-effect-text" class="reveal-effect-text text-xl font-bold"></div>
                </div>
                <button onclick="confirmObtainItem()"
                        class="w-full py-3 theme-btn-primary rounded-2xl font-semibold text-sm">
                    確認獲得
                </button>
            </div>
        </div>
    </div>

    <!-- 掃描 QR Code Modal -->
    <div id="qr-scanner-modal" onclick="if (event.target.id === 'qr-scanner-modal') stopQRScanner()"
         class="hidden fixed inset-0 bg-black/80 items-center justify-center z-[100]">
        <div onclick="event.stopImmediatePropagation()"
             class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl overflow-hidden border border-zinc-700">
            <div class="flex justify-between items-center p-4 border-b border-zinc-700">
                <h3 class="text-lg font-bold">掃描 QR Code 獲得物品</h3>
                <button onclick="stopQRScanner()" class="text-2xl leading-none text-zinc-400 hover:text-white px-2">×</button>
            </div>
            <div class="p-4">
                <div id="qr-reader" class="w-full rounded-xl overflow-hidden border border-zinc-700"></div>
                <p id="qr-status" class="text-center text-sm mt-3 text-zinc-400">請對準 QR Code</p>
            </div>
            <div class="p-4 border-t border-zinc-700">
                <button onclick="stopQRScanner()"
                        class="w-full py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm">取消</button>
            </div>
        </div>
    </div>

    <!-- 戰鬥行動 Modal（置於 body 層級） -->
    <div id="combat-action-modal"
         onclick="if (event.target.id === 'combat-action-modal') closeCombatModal()"
         class="hidden fixed inset-0 bg-black/85 z-[70] p-4">
        <div onclick="event.stopPropagation()"
             class="bg-zinc-900 w-full max-w-md mx-auto rounded-3xl border border-zinc-700 overflow-hidden shadow-2xl">
            <div class="px-5 py-4 border-b border-zinc-700 flex justify-between items-center">
                <div>
                    <div id="modal-action-title" class="font-semibold text-lg text-amber-400"></div>
                    <div id="modal-status-hint" class="text-xs text-zinc-400 mt-0.5">系統正在擲骰…</div>
                </div>
                <button type="button" id="modal-close-btn" onclick="closeCombatModal()"
                        class="text-2xl text-zinc-400 hover:text-white leading-none">×</button>
            </div>

            <div id="modal-dice-area" class="px-6 py-8 flex flex-col items-center">
                <div class="text-xs text-zinc-400 mb-3">系統正在擲骰…</div>
                <div id="modal-dice-box"
                     class="w-24 h-24 flex items-center justify-center text-6xl font-bold border-[6px] border-amber-500 rounded-3xl bg-zinc-950 mb-3 transition-all">
                    <span id="modal-dice-value">?</span>
                </div>
                <div id="modal-dice-final" class="text-sm text-zinc-400 hidden text-center">
                    <div>
                        擲出：<span id="modal-dice-number" class="text-2xl font-bold text-amber-400"></span>
                    </div>
                    <div id="modal-dice-desc" class="text-xs mt-0.5 text-zinc-400"></div>
                </div>
            </div>

            <div id="modal-preview-area" class="hidden px-6 pb-5">
                <div class="border-t border-zinc-700 pt-4">
                    <div class="text-sm font-medium text-amber-400 mb-1">本回合預計結果</div>
                    <div id="modal-preview-summary" class="text-xs text-zinc-400 mb-3"></div>
                    <div class="grid grid-cols-2 gap-3 mb-3">
                        <div class="bg-zinc-800 rounded-2xl p-3 text-center">
                            <div class="text-emerald-400 text-xs">對敵人造成</div>
                            <div class="text-3xl font-bold text-emerald-400">-<span id="preview-damage-enemy">0</span></div>
                            <div id="modal-my-damage-note" class="text-[10px] text-zinc-500 mt-1"></div>
                        </div>
                        <div class="bg-zinc-800 rounded-2xl p-3 text-center">
                            <div class="text-red-400 text-xs">敵人反擊</div>
                            <div class="text-3xl font-bold text-red-400">-<span id="preview-damage-player">0</span></div>
                            <div id="modal-counter-note" class="text-[10px] text-zinc-500 mt-1"></div>
                        </div>
                    </div>
                    <div id="preview-warning" class="text-xs space-y-1 mb-4"></div>
                </div>
            </div>

            <div class="px-5 py-4 bg-zinc-950 border-t border-zinc-700">
                <button type="button" id="modal-confirm-btn" onclick="confirmRound()"
                        class="hidden w-full py-3 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl mb-2">
                    確認並結束本回合
                </button>
                <button type="button" id="modal-cancel-btn" onclick="closeCombatModal()"
                        class="w-full py-2 text-sm text-zinc-400 hover:text-white">
                    取消
                </button>
            </div>
        </div>
    </div>

    <div id="avatar-modal" class="hidden fixed inset-0 bg-black/80 items-center justify-center z-[100]">
        <div class="bg-zinc-900 w-full max-w-2xl mx-4 rounded-3xl p-6 border border-zinc-700">
            <div class="flex justify-between items-center mb-6">
                <div class="text-2xl font-bold">選擇角色頭像</div>
                <button onclick="hideAvatarModal()" class="text-3xl text-zinc-400 hover:text-white">×</button>
            </div>

            <div id="avatar-grid" class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-4 max-h-[400px] overflow-auto p-1">
            </div>

            <div class="mt-6 text-center text-xs text-zinc-400">
                頭像只會喺呢個營會顯示
            </div>
        </div>
    </div>
</body>
</html>
"""

CLAIM_ITEM_HTML = """
<!DOCTYPE html>
<html lang="zh-HK">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>獲得物品 • Oikonomia</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
</head>
<body class="bg-zinc-950 text-zinc-100 min-h-screen flex items-center justify-center p-6">
    <div id="claim-card" class="max-w-md w-full bg-zinc-900 border border-zinc-700 rounded-3xl overflow-hidden">
        <div class="relative">
            <img id="claim-image" src="{{ item.image_path or '/static/images/default-item.svg' }}"
                 class="w-full h-56 object-cover" alt="">
            {% if item.has_ability %}
            <div class="absolute top-4 right-4 bg-amber-400 text-zinc-900 px-3 py-1 rounded-full text-sm font-bold">
                <i class="fa-solid fa-bolt"></i> 能力物品
            </div>
            {% endif %}
        </div>
        <div class="p-6 text-center">
            <h1 class="text-2xl font-bold mb-2">{{ item.name }}</h1>
            <p class="text-zinc-400 text-sm mb-4">{{ item.description or '' }}</p>
            {% if item.has_ability and item.effect_type %}
            <div class="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-4 mb-4 text-left">
                <div class="text-xs text-zinc-400 mb-1">獲得效果</div>
                <div id="claim-effect" class="text-xl font-bold text-amber-400"></div>
            </div>
            {% endif %}
            <div id="claim-status" class="text-sm text-zinc-400 mb-4">正在領取物品...</div>
            <button id="claim-btn" onclick="claimNow()"
                    class="w-full py-3 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl mb-3">
                確認獲得
            </button>
            <a href="/" class="text-sm text-amber-400 hover:underline">返回 Dashboard</a>
        </div>
    </div>
    <script>
        const qrPayload = {{ qr_payload|tojson }};
        const itemMeta = {{ item|tojson }};
        const effectLabels = {
            power_up: '力量', sanity_up: '神智', resilience_up: '韌性',
            hp_up: '生命值', intellect_up: '智力'
        };

        (function initClaimPage() {
            const effectEl = document.getElementById('claim-effect');
            if (effectEl && itemMeta.has_ability && itemMeta.effect_type) {
                const label = effectLabels[itemMeta.effect_type] || '';
                const value = Number(itemMeta.effect_value) || 0;
                const sign = value >= 0 ? '+' : '';
                effectEl.textContent = label ? `${sign}${value} ${label}` : '';
            }
            const img = document.getElementById('claim-image');
            if (img) img.onerror = () => { img.src = '/static/images/default-item.svg'; };
        })();

        async function claimNow() {
            const status = document.getElementById('claim-status');
            const btn = document.getElementById('claim-btn');
            btn.disabled = true;
            status.textContent = '領取中...';

            const res = await fetch('/add_item', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ qr_payload: qrPayload, source: 'qr' })
            });
            const data = await res.json();

            if (data.success) {
                status.textContent = data.message || '成功獲得物品！';
                status.className = 'text-sm text-emerald-400 mb-4';
                btn.classList.add('hidden');
                if (data.applied_effect && data.applied_effect.effect_text) {
                    const effectEl = document.getElementById('claim-effect');
                    if (effectEl) effectEl.textContent = data.applied_effect.effect_text;
                }
            } else {
                status.textContent = data.error || '領取失敗';
                status.className = 'text-sm text-red-400 mb-4';
                btn.disabled = false;
            }
        }

        claimNow();
    </script>
</body>
</html>
"""

# ==================== GM HTML Templates ====================

GM_LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>GM Login • Oikonomia</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-white flex items-center justify-center min-h-screen">
    <div class="w-full max-w-sm">
        <div class="text-center mb-8">
            <h1 class="text-3xl font-bold">GM 後台</h1>
            <p class="text-zinc-400 mt-2">請輸入管理員 PIN</p>
        </div>
        
        <form id="gm-login-form" class="space-y-4">
            <input type="password" id="pin" placeholder="輸入 GM PIN" 
                   class="w-full bg-zinc-900 border border-zinc-700 focus:border-amber-500 rounded-2xl px-6 py-4 text-xl text-center">
            <button type="submit" 
                    class="w-full bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold py-4 rounded-2xl">
                登入 GM 後台
            </button>
        </form>
    </div>

    <script>
        document.getElementById('gm-login-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            const pin = document.getElementById('pin').value;
            
            const res = await fetch('/gm/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({pin: pin})
            });
            
            const data = await res.json();
            if (data.success) {
                window.location.href = '/gm/dashboard';
            } else {
                alert(data.error || '登入失敗');
            }
        });
    </script>
</body>
</html>
"""

GM_DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>GM Dashboard • Oikonomia</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        .hidden { display: none !important; }
        .gm-tab { background: #27272a; color: #a1a1aa; }
        .gm-tab.active { background: #f59e0b; color: #09090b; }
        .route-card {
            border: 3px solid #2C3E50;
            border-radius: 12px;
            cursor: pointer;
            transition: transform 0.1s ease, box-shadow 0.1s ease;
            box-shadow: 4px 4px 0px rgba(44, 62, 80, 0.5);
        }
        .route-card:hover { transform: translate(-2px, -2px); box-shadow: 6px 6px 0px rgba(44, 62, 80, 0.5); }
        .route-iggy { background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%); }
        .route-marah { background: linear-gradient(135deg, #1e3a5f 0%, #1e40af 100%); }
    </style>
</head>
<body class="bg-zinc-950 text-white p-8">
    <div class="max-w-6xl mx-auto">
        <div class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-3xl font-bold">GM Dashboard</h1>
                <p class="text-zinc-400 text-sm mt-1">即時監控所有玩家狀態</p>
            </div>
            <div class="flex items-center gap-x-3">
                <div class="text-xs px-3 py-1.5 bg-zinc-800 rounded-2xl text-zinc-400 flex items-center gap-x-2">
                    <i class="fa-solid fa-sync"></i>
                    <span>手動刷新</span>
                </div>
                <button onclick="location.reload()" 
                        class="px-5 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-2xl text-sm flex items-center gap-x-2">
                    <i class="fa-solid fa-redo"></i>
                    <span>手動刷新</span>
                </button>
                <a href="/" class="px-5 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-2xl text-sm">返回玩家端</a>
            </div>
        </div>

        <!-- Tab 切換 -->
        <div class="flex gap-x-2 mb-6 px-1">
            <button onclick="switchGMTab('squads')" id="tab-squads"
                    class="gm-tab active px-6 py-2 rounded-2xl text-sm font-medium">玩家狀態</button>
            <button onclick="switchGMTab('teams')" id="tab-teams"
                    class="gm-tab px-6 py-2 rounded-2xl text-sm font-medium">Team 管理</button>
            <button onclick="switchGMTab('overview')" id="tab-overview"
                    class="gm-tab px-6 py-2 rounded-2xl text-sm font-medium">進度總覽</button>
            <button onclick="switchGMTab('combat')" id="tab-combat"
                    class="gm-tab px-6 py-2 rounded-2xl text-sm font-medium">戰鬥監控</button>
        </div>

        <div id="gm-squads-tab">
        <div class="bg-zinc-900 rounded-3xl p-6">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-semibold">所有玩家即時狀態</h2>
                <div class="text-xs text-zinc-500">最後更新：{{ last_update }}</div>
            </div>
            
            <table class="w-full">
                <thead>
                    <tr class="border-b border-zinc-700 text-left text-sm text-zinc-400">
                        <th class="py-3 pl-2 w-12"></th>
                        <th class="py-3">玩家名稱</th>
                        <th class="py-3">路線</th>
                        <th class="py-3">生命值</th>
                        <th class="py-3">神智</th>
                        <th class="py-3">力量/智力/韌性</th>
                        <th class="py-3">提交次數</th>
                        <th class="py-3">操作</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-zinc-800">
                    {% for squad in squads %}
                    <tr class="hover:bg-zinc-800/60">
                        <td class="py-4 pl-2">
                            <img src="/static/avatars/{{ squad.avatar or 'default.png' }}"
                                 class="w-10 h-10 rounded-full object-cover border border-zinc-600">
                        </td>
                        <td class="py-4 font-mono font-semibold text-amber-400">
                            <a href="/gm/squad/{{ squad.squad_id }}" class="hover:underline">
                                {{ squad.display_name or squad.squad_id }}
                            </a>
                        </td>
                        <td class="py-4 text-sm">{{ squad.route_label }}</td>
                        <td class="py-4">
                            <div class="flex items-center gap-x-3">
                                <span class="font-mono w-8">{{ squad.hp }}</span>
                                <div class="w-28 h-2 bg-zinc-700 rounded-full">
                                    <div class="h-2 bg-red-500 rounded-full" style="width: {{ squad.hp }}%"></div>
                                </div>
                            </div>
                        </td>
                        <td class="py-4">
                            <div class="flex items-center gap-x-3">
                                <span class="font-mono w-8">{{ squad.sanity }}</span>
                                <div class="w-28 h-2 bg-zinc-700 rounded-full">
                                    <div class="h-2 bg-amber-500 rounded-full" style="width: {{ squad.sanity }}%"></div>
                                </div>
                            </div>
                        </td>
                        <td class="py-4 font-mono text-xs">{{ squad.power }}/{{ squad.intellect }}/{{ squad.resilience }}</td>
                        <td class="py-4">
                            <span class="px-3 py-1 bg-zinc-700 rounded-full text-xs">{{ squad.submission_count }} 次</span>
                            
                        </td>
                        <td class="py-4">
                            {% if squad.submission_count > 0 %}
                            <button onclick="viewPlayerLogs('{{ squad.squad_id }}')"
                                    class="px-3 py-1 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-full mr-2">
                                任務 Log
                            </button>
                            <a href="/gm/squad/{{ squad.squad_id }}" 
                               class="px-3 py-1 text-xs bg-amber-500 hover:bg-amber-600 text-zinc-950 rounded-full">
                                詳情
                            </a>
                            {% else %}
                            <span class="text-xs text-zinc-500">—</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Global Event -->
        <div class="bg-zinc-900 rounded-3xl p-6 mt-6">
            <h2 class="text-xl font-semibold mb-4">觸發 Global Event</h2>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                
                <!-- 全營神智調整 -->
                <div class="bg-zinc-800 rounded-2xl p-5">
                    <div class="font-medium mb-3">全營神智調整</div>
                    <div class="flex gap-x-2">
                        <input type="number" id="sanity-value" value="-5" 
                               class="flex-1 bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button onclick="triggerGlobalEvent('adjust_sanity')" 
                                class="px-6 py-2 bg-amber-600 hover:bg-amber-700 rounded-2xl text-sm">
                            執行
                        </button>
                    </div>
                    <div class="text-xs text-zinc-400 mt-2">正數 = 增加，負數 = 減少</div>
                </div>

                <!-- 劇情事件 -->
                <div class="bg-zinc-800 rounded-2xl p-5">
                    <div class="font-medium mb-3">劇情事件</div>
                    <div class="flex flex-wrap gap-2">
                        <button onclick="triggerGlobalEvent('judas_strengthen')" 
                                class="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm">
                            Judas 加強
                        </button>
                        <button onclick="triggerGlobalEvent('iggy_collapse')" 
                                class="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm">
                            Iggy 崩潰
                        </button>
                    </div>
                </div>

                <!-- 自訂全球事件 -->
                <div class="bg-zinc-800 rounded-2xl p-5 md:col-span-2">
                    <div class="font-medium mb-3">自訂全球事件</div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                        <input type="text" id="custom-event-title" placeholder="事件標題（例如：裂縫擴大）"
                               class="bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <select id="custom-event-effect-type"
                                class="bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                            <option value="">只記錄，不套用效果</option>
                            <option value="sanity_down">全營神智下降</option>
                            <option value="sanity_up">全營神智上升</option>
                            <option value="power_up">全營力量上升</option>
                            <option value="intellect_up">全營智力上升</option>
                            <option value="resilience_up">全營韌性上升</option>
                            <option value="global_debuff">全球減益（只記錄）</option>
                        </select>
                    </div>
                    <textarea id="custom-event-description" rows="2" placeholder="事件描述（可選）"
                              class="w-full bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm mb-3"></textarea>
                    <div class="flex gap-x-3 items-center">
                        <input type="number" id="custom-event-effect-value" value="5" placeholder="效果數值"
                               class="w-32 bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button onclick="createCustomGlobalEvent()"
                                class="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-2xl text-sm">
                            建立全球事件
                        </button>
                    </div>
                    <div class="text-xs text-zinc-400 mt-2">事件會顯示喺玩家日誌頁最底部嘅「全球事件記錄」</div>
                </div>

            </div>
        </div>

        <!-- Global Announcement -->
        <div class="bg-zinc-900 rounded-3xl p-6 mt-6">
            <h2 class="text-xl font-semibold mb-4">發送 Global Announcement</h2>
            
            <div class="flex gap-x-3">
                <input type="text" id="announcement-input" placeholder="輸入要發送嘅訊息..." 
                       class="flex-1 bg-zinc-800 border border-zinc-700 rounded-2xl px-5 py-3">
                <button onclick="sendAnnouncement()" 
                        class="px-8 py-3 bg-blue-600 hover:bg-blue-700 rounded-2xl font-medium">
                    發送
                </button>
            </div>
        </div>

        <!-- Danger Zone -->
        <div class="mt-8 border border-red-500/30 rounded-3xl p-6">
            <div class="flex items-center gap-x-2 mb-4">
                <i class="fa-solid fa-exclamation-triangle text-red-400"></i>
                <h2 class="text-lg font-semibold text-red-400">Danger Zone</h2>
            </div>
            
            <div class="flex items-center justify-between mb-4 pb-4 border-b border-red-500/20">
                <div>
                    <div class="font-medium">清空所有玩家上傳圖片</div>
                    <div class="text-xs text-zinc-400">刪除 uploads 資料夾內嘅圖片檔案，並清空提交記錄中的圖片欄位（可減少 Storage）</div>
                </div>
                <button onclick="showClearImagesModal()"
                        class="px-6 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm font-medium">
                    清空圖片
                </button>
            </div>

            <div class="flex items-center justify-between">
                <div>
                    <div class="font-medium">重置整個遊戲</div>
                    <div class="text-xs text-zinc-400">會刪除所有玩家ID（FRAG-XX）、Team 同提交記錄，一切由零開始</div>
                </div>
                <button onclick="showResetModal()" 
                        class="px-6 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm font-medium">
                    重置遊戲
                </button>
            </div>
        </div>
        </div>

        <div id="gm-teams-tab" class="hidden">
        <!-- Team 管理 (加強版) -->
        <div class="bg-zinc-900 rounded-3xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-xl font-semibold">Team 管理</h2>
                <button onclick="loadGMTeams()" 
                        class="px-4 py-1.5 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm flex items-center gap-x-2">
                    <i class="fa-solid fa-sync"></i>
                    <span>刷新</span>
                </button>
            </div>

            <!-- 建立新 Team -->
            <div class="bg-zinc-800 rounded-2xl p-5 mb-4">
                <div class="font-medium mb-3">建立新 Team</div>
                <div class="flex gap-x-3">
                    <input type="text" id="new-team-name" placeholder="輸入隊名（例如：界線守護者）" 
                           class="flex-1 bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                    <button onclick="gmCreateTeam()" 
                            class="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-2xl text-sm font-medium">
                        建立新隊
                    </button>
                </div>
            </div>

            <!-- Teams 列表 -->
            <div id="gm-teams-list" class="space-y-4"></div>
        </div>
        </div>

        <div id="gm-overview-tab" class="hidden">
        <div class="bg-zinc-900 rounded-3xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-xl font-semibold">隊伍 / 玩家進度總覽</h2>
                <button onclick="loadTeamsOverview()"
                        class="px-4 py-1.5 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm flex items-center gap-x-2">
                    <i class="fa-solid fa-sync"></i>
                    <span>刷新</span>
                </button>
            </div>
            <div id="gm-overview-content" class="text-zinc-400 text-center py-8">載入中...</div>
        </div>
        </div>

        <div id="gm-combat-tab" class="hidden">
        <div class="bg-zinc-900 rounded-3xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-xl font-semibold">進行中戰鬥</h2>
                <button onclick="loadActiveCombats()"
                        class="px-4 py-1.5 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm flex items-center gap-x-2">
                    <i class="fa-solid fa-sync"></i>
                    <span>刷新</span>
                </button>
            </div>
            <div id="gm-combat-content" class="text-zinc-400 text-center py-8">載入中...</div>
        </div>
        </div>

        <script>
        function sendAnnouncement() {
            const message = document.getElementById('announcement-input').value.trim();
            if (!message) {
                alert('請輸入訊息');
                return;
            }

            fetch('/gm/announcement', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({message: message})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert('公告已發送');
                    document.getElementById('announcement-input').value = '';
                }
            });
        }
        </script>

        <script>
        function triggerGlobalEvent(eventType) {
            let value = 0;
            if (eventType === 'adjust_sanity') {
                value = parseInt(document.getElementById('sanity-value').value) || 0;
            }

            fetch('/gm/global_event', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    event_type: eventType,
                    value: value
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert(data.message || '事件已觸發');
                    location.reload();
                } else {
                    alert('觸發失敗');
                }
            });
        }

        async function createCustomGlobalEvent() {
            const title = document.getElementById('custom-event-title').value.trim();
            const description = document.getElementById('custom-event-description').value.trim();
            const effect_type = document.getElementById('custom-event-effect-type').value;
            const effect_value = parseInt(document.getElementById('custom-event-effect-value').value) || 0;

            if (!title) {
                alert('請輸入事件標題');
                return;
            }

            const res = await fetch('/gm/create_global_event', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ title, description, effect_type: effect_type || null, effect_value })
            });
            const data = await res.json();

            if (data.success) {
                alert(data.message || '全球事件已建立');
                document.getElementById('custom-event-title').value = '';
                document.getElementById('custom-event-description').value = '';
                document.getElementById('custom-event-effect-type').value = '';
                document.getElementById('custom-event-effect-value').value = '5';
            } else {
                alert(data.error || '建立失敗');
            }
        }

        // ==================== GM Team 管理加強版 ====================
        async function loadGMTeams() {
            const container = document.getElementById('gm-teams-list');
            container.innerHTML = '<div class="text-zinc-400 text-center py-4">載入中...</div>';
            
            const res = await fetch('/gm/teams');
            const data = await res.json();
            
            if (!data.teams || data.teams.length === 0) {
                container.innerHTML = '<div class="text-zinc-400 text-center py-8">尚未有任何 Team</div>';
                return;
            }
            
            container.innerHTML = '';
            
            // 統一排序（同玩家一樣）
            data.teams.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
            
            for (const team of data.teams) {
                const div = document.createElement('div');
                div.className = 'bg-zinc-800 rounded-2xl p-5 border border-zinc-700';
                const safeName = (team.team_name || '').replace(/'/g, "\\'");
                
                div.innerHTML = `
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <div class="font-mono font-bold text-emerald-400">${team.team_id}</div>
                            <div class="text-lg font-semibold flex items-center gap-x-2">
                                ${team.team_name}
                                <button onclick="gmEditTeamName('${team.team_id}', '${safeName}')" 
                                        class="text-xs px-2 py-0.5 bg-zinc-700 hover:bg-zinc-600 rounded">改名</button>
                            </div>
                            <div class="text-xs text-zinc-400 mt-0.5">${team.member_count} 位成員</div>
                        </div>
                        <div>
                            <div class="text-xs px-3 py-1 rounded-full text-center ${team.route === 'iggy' ? 'bg-red-900/60 text-red-400' : team.route === 'marah' ? 'bg-blue-900/60 text-blue-400' : 'bg-zinc-700 text-zinc-400'}">
                                ${team.route === 'iggy' ? '🔥 Iggy 線' : team.route === 'marah' ? '🌊 Marah 線' : '未設定路線'}
                            </div>
                        </div>
                    </div>
                    
                    <div class="flex flex-wrap gap-2 mb-3">
                        <button onclick="gmAssignSquadToTeam('${team.team_id}')" 
                                class="px-3 py-1.5 text-xs bg-amber-600 hover:bg-amber-700 rounded-xl flex items-center gap-x-1">
                            <i class="fa-solid fa-exchange-alt"></i>
                            <span>轉隊 / 分配</span>
                        </button>
                        <button onclick="gmSetRoutePrompt('${team.team_id}')" 
                                class="px-3 py-1.5 text-xs bg-purple-600 hover:bg-purple-700 rounded-xl">設定路線</button>
                        <button onclick="gmViewTeamMembers('${team.team_id}', '${safeName}')" 
                                class="px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-xl">查看成員</button>
                    </div>
                `;
                container.appendChild(div);
            }
        }

        async function gmCreateTeam() {
            const name = document.getElementById('new-team-name').value.trim() || '新小隊';
            const res = await fetch('/gm/create_team', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({team_name: name})
            });
            const data = await res.json();
            if (data.success) {
                alert(`Team ${data.team_id} 已建立`);
                document.getElementById('new-team-name').value = '';
                loadGMTeams();
            }
        }

        function gmEditTeamName(teamId, currentName) {
            const safeVal = (currentName || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100]';
            
            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-zinc-700">
                    <div class="text-xl font-bold mb-1">修改隊名</div>
                    <div class="text-sm text-zinc-400 mb-4">Team ID: ${teamId}</div>
                    
                    <input type="text" id="edit-team-name-input" value="${safeVal}" 
                           class="w-full bg-zinc-800 border border-zinc-700 focus:border-amber-500 rounded-2xl px-5 py-3 text-lg mb-6">
                    
                    <div class="flex gap-x-3">
                        <button onclick="this.closest('.fixed').remove()" 
                                class="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm">
                            取消
                        </button>
                        <button onclick="confirmUpdateTeamName('${teamId}', this)" 
                                class="flex-1 py-3 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl text-sm">
                            確認修改
                        </button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            setTimeout(() => {
                const input = modal.querySelector('#edit-team-name-input');
                if (input) input.focus();
            }, 100);
        }

        function confirmUpdateTeamName(teamId, buttonElement) {
            const input = document.getElementById('edit-team-name-input');
            const newName = input.value.trim();
            
            if (!newName) {
                alert('隊名不能為空');
                return;
            }

            buttonElement.disabled = true;
            buttonElement.textContent = '更新中...';

            fetch('/gm/update_team_name', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    team_id: teamId,
                    new_name: newName
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    buttonElement.closest('.fixed').remove();
                    alert('隊名已成功更新！');
                    loadGMTeams();
                } else {
                    alert(data.error || '更新失敗');
                    buttonElement.disabled = false;
                    buttonElement.textContent = '確認修改';
                }
            })
            .catch(() => {
                alert('發生錯誤，請重試');
                buttonElement.disabled = false;
                buttonElement.textContent = '確認修改';
            });
        }

        async function gmAssignSquadToTeam(teamId) {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100]';

            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-zinc-700">
                    <div class="text-xl font-bold mb-1">分配 / 轉隊玩家</div>
                    <div class="text-sm text-zinc-400 mb-4">Team ID: ${teamId}</div>

                    <div class="mb-4">
                        <div class="text-sm text-zinc-400 mb-2">選擇玩家：</div>
                        <select id="assign-player-select"
                                class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-3 text-sm">
                            <option value="">載入中...</option>
                        </select>
                    </div>

                    <div class="flex gap-x-3">
                        <button onclick="this.closest('.fixed').remove()"
                                class="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm">
                            取消
                        </button>
                        <button onclick="confirmAssignPlayer('${teamId}', this)"
                                class="flex-1 py-3 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl text-sm">
                            確認分配
                        </button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            try {
                const res = await fetch(
                    `/gm/assignable_players?team_id=${encodeURIComponent(teamId)}`,
                    { credentials: 'same-origin' }
                );
                const data = await res.json();

                const select = modal.querySelector('#assign-player-select');
                select.innerHTML = '<option value="">-- 請選擇玩家 --</option>';

                if (!res.ok || data.success === false) {
                    select.innerHTML = '<option value="">載入失敗</option>';
                    alert(data.error || '載入玩家列表失敗，請重新登入 GM');
                    return;
                }

                const players = data.players || [];
                if (players.length === 0) {
                    select.innerHTML = '<option value="">（無可分配玩家 — 可能全部已在隊內）</option>';
                    return;
                }

                players.forEach(player => {
                    const option = document.createElement('option');
                    option.value = player.squad_id;
                    option.textContent = player.label || `${player.display_name} (${player.squad_id})`;
                    select.appendChild(option);
                });
            } catch (e) {
                alert('載入玩家列表失敗');
                modal.remove();
            }
        }

        async function confirmAssignPlayer(teamId, buttonElement) {
            const modal = buttonElement.closest('.fixed');
            const select = modal.querySelector('#assign-player-select');
            const squadId = select.value;

            if (!squadId) {
                alert('請選擇一個玩家');
                return;
            }

            buttonElement.disabled = true;
            buttonElement.textContent = '分配中...';

            const res = await fetch('/gm/assign_squad', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    squad_id: squadId,
                    team_id: teamId
                })
            });

            const data = await res.json();

            if (data.success) {
                modal.remove();
                alert(data.message || '分配成功！');
                loadGMTeams();
            } else {
                alert(data.error || '分配失敗');
                buttonElement.disabled = false;
                buttonElement.textContent = '確認分配';
            }
        }

        function gmSetRoutePrompt(teamId) {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100]';
            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-zinc-700">
                    <div class="text-xl font-bold mb-1">設定 Team 路線</div>
                    <div class="text-sm text-zinc-400 mb-6">Team ID: ${teamId}</div>
                    
                    <div class="grid grid-cols-2 gap-4 mb-6">
                        <div onclick="gmConfirmSetRoute('${teamId}', 'iggy', this)" 
                             class="route-card route-iggy p-6 text-center cursor-pointer">
                            <div class="text-3xl mb-2">🔥</div>
                            <div class="text-xl font-bold">Iggy 路線</div>
                            <div class="text-xs mt-1 opacity-80">界線、力量、面對 Judas</div>
                        </div>
                        
                        <div onclick="gmConfirmSetRoute('${teamId}', 'marah', this)" 
                             class="route-card route-marah p-6 text-center cursor-pointer">
                            <div class="text-3xl mb-2">🌊</div>
                            <div class="text-xl font-bold">Marah 路線</div>
                            <div class="text-xs mt-1 opacity-80">智慧、韌性、深度連結</div>
                        </div>
                    </div>
                    
                    <button onclick="this.closest('.fixed').remove()" 
                            class="w-full py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm">
                        取消
                    </button>
                </div>
            `;
            document.body.appendChild(modal);
        }

        function gmConfirmSetRoute(teamId, route, element) {
            fetch('/gm/set_team_route', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({team_id: teamId, route: route})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    element.closest('.fixed').remove();
                    alert('路線已成功設定為 ' + (route === 'iggy' ? 'Iggy' : 'Marah'));
                    loadGMTeams();
                } else {
                    alert('設定失敗');
                }
            });
        }

        async function gmViewTeamMembers(teamId, teamName) {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100]';

            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-2xl mx-4 rounded-3xl p-6 border border-zinc-700 max-h-[80vh] overflow-auto">
                    <div class="flex justify-between items-center mb-6">
                        <div>
                            <div class="text-xl font-bold">${teamName}</div>
                            <div class="text-sm text-zinc-400">Team ID: ${teamId}</div>
                        </div>
                        <button onclick="this.closest('.fixed').remove()"
                                class="text-3xl leading-none text-zinc-400 hover:text-white">×</button>
                    </div>
                    <div id="team-members-content">
                        <div class="text-center py-8 text-zinc-400">載入中...</div>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            const contentEl = modal.querySelector('#team-members-content');
            try {
                const res = await fetch(`/gm/team_members/${teamId}`);
                const data = await res.json();

                if (!data.members || data.members.length === 0) {
                    contentEl.innerHTML = '<div class="text-center py-6 text-zinc-400">暫無成員</div>';
                    return;
                }

                contentEl.innerHTML = '';
                data.members.forEach(m => {
                    const el = document.createElement('div');
                    el.className = 'bg-zinc-800 border border-zinc-700 rounded-2xl p-4 mb-3';
                    const name = m.display_name || m.squad_id;
                    el.innerHTML = `
                        <div class="flex justify-between items-start mb-2">
                            <div class="flex items-center gap-x-3">
                                <img src="/static/avatars/${m.avatar || 'default.png'}"
                                     class="w-10 h-10 rounded-full object-cover border border-zinc-600 shrink-0">
                                <div>
                                    <div class="font-semibold text-lg">${name}</div>
                                    <div class="text-xs text-zinc-500 font-mono">${m.squad_id}</div>
                                </div>
                            </div>
                            <a href="/gm/squad/${m.squad_id}" class="text-xs px-3 py-1 bg-amber-500/20 text-amber-400 rounded-xl hover:bg-amber-500/30">詳情</a>
                        </div>
                        <div class="grid grid-cols-5 gap-2 text-center text-xs">
                            <div><div class="text-red-400 font-mono">${m.hp}</div><div class="text-zinc-500">生命值</div></div>
                            <div><div class="text-purple-400 font-mono">${m.sanity}</div><div class="text-zinc-500">神智</div></div>
                            <div><div class="text-orange-400 font-mono">${m.power}</div><div class="text-zinc-500">力量</div></div>
                            <div><div class="text-blue-400 font-mono">${m.intellect}</div><div class="text-zinc-500">智力</div></div>
                            <div><div class="text-emerald-400 font-mono">${m.resilience}</div><div class="text-zinc-500">韌性</div></div>
                        </div>
                    `;
                    contentEl.appendChild(el);
                });
            } catch (e) {
                contentEl.innerHTML = '<div class="text-red-400 text-center py-6">載入失敗</div>';
            }
        }

        async function downloadTeamImages(teamId) {
            try {
                const res = await fetch(`/gm/download_team_images/${encodeURIComponent(teamId)}`, { credentials: 'same-origin' });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    alert(data.error || '下載失敗');
                    return;
                }
                const blob = await res.blob();
                const disposition = res.headers.get('Content-Disposition') || '';
                let filename = `team_${teamId}_images.zip`;
                const match = disposition.match(/filename="?([^";]+)"?/);
                if (match) filename = match[1];
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = filename;
                link.click();
                URL.revokeObjectURL(url);
            } catch (e) {
                alert('下載失敗');
            }
        }

        async function viewPlayerLogs(squadId) {
            const modal = document.getElementById('player-log-modal');
            const titleEl = document.getElementById('player-log-modal-title');
            const contentEl = document.getElementById('player-log-modal-content');
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            titleEl.textContent = '載入中...';
            contentEl.innerHTML = '<div class="text-zinc-400 text-center py-8">載入中...</div>';

            try {
                const res = await fetch(`/gm/player_logs/${encodeURIComponent(squadId)}`, { credentials: 'same-origin' });
                const data = await res.json();

                if (!res.ok || !data.success) {
                    titleEl.textContent = '載入失敗';
                    contentEl.innerHTML = `<div class="text-red-400 text-center py-8">${data.error || '載入失敗'}</div>`;
                    return;
                }

                const player = data.player || {};
                const teamLabel = player.team_name || player.team_id || '未入隊';
                titleEl.textContent = `${player.display_name || squadId} · ${teamLabel}`;

                const logs = data.logs || [];
                if (logs.length === 0) {
                    contentEl.innerHTML = '<div class="text-zinc-400 text-center py-8">暫無任務記錄</div>';
                    return;
                }

                contentEl.innerHTML = '';
                logs.forEach(log => {
                    const div = document.createElement('div');
                    div.className = 'border border-zinc-700 rounded-2xl p-4 mb-3';
                    div.innerHTML = `
                        <div class="flex flex-wrap justify-between items-start gap-2 mb-2">
                            <div>
                                <div class="font-semibold text-amber-400">${log.task_name}</div>
                                <div class="text-xs text-zinc-500 font-mono">${log.task_id || ''}</div>
                            </div>
                            <span class="text-xs px-2 py-0.5 bg-emerald-900/50 text-emerald-300 rounded-full">${log.status}</span>
                        </div>
                        <div class="text-xs text-zinc-500 mb-2">${log.timestamp || ''}</div>
                        ${log.description ? `<div class="text-zinc-300 text-sm mb-3 whitespace-pre-wrap">${log.description}</div>` : ''}
                        ${(log.photo_url || log.photo_path) ? `
                            <img src="${log.photo_url || '/' + log.photo_path}" class="max-h-48 rounded-xl border border-zinc-700">
                        ` : ''}
                    `;
                    contentEl.appendChild(div);
                });
            } catch (e) {
                titleEl.textContent = '載入失敗';
                contentEl.innerHTML = '<div class="text-red-400 text-center py-8">載入失敗</div>';
            }
        }

        function hidePlayerLogModal() {
            const modal = document.getElementById('player-log-modal');
            modal.classList.remove('flex');
            modal.classList.add('hidden');
        }

        function formatOverviewTime(ts) {
            if (!ts) return '—';
            try {
                const d = new Date(ts);
                if (isNaN(d.getTime())) return ts;
                return d.toLocaleString('zh-HK', { hour12: false });
            } catch (e) {
                return ts;
            }
        }

        async function loadTeamsOverview() {
            const container = document.getElementById('gm-overview-content');
            container.innerHTML = '<div class="text-zinc-400 text-center py-8">載入中...</div>';

            try {
                const res = await fetch('/gm/teams_overview', { credentials: 'same-origin' });
                const data = await res.json();

                if (!res.ok || !data.success) {
                    container.innerHTML = '<div class="text-red-400 text-center py-8">載入失敗</div>';
                    return;
                }

                const teams = data.teams || [];
                const solo = data.solo_players || [];

                if (teams.length === 0 && solo.length === 0) {
                    container.innerHTML = '<div class="text-zinc-400 text-center py-8">暫無隊伍或玩家資料</div>';
                    return;
                }

                let html = '';

                if (teams.length > 0) {
                    html += '<div class="space-y-4">';
                    teams.forEach(team => {
                        const routeClass = team.route === 'iggy'
                            ? 'bg-red-900/40 text-red-300'
                            : team.route === 'marah'
                                ? 'bg-blue-900/40 text-blue-300'
                                : 'bg-zinc-700 text-zinc-300';
                        html += `
                            <div class="bg-zinc-800 border border-zinc-700 rounded-2xl p-5 text-left">
                                <div class="flex flex-wrap justify-between items-start gap-3 mb-4">
                                    <div>
                                        <div class="text-lg font-semibold text-emerald-400">${team.team_name}</div>
                                        <div class="text-xs text-zinc-500 font-mono mt-0.5">${team.team_id}</div>
                                        <div class="text-sm text-zinc-300 mt-1">隊長：${team.leader_name} · ${team.member_count} 位成員</div>
                                    </div>
                                    <span class="text-xs px-3 py-1 rounded-full ${routeClass}">${team.route_label}</span>
                                </div>
                                <div class="grid grid-cols-2 md:grid-cols-5 gap-3 text-center text-xs mb-4">
                                    <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-red-400 font-mono text-base">${team.avg_hp}</div><div class="text-zinc-500">平均生命值</div></div>
                                    <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-purple-400 font-mono text-base">${team.avg_sanity}</div><div class="text-zinc-500">平均神智</div></div>
                                    <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-orange-400 font-mono text-base">${team.avg_power}</div><div class="text-zinc-500">平均力量</div></div>
                                    <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-blue-400 font-mono text-base">${team.avg_intellect}</div><div class="text-zinc-500">平均智力</div></div>
                                    <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-emerald-400 font-mono text-base">${team.avg_resilience}</div><div class="text-zinc-500">平均韌性</div></div>
                                </div>
                                <div class="flex flex-wrap gap-x-6 gap-y-1 text-sm text-zinc-400 mb-4">
                                    <span>已完成任務：<strong class="text-amber-400">${team.distinct_tasks}</strong></span>
                                    <span>劇情階段：<strong class="text-zinc-200">Stage ${team.story_stage}</strong></span>
                                    <span>提交次數：<strong class="text-zinc-200">${team.submission_count}</strong></span>
                                    <span>最近提交：<strong class="text-zinc-200">${formatOverviewTime(team.last_submission)}</strong></span>
                                </div>
                                <div class="flex flex-wrap gap-2 mb-4">
                                    <button onclick="downloadTeamImages('${team.team_id}')"
                                            class="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 rounded-xl flex items-center gap-x-1">
                                        <i class="fa-solid fa-download"></i>
                                        <span>下載該隊圖片 (ZIP)</span>
                                    </button>
                                </div>
                                ${(team.members && team.members.length) ? `
                                    <div class="border-t border-zinc-700 pt-3">
                                        <div class="text-xs text-zinc-500 mb-2">隊員任務記錄</div>
                                        <div class="flex flex-wrap gap-2">
                                            ${team.members.map(m => `
                                                <button onclick="viewPlayerLogs('${m.squad_id}')"
                                                        class="px-2 py-1 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-lg">
                                                    ${m.is_leader ? '👑 ' : ''}${m.display_name}
                                                </button>
                                            `).join('')}
                                        </div>
                                    </div>
                                ` : ''}
                            </div>
                        `;
                    });
                    html += '</div>';
                }

                if (solo.length > 0) {
                    html += `
                        <div class="mt-8">
                            <h3 class="text-lg font-semibold text-left mb-3 text-zinc-300">未加入隊伍的玩家</h3>
                            <div class="overflow-x-auto">
                                <table class="w-full text-sm text-left">
                                    <thead>
                                        <tr class="border-b border-zinc-700 text-zinc-400">
                                            <th class="py-2 pr-4">玩家</th>
                                            <th class="py-2 pr-4">路線</th>
                                            <th class="py-2 pr-4">生命值/神智/力量/智力/韌性</th>
                                            <th class="py-2 pr-4">任務</th>
                                            <th class="py-2 pr-4">階段</th>
                                            <th class="py-2 pr-4">提交</th>
                                            <th class="py-2 pr-4">最近提交</th>
                                            <th class="py-2">操作</th>
                                        </tr>
                                    </thead>
                                    <tbody class="divide-y divide-zinc-800">
                    `;
                    solo.forEach(p => {
                        html += `
                            <tr class="hover:bg-zinc-800/50">
                                <td class="py-3 pr-4">
                                    <a href="/gm/squad/${p.squad_id}" class="text-amber-400 hover:underline">${p.display_name}</a>
                                    <div class="text-xs text-zinc-500 font-mono">${p.squad_id}</div>
                                </td>
                                <td class="py-3 pr-4 text-xs">${p.route_label}</td>
                                <td class="py-3 pr-4 font-mono text-xs">${p.hp}/${p.sanity}/${p.power}/${p.intellect}/${p.resilience}</td>
                                <td class="py-3 pr-4">${p.distinct_tasks}</td>
                                <td class="py-3 pr-4">Stage ${p.story_stage}</td>
                                <td class="py-3 pr-4">${p.submission_count}</td>
                                <td class="py-3 text-xs text-zinc-400">${formatOverviewTime(p.last_submission)}</td>
                                <td class="py-3">
                                    ${p.submission_count > 0 ? `
                                        <button onclick="viewPlayerLogs('${p.squad_id}')"
                                                class="px-2 py-1 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-lg">任務 Log</button>
                                    ` : '<span class="text-zinc-500">—</span>'}
                                </td>
                            </tr>
                        `;
                    });
                    html += '</tbody></table></div></div>';
                }

                container.innerHTML = html;
            } catch (e) {
                container.innerHTML = '<div class="text-red-400 text-center py-8">載入失敗</div>';
            }
        }

        async function loadActiveCombats() {
            const container = document.getElementById('gm-combat-content');
            container.innerHTML = '<div class="text-zinc-400 text-center py-8">載入中...</div>';

            try {
                const res = await fetch('/gm/active_combats', { credentials: 'same-origin' });
                const data = await res.json();

                if (!res.ok || !data.success) {
                    container.innerHTML = '<div class="text-red-400 text-center py-8">載入失敗</div>';
                    return;
                }

                const combats = data.combats || [];
                if (combats.length === 0) {
                    container.innerHTML = '<div class="text-zinc-400 text-center py-8">目前沒有進行中的戰鬥</div>';
                    return;
                }

                container.innerHTML = '<div class="space-y-4">' + combats.map(c => `
                    <div class="bg-zinc-800 border border-zinc-700 rounded-2xl p-5 text-left">
                        <div class="flex flex-wrap justify-between items-start gap-3 mb-3">
                            <div>
                                <div class="text-lg font-semibold text-red-400">${c.title || c.encounter_id}</div>
                                <div class="text-xs text-zinc-500 font-mono mt-0.5">Combat #${c.combat_id} · ${c.encounter_id}</div>
                                <div class="text-sm text-zinc-300 mt-1">${c.team_name || '未知隊伍'} (${c.team_id || '—'})</div>
                            </div>
                            <span class="text-xs px-3 py-1 rounded-full bg-amber-900/40 text-amber-300">${c.status}</span>
                        </div>
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-center text-xs mb-4">
                            <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-red-400 font-mono text-base">${c.enemy_hp}/${c.enemy_max_hp}</div><div class="text-zinc-500">敵人 HP</div></div>
                            <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-amber-400 font-mono text-base">Phase ${c.current_phase || 0}</div><div class="text-zinc-500">回合</div></div>
                            <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-emerald-400 font-mono text-base">${c.submitted_count}/${c.participant_count}</div><div class="text-zinc-500">已提交行動</div></div>
                            <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-zinc-200 font-mono text-xs">${formatOverviewTime(c.phase_deadline)}</div><div class="text-zinc-500">Phase 截止</div></div>
                        </div>
                        <div class="flex flex-wrap gap-2">
                            ${c.can_resolve ? `
                                <button onclick="gmResolveCombatPhase(${c.combat_id}, '${(c.title || c.encounter_id).replace(/'/g, '')}')"
                                        class="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 rounded-xl flex items-center gap-x-2">
                                    <i class="fa-solid fa-gavel"></i>
                                    <span>強制結算 Phase</span>
                                </button>
                            ` : `
                                <span class="text-xs text-zinc-500 py-2">非 player_phase，無法強制結算</span>
                            `}
                        </div>
                    </div>
                `).join('') + '</div>';
            } catch (e) {
                container.innerHTML = '<div class="text-red-400 text-center py-8">載入失敗</div>';
            }
        }

        async function gmResolveCombatPhase(combatId, title) {
            if (!confirm(`確定要強制結算「${title}」(Combat #${combatId}) 的 Player Phase？\\n未提交行動的隊員將視為未行動。`)) return;

            try {
                const res = await fetch('/gm/combat/resolve_phase', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ combat_id: combatId }),
                });
                const data = await res.json();

                if (!res.ok || !data.success) {
                    alert(data.error || '結算失敗');
                    return;
                }

                if (data.outcome === 'victory') {
                    alert('戰鬥結束：隊伍勝利！');
                } else if (data.outcome === 'defeat') {
                    alert('戰鬥結束：隊伍落敗。');
                } else {
                    alert(data.message || 'Phase 已強制結算');
                }
                loadActiveCombats();
            } catch (e) {
                alert('結算失敗：' + e.message);
            }
        }

        function switchGMTab(tab) {
            const squadsTab = document.getElementById('gm-squads-tab');
            const teamsTab = document.getElementById('gm-teams-tab');
            const overviewTab = document.getElementById('gm-overview-tab');
            const combatTab = document.getElementById('gm-combat-tab');
            const btnSquads = document.getElementById('tab-squads');
            const btnTeams = document.getElementById('tab-teams');
            const btnOverview = document.getElementById('tab-overview');
            const btnCombat = document.getElementById('tab-combat');
            const allTabs = [squadsTab, teamsTab, overviewTab, combatTab];
            const allBtns = [btnSquads, btnTeams, btnOverview, btnCombat];

            allTabs.forEach(el => el.classList.add('hidden'));
            allBtns.forEach(btn => btn.classList.remove('active', 'bg-amber-500', 'text-zinc-950'));

            if (tab === 'teams') {
                teamsTab.classList.remove('hidden');
                btnTeams.classList.add('active', 'bg-amber-500', 'text-zinc-950');
                loadGMTeams();
            } else if (tab === 'overview') {
                overviewTab.classList.remove('hidden');
                btnOverview.classList.add('active', 'bg-amber-500', 'text-zinc-950');
                loadTeamsOverview();
            } else if (tab === 'combat') {
                combatTab.classList.remove('hidden');
                btnCombat.classList.add('active', 'bg-amber-500', 'text-zinc-950');
                loadActiveCombats();
            } else {
                squadsTab.classList.remove('hidden');
                btnSquads.classList.add('active', 'bg-amber-500', 'text-zinc-950');
            }
        }

        setTimeout(() => {
            const btn = document.getElementById('tab-squads');
            if (btn) btn.classList.add('active', 'bg-amber-500', 'text-zinc-950');
        }, 300);
        </script>

        <!-- 玩家任務 Log Modal -->
        <div id="player-log-modal" onclick="if (event.target.id === 'player-log-modal') hidePlayerLogModal()"
             class="hidden fixed inset-0 bg-black/80 items-center justify-center z-[60]">
            <div onclick="event.stopImmediatePropagation()"
                 class="bg-zinc-900 w-full max-w-2xl mx-4 rounded-3xl p-6 border border-zinc-700 max-h-[85vh] flex flex-col">
                <div class="flex justify-between items-start mb-4 shrink-0">
                    <div>
                        <div class="text-lg font-bold" id="player-log-modal-title">任務 Log</div>
                        <div class="text-xs text-zinc-500 mt-0.5">玩家過往提交記錄</div>
                    </div>
                    <button onclick="hidePlayerLogModal()" class="text-3xl leading-none text-zinc-400 hover:text-white">×</button>
                </div>
                <div id="player-log-modal-content" class="overflow-y-auto flex-1"></div>
            </div>
        </div>

        <!-- 清空圖片確認 Modal -->
        <div id="clear-images-modal" onclick="if (event.target.id === 'clear-images-modal') hideClearImagesModal()"
             class="hidden fixed inset-0 bg-black/80 flex items-center justify-center z-[60]">
            <div onclick="event.stopImmediatePropagation()"
                 class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-red-500/30">

                <div class="text-red-400 font-semibold text-xl mb-2">⚠️ 確認清空所有上傳圖片</div>
                <div class="text-zinc-300 mb-6">此操作無法復原。請輸入 <span class="font-mono text-amber-400">CLEAR_IMAGES</span> 確認。</div>

                <input type="text" id="clear-images-confirm" placeholder="輸入 CLEAR_IMAGES"
                       class="w-full bg-zinc-800 border border-zinc-700 focus:border-red-500 rounded-2xl px-5 py-3 mb-4">

                <div class="flex gap-x-3">
                    <button onclick="hideClearImagesModal()"
                            class="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl">取消</button>
                    <button onclick="confirmClearAllImages()"
                            class="flex-1 py-3 bg-red-600 hover:bg-red-700 rounded-2xl font-medium">確認刪除</button>
                </div>
            </div>
        </div>

        <!-- 重置確認 Modal -->
        <div id="reset-modal" onclick="if (event.target.id === 'reset-modal') hideResetModal()" 
             class="hidden fixed inset-0 bg-black/80 flex items-center justify-center z-[60]">
            <div onclick="event.stopImmediatePropagation()" 
                 class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-red-500/30">
                
                <div class="text-red-400 font-semibold text-xl mb-2">⚠️ 確認重置遊戲</div>
                <div class="text-zinc-300 mb-6">此操作無法復原。請輸入重置密碼確認。</div>
                
                <input type="password" id="reset-password" placeholder="輸入重置密碼" 
                       class="w-full bg-zinc-800 border border-zinc-700 focus:border-red-500 rounded-2xl px-5 py-3 mb-4">
                
                <div class="flex gap-x-3">
                    <button onclick="hideResetModal()" 
                            class="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl">取消</button>
                    <button onclick="confirmResetGame()" 
                            class="flex-1 py-3 bg-red-600 hover:bg-red-700 rounded-2xl font-medium">確認重置</button>
                </div>
            </div>
        </div>

        <script>
        function showClearImagesModal() {
            document.getElementById('clear-images-modal').classList.remove('hidden');
            document.getElementById('clear-images-modal').classList.add('flex');
            document.getElementById('clear-images-confirm').focus();
        }

        function hideClearImagesModal() {
            document.getElementById('clear-images-modal').classList.remove('flex');
            document.getElementById('clear-images-modal').classList.add('hidden');
            document.getElementById('clear-images-confirm').value = '';
        }

        async function confirmClearAllImages() {
            const confirmText = document.getElementById('clear-images-confirm').value.trim();

            if (confirmText !== 'CLEAR_IMAGES') {
                alert('確認碼錯誤！請輸入 CLEAR_IMAGES');
                return;
            }

            if (!confirm('確定要刪除所有玩家上傳過的圖片嗎？此操作不可恢復！')) {
                return;
            }

            try {
                const res = await fetch('/gm/clear_all_images', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ confirm: confirmText })
                });
                const data = await res.json();

                if (data.success) {
                    alert(data.message || '圖片已清空');
                    hideClearImagesModal();
                } else {
                    alert(data.error || '清空失敗');
                }
            } catch (e) {
                alert('發生錯誤，請重試');
            }
        }

        function showResetModal() {
            document.getElementById('reset-modal').classList.remove('hidden');
            document.getElementById('reset-modal').classList.add('flex');
            document.getElementById('reset-password').focus();
        }

        function hideResetModal() {
            document.getElementById('reset-modal').classList.remove('flex');
            document.getElementById('reset-modal').classList.add('hidden');
            document.getElementById('reset-password').value = '';
        }

        function confirmResetGame() {
            const password = document.getElementById('reset-password').value;
            
            fetch('/gm/reset_game', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({password: password})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert(data.message || '遊戲已重置');
                    window.location.reload();
                } else {
                    alert(data.error || '密碼錯誤或重置失敗');
                }
            })
            .catch(() => {
                alert('發生錯誤，請重試');
            });
        }
        </script>
    </div>

</body>
</html>
"""

GM_SQUAD_DETAIL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ squad.display_name or squad.squad_id }} 詳情 • GM</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
</head>
<body class="bg-zinc-950 text-white p-8">
    <div class="max-w-5xl mx-auto">
        <div class="mb-8">
            <a href="/gm/dashboard" class="text-amber-400 hover:underline flex items-center gap-x-2 mb-2">
                <i class="fa-solid fa-arrow-left"></i>
                <span>返回 GM Dashboard</span>
            </a>
            
            <div class="flex items-end gap-x-4">
                <img src="/static/avatars/{{ squad.avatar or 'default.png' }}"
                     class="w-16 h-16 rounded-full object-cover border-2 border-zinc-600">
                <div class="flex items-end gap-x-3">
                    <h1 class="text-3xl font-bold">{{ squad.display_name or squad.squad_id }}</h1>
                </div>
            </div>
            
            <div class="text-sm text-zinc-400 mt-1">玩家詳情與提交記錄</div>
        </div>

        <div class="bg-zinc-900 rounded-3xl p-6 mb-8">
            <h2 class="text-lg font-semibold mb-4">玩家目前狀態</h2>
            
            <div class="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-4 text-sm">
                <div>
                    <span class="text-zinc-400">顯示名稱</span><br>
                    <span class="font-semibold text-lg">{{ squad.display_name or squad.squad_id }}</span>
                </div>
                <div>
                    <span class="text-zinc-400">所屬 Team</span><br>
                    <span class="font-mono text-emerald-400">{{ squad.team_id or '未加入任何隊' }}</span>
                </div>
                <div>
                    <span class="text-zinc-400">路線</span><br>
                    <span class="font-mono">{{ squad.route_label }}</span>
                </div>
                <div>
                    <span class="text-zinc-400">Resource</span><br>
                    <span class="font-mono text-purple-400">{{ squad.resources }}</span>
                </div>
                <div>
                    <span class="text-zinc-400">PIN 狀態</span><br>
                    <span class="font-mono {{ 'text-emerald-400' if squad.has_pin else 'text-zinc-500' }}">
                        {{ '已設定' if squad.has_pin else '未設定' }}
                    </span>
                </div>
                
                <div class="col-span-2 md:col-span-4 grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-3 mt-2 pt-4 border-t border-zinc-700">
                    <div>生命值: <span class="font-mono text-red-400">{{ squad.hp }}</span></div>
                    <div>神智: <span class="font-mono text-purple-400">{{ squad.sanity }}</span></div>
                    <div>力量: <span class="font-mono text-orange-400">{{ squad.power }}</span></div>
                    <div>智力: <span class="font-mono text-blue-400">{{ squad.intellect }}</span></div>
                    <div>韌性: <span class="font-mono text-emerald-400">{{ squad.resilience }}</span></div>
                </div>
            </div>
        </div>

        <button onclick="gmResetPlayerPin('{{ squad.squad_id }}', '{{ squad.display_name or squad.squad_id }}')"
                class="mb-8 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm">
            重置玩家 PIN
        </button>

        <!-- 手動調整數值 -->
        <div class="bg-zinc-900 rounded-3xl p-6 mt-6">
            <h2 class="text-lg font-semibold mb-4">手動調整數值</h2>
            
            <form id="adjust-form" class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <input type="hidden" name="squad_id" value="{{ squad.squad_id }}">
                
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">生命值</label>
                    <div class="flex gap-x-2">
                        <input type="number" name="value" id="hp-value" value="{{ squad.hp }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('hp')" 
                                class="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
                
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">神智</label>
                    <div class="flex gap-x-2">
                        <input type="number" name="value" id="sanity-value" value="{{ squad.sanity }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('sanity')" 
                                class="px-4 py-2 bg-amber-600 hover:bg-amber-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
                
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">力量</label>
                    <div class="flex gap-x-2">
                        <input type="number" id="power-value" value="{{ squad.power }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('power')" 
                                class="px-4 py-2 bg-orange-600 hover:bg-orange-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">智力</label>
                    <div class="flex gap-x-2">
                        <input type="number" id="intellect-value" value="{{ squad.intellect }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('intellect')" 
                                class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">韌性</label>
                    <div class="flex gap-x-2">
                        <input type="number" id="resilience-value" value="{{ squad.resilience }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('resilience')" 
                                class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">Resource</label>
                    <div class="flex gap-x-2">
                        <input type="number" id="resource-value" value="{{ squad.resources }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('resources')" 
                                class="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
            </form>
        </div>

        <script>
        function gmResetPlayerPin(squadId, displayName) {
            if (!confirm(`確定要重置 ${displayName || squadId} 的 PIN 嗎？`)) return;

            const newPin = prompt('輸入新 PIN（留空則自動生成 4 位數字）');

            fetch('/gm/reset_pin', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    squad_id: squadId,
                    new_pin: newPin || ''
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert(`${displayName || squadId} 的新 PIN 是：${data.new_pin}\\n請告知玩家！`);
                    location.reload();
                } else {
                    alert(data.error || '重置失敗');
                }
            });
        }

        function adjustValue(field) {
            let valueInput;
            const ids = {hp:'hp-value', sanity:'sanity-value', power:'power-value', intellect:'intellect-value', resilience:'resilience-value', resources:'resource-value'};
            valueInput = document.getElementById(ids[field]);

            const value = valueInput.value;
            const squadId = '{{ squad.squad_id }}';

            fetch('/gm/adjust', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    squad_id: squadId,
                    field: field,
                    value: value
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert(field + ' 已更新');
                    location.reload();
                } else {
                    alert('更新失敗: ' + data.error);
                }
            });
        }
        </script>

        <div class="bg-zinc-900 rounded-3xl p-6">
            <h2 class="text-lg font-semibold mb-4">提交記錄（{{ submissions|length }} 筆）</h2>
            
            {% if submissions %}
                <div class="space-y-6">
                    {% for sub in submissions %}
                    <div class="border border-zinc-700 rounded-2xl p-5">
                        <div class="flex justify-between text-sm mb-2">
                            <div>
                                <span class="text-amber-400 font-mono">{{ sub.task_id }}</span>
                            </div>
                            <div class="text-zinc-400 text-xs">{{ sub.timestamp }}</div>
                        </div>
                        
                        {% if sub.content %}
                        <div class="text-zinc-300 mb-3">{{ sub.content }}</div>
                        {% endif %}
                        
                        {% if sub.photo_url or sub.photo_path %}
                        <div>
                            <div class="text-xs text-zinc-400 mb-1">上傳相片：</div>
                            <img src="{{ sub.photo_url or '/' + sub.photo_path }}" class="max-h-64 rounded-xl border border-zinc-700">
                        </div>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
            {% else %}
                <div class="text-zinc-400 py-8 text-center">此小隊尚未有任何提交記錄。</div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "1").lower() in ("1", "true", "yes")
    print(f"\n  Oikonomia 本地伺服器")
    print(f"  ➜  http://localhost:{port}")
    print(f"  （注意：macOS 嘅 5000 port 通常被系統佔用，請用 {port}）\n")
    try:
        app.run(host="0.0.0.0", port=port, debug=debug)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"\n  ❌ Port {port} 已被佔用。請執行：")
            print(f"     lsof -ti:{port} | xargs kill -9")
            print(f"  或者用其他 port：PORT=5002 python3 app.py\n")
        raise