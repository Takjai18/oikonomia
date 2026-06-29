import sqlite3
from datetime import datetime

from models.settings import settings
from models.squad import apply_hp_change, get_squad, is_near_death_active
from utils.db_tx import immediate_transaction
from utils.helpers import clamped_stat_delta_expr, normalize_team_id

NEAR_DEATH_RESCUE_EFFECT_TYPES = frozenset({"hp_up", "near_death_rescue"})
RESCUE_REVIVE_HP = 25


def get_item_by_id(item_id):
    conn = sqlite3.connect(settings.db_path)
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
    conn = sqlite3.connect(settings.db_path)
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
    labels = settings.item_effect_labels or {}
    label = labels.get(effect_type)
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


def _apply_stat_delta(c, squad_id, stat, delta):
    row = c.execute(
        "SELECT hp, max_hp, sanity, power, intellect, resilience, near_death_until FROM squads WHERE squad_id = ?",
        (squad_id,),
    ).fetchone()
    if not row:
        return None

    if stat == "hp":
        if delta > 0 and is_near_death_active(dict(row)):
            return dict(row)
        new_hp, new_max_hp = apply_hp_change(row["hp"], row["max_hp"], delta)
        c.execute(
            "UPDATE squads SET hp = ?, max_hp = ? WHERE squad_id = ?",
            (new_hp, new_max_hp, squad_id),
        )
    elif stat == "sanity":
        operator = "+" if delta >= 0 else "-"
        magnitude = abs(delta)
        c.execute(
            f"UPDATE squads SET sanity = {clamped_stat_delta_expr('sanity', operator)} WHERE squad_id = ?",
            (magnitude, magnitude, squad_id),
        )
    else:
        operator = "+" if delta >= 0 else "-"
        magnitude = abs(delta)
        c.execute(
            f"UPDATE squads SET {stat} = {clamped_stat_delta_expr(stat, operator)} WHERE squad_id = ?",
            (magnitude, magnitude, squad_id),
        )

    updated = c.execute(
        "SELECT hp, max_hp, sanity, power, intellect, resilience FROM squads WHERE squad_id = ?",
        (squad_id,),
    ).fetchone()
    return dict(updated) if updated else None


def apply_item_effect_to_squad(squad_id, item):
    if not item or not item.get("has_ability") or not item.get("effect_type"):
        return None

    effect_type = item.get("effect_type")
    if effect_type == "mixed":
        return None

    stat_map = settings.item_effect_stat_map or {}
    squad_attrs = settings.squad_attributes or []
    stat = stat_map.get(effect_type)
    if not stat or stat not in squad_attrs:
        return None

    try:
        delta = int(item.get("effect_value") or 0)
    except (TypeError, ValueError):
        return None
    if delta == 0:
        return None

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        stats = _apply_stat_delta(c, squad_id, stat, delta)
        conn.commit()
    finally:
        conn.close()

    if not stats:
        return None

    return {
        "effect_type": effect_type,
        "effect_value": delta,
        "effect_text": format_item_effect_text(effect_type, delta),
        "stat": stat,
        "stats": stats,
    }


def team_has_item(team_id, item_id):
    if not team_id:
        return False
    clean_team_id = normalize_team_id(team_id)
    conn = sqlite3.connect(settings.db_path)
    count = conn.execute("""
        SELECT COUNT(*) FROM player_items pi
        JOIN squads s ON pi.squad_id = s.squad_id
        WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?)) AND pi.item_id = ?
    """, (clean_team_id, item_id)).fetchone()[0]
    conn.close()
    return count > 0


def team_has_item_by_name(team_id, item_name):
    if not team_id or not item_name:
        return False
    clean_team_id = normalize_team_id(team_id)
    conn = sqlite3.connect(settings.db_path)
    row = conn.execute("""
        SELECT COUNT(*) FROM player_items pi
        JOIN squads s ON pi.squad_id = s.squad_id
        JOIN items i ON pi.item_id = i.id
        WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?)) AND i.name = ?
    """, (clean_team_id, item_name)).fetchone()
    conn.close()
    return row[0] > 0


