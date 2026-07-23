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


# Player-facing avatar picker only (not root static/avatars legacy files).
PLAYER_AVATAR_SUBDIR = "new avatars for players"

# Old filenames → current basenames (rename / png→jpg optimisations).
PLAYER_AVATAR_ALIASES = {
    "lok sum.jpg": "loksum.jpg",
    "lok tin.jpg": "lokting.jpg",
    "lok tIn.jpg": "lokting.jpg",
    "lok ting.jpg": "lokting.jpg",
    "lok ying.jpg": "lokying.jpg",
    "lok yiu.jpg": "lokyiu.jpg",
    "sumwing 2.jpg": "sumwing2.jpg",
    "pak yat.jpg": "ethan.jpg",
    "fung.png": "fung.jpg",
    "siujai.png": "siujai.jpg",
    "sumwing.png": "sumwing.jpg",
    "tak.png": "tak.jpg",
    "ted.png": "ted.jpg",
}


def player_avatar_pick_dir():
    base = settings.avatar_dir or ""
    return os.path.join(base, PLAYER_AVATAR_SUBDIR) if base else PLAYER_AVATAR_SUBDIR


def list_player_pick_avatars():
    """Basenames of images players may choose at start / in avatar modal."""
    return list_image_files(player_avatar_pick_dir())


def normalize_player_avatar_basename(basename):
    """Map legacy / optimized-away filenames to a file that exists on disk."""
    name = os.path.basename(str(basename or "").replace("\\", "/").strip())
    if not name:
        return name
    pick_dir = player_avatar_pick_dir()
    alias = PLAYER_AVATAR_ALIASES.get(name) or PLAYER_AVATAR_ALIASES.get(name.lower())
    candidates = []
    if alias:
        candidates.append(alias)
    candidates.append(name)
    # png → jpg after web optimise
    if name.lower().endswith(".png"):
        candidates.append(name[:-4] + ".jpg")
    if name.lower().endswith((".jpeg", ".jpg")):
        stem = name.rsplit(".", 1)[0]
        candidates.append(stem + ".jpg")
        candidates.append(stem + ".png")
    # Case-insensitive match against pick dir
    if os.path.isdir(pick_dir):
        existing = {f.lower(): f for f in os.listdir(pick_dir) if not f.startswith(".")}
        for c in candidates:
            if os.path.isfile(os.path.join(pick_dir, c)):
                return c
            hit = existing.get(c.lower())
            if hit:
                return hit
    return name


def resolve_player_pick_avatar(avatar_value):
    """
    Validate avatar is inside PLAYER_AVATAR_SUBDIR.
    Returns (stored_relative_path, abs_path) or (None, None).
    stored form: 'new avatars for players/Mike.jpg'
    """
    raw = str(avatar_value or "").replace("\\", "/").strip()
    if not raw or ".." in raw or raw.startswith("/"):
        return None, None
    basename = normalize_player_avatar_basename(os.path.basename(raw))
    if not basename or basename.startswith(".") or basename == "default.png":
        return None, None
    if not basename.lower().endswith(PORTRAIT_IMAGE_EXTS):
        return None, None
    pick_dir = player_avatar_pick_dir()
    if not os.path.isdir(pick_dir):
        return None, None
    abs_path = os.path.join(pick_dir, basename)
    try:
        abs_real = os.path.realpath(abs_path)
        pick_real = os.path.realpath(pick_dir)
        if os.path.commonpath([abs_real, pick_real]) != pick_real:
            return None, None
    except (OSError, ValueError):
        return None, None
    if not os.path.isfile(abs_real):
        return None, None
    stored = f"{PLAYER_AVATAR_SUBDIR}/{basename}"
    return stored, abs_real


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


def clamped_stat_delta_expr(stat, operator="+"):
    """SQL expression for bounded stat changes.

    Normal stats (<=100) stay capped at 100; GM-boosted stats (>100) are not
    clamped so global events and items do not wipe manual adjustments.
    """
    if operator == "+":
        delta = f"{stat} + ?"
    elif operator == "-":
        delta = f"{stat} - ?"
    else:
        raise ValueError(f"unsupported operator: {operator}")
    return (
        f"MAX(0, CASE WHEN {stat} > 100 THEN {delta} "
        f"ELSE MIN(100, {delta}) END)"
    )