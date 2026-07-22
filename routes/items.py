"""Inventory and item claim routes."""
import os
import sqlite3

from flask import Blueprint, jsonify, redirect, render_template, request, session

from models.item import (
    format_item_effect_text,
    get_item_by_id,
    get_item_by_qr_code_value,
    grant_item_to_squad,
    serialize_item_for_client,
)
from models.settings import settings
from utils.decorators import require_player
from utils.qr import build_item_qr_payload, resolve_item_from_qr_payload

items_bp = Blueprint("items", __name__)


@items_bp.route("/my_items")
@require_player()
def my_items():
    squad_id = session["squad_id"]
    conn = sqlite3.connect(settings.db_path)
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
        "max_slots": settings.max_inventory_slots,
        "current_count": len(items),
    })


@items_bp.route("/api/inventory", methods=["GET"])
@require_player()
def get_combat_inventory_api():
    """Combat V2: uncached inventory slice for in-battle item picker."""
    squad_id = session["squad_id"]
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT pi.id AS player_item_id, pi.item_id, i.name, i.description, i.icon,
                   i.effect_type, i.effect_value, i.has_ability, i.image_path
            FROM player_items pi
            INNER JOIN items i ON pi.item_id = i.id
            WHERE pi.squad_id = ? AND COALESCE(i.is_active, 1) = 1
              AND (COALESCE(i.has_ability, 0) = 1 OR i.effect_type IS NOT NULL)
            ORDER BY pi.obtained_at DESC
        """, (squad_id,)).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["has_ability"] = bool(item.get("has_ability"))
            item["effect_text"] = (
                format_item_effect_text(item.get("effect_type"), item.get("effect_value"))
                if item.get("has_ability") else None
            )
            items.append(item)
        return jsonify({"success": True, "items": items})
    finally:
        conn.close()


@items_bp.route("/add_item", methods=["POST"])
@require_player()
def add_item():
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

    # Act 1+ QR hooks: auto-complete linked explore task; optional combat start.
    from data.act1_qr_hooks import hooks_for_qr_code
    from services.story import record_task_completion_from_qr

    hooks = hooks_for_qr_code(item.get("qr_code_value"))
    linked_task_id = hooks.get("linked_task_id")
    if linked_task_id:
        newly = record_task_completion_from_qr(
            session["squad_id"],
            linked_task_id,
            note=f"QR 獲得物品：{item.get('name')}",
        )
        response["linked_task_id"] = linked_task_id
        response["task_completed"] = True
        response["task_newly_completed"] = bool(newly)
        if newly:
            response["message"] = f"{message}（任務已完成）"
    start_encounter = hooks.get("start_encounter")
    if start_encounter:
        response["start_encounter"] = start_encounter
        response["message"] = (
            f"{response.get('message') or message}"
            " — 你們撿起木材的一刻，樹林傳來咆哮！雪山熊「布布」撲出——進入戰鬥教學。"
        )
    return jsonify(response)


@items_bp.route("/discard_item", methods=["POST"])
@require_player()
def discard_item():
    data = request.get_json(silent=True) or {}
    player_item_id = data.get("player_item_id")
    try:
        player_item_id = int(player_item_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "無效物品記錄"}), 400

    conn = sqlite3.connect(settings.db_path)
    try:
        c = conn.cursor()
        c.execute(
            "DELETE FROM player_items WHERE id = ? AND squad_id = ?",
            (player_item_id, session["squad_id"]),
        )
        deleted = c.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        return jsonify({"success": False, "error": "丟棄失敗，請稍後再試"}), 500
    finally:
        conn.close()

    if deleted == 0:
        return jsonify({"success": False, "error": "找不到物品或無權限丟棄"}), 404

    return jsonify({"success": True, "message": "物品已丟棄"})


@items_bp.route("/claim_item/<int:item_id>")
def claim_item_page(item_id):
    if "squad_id" not in session:
        return redirect(f"/?next=/claim_item/{item_id}")

    item = get_item_by_id(item_id)
    if not item:
        return "找不到此物品", 404

    return render_template(
        "claim_item.html",
        item=item,
        qr_payload=build_item_qr_payload(item),
    )


@items_bp.route("/claim_qr/<path:qr_value>")
def claim_qr_page(qr_value):
    if "squad_id" not in session:
        return redirect(f"/?next=/claim_qr/{qr_value}")

    item = get_item_by_qr_code_value(qr_value)
    if not item:
        return "找不到此物品", 404

    return render_template(
        "claim_item.html",
        item=item,
        qr_payload=build_item_qr_payload(item),
    )