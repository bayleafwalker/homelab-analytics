"""Session manager: cookie-backed session issuance and authentication."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from typing import Any, Literal

from packages.platform.auth._signing import _decode_signed_payload, _encode_signed_payload
from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal
from packages.shared.auth_modes import is_cookie_auth_mode
from packages.shared.settings import AppSettings
from packages.storage.auth_store import AuthStore, LocalUserRecord, UserRole

SESSION_COOKIE_NAME = "homelab_analytics_session"
CSRF_COOKIE_NAME = "homelab_analytics_csrf"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12


@dataclass(frozen=True)
class IssuedSession:
    cookie_value: str
    csrf_token: str


def _password_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()


def _payload_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) else None


def _payload_string_tuple(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    return ()


def build_session_manager(settings: AppSettings) -> "SessionManager | None":
    if not is_cookie_auth_mode(settings.resolved_auth_mode):
        return None
    if not settings.session_secret:
        raise ValueError(
            "Cookie-backed authentication requires HOMELAB_ANALYTICS_SESSION_SECRET to be configured."
        )
    return SessionManager(settings.session_secret)


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

    def issue_session(
        self,
        principal: AuthenticatedPrincipal | LocalUserRecord,
        *,
        credential_fingerprint: str | None = None,
    ) -> IssuedSession:
        now = datetime.now(UTC)
        csrf_token = secrets.token_urlsafe(24)
        resolved_fingerprint: str | None
        if isinstance(principal, LocalUserRecord):
            session_principal = AuthenticatedPrincipal(
                user_id=principal.user_id,
                username=principal.username,
                role=principal.role,
                auth_provider="local",
                csrf_token=csrf_token,
            )
            resolved_fingerprint = _password_fingerprint(principal.password_hash)
        else:
            session_principal = AuthenticatedPrincipal(
                user_id=principal.user_id,
                username=principal.username,
                role=principal.role,
                auth_provider=principal.auth_provider,
                csrf_token=csrf_token,
                scopes=principal.scopes,
                permissions=principal.permissions,
            )
            resolved_fingerprint = credential_fingerprint
        payload: dict[str, Any] = {
            "sub": session_principal.user_id,
            "usr": session_principal.username,
            "role": session_principal.role.value,
            "provider": session_principal.auth_provider,
            "csrf": csrf_token,
            "sid": uuid.uuid4().hex,
            "iat": now.isoformat(),
            "exp": (now + timedelta(seconds=self.max_age_seconds)).isoformat(),
        }
        if resolved_fingerprint:
            payload["fp"] = resolved_fingerprint
        if session_principal.scopes:
            payload["scopes"] = list(session_principal.scopes)
        if session_principal.permissions:
            payload["permissions"] = list(session_principal.permissions)
        return IssuedSession(
            cookie_value=_encode_signed_payload(self._secret, payload),
            csrf_token=csrf_token,
        )

    def issue_session_cookie(self, principal: AuthenticatedPrincipal | LocalUserRecord) -> str:
        return self.issue_session(principal).cookie_value

    def authenticate(
        self,
        cookie_value: str | None,
        auth_store: AuthStore | None = None,
    ) -> AuthenticatedPrincipal | None:
        payload = _decode_signed_payload(
            self._secret,
            cookie_value,
            required_fields={"sub", "usr", "role", "provider", "csrf", "exp"},
        )
        if payload is None:
            return None
        provider = _payload_string(payload, "provider")
        subject = _payload_string(payload, "sub")
        username = _payload_string(payload, "usr")
        role_value = _payload_string(payload, "role")
        csrf_token = _payload_string(payload, "csrf")
        if provider is None or subject is None or username is None or role_value is None:
            return None
        if provider == "local":
            if auth_store is None:
                return None
            try:
                user = auth_store.get_local_user(subject)
            except (KeyError, ValueError):
                return None
            if not user.enabled:
                return None
            if user.username != username:
                return None
            fingerprint = _payload_string(payload, "fp") or ""
            if _password_fingerprint(user.password_hash) != fingerprint:
                return None
            return AuthenticatedPrincipal(
                user_id=user.user_id,
                username=user.username,
                role=user.role,
                auth_provider="local",
                csrf_token=csrf_token,
            )
        if provider == "oidc":
            try:
                role = UserRole(role_value)
            except ValueError:
                return None
            permissions = _payload_string_tuple(payload, "permissions")
            scopes = _payload_string_tuple(payload, "scopes")
            return AuthenticatedPrincipal(
                user_id=subject,
                username=username,
                role=role,
                auth_provider="oidc",
                csrf_token=csrf_token,
                scopes=scopes,
                permissions=permissions,
            )
        return None

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
