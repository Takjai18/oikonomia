"""SQLite transaction helpers (BEGIN IMMEDIATE + rollback)."""
import sqlite3
import time
from contextlib import contextmanager

from models.settings import settings


def with_db_retry(operation, max_attempts=5, base_delay=0.05):
    """Retry SQLite operations that fail with database is locked."""
    last_error = None
    for attempt in range(max_attempts):
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            last_error = exc
            if "locked" not in str(exc).lower() or attempt >= max_attempts - 1:
                raise
            time.sleep(base_delay * (attempt + 1))
    if last_error:
        raise last_error


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