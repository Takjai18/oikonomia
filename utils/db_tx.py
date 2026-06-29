"""SQLite transaction helpers (BEGIN IMMEDIATE + rollback)."""
import sqlite3
from contextlib import contextmanager

from models.settings import settings


@contextmanager
def immediate_transaction(db_path=None):
    """
    Open a connection, BEGIN IMMEDIATE, yield it, commit on success.
    Rolls back and re-raises on any exception.
    """
    path = db_path or settings.db_path
    conn = sqlite3.connect(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()