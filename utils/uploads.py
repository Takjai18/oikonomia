import io
import os
import random
from datetime import datetime

from PIL import Image

from models.settings import settings

MAX_TASK_PHOTO_BYTES = 8 * 1024 * 1024
MAX_TASK_AUDIO_BYTES = 6 * 1024 * 1024
MAX_TASK_PHOTO_DIMENSION = 1200
TASK_PHOTO_JPEG_QUALITY = 85

_AUDIO_EXT_BY_MIME = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/wav": ".wav",
    "audio/wave": ".wav",
    "audio/x-wav": ".wav",
}


def save_task_submission_photo(file_storage, squad_id):
    """
    Validate, resize, and persist a task submission photo as JPEG.
    Returns {"ok": True, "photo_path": "uploads/..."} or
            {"ok": False, "error": "...", "status": 400|413}.
    """
    if not file_storage or not file_storage.filename:
        return {"ok": False, "error": "未選擇相片", "status": 400}

    upload_folder = settings.upload_folder
    if not upload_folder:
        return {"ok": False, "error": "上傳目錄未設定", "status": 500}

    try:
        img_bytes = file_storage.read()
        if len(img_bytes) > MAX_TASK_PHOTO_BYTES:
            return {
                "ok": False,
                "error": "相片檔案太大（上限 8MB）",
                "status": 413,
            }

        img = Image.open(io.BytesIO(img_bytes))
        img.verify()
        img = Image.open(io.BytesIO(img_bytes))
        img = img.convert("RGB")

        if max(img.size) > MAX_TASK_PHOTO_DIMENSION:
            ratio = MAX_TASK_PHOTO_DIMENSION / max(img.size)
            new_size = (
                max(1, int(img.size[0] * ratio)),
                max(1, int(img.size[1] * ratio)),
            )
            resample = getattr(Image, "Resampling", Image).LANCZOS
            img = img.resize(new_size, resample)

        ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
        safe_name = f"{squad_id}_{ts}_{random.randint(1000, 9999)}.jpg"
        save_path = os.path.join(upload_folder, safe_name)
        img.save(save_path, "JPEG", quality=TASK_PHOTO_JPEG_QUALITY, optimize=True)

        return {"ok": True, "photo_path": f"uploads/{safe_name}"}
    except Exception:
        return {
            "ok": False,
            "error": "只接受有效嘅 JPEG / PNG 圖片",
            "status": 400,
        }


def save_task_submission_audio(file_storage, squad_id):
    """
    Persist a task voice recording (webm/ogg/m4a/wav/mp3).
    Returns {"ok": True, "audio_path": "uploads/..."} or error dict.
    """
    if not file_storage or not getattr(file_storage, "filename", None):
        return {"ok": False, "error": "未選擇錄音", "status": 400}

    upload_folder = settings.upload_folder
    if not upload_folder:
        return {"ok": False, "error": "上傳目錄未設定", "status": 500}

    try:
        raw = file_storage.read()
        if not raw:
            return {"ok": False, "error": "錄音檔案係空嘅", "status": 400}
        if len(raw) > MAX_TASK_AUDIO_BYTES:
            return {
                "ok": False,
                "error": "錄音檔案太大（上限 6MB）",
                "status": 413,
            }

        # Reject obvious non-audio payloads (images / empty shell).
        if raw[:3] == b"\xff\xd8\xff" or raw[:8] == b"\x89PNG\r\n\x1a\n":
            return {"ok": False, "error": "請上傳錄音檔，唔係圖片", "status": 400}

        content_type = (getattr(file_storage, "mimetype", None) or "").split(";")[0].strip().lower()
        filename = (file_storage.filename or "").lower()
        ext = _AUDIO_EXT_BY_MIME.get(content_type)
        if not ext:
            if filename.endswith(".webm"):
                ext = ".webm"
            elif filename.endswith(".ogg"):
                ext = ".ogg"
            elif filename.endswith(".m4a") or filename.endswith(".mp4"):
                ext = ".m4a"
            elif filename.endswith(".mp3"):
                ext = ".mp3"
            elif filename.endswith(".wav"):
                ext = ".wav"
            else:
                # MediaRecorder often sends webm without a reliable client filename.
                if raw[:4] == b"\x1a\x45\xdf\xa3" or b"webm" in raw[:64].lower():
                    ext = ".webm"
                else:
                    ext = ".webm"

        ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
        safe_name = f"{squad_id}_{ts}_{random.randint(1000, 9999)}{ext}"
        save_path = os.path.join(upload_folder, safe_name)
        with open(save_path, "wb") as fh:
            fh.write(raw)

        return {"ok": True, "audio_path": f"uploads/{safe_name}"}
    except Exception:
        return {
            "ok": False,
            "error": "錄音儲存失敗，請再試一次",
            "status": 400,
        }