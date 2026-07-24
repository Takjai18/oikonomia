"""Pending stat-point bank after mission rewards (player pick + Iggy random)."""
from __future__ import annotations

import json
import os
import random
from typing import Dict, Optional

from models.protagonist import get_protagonist_state, update_protagonist_state
from models.settings import settings
from models.squad import get_squad, get_team_members, update_squad
from utils.helpers import normalize_team_id

STAT_KEYS = ("power", "resilience", "sanity", "max_hp")
STAT_LABELS = {
    "power": "力量",
    "resilience": "韌性",
    "sanity": "神智",
    "max_hp": "生命上限",
}


def _path() -> str:
    base = os.path.dirname(settings.db_path or "") or "."
    return os.path.join(base, "pending_stat_points.json")


def _load() -> dict:
    path = _path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f) or {}
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    path = _path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    os.replace(tmp, path)


def get_pending_points(squad_id: str) -> int:
    if not squad_id:
        return 0
    data = _load()
    try:
        return max(0, int((data.get(squad_id) or {}).get("points") or 0))
    except (TypeError, ValueError):
        return 0


def add_pending_points(squad_id: str, points: int) -> int:
    pts = max(0, int(points or 0))
    if not squad_id or pts <= 0:
        return get_pending_points(squad_id)
    data = _load()
    bag = dict(data.get(squad_id) or {})
    cur = max(0, int(bag.get("points") or 0))
    bag["points"] = cur + pts
    data[squad_id] = bag
    _save(data)
    return bag["points"]


def _apply_player_stats(squad_id: str, alloc: Dict[str, int]) -> Optional[dict]:
    squad = get_squad(squad_id)
    if not squad:
        return None
    updates = {}
    for key in STAT_KEYS:
        n = int(alloc.get(key) or 0)
        if n <= 0:
            continue
        if key == "max_hp":
            new_max = int(squad.get("max_hp") or 100) + n
            new_hp = int(squad.get("hp") or 0) + n
            updates["max_hp"] = new_max
            updates["hp"] = new_hp
        else:
            updates[key] = int(squad.get(key) or 0) + n
    if updates:
        update_squad(squad_id, **updates)
    return get_squad(squad_id)


def _random_alloc(points: int) -> Dict[str, int]:
    keys = list(STAT_KEYS)
    bag = {k: 0 for k in keys}
    for _ in range(max(0, points)):
        bag[random.choice(keys)] += 1
    return bag


def _bonus_path() -> str:
    base = os.path.dirname(settings.db_path or "") or "."
    return os.path.join(base, "protagonist_stat_bonus.json")


def get_protagonist_bonus(team_id: str, protagonist_key: str = "iggy") -> Dict[str, int]:
    team_id = normalize_team_id(team_id)
    key = (protagonist_key or "iggy").strip().lower()
    if not team_id:
        return {k: 0 for k in STAT_KEYS}
    try:
        with open(_bonus_path(), encoding="utf-8") as f:
            data = json.load(f) or {}
    except (OSError, json.JSONDecodeError):
        data = {}
    bag = ((data.get(team_id) or {}).get(key) or {})
    out = {}
    for k in STAT_KEYS:
        try:
            out[k] = max(0, int(bag.get(k) or 0))
        except (TypeError, ValueError):
            out[k] = 0
    return out


def add_protagonist_bonus(team_id: str, protagonist_key: str, alloc: Dict[str, int]) -> Dict[str, int]:
    team_id = normalize_team_id(team_id)
    key = (protagonist_key or "iggy").strip().lower()
    path = _bonus_path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f) or {}
    except (OSError, json.JSONDecodeError):
        data = {}
    team_bag = dict(data.get(team_id) or {})
    cur = dict(team_bag.get(key) or {})
    for k in STAT_KEYS:
        try:
            n = max(0, int(alloc.get(k) or 0))
        except (TypeError, ValueError):
            n = 0
        cur[k] = max(0, int(cur.get(k) or 0)) + n
    team_bag[key] = cur
    data[team_id] = team_bag
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    os.replace(tmp, path)
    return cur


def apply_protagonist_random(team_id: str, points: int, route: str = "iggy") -> Optional[dict]:
    """Randomly distribute points into protagonist combat bonus (+ HP/sanity on state)."""
    team_id = normalize_team_id(team_id)
    key = (route or "iggy").strip().lower()
    if key not in ("iggy", "marah"):
        key = "iggy"
    pts = max(0, int(points or 0))
    if not team_id or pts <= 0:
        return None
    alloc = _random_alloc(pts)
    bonus = add_protagonist_bonus(team_id, key, alloc)
    state = get_protagonist_state(team_id, key, create=True)
    if state and (alloc.get("max_hp") or alloc.get("sanity")):
        updates = {}
        if alloc.get("max_hp"):
            new_max = int(state.get("max_hp") or 10) + int(alloc["max_hp"])
            updates["max_hp"] = new_max
            updates["hp"] = min(new_max, int(state.get("hp") or 0) + int(alloc["max_hp"]))
        if alloc.get("sanity"):
            updates["sanity"] = min(100, int(state.get("sanity") or 0) + int(alloc["sanity"]))
        if updates:
            state = update_protagonist_state(team_id, key, **updates)
    return {"bonus": bonus, "alloc": alloc, "state": state}


def grant_mission_stat_rewards(team_id: str, points: int, protagonist_key: str = "iggy") -> dict:
    """Give each player pending points; randomly spend same points on protagonist."""
    team_id = normalize_team_id(team_id)
    pts = max(0, int(points or 0))
    result = {"player_pending": {}, "protagonist": None, "points": pts}
    if not team_id or pts <= 0:
        return result
    members = get_team_members(team_id) or []
    for m in members:
        sid = (m or {}).get("squad_id")
        if not sid or str(sid).startswith("protagonist:"):
            continue
        result["player_pending"][sid] = add_pending_points(sid, pts)
    try:
        result["protagonist"] = apply_protagonist_random(team_id, pts, protagonist_key)
    except Exception:
        result["protagonist"] = None
    return result


def spend_pending_points(squad_id: str, alloc: Dict[str, int]) -> dict:
    """Player assigns pending points. alloc values must sum to pending (or less)."""
    pending = get_pending_points(squad_id)
    cleaned = {}
    total = 0
    for key in STAT_KEYS:
        try:
            n = max(0, int(alloc.get(key) or 0))
        except (TypeError, ValueError):
            n = 0
        if n:
            cleaned[key] = n
            total += n
    if total <= 0:
        return {"success": False, "error": "請分配至少 1 點", "pending": pending}
    if total > pending:
        return {"success": False, "error": f"超過可用點數（剩餘 {pending}）", "pending": pending}
    squad = _apply_player_stats(squad_id, cleaned)
    if not squad:
        return {"success": False, "error": "玩家不存在", "pending": pending}
    data = _load()
    bag = dict(data.get(squad_id) or {})
    bag["points"] = pending - total
    data[squad_id] = bag
    _save(data)
    return {
        "success": True,
        "pending": bag["points"],
        "allocated": cleaned,
        "squad": squad,
        "message": f"已分配 {total} 點能力",
    }
