"""Environment helpers."""
import os


def is_production_env():
    return (
        os.environ.get("FLASK_ENV") == "production"
        or bool(os.environ.get("PYTHONANYWHERE_SITE"))
    )