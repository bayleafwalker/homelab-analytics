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
from typing import Any, Literal
from urllib.parse import urlencode

import bcrypt
import httpx
import jwt

from packages.shared.settings import AppSettings
from packages.storage.auth_store import (
    AuthStore,
    LocalUserCreate,
    LocalUserRecord,
    ServiceTokenRecord,
    UserRole,
)

SESSION_COOKIE_NAME = "homelab_analytics_session"
CSRF_COOKIE_NAME = "homelab_analytics_csrf"
OIDC_STATE_COOKIE_NAME = "homelab_analytics_oidc_state"
SERVICE_TOKEN_VALUE_PREFIX = "hst_"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12
OIDC_STATE_MAX_AGE_SECONDS = 60 * 10
_ROLE_ORDER = {
    UserRole.READER: 0,
    UserRole.OPERATOR: 1,
    UserRole.ADMIN: 2,
}


class OidcAuthenticationError(ValueError):
    """Raised when OIDC token exchange or validation fails."""


class OidcAuthorizationError(PermissionError):
    """Raised when a validated OIDC identity is not mapped to an app role."""


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: str
    username: str
    role: UserRole
    auth_provider: Literal["local", "oidc", "service_token"] = "local"
    csrf_token: str | None = None
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class IssuedSession:
    cookie_value: str
    csrf_token: str


@dataclass(frozen=True)
class IssuedServiceToken:
    token_id: str
    token_value: str
    token_secret_hash: str


@dataclass(frozen=True)
class OidcLoginRedirect:
    authorization_url: str
    state_cookie_value: str
    state: str


@dataclass(frozen=True)
class OidcLoginState:
    state: str
    nonce: str
    return_to: str


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


def serialize_user(user: LocalUserRecord) -> dict[str, object]:
    return {
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role.value,
        "enabled": user.enabled,
        "created_at": user.created_at.isoformat(),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "auth_provider": "local",
    }


def serialize_authenticated_user(principal: AuthenticatedPrincipal) -> dict[str, object]:
    payload: dict[str, object] = {
        "user_id": principal.user_id,
        "username": principal.username,
        "role": principal.role.value,
        "enabled": True,
        "created_at": None,
        "last_login_at": None,
        "auth_provider": principal.auth_provider,
    }
    if principal.auth_provider == "service_token":
        payload["scopes"] = list(principal.scopes)
        payload["token_id"] = principal.user_id
    return payload


def serialize_service_token(
    token: ServiceTokenRecord,
) -> dict[str, object]:
    return {
        "token_id": token.token_id,
        "token_name": token.token_name,
        "role": token.role.value,
        "scopes": list(token.scopes),
        "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        "created_at": token.created_at.isoformat(),
        "last_used_at": token.last_used_at.isoformat() if token.last_used_at else None,
        "revoked_at": token.revoked_at.isoformat() if token.revoked_at else None,
        "revoked": token.revoked_at is not None,
        "expired": token.expires_at is not None and token.expires_at <= datetime.now(UTC),
    }


def serialize_principal(principal: AuthenticatedPrincipal) -> dict[str, str]:
    payload = {
        "user_id": principal.user_id,
        "username": principal.username,
        "role": principal.role.value,
        "auth_provider": principal.auth_provider,
    }
    if principal.auth_provider == "service_token":
        payload["scopes"] = ",".join(principal.scopes)
    return payload


def build_session_manager(settings: AppSettings) -> "SessionManager | None":
    if settings.auth_mode.lower() not in {"local", "oidc"}:
        return None
    if not settings.session_secret:
        raise ValueError(
            "Cookie-backed authentication requires HOMELAB_ANALYTICS_SESSION_SECRET to be configured."
        )
    return SessionManager(settings.session_secret)


