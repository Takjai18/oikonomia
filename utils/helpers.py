import os
import re
from datetime import datetime, timedelta

from models.settings import settings


def hkt_timestamp():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")


def normalize_team_id(team_id):
    if not team_id:
        return None
    return str(team_id).strip().upper()


def normalize_photo_url(photo_path):
    if not photo_path:
        return None
    path = str(photo_path).replace("\\", "/")
    if path.startswith("uploads/"):
        return path
    return f"uploads/{os.path.basename(path)}"


def photo_public_url(photo_path):
    normalized = normalize_photo_url(photo_path)
    return f"/{normalized}" if normalized else None


def safe_zip_arcname(*parts):
    name = "_".join(str(p or "unknown") for p in parts)
    return re.sub(r"[^\w\-.]", "_", name)


def resolve_upload_disk_path(filename):
    basename = os.path.basename(str(filename).replace("\\", "/"))
    if not basename:
        return None
    for folder in (settings.upload_folder, settings.legacy_upload_folder):
        if not folder or not os.path.isdir(folder):
            continue
        path = os.path.join(folder, basename)
        if os.path.isfile(path):
            return path
    return None