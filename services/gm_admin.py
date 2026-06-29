"""GM destructive / admin operations."""

import os
import sqlite3

from models.settings import settings
from utils.helpers import resolve_upload_disk_path

RESET_GAME_PASSWORD = os.environ.get("RESET_GAME_PASSWORD", "reset2026")


def reset_game_data():
    conn = sqlite3.connect(settings.db_path)
    c = conn.cursor()
    c.execute("DELETE FROM submissions")
    c.execute("DELETE FROM player_items")
    c.execute("DELETE FROM qr_code_uses")
    c.execute("DELETE FROM teams")
    c.execute("DELETE FROM squads")
    c.execute("DELETE FROM global_events")
    conn.commit()
    conn.close()


def clear_all_submission_images():
    conn = sqlite3.connect(settings.db_path)
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
    return deleted_count, cleared_count