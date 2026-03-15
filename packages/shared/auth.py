from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from typing import Literal

import bcrypt

from packages.shared.settings import AppSettings
from packages.storage.auth_store import (
    AuthStore,
    LocalUserCreate,
    LocalUserRecord,
    UserRole,
)

SESSION_COOKIE_NAME = "homelab_analytics_session"
CSRF_COOKIE_NAME = "homelab_analytics_csrf"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12
_ROLE_ORDER = {
    UserRole.READER: 0,
    UserRole.OPERATOR: 1,
    UserRole.ADMIN: 2,
}


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: str
    username: str
    role: UserRole
    csrf_token: str | None = None


@dataclass(frozen=True)
class IssuedSession:
    cookie_value: str
    csrf_token: str


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def has_required_role(role: UserRole, required_role: UserRole) -> bool:
    return _ROLE_ORDER[role] >= _ROLE_ORDER[required_role]


def serialize_user(user: LocalUserRecord) -> dict[str, object]:
    return {
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role.value,
        "enabled": user.enabled,
        "created_at": user.created_at.isoformat(),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def serialize_principal(principal: AuthenticatedPrincipal) -> dict[str, str]:
    return {
        "user_id": principal.user_id,
        "username": principal.username,
        "role": principal.role.value,
    }


def build_session_manager(settings: AppSettings) -> "SessionManager | None":
    if settings.auth_mode.lower() != "local":
        return None
    if not settings.session_secret:
        raise ValueError(
            "Local auth requires HOMELAB_ANALYTICS_SESSION_SECRET to be configured."
        )
    return SessionManager(settings.session_secret)


def maybe_bootstrap_local_admin(
    auth_store: AuthStore,
    settings: AppSettings,
) -> LocalUserRecord | None:
    if settings.auth_mode.lower() != "local":
        return None
    username = settings.bootstrap_admin_username
    password = settings.bootstrap_admin_password
    if not username and not password:
        return None
    if not username or not password:
        raise ValueError(
            "Bootstrap local admin requires both username and password settings."
        )
    try:
        existing = auth_store.get_local_user_by_username(username)
    except KeyError:
        return auth_store.create_local_user(
            LocalUserCreate(
                user_id=f"user-{uuid.uuid4().hex}",
                username=username,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
            )
        )
    if existing.role != UserRole.ADMIN:
        raise ValueError("Bootstrap local admin username already exists without admin role.")
    return existing


class SessionManager:
    def __init__(
        self,
        secret: str,
        *,
        cookie_name: str = SESSION_COOKIE_NAME,
        csrf_cookie_name: str = CSRF_COOKIE_NAME,
        max_age_seconds: int = SESSION_MAX_AGE_SECONDS,
        same_site: Literal["lax", "strict", "none"] = "lax",
    ) -> None:
        self._secret = secret.encode("utf-8")
        self.cookie_name = cookie_name
        self.csrf_cookie_name = csrf_cookie_name
        self.max_age_seconds = max_age_seconds
        self.same_site = same_site

    def issue_session(self, user: LocalUserRecord) -> IssuedSession:
        now = datetime.now(UTC)
        csrf_token = secrets.token_urlsafe(24)
        payload = {
            "sub": user.user_id,
            "usr": user.username,
            "role": user.role.value,
            "fp": _password_fingerprint(user.password_hash),
            "csrf": csrf_token,
            "sid": uuid.uuid4().hex,
            "iat": now.isoformat(),
            "exp": (now + timedelta(seconds=self.max_age_seconds)).isoformat(),
        }
        encoded_payload = _urlsafe_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = hmac.new(
            self._secret,
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        return IssuedSession(
            cookie_value=f"{encoded_payload}.{signature}",
            csrf_token=csrf_token,
        )

    def issue_session_cookie(self, user: LocalUserRecord) -> str:
        return self.issue_session(user).cookie_value

    def authenticate(
        self,
        cookie_value: str | None,
        auth_store: AuthStore,
    ) -> AuthenticatedPrincipal | None:
        payload = self._decode_payload(cookie_value)
        if payload is None:
            return None
        try:
            user = auth_store.get_local_user(payload["sub"])
        except (KeyError, ValueError):
            return None
        if not user.enabled:
            return None
        if user.username != payload["usr"]:
            return None
        if _password_fingerprint(user.password_hash) != payload["fp"]:
            return None
        return AuthenticatedPrincipal(
            user_id=user.user_id,
            username=user.username,
            role=user.role,
            csrf_token=payload.get("csrf"),
        )

    def build_wsgi_set_cookie_header(
        self,
        cookie_value: str,
        *,
        secure: bool = False,
    ) -> tuple[str, str]:
        cookie = SimpleCookie()
        cookie[self.cookie_name] = cookie_value
        morsel = cookie[self.cookie_name]
        morsel["httponly"] = True
        morsel["max-age"] = str(self.max_age_seconds)
        morsel["path"] = "/"
        morsel["samesite"] = self.same_site.capitalize()
        if secure:
            morsel["secure"] = True
        return ("Set-Cookie", morsel.OutputString())

    def build_wsgi_clear_cookie_header(self) -> tuple[str, str]:
        cookie = SimpleCookie()
        cookie[self.cookie_name] = ""
        morsel = cookie[self.cookie_name]
        morsel["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        morsel["httponly"] = True
        morsel["max-age"] = "0"
        morsel["path"] = "/"
        morsel["samesite"] = self.same_site.capitalize()
        return ("Set-Cookie", morsel.OutputString())

    def _decode_payload(self, cookie_value: str | None) -> dict[str, str] | None:
        if not cookie_value or "." not in cookie_value:
            return None
        encoded_payload, signature = cookie_value.rsplit(".", 1)
        expected_signature = hmac.new(
            self._secret,
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
        required_fields = {"sub", "usr", "role", "fp", "csrf", "exp"}
        if not required_fields.issubset(payload):
            return None
        try:
            expires_at = datetime.fromisoformat(str(payload["exp"]))
        except ValueError:
            return None
        if expires_at <= datetime.now(UTC):
            return None
        return {key: str(value) for key, value in payload.items()}


def _password_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()


def _urlsafe_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _urlsafe_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
