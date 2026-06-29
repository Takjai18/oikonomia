"""GM session validation (time-limited, PIN-based)."""
from datetime import datetime, timedelta

GM_SESSION_HOURS = 8


def establish_gm_session(session):
    session.permanent = True
    session["is_gm"] = True
    session["gm_auth_at"] = datetime.utcnow().isoformat()


def gm_session_valid(session):
    if not session.get("is_gm"):
        return False
    auth_at = session.get("gm_auth_at")
    if not auth_at:
        return False
    try:
        issued = datetime.fromisoformat(auth_at)
    except ValueError:
        return False
    return datetime.utcnow() - issued < timedelta(hours=GM_SESSION_HOURS)


def clear_gm_session(session):
    session.pop("is_gm", None)
    session.pop("gm_auth_at", None)