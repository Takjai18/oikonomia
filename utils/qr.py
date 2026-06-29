"""Signed QR payload helpers for item claims."""
import hashlib
import hmac
import json
import os
import re

from flask import current_app

from models.item import get_item_by_id, get_item_by_qr_code_value


def qr_signing_secret():
    return (
        os.environ.get("QR_SECRET")
        or os.environ.get("SECRET_KEY")
        or (current_app.secret_key if current_app else None)
        or "oikonomia-2026-prototype"
    )


def sign_qr_token(qr_value):
    if not qr_value:
        return None
    signature = hmac.new(
        qr_signing_secret().encode(),
        str(qr_value).encode(),
        hashlib.sha256,
    ).hexdigest()[:12]
    return f"{qr_value}.{signature}"


def verify_signed_qr_token(token):
    if not token or "." not in token:
        return None
    payload, signature = token.rsplit(".", 1)
    expected = hmac.new(
        qr_signing_secret().encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()[:12]
    if not hmac.compare_digest(signature, expected):
        return None
    return payload


def allow_legacy_unsigned_qr():
    return os.environ.get("ALLOW_LEGACY_QR", "1") != "0"


def build_item_qr_payload(item):
    if not item:
        return None
    qr_value = item.get("qr_code_value")
    signed = sign_qr_token(qr_value) if qr_value else None
    return json.dumps({
        "type": "item",
        "id": item["id"],
        "qr": qr_value,
        "token": signed,
        "v": 2,
    }, ensure_ascii=False)


def resolve_item_from_qr_payload(raw_payload):
    text = (raw_payload or "").strip()
    if not text:
        return None

    if text.startswith("{"):
        try:
            obj = json.loads(text)
            if obj.get("type") == "item":
                token = obj.get("token")
                if token:
                    verified = verify_signed_qr_token(token)
                    if not verified:
                        return None
                    item = get_item_by_qr_code_value(verified)
                    if item:
                        return item
                if obj.get("qr"):
                    if not allow_legacy_unsigned_qr():
                        return None
                    item = get_item_by_qr_code_value(obj["qr"])
                    if item:
                        return item
                if obj.get("id") is not None and allow_legacy_unsigned_qr():
                    return get_item_by_id(int(obj["id"]))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    if "." in text and not text.startswith("http"):
        verified = verify_signed_qr_token(text)
        if verified:
            item = get_item_by_qr_code_value(verified)
            if item:
                return item
            if verified.isdigit():
                return get_item_by_id(int(verified))
        if not allow_legacy_unsigned_qr():
            return None

    claim_qr_match = re.search(r"/claim_qr/([^/?#]+)", text, re.I)
    if claim_qr_match:
        item = get_item_by_qr_code_value(claim_qr_match.group(1))
        if item:
            return item

    claim_id_match = re.search(r"/claim_item/(\d+)", text, re.I)
    if claim_id_match:
        return get_item_by_id(int(claim_id_match.group(1)))

    if re.match(r"^item-\d{3}$", text, re.I):
        if not allow_legacy_unsigned_qr():
            return None
        return get_item_by_qr_code_value(text.lower())

    if text.lower().startswith("oiko-item-"):
        suffix = text.lower().replace("oiko-item-", "", 1)
        if suffix.isdigit():
            return get_item_by_qr_code_value(f"item-{int(suffix):03d}")
        return get_item_by_qr_code_value(text)

    direct = get_item_by_qr_code_value(text)
    if direct:
        return direct

    if text.isdigit():
        return get_item_by_id(int(text))

    return None