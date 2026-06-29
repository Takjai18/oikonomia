"""Player session and device restore tokens."""
from flask import current_app, session
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

RESTORE_TOKEN_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


def get_restore_serializer():
    return URLSafeTimedSerializer(
        current_app.secret_key,
        salt="oikonomia-session-restore",
    )


def make_restore_token(squad_id):
    return get_restore_serializer().dumps({"sid": squad_id})


def verify_restore_token(token):
    if not token:
        return None
    try:
        payload = get_restore_serializer().loads(token, max_age=RESTORE_TOKEN_MAX_AGE)
        return payload.get("sid")
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None


def attach_restore_token(status_dict, squad_id):
    if status_dict and squad_id:
        status_dict["restore_token"] = make_restore_token(squad_id)
    return status_dict


def establish_player_session(squad_id):
    session.permanent = True
    session["squad_id"] = squad_id
    session.modified = True