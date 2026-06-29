"""
Combat Blueprint — Phase 2 stub.

Production endpoints (/combat/status, /combat/submit_action, etc.) still live in
app.py to avoid URL / behaviour regressions during refactor.

When migrating, move handlers from app.py into this blueprint and register:

    from routes.combat import combat_bp
    app.register_blueprint(combat_bp)
"""
from flask import Blueprint

combat_bp = Blueprint("combat", __name__, url_prefix="/combat")