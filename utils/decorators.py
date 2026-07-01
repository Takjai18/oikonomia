"""Flask route decorators."""
from functools import wraps

from flask import jsonify, session


def require_player(*, response_style="api"):
    """
    Ensure squad_id is in session before handling the route.

    response_style:
      - "api": {"success": False, "error": "未登入"} — items / summon_gm
      - "combat": {"error": "未登入"} — combat JSON APIs
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "squad_id" not in session:
                if response_style == "combat":
                    return jsonify({"error": "未登入"}), 401
                return jsonify({"success": False, "error": "未登入"}), 401
            return f(*args, **kwargs)

        return decorated_function

    return decorator