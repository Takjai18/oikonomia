"""Global event persistence and squad-wide effects."""
import sqlite3

from models.settings import settings
from utils.helpers import clamped_stat_delta_expr, hkt_timestamp

# Staff-only rows: never shown on player /announcements or /global_events.
STAFF_ONLY_EFFECT_TYPES = frozenset({"gm_alert"})


def is_staff_only_event(event):
    """True if this row must stay on the GM console only."""
    if not event:
        return False
    effect = str(event.get("effect_type") or "").strip().lower()
    if effect in STAFF_ONLY_EFFECT_TYPES:
        return True
    title = str(event.get("title") or "")
    desc = str(event.get("description") or "")
    # Legacy summon_gm rows were written as effect_type=announcement.
    if "救援訊號" in title or "請求 GM 介入" in desc:
        return True
    return False


def apply_global_effect(effect_type, effect_value=0):
    if not effect_type or effect_type in ("announcement", "global_debuff", "gm_alert"):
        return
    conn = sqlite3.connect(settings.db_path)
    try:
        c = conn.cursor()
        if effect_type in ("adjust_sanity", "sanity_adjust"):
            c.execute(
                f"UPDATE squads SET sanity = {clamped_stat_delta_expr('sanity', '+')}",
                (effect_value, effect_value),
            )
        elif effect_type == "sanity_down":
            delta = abs(effect_value)
            c.execute(
                f"UPDATE squads SET sanity = {clamped_stat_delta_expr('sanity', '-')}",
                (delta, delta),
            )
        elif effect_type == "sanity_up":
            delta = abs(effect_value)
            c.execute(
                f"UPDATE squads SET sanity = {clamped_stat_delta_expr('sanity', '+')}",
                (delta, delta),
            )
        elif effect_type == "power_up":
            delta = abs(effect_value)
            c.execute(
                f"UPDATE squads SET power = {clamped_stat_delta_expr('power', '+')}",
                (delta, delta),
            )
        elif effect_type == "intellect_up":
            # Intellect retired — treat as power boost for legacy events.
            delta = abs(effect_value)
            c.execute(
                f"UPDATE squads SET power = {clamped_stat_delta_expr('power', '+')}",
                (delta, delta),
            )
        elif effect_type == "resilience_up":
            delta = abs(effect_value)
            c.execute(
                f"UPDATE squads SET resilience = {clamped_stat_delta_expr('resilience', '+')}",
                (delta, delta),
            )
        elif effect_type == "judas_strengthen":
            c.execute("UPDATE squads SET sanity = MAX(0, sanity - 8)")
        elif effect_type == "iggy_collapse":
            c.execute("UPDATE squads SET sanity = MAX(0, sanity - 12)")
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_global_events_log(limit=50, *, db_path=None):
    """Read-only snapshot of recent global events (GM / audit; no writes)."""
    path = db_path or settings.db_path
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT id, title, description, effect_type, effect_value, created_by, timestamp
               FROM global_events
               ORDER BY timestamp DESC
               LIMIT ?""",
            (max(1, min(int(limit), 100)),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_public_global_events(limit=30, *, db_path=None):
    """Player-facing feed — excludes GM alerts / staff-only rescue signals."""
    rows = list_global_events_log(limit=max(limit * 3, 50), db_path=db_path)
    public = [r for r in rows if not is_staff_only_event(r)]
    return public[: max(1, min(int(limit), 50))]


def create_global_event(title, description="", effect_type=None, effect_value=0, created_by="GM"):
    conn = sqlite3.connect(settings.db_path)
    try:
        conn.execute(
            """INSERT INTO global_events
               (title, description, effect_type, effect_value, created_by, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (title, description, effect_type, effect_value, created_by, hkt_timestamp()),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_global_event(event_id, *, db_path=None):
    """Delete one global_events row by id. Returns True if a row was removed."""
    path = db_path or settings.db_path
    try:
        eid = int(event_id)
    except (TypeError, ValueError):
        return False
    conn = sqlite3.connect(path, timeout=30.0)
    try:
        cur = conn.execute("DELETE FROM global_events WHERE id = ?", (eid,))
        conn.commit()
        return cur.rowcount > 0
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def clear_staff_alert_events(*, db_path=None):
    """Remove all GM-alert / legacy rescue-signal rows. Returns deleted count."""
    path = db_path or settings.db_path
    conn = sqlite3.connect(path, timeout=30.0)
    try:
        cur = conn.execute(
            """DELETE FROM global_events
               WHERE effect_type = 'gm_alert'
                  OR title LIKE '%救援訊號%'
                  OR description LIKE '%請求 GM 介入%'"""
        )
        conn.commit()
        return int(cur.rowcount or 0)
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()