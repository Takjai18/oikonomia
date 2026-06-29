import sqlite3
from datetime import datetime

from models.settings import settings
from models.squad import apply_hp_change, get_squad
from utils.db_tx import immediate_transaction
from utils.helpers import clamped_stat_delta_expr, normalize_team_id


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
        "SELECT hp, max_hp, sanity, power, intellect, resilience FROM squads WHERE squad_id = ?",
        (squad_id,),
    ).fetchone()
    if not row:
        return None

    if stat == "hp":
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

    conn = sqlite3.connect(settings.db_path)
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
        max_slots = settings.max_inventory_slots
        if owned_count >= max_slots:
            return False, f"你已經持有 {max_slots} 樣物品，請先丟棄", None
    finally:
        conn.close()

    now = datetime.now().isoformat()
    try:
        with immediate_transaction() as tx:
            tc = tx.cursor()
            tc.execute(
                "INSERT INTO player_items (squad_id, item_id, source, obtained_at) VALUES (?, ?, ?, ?)",
                (squad_id, item_id, source, now),
            )
            if enforce_qr_once:
                tc.execute(
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
    except sqlite3.IntegrityError:
        return False, "此 QR Code 已經被使用", None
    except sqlite3.Error:
        return False, "物品發放失敗，請稍後再試", None

    applied_effect = apply_item_effect_to_squad(squad_id, item)
    return True, f"成功獲得物品：{item['name']}", applied_effect