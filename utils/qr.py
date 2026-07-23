"""Signed QR payload helpers for item claims."""
import hashlib
import hmac
import json
import os
import re
import unicodedata

from flask import current_app

from models.item import get_item_by_id, get_item_by_qr_code_value
from utils.env import is_production_env

# Zero-width / BOM that often appear after print → phone camera scan.
_ZW_RE = re.compile(r"[\u200b-\u200d\ufeff\u2060]")
# Various unicode dashes → ASCII hyphen for act1-water style codes.
_DASH_RE = re.compile(r"[\u2010-\u2015\u2212\ufe58\ufe63\uff0d]")
# Signed token: payload + "." + 12 hex chars (see sign_qr_token).
_SIGNED_TOKEN_RE = re.compile(r"^(.+)\.([0-9a-fA-F]{12})$")


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
    if len(signature) != 12:
        return None
    expected = hmac.new(
        qr_signing_secret().encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()[:12]
    if not hmac.compare_digest(signature.lower(), expected.lower()):
        return None
    return payload


def allow_legacy_unsigned_qr():
    default = "0" if is_production_env() else "1"
    return os.environ.get("ALLOW_LEGACY_QR", default) != "0"


def normalize_qr_payload(raw_payload):
    """Strip noise from camera / print pipelines so act1-water still matches."""
    if raw_payload is None:
        return ""
    text = str(raw_payload)
    text = unicodedata.normalize("NFKC", text)
    text = _ZW_RE.sub("", text)
    text = _DASH_RE.sub("-", text)
    text = text.strip()
    # Drop surrounding quotes sometimes added by third-party scanners
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"', "`"):
        text = text[1:-1].strip()
    return text


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


def _lookup_catalog_qr(value):
    """Match items.qr_code_value (case-insensitive). Catalog codes are intentional print payloads."""
    if not value:
        return None
    clean = normalize_qr_payload(value)
    if not clean:
        return None
    item = get_item_by_qr_code_value(clean)
    if item:
        return item
    # Case-insensitive fallback (DB helper also does LOWER match).
    lower = clean.lower()
    if lower != clean:
        item = get_item_by_qr_code_value(lower)
        if item:
            return item
    return None


def resolve_item_from_qr_payload(raw_payload):
    text = normalize_qr_payload(raw_payload)
    if not text:
        return None

    # 1) Catalog plain codes FIRST (act1-wood, item-001, …).
    # These are the codes printed on physical props — always allowed when present in DB.
    # Do this before signed-token / legacy gates so production ALLOW_LEGACY_QR=0
    # does not block intentional print payloads.
    catalog = _lookup_catalog_qr(text)
    if catalog:
        return catalog

    # 2) v2 JSON envelope
    if text.startswith("{"):
        try:
            obj = json.loads(text)
            if obj.get("type") == "item":
                token = obj.get("token")
                if token:
                    verified = verify_signed_qr_token(normalize_qr_payload(token))
                    if verified:
                        item = _lookup_catalog_qr(verified)
                        if item:
                            return item
                if obj.get("qr"):
                    item = _lookup_catalog_qr(obj["qr"])
                    if item:
                        # Prefer catalog match; only require legacy flag if not in catalog
                        # (already matched above if valid)
                        return item
                if obj.get("id") is not None and allow_legacy_unsigned_qr():
                    return get_item_by_id(int(obj["id"]))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # 3) Signed compact token: "act1-wood.a1b2c3d4e5f6"
    signed_match = _SIGNED_TOKEN_RE.match(text)
    if signed_match:
        verified = verify_signed_qr_token(text)
        if verified:
            item = _lookup_catalog_qr(verified)
            if item:
                return item
            if verified.isdigit():
                return get_item_by_id(int(verified))
        # Invalid signature — do not fall through as catalog id containing a dot
        return None

    # 4) Claim page URLs
    claim_qr_match = re.search(r"/claim_qr/([^/?#]+)", text, re.I)
    if claim_qr_match:
        from urllib.parse import unquote
        item = _lookup_catalog_qr(unquote(claim_qr_match.group(1)))
        if item:
            return item

    claim_id_match = re.search(r"/claim_item/(\d+)", text, re.I)
    if claim_id_match:
        return get_item_by_id(int(claim_id_match.group(1)))

    # 5) Legacy aliases
    if re.match(r"^item-\d{3}$", text, re.I):
        item = _lookup_catalog_qr(text.lower())
        if item:
            return item

    if text.lower().startswith("oiko-item-"):
        suffix = text.lower().replace("oiko-item-", "", 1)
        if suffix.isdigit():
            return _lookup_catalog_qr(f"item-{int(suffix):03d}")
        return _lookup_catalog_qr(text)

    if text.isdigit() and allow_legacy_unsigned_qr():
        return get_item_by_id(int(text))

    return None
