"""
WSGI entry point for PythonAnywhere (and other production hosts).
PythonAnywhere Web tab → WSGI configuration file should import: from wsgi import application
"""
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(PROJECT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
os.environ.setdefault("DATA_DIR", DATA_DIR)
os.environ.setdefault("FLASK_ENV", "production")


def _load_file_env(filename, env_key):
    """Load Web worker secrets from data/ (deploy scripts create these files)."""
    if os.environ.get(env_key):
        return
    path = os.path.join(DATA_DIR, filename)
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            value = fh.read().strip()
            if value:
                os.environ[env_key] = value
    except OSError:
        pass


_load_file_env(".secret_key", "SECRET_KEY")
_load_file_env(".gm_pin", "GM_PIN")

from app import app as application