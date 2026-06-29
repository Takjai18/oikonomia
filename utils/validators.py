import json


def parse_status_effects(raw):
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def serialize_status_effects(effects):
    return json.dumps(effects or {}, ensure_ascii=False)