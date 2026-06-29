"""Deployment / version helpers."""
import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_deploy_version():
    version_file = os.path.join(PROJECT_DIR, ".deploy-version")
    if os.path.isfile(version_file):
        with open(version_file, encoding="utf-8") as f:
            return f.read().strip()
    return "unknown"


def player_template_text():
    path = os.path.join(PROJECT_DIR, "templates", "index.html")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return ""