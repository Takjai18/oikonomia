"""Global event persistence and squad-wide effects."""
import sqlite3

from models.settings import settings
from utils.helpers import hkt_timestamp


def apply_global_effect(effect_type, effect_value=0):
    if not effect_type or effect_type in ("announcement", "global_debuff"):
        return
    conn = sqlite3.connect(settings.db_path)
    try:
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
    except sqlite3.Error:
        conn.rollback()
        raise
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