def grant_item_to_squad(squad_id, item_id, source="story"):
    squad = get_squad(squad_id)
    if not squad:
        return False, "找不到玩家", None

    item = get_item_by_id(item_id)
    if not item:
        return False, "物品不存在或已停用", None

    is_one_time = item.get("is_one_time_use", 1)
    enforce_qr_once = source == "qr" and is_one_time
    team_id = squad.get("team_id")
    clean_team_id = normalize_team_id(team_id) if team_id else None
    now = datetime.now().isoformat()

    try:
        with immediate_transaction() as tx:
            tc = tx.cursor()
            if enforce_qr_once:
                used = tc.execute(
                    "SELECT squad_id FROM qr_code_uses WHERE item_id = ?",
                    (item_id,),
                ).fetchone()
                if used:
                    return False, "此 QR Code 已經被使用", None

            existing = tc.execute(
                "SELECT id FROM player_items WHERE squad_id = ? AND item_id = ?",
                (squad_id, item_id),
            ).fetchone()
            if existing:
                return False, "你已經擁有此物品", None

            if clean_team_id:
                team_dup = tc.execute(
                    """
                    SELECT COUNT(*) FROM player_items pi
                    JOIN squads s ON pi.squad_id = s.squad_id
                    WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?)) AND pi.item_id = ?
                    """,
                    (clean_team_id, item_id),
                ).fetchone()[0]
                if team_dup > 0:
                    return False, "同一隊內已經有人擁有此物品", None

            owned_count = tc.execute(
                "SELECT COUNT(*) FROM player_items WHERE squad_id = ?",
                (squad_id,),
            ).fetchone()[0]
            max_slots = settings.max_inventory_slots
            if owned_count >= max_slots:
                return False, f"你已經持有 {max_slots} 樣物品，請先丟棄", None

            tc.execute(
                "INSERT INTO player_items (squad_id, item_id, source, obtained_at) VALUES (?, ?, ?, ?)",
                (squad_id, item_id, source, now),
            )
            if enforce_qr_once:
                tc.execute(
                    """INSERT INTO qr_code_uses (item_id, squad_id, team_id, source, used_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (item_id, squad_id, clean_team_id, source, now),
                )
    except sqlite3.IntegrityError:
        return False, "此 QR Code 已經被使用", None
    except sqlite3.Error:
        return False, "物品發放失敗，請稍後再試", None

    applied_effect = apply_item_effect_to_squad(squad_id, item)
    return True, f"成功獲得物品：{item['name']}", applied_effect


def is_near_death_rescue_item(item):
    """Items that may revive a near-death teammate when consumed."""
    if not item or not item.get("has_ability"):
        return False
    effect_type = item.get("effect_type")
    if effect_type not in NEAR_DEATH_RESCUE_EFFECT_TYPES:
        return False
    if effect_type == "hp_up":
        try:
            return int(item.get("effect_value") or 0) > 0
        except (TypeError, ValueError):
            return False
    return True


def apply_near_death_item_rescue(rescuer_squad_id, target_squad_id, item_id):
    """
    Consume rescuer's item and revive target (clear near_death, HP=25).
    Returns (success, message, rescued_bool).
    """
    rescuer = get_squad(rescuer_squad_id)
    target = get_squad(target_squad_id)
    if not rescuer or not target:
        return False, "找不到玩家", False
    if not rescuer.get("team_id") or rescuer.get("team_id") != target.get("team_id"):
        return False, "只能救援同隊隊友", False
    if rescuer_squad_id == target_squad_id:
        return False, "無法救援自己", False
    if not is_near_death_active(target):
        return False, "沒有需要救援的隊友", False

    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return False, "無效的物品", False

    item = get_item_by_id(item_id)
    if not item:
        return False, "物品不存在或已停用", False
    if not is_near_death_rescue_item(item):
        return False, "此物品不能用作瀕死救援", False

    try:
        with immediate_transaction() as conn:
            c = conn.cursor()
            owned = c.execute(
                "SELECT id FROM player_items WHERE squad_id = ? AND item_id = ?",
                (rescuer_squad_id, item_id),
            ).fetchone()
            if not owned:
                return False, "你沒有這件物品", False

            target_row = c.execute(
                "SELECT near_death_until FROM squads WHERE squad_id = ?",
                (target_squad_id,),
            ).fetchone()
            if not target_row or not is_near_death_active({"near_death_until": target_row[0]}):
                return False, "沒有需要救援的隊友", False

            deleted = c.execute(
                "DELETE FROM player_items WHERE squad_id = ? AND item_id = ?",
                (rescuer_squad_id, item_id),
            )
            if deleted.rowcount != 1:
                return False, "物品消耗失敗", False

            c.execute(
                "UPDATE squads SET near_death_until = NULL, hp = ? WHERE squad_id = ?",
                (RESCUE_REVIVE_HP, target_squad_id),
            )
    except sqlite3.Error:
        return False, "救援失敗，請稍後再試", False

    rescuer_name = rescuer.get("display_name") or rescuer_squad_id
    target_name = target.get("display_name") or target_squad_id
    message = f"{rescuer_name} 使用 {item['name']} 救援 {target_name}，恢復至 {RESCUE_REVIVE_HP} 生命值。"
    return True, message, True