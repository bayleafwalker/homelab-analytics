"""OIDC provider: login redirect, token exchange, and callback authentication."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
import jwt

from packages.platform.auth._signing import _decode_signed_payload, _encode_signed_payload
from packages.platform.auth.contracts import UserRole
from packages.platform.auth.permission_registry import normalize_permission_grants
from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal
from packages.shared.settings import AppSettings

OIDC_STATE_COOKIE_NAME = "homelab_analytics_oidc_state"
OIDC_STATE_MAX_AGE_SECONDS = 60 * 10


class OidcAuthenticationError(ValueError):
    """Raised when OIDC token exchange or validation fails."""


class OidcAuthorizationError(PermissionError):
    """Raised when a validated OIDC identity is not mapped to an app role."""


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


def normalize_return_to(return_to: str | None) -> str:
    if not return_to:
        return "/"
    candidate = return_to.strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return "/"
    return candidate


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


def _parse_permission_group_mappings(
    raw_mappings: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    parsed: dict[str, tuple[str, ...]] = {}
    for raw_mapping in raw_mappings:
        if "=" not in raw_mapping:
            raise ValueError(
                "OIDC permission-group mappings must use '<group>=<permission[,permission...]>' entries."
            )
        raw_group, raw_permissions = raw_mapping.split("=", 1)
        group = raw_group.strip().lower()
        if not group:
            raise ValueError("OIDC permission-group mappings must include a group name.")
        permissions = normalize_permission_grants(
            [part for part in raw_permissions.split(",")]
        )
        if not permissions:
            raise ValueError(
                "OIDC permission-group mappings must include at least one known permission."
            )
        existing = set(parsed.get(group, ()))
        existing.update(permissions)
        parsed[group] = tuple(sorted(existing))
    return parsed


def build_oidc_provider(
    settings: AppSettings,
    *,
    http_client: httpx.Client | None = None,
) -> "OidcProvider | None":
    if settings.resolved_auth_mode != "oidc":
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
        self.permissions_claim = settings.oidc_permissions_claim
        self.permission_group_mappings = _parse_permission_group_mappings(
            settings.oidc_permission_group_mappings
        )
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
        if payload is None:
            raise OidcAuthenticationError("OIDC login state is invalid or expired.")
        state_value = payload.get("state")
        nonce_value = payload.get("nonce")
        return_to_value = payload.get("return_to")
        if (
            not isinstance(state_value, str)
            or not isinstance(nonce_value, str)
            or not isinstance(return_to_value, str)
            or state_value != state
        ):
            raise OidcAuthenticationError("OIDC login state is invalid or expired.")
        return OidcLoginState(
            state=state_value,
            nonce=nonce_value,
            return_to=normalize_return_to(return_to_value),
        )

    def principal_from_claims(self, claims: dict[str, Any]) -> AuthenticatedPrincipal:
        username = self._claim_username(claims)
        groups = self._groups_from_claims(claims)
        has_group_role_mapping = self._has_group_role_mapping(groups)
        permissions = normalize_permission_grants(
            [
                *self._permissions_from_claims(claims),
                *self._permissions_from_groups(groups),
            ]
        )
        role_mapping_configured = bool(
            self.reader_groups or self.operator_groups or self.admin_groups
        )
        role = self._role_from_groups(
            groups,
            allow_unmapped=bool(permissions),
        )
        subject = str(claims.get("sub", "")).strip()
        if not subject:
            raise OidcAuthenticationError("OIDC token is missing a subject.")
        return AuthenticatedPrincipal(
            user_id=f"oidc:{subject}",
            username=username,
            role=role,
            auth_provider="oidc",
            permissions=permissions,
            permission_bound=(
                bool(permissions)
                and role_mapping_configured
                and not has_group_role_mapping
            ),
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
        configured_claim = self.username_claim.strip()
        raw_configured = claims.get(configured_claim)
        if raw_configured is not None:
            if isinstance(raw_configured, str) and raw_configured.strip():
                return raw_configured.strip()
            raise OidcAuthenticationError(
                f"OIDC username claim '{configured_claim}' must be a non-empty string."
            )
        for field_name in (
            "preferred_username",
            "email",
            "name",
            "sub",
        ):
            if field_name == configured_claim:
                continue
            value = claims.get(field_name)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise OidcAuthenticationError("OIDC token did not include a usable username claim.")

    def _groups_from_claims(self, claims: dict[str, Any]) -> set[str]:
        raw_groups = claims.get(self.groups_claim)
        if raw_groups is None:
            return set()
        if isinstance(raw_groups, list):
            groups: set[str] = set()
            for value in raw_groups:
                if not isinstance(value, str):
                    raise OidcAuthenticationError(
                        f"OIDC groups claim '{self.groups_claim}' must contain only string values."
                    )
                normalized = value.strip().lower()
                if normalized:
                    groups.add(normalized)
            return groups
        if isinstance(raw_groups, str):
            return {part.strip().lower() for part in raw_groups.split(",") if part.strip()}
        raise OidcAuthenticationError(
            f"OIDC groups claim '{self.groups_claim}' must be a string or list of strings."
        )

    def _role_from_groups(
        self,
        groups: set[str],
        *,
        allow_unmapped: bool,
    ) -> UserRole:
        if groups & self.admin_groups:
            return UserRole.ADMIN
        if groups & self.operator_groups:
            return UserRole.OPERATOR
        if groups & self.reader_groups:
            return UserRole.READER
        if self.reader_groups or self.operator_groups or self.admin_groups:
            if allow_unmapped:
                return UserRole.READER
            raise OidcAuthorizationError("OIDC identity is not mapped to any application role.")
        return UserRole.READER

    def _has_group_role_mapping(self, groups: set[str]) -> bool:
        return bool(
            groups & self.admin_groups
            or groups & self.operator_groups
            or groups & self.reader_groups
        )

    def _permissions_from_claims(self, claims: dict[str, Any]) -> tuple[str, ...]:
        if not self.permissions_claim:
            return ()
        raw_permissions = claims.get(self.permissions_claim)
        if raw_permissions is None:
            return ()
        if isinstance(raw_permissions, list):
            permissions: list[str] = []
            for value in raw_permissions:
                if not isinstance(value, str):
                    raise OidcAuthenticationError(
                        f"OIDC permissions claim '{self.permissions_claim}' must contain only string values."
                    )
                permissions.append(value)
            return normalize_permission_grants(permissions)
        if isinstance(raw_permissions, str) and raw_permissions.strip():
            return normalize_permission_grants(
                [part for part in raw_permissions.split(",")]
            )
        raise OidcAuthenticationError(
            f"OIDC permissions claim '{self.permissions_claim}' must be a string or list of strings."
        )

    def _permissions_from_groups(self, groups: set[str]) -> tuple[str, ...]:
        if not self.permission_group_mappings:
            return ()
        permissions: set[str] = set()
        for group in groups:
            permissions.update(self.permission_group_mappings.get(group, ()))
        return tuple(sorted(permissions))

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
