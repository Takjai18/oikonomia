"""Announcement feed — persisted in global_events (multi-worker safe)."""
import sqlite3

from models.settings import settings


def add_announcement(message, timestamp):
    """Write announcement to DB. Prefer create_global_event() at call sites."""
    from services.global_events import create_global_event
    create_global_event("公告", message, "announcement", 0, "GM")


def list_announcements(limit=50):
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT description AS message, timestamp
            FROM global_events
            WHERE effect_type = 'announcement'
            ORDER BY id ASC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()