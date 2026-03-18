"""Cryptographic helpers for passwords and service tokens."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

import bcrypt

SERVICE_TOKEN_VALUE_PREFIX = "hst_"


@dataclass(frozen=True)
class IssuedServiceToken:
    token_id: str
    token_value: str
    token_secret_hash: str


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def hash_service_token_secret(secret: str) -> str:
    if not secret:
        raise ValueError("Service-token secret must not be empty.")
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_service_token_secret(secret: str, token_secret_hash: str) -> bool:
    if not secret:
        return False
    return hmac.compare_digest(hash_service_token_secret(secret), token_secret_hash)


def issue_service_token(token_id: str) -> IssuedServiceToken:
    if not token_id.strip():
        raise ValueError("Service-token id must not be empty.")
    token_secret = secrets.token_urlsafe(32)
    return IssuedServiceToken(
        token_id=token_id,
        token_value=f"{SERVICE_TOKEN_VALUE_PREFIX}{token_id}.{token_secret}",
        token_secret_hash=hash_service_token_secret(token_secret),
    )


def parse_service_token(token_value: str | None) -> tuple[str, str] | None:
    if not token_value or "." not in token_value:
        return None
    prefix_and_id, secret = token_value.split(".", 1)
    if not prefix_and_id.startswith(SERVICE_TOKEN_VALUE_PREFIX) or not secret:
        return None
    token_id = prefix_and_id[len(SERVICE_TOKEN_VALUE_PREFIX) :].strip()
    if not token_id:
        return None
    return token_id, secret


def has_required_service_token_scope(
    scopes: tuple[str, ...],
    required_scope: str | None,
) -> bool:
    if required_scope is None:
        return True
    return required_scope in set(scopes)
