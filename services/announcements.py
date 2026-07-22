"""Announcement feed — persisted in global_events (multi-worker safe)."""
import sqlite3

from models.settings import settings


def add_announcement(message, timestamp):
    """Write announcement to DB. Prefer create_global_event() at call sites."""
    from services.global_events import create_global_event
    create_global_event("公告", message, "announcement", 0, "GM")


def list_announcements(limit=50):
    """Player announcement banner — GM public posts only (not combat GM alerts)."""
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        # Staff-only / legacy summon_gm rows must never hit the player banner.
        rows = conn.execute("""
            SELECT description AS message, timestamp
            FROM global_events
            WHERE effect_type = 'announcement'
              AND IFNULL(effect_type, '') != 'gm_alert'
              AND title NOT LIKE '%救援訊號%'
              AND IFNULL(description, '') NOT LIKE '%請求 GM 介入%'
              AND (
                    IFNULL(created_by, '') = 'GM'
                 OR title = '公告'
              )
            ORDER BY id ASC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()