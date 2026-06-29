"""Task / location display helpers."""
from models.settings import settings


def task_display_name(task_id):
    if not task_id:
        return "未知任務"
    locations = settings.locations or {}
    return locations.get(task_id, {}).get("name", task_id)