import os
import re
from datetime import datetime, timedelta
from urllib.parse import unquote

from werkzeug.utils import secure_filename

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


PORTRAIT_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".svg")


def list_image_files(directory, exclude=()):
    if not os.path.isdir(directory):
        return []
    skip = set(exclude)
    return sorted(
        name for name in os.listdir(directory)
        if name not in skip
        and not name.startswith(".")
        and os.path.isfile(os.path.join(directory, name))
        and name.lower().endswith(PORTRAIT_IMAGE_EXTS)
    )


def safe_zip_arcname(*parts):
    name = "_".join(str(p or "unknown") for p in parts)
    return re.sub(r"[^\w\-.]", "_", name)


def resolve_upload_disk_path(filename):
    """Resolve upload file path; rejects directory traversal (only basename allowed)."""
    raw = unquote(str(filename or "")).replace("\\", "/").strip("\x00")
    if not raw or ".." in raw or raw.startswith("/"):
        return None
    basename = os.path.basename(raw)
    safe_name = secure_filename(basename)
    if not safe_name or safe_name in (".", ".."):
        return None

    for folder in (settings.upload_folder, settings.legacy_upload_folder):
        if not folder or not os.path.isdir(folder):
            continue
        candidate = os.path.join(folder, safe_name)
        try:
            real_file = os.path.realpath(candidate)
            real_root = os.path.realpath(folder)
            if not real_file.startswith(real_root + os.sep) and real_file != real_root:
                continue
        except OSError:
            continue
        if os.path.isfile(real_file):
            return real_file
    return None