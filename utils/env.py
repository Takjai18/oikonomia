"""Environment helpers."""
import os


def is_production_env():
    return (
        os.environ.get("FLASK_ENV") == "production"
        or os.environ.get("RENDER") == "true"
        or bool(os.environ.get("PYTHONANYWHERE_SITE"))
    )