def build_oidc_provider(
    settings: AppSettings,
    *,
    http_client: httpx.Client | None = None,
) -> "OidcProvider | None":
    if settings.auth_mode.lower() != "oidc":
        return None
    missing = [
        variable
        for variable, value in (
            ("HOMELAB_ANALYTICS_OIDC_ISSUER_URL", settings.oidc_issuer_url),
            ("HOMELAB_ANALYTICS_OIDC_CLIENT_ID", settings.oidc_client_id),
            ("HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET", settings.oidc_client_secret),
            ("HOMELAB_ANALYTICS_OIDC_REDIRECT_URI", settings.oidc_redirect_uri),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"OIDC auth requires settings: {', '.join(missing)}")
    return OidcProvider(settings, http_client=http_client)


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


def principal_from_service_token(token: ServiceTokenRecord) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=token.token_id,
        username=token.token_name,
        role=token.role,
        auth_provider="service_token",
        scopes=token.scopes,
    )


def authenticate_service_token(
    token_value: str | None,
    auth_store: AuthStore,
) -> AuthenticatedPrincipal | None:
    parsed = parse_service_token(token_value)
    if parsed is None:
        return None
    token_id, token_secret = parsed
    try:
        token = auth_store.get_service_token(token_id)
    except KeyError:
        return None
    if token.revoked_at is not None:
        return None
    if token.expires_at is not None and token.expires_at <= datetime.now(UTC):
        return None
    if not verify_service_token_secret(token_secret, token.token_secret_hash):
        return None
    token = auth_store.record_service_token_use(token.token_id)
    return principal_from_service_token(token)


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
            )
            resolved_fingerprint = credential_fingerprint
        payload = {
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
        provider = payload["provider"]
        if provider == "local":
            if auth_store is None:
                return None
            try:
                user = auth_store.get_local_user(payload["sub"])
            except (KeyError, ValueError):
                return None
            if not user.enabled:
                return None
            if user.username != payload["usr"]:
                return None
            if _password_fingerprint(user.password_hash) != payload.get("fp", ""):
                return None
            return AuthenticatedPrincipal(
                user_id=user.user_id,
                username=user.username,
                role=user.role,
                auth_provider="local",
                csrf_token=payload.get("csrf"),
            )
        if provider == "oidc":
            try:
                role = UserRole(payload["role"])
            except ValueError:
                return None
            return AuthenticatedPrincipal(
                user_id=payload["sub"],
                username=payload["usr"],
                role=role,
                auth_provider="oidc",
                csrf_token=payload.get("csrf"),
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


class OidcProvider:
    def __init__(
        self,
        settings: AppSettings,
        *,
        http_client: httpx.Client | None = None,
        state_cookie_name: str = OIDC_STATE_COOKIE_NAME,
        state_max_age_seconds: int = OIDC_STATE_MAX_AGE_SECONDS,
    ) -> None:
        if not settings.session_secret:
            raise ValueError(
                "OIDC auth requires HOMELAB_ANALYTICS_SESSION_SECRET so the app can sign state and session cookies."
            )
        self._secret = settings.session_secret.encode("utf-8")
        self.state_cookie_name = state_cookie_name
        self.state_max_age_seconds = state_max_age_seconds
        self.same_site: Literal["lax", "strict", "none"] = "lax"
        self.issuer_url = str(settings.oidc_issuer_url)
        self.client_id = str(settings.oidc_client_id)
        self.client_secret = str(settings.oidc_client_secret)
        self.redirect_uri = str(settings.oidc_redirect_uri)
        self.scopes = settings.oidc_scopes or ("openid", "profile", "email")
        self.api_audience = settings.oidc_api_audience or self.client_id
        self.username_claim = settings.oidc_username_claim
        self.groups_claim = settings.oidc_groups_claim
        self.reader_groups = {value.strip().lower() for value in settings.oidc_reader_groups if value.strip()}
        self.operator_groups = {
            value.strip().lower() for value in settings.oidc_operator_groups if value.strip()
        }
        self.admin_groups = {value.strip().lower() for value in settings.oidc_admin_groups if value.strip()}
        self._http = http_client or httpx.Client(timeout=10.0, follow_redirects=False)
        self._discovery: dict[str, Any] | None = None
        self._jwks: dict[str, Any] | None = None

    def build_login_redirect(self, return_to: str | None = None) -> OidcLoginRedirect:
        login_state = OidcLoginState(
            state=secrets.token_urlsafe(24),
            nonce=secrets.token_urlsafe(24),
            return_to=normalize_return_to(return_to),
        )
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": " ".join(self.scopes),
                "state": login_state.state,
                "nonce": login_state.nonce,
            }
        )
        discovery = self._load_discovery()
        authorization_endpoint = str(discovery["authorization_endpoint"])
        separator = "&" if "?" in authorization_endpoint else "?"
        return OidcLoginRedirect(
            authorization_url=f"{authorization_endpoint}{separator}{query}",
            state_cookie_value=_encode_signed_payload(
                self._secret,
                {
                    "state": login_state.state,
                    "nonce": login_state.nonce,
                    "return_to": login_state.return_to,
                    "iat": datetime.now(UTC).isoformat(),
                    "exp": (
                        datetime.now(UTC) + timedelta(seconds=self.state_max_age_seconds)
                    ).isoformat(),
                },
            ),
            state=login_state.state,
        )

    def authenticate_callback(
        self,
        *,
        code: str,
        state: str,
        cookie_value: str | None,
    ) -> tuple[AuthenticatedPrincipal, str]:
        login_state = self.read_login_state(state=state, cookie_value=cookie_value)
        token_response = self._exchange_code(code)
        id_token = token_response.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise OidcAuthenticationError("OIDC token response did not include an id_token.")
        claims = self._decode_token(
            id_token,
            audiences=(self.client_id,),
            nonce=login_state.nonce,
        )
        return self.principal_from_claims(claims), login_state.return_to

    def authenticate_bearer_token(self, token: str) -> AuthenticatedPrincipal:
        claims = self._decode_token(token, audiences=(self.api_audience, self.client_id))
        return self.principal_from_claims(claims)

    def read_login_state(
        self,
        *,
        state: str,
        cookie_value: str | None,
    ) -> OidcLoginState:
        payload = _decode_signed_payload(
            self._secret,
            cookie_value,
            required_fields={"state", "nonce", "return_to", "exp"},
        )
        if payload is None or payload.get("state") != state:
            raise OidcAuthenticationError("OIDC login state is invalid or expired.")
        return OidcLoginState(
            state=payload["state"],
            nonce=payload["nonce"],
            return_to=normalize_return_to(payload["return_to"]),
        )

    def principal_from_claims(self, claims: dict[str, Any]) -> AuthenticatedPrincipal:
        username = self._claim_username(claims)
        role = self._role_from_claims(claims)
        subject = str(claims.get("sub", "")).strip()
        if not subject:
            raise OidcAuthenticationError("OIDC token is missing a subject.")
        return AuthenticatedPrincipal(
            user_id=f"oidc:{subject}",
            username=username,
            role=role,
            auth_provider="oidc",
        )

    def build_set_state_cookie_header(
        self,
        cookie_value: str,
        *,
        secure: bool = False,
    ) -> tuple[str, str]:
        cookie = SimpleCookie()
        cookie[self.state_cookie_name] = cookie_value
        morsel = cookie[self.state_cookie_name]
        morsel["httponly"] = True
        morsel["max-age"] = str(self.state_max_age_seconds)
        morsel["path"] = "/"
        morsel["samesite"] = self.same_site.capitalize()
        if secure:
            morsel["secure"] = True
        return ("Set-Cookie", morsel.OutputString())

    def build_clear_state_cookie_header(self, *, secure: bool = False) -> tuple[str, str]:
        cookie = SimpleCookie()
        cookie[self.state_cookie_name] = ""
        morsel = cookie[self.state_cookie_name]
        morsel["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        morsel["httponly"] = True
        morsel["max-age"] = "0"
        morsel["path"] = "/"
        morsel["samesite"] = self.same_site.capitalize()
        if secure:
            morsel["secure"] = True
        return ("Set-Cookie", morsel.OutputString())

    def _claim_username(self, claims: dict[str, Any]) -> str:
        for field_name in (
            self.username_claim,
            "preferred_username",
            "email",
            "name",
            "sub",
        ):
            value = claims.get(field_name)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise OidcAuthenticationError("OIDC token did not include a usable username claim.")

    def _role_from_claims(self, claims: dict[str, Any]) -> UserRole:
        raw_groups = claims.get(self.groups_claim)
        groups: set[str] = set()
        if isinstance(raw_groups, list):
            groups = {str(value).strip().lower() for value in raw_groups if str(value).strip()}
        elif isinstance(raw_groups, str) and raw_groups.strip():
            groups = {part.strip().lower() for part in raw_groups.split(",") if part.strip()}
        if groups & self.admin_groups:
            return UserRole.ADMIN
        if groups & self.operator_groups:
            return UserRole.OPERATOR
        if groups & self.reader_groups:
            return UserRole.READER
        if self.reader_groups or self.operator_groups or self.admin_groups:
            raise OidcAuthorizationError("OIDC identity is not mapped to any application role.")
        return UserRole.READER

    def _load_discovery(self) -> dict[str, Any]:
        if self._discovery is not None:
            return self._discovery
        metadata_url = f"{self.issuer_url.rstrip('/')}/.well-known/openid-configuration"
        response = self._http.get(metadata_url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise OidcAuthenticationError("OIDC discovery response was not a JSON object.")
        issuer = str(payload.get("issuer", "")).rstrip("/")
        if issuer != self.issuer_url.rstrip("/"):
            raise OidcAuthenticationError("OIDC discovery issuer does not match configured issuer.")
        self._discovery = payload
        return payload

    def _load_jwks(self) -> dict[str, Any]:
        if self._jwks is not None:
            return self._jwks
        discovery = self._load_discovery()
        jwks_uri = discovery.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise OidcAuthenticationError("OIDC discovery response is missing jwks_uri.")
        response = self._http.get(jwks_uri)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise OidcAuthenticationError("OIDC JWKS response was not a JSON object.")
        self._jwks = payload
        return payload

    def _exchange_code(self, code: str) -> dict[str, Any]:
        discovery = self._load_discovery()
        token_endpoint = discovery.get("token_endpoint")
        if not isinstance(token_endpoint, str) or not token_endpoint:
            raise OidcAuthenticationError("OIDC discovery response is missing token_endpoint.")
        response = self._http.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise OidcAuthenticationError("OIDC token response was not a JSON object.")
        return payload

    def _decode_token(
        self,
        token: str,
        *,
        audiences: tuple[str, ...],
        nonce: str | None = None,
    ) -> dict[str, Any]:
        discovery = self._load_discovery()
        jwks = self._load_jwks()
        header = jwt.get_unverified_header(token)
        key = _resolve_jwt_key(header, jwks)
        allowed_algorithms = discovery.get("id_token_signing_alg_values_supported")
        if not isinstance(allowed_algorithms, list) or not allowed_algorithms:
            allowed_algorithms = [str(header.get("alg", "RS256"))]
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=[str(value) for value in allowed_algorithms],
                audience=audiences,
                issuer=self.issuer_url.rstrip("/"),
            )
        except jwt.PyJWTError as exc:
            raise OidcAuthenticationError("OIDC token validation failed.") from exc
        if nonce is not None and claims.get("nonce") != nonce:
            raise OidcAuthenticationError("OIDC token nonce did not match the login state.")
        if not isinstance(claims, dict):
            raise OidcAuthenticationError("OIDC decoded claims were not a JSON object.")
        return claims


def normalize_return_to(return_to: str | None) -> str:
    if not return_to:
        return "/"
    candidate = return_to.strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return "/"
    return candidate


def _password_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()


def _resolve_jwt_key(header: dict[str, Any], jwks: dict[str, Any]) -> Any:
    raw_keys = jwks.get("keys")
    if not isinstance(raw_keys, list) or not raw_keys:
        raise OidcAuthenticationError("OIDC JWKS response does not include signing keys.")
    kid = header.get("kid")
    for raw_key in raw_keys:
        if not isinstance(raw_key, dict):
            continue
        if kid and raw_key.get("kid") != kid:
            continue
        return jwt.PyJWK.from_dict(raw_key).key
    raise OidcAuthenticationError("OIDC token signing key was not found in JWKS.")


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
