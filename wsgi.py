"""
WSGI entry point for PythonAnywhere (and other production hosts).
PythonAnywhere Web tab → WSGI configuration file can import from here.
"""
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.makedirs(os.path.join(PROJECT_DIR, "data"), exist_ok=True)
os.environ.setdefault("DATA_DIR", os.path.join(PROJECT_DIR, "data"))
os.environ.setdefault("FLASK_ENV", "production")

from app import app as application