import io
import os
import random
from datetime import datetime

from PIL import Image

from models.settings import settings

MAX_TASK_PHOTO_BYTES = 8 * 1024 * 1024
MAX_TASK_PHOTO_DIMENSION = 1200
TASK_PHOTO_JPEG_QUALITY = 85


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