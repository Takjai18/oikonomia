"""SQLite transaction helpers (BEGIN IMMEDIATE + rollback)."""
import sqlite3
import time
from contextlib import contextmanager

from models.settings import settings

SQLITE_CONNECT_TIMEOUT = 30.0


def configure_sqlite_connection(conn):
    """
    High-concurrency defaults for camp-scale co-op (WAL + relaxed sync).
    Safe to call on every connection; journal_mode=WAL is idempotent.
    """
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=30000;")


def get_db_connection(db_path=None, *, row_factory=None):
    """Authoritative SQLite connection factory (30s timeout + WAL pragmas)."""
    path = db_path or settings.db_path
    conn = sqlite3.connect(path, timeout=SQLITE_CONNECT_TIMEOUT)
    if row_factory is not None:
        conn.row_factory = row_factory
    configure_sqlite_connection(conn)
    return conn


def ensure_wal_mode(db_path=None):
    """Persist WAL journal mode at bootstrap (called from init_db / migrate_db)."""
    conn = get_db_connection(db_path)
    try:
        mode = conn.execute("PRAGMA journal_mode;").fetchone()
        return (mode[0] if mode else "").lower() == "wal"
    finally:
        conn.close()


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
    conn = get_db_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()