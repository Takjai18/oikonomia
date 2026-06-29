"""
WSGI entry point for PythonAnywhere (and other production hosts).
PythonAnywhere Web tab → WSGI configuration file should import: from wsgi import application
"""
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

DATA_DIR = os.path.join(PROJECT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
os.environ.setdefault("DATA_DIR", DATA_DIR)
os.environ.setdefault("FLASK_ENV", "production")

if not os.environ.get("SECRET_KEY"):
    secret_file = os.path.join(DATA_DIR, ".secret_key")
    if os.path.isfile(secret_file):
        with open(secret_file, encoding="utf-8") as fh:
            key = fh.read().strip()
            if key:
                os.environ["SECRET_KEY"] = key

from app import app as application