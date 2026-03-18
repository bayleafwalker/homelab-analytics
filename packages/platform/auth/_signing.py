"""Private signing helpers shared by SessionManager and OidcProvider."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any


def _encode_signed_payload(secret: bytes, payload: dict[str, Any]) -> str:
    encoded_payload = _urlsafe_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = hmac.new(
        secret,
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded_payload}.{signature}"


def _decode_signed_payload(
    secret: bytes,
    value: str | None,
    *,
    required_fields: set[str],
) -> dict[str, str] | None:
    if not value or "." not in value:
        return None
    encoded_payload, signature = value.rsplit(".", 1)
    expected_signature = hmac.new(
        secret,
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None
    try:
        payload = json.loads(_urlsafe_decode(encoded_payload).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if not required_fields.issubset(payload):
        return None
    try:
        expires_at = datetime.fromisoformat(str(payload["exp"]))
    except ValueError:
        return None
    if expires_at <= datetime.now(UTC):
        return None
    return {key: str(value) for key, value in payload.items()}


def _urlsafe_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _urlsafe_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
