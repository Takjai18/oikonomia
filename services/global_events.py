"""Global event persistence and squad-wide effects."""
import sqlite3

from models.settings import settings
from utils.helpers import clamped_stat_delta_expr, hkt_timestamp


def apply_global_effect(effect_type, effect_value=0):
    if not effect_type or effect_type in ("announcement", "global_debuff"):
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
            delta = abs(effect_value)
            c.execute(
                f"UPDATE squads SET intellect = {clamped_stat_delta_expr('intellect', '+')}",
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