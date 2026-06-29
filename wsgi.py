"""
WSGI entry point for PythonAnywhere (and other production hosts).
PythonAnywhere Web tab → WSGI configuration file should import: from wsgi import application
"""
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.environ.setdefault("DATA_DIR", os.path.join(PROJECT_DIR, "data"))
os.environ.setdefault("FLASK_ENV", "production")

from utils.production_secrets import load_production_secrets

load_production_secrets(PROJECT_DIR)

from app import app as application