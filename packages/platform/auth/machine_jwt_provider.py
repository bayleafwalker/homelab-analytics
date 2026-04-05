"""Upstream machine JWT provider for non-interactive bearer authentication."""
from __future__ import annotations

import re
from typing import Any

import httpx
import jwt

from packages.platform.auth.permission_registry import normalize_permission_grants
from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal
from packages.shared.settings import AppSettings
from packages.storage.auth_store import SERVICE_TOKEN_SCOPES, UserRole


class MachineJwtAuthenticationError(ValueError):
    """Raised when machine JWT validation or claim parsing fails."""


class MachineJwtAuthorizationError(PermissionError):
    """Raised when a machine JWT is valid but not authorized for app usage."""


_ROLE_BY_NAME = {
    "reader": UserRole.READER,
    "operator": UserRole.OPERATOR,
    "admin": UserRole.ADMIN,
}


def _resolve_jwt_key(header: dict[str, Any], jwks: dict[str, Any]) -> Any:
    raw_keys = jwks.get("keys")
    if not isinstance(raw_keys, list) or not raw_keys:
        raise MachineJwtAuthenticationError(
            "Machine JWT JWKS response does not include signing keys."
        )
    kid = header.get("kid")
    for raw_key in raw_keys:
        if not isinstance(raw_key, dict):
            continue
        if kid and raw_key.get("kid") != kid:
            continue
        return jwt.PyJWK.from_dict(raw_key).key
    raise MachineJwtAuthenticationError(
        "Machine JWT signing key was not found in JWKS."
    )


def build_machine_jwt_provider(
    settings: AppSettings,
    *,
    http_client: httpx.Client | None = None,
) -> "MachineJwtProvider | None":
    if not settings.machine_jwt_enabled:
        return None
    return MachineJwtProvider(settings, http_client=http_client)


class MachineJwtProvider:
    def __init__(
        self,
        settings: AppSettings,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.issuer_url = str(settings.machine_jwt_issuer_url or "").strip().rstrip("/")
        self.jwks_url = (settings.machine_jwt_jwks_url or "").strip() or None
        self.audience = str(settings.machine_jwt_audience or "").strip()
        self.username_claim = settings.machine_jwt_username_claim.strip() or "sub"
        self.role_claim = (
            settings.machine_jwt_role_claim.strip()
            if settings.machine_jwt_role_claim
            else None
        )
        self.permissions_claim = (
            settings.machine_jwt_permissions_claim.strip()
            if settings.machine_jwt_permissions_claim
            else None
        )
        self.scopes_claim = (
            settings.machine_jwt_scopes_claim.strip()
            if settings.machine_jwt_scopes_claim
            else None
        )
        try:
            self.default_role = UserRole(settings.machine_jwt_default_role.strip().lower())
        except ValueError as exc:
            raise ValueError(
                "HOMELAB_ANALYTICS_MACHINE_JWT_DEFAULT_ROLE must be one of: "
                "reader, operator, admin."
            ) from exc

        self._http = http_client or httpx.Client(timeout=10.0, follow_redirects=False)
        self._discovery: dict[str, Any] | None = None
        self._jwks: dict[str, Any] | None = None

    def authenticate_bearer_token(self, token: str) -> AuthenticatedPrincipal:
        claims = self._decode_token(token)
        subject = str(claims.get("sub", "")).strip()
        username = self._username_from_claims(claims)
        role, has_explicit_role = self._role_from_claims(claims)
        permissions = self._permissions_from_claims(claims)
        scopes = self._scopes_from_claims(claims)
        principal_key = subject or username
        if not principal_key:
            raise MachineJwtAuthenticationError(
                "Machine JWT token did not include a usable subject."
            )
        permission_bound = not has_explicit_role and bool(permissions) and not bool(scopes)
        return AuthenticatedPrincipal(
            user_id=f"machine_jwt:{principal_key}",
            username=username or principal_key,
            role=role,
            auth_provider="machine_jwt",
            scopes=scopes,
            permissions=permissions,
            permission_bound=permission_bound,
        )

    def _username_from_claims(self, claims: dict[str, Any]) -> str:
        configured_claim = self.username_claim
        raw_value = claims.get(configured_claim)
        if raw_value is not None:
            if isinstance(raw_value, str) and raw_value.strip():
                return raw_value.strip()
            raise MachineJwtAuthenticationError(
                f"Machine JWT username claim '{configured_claim}' must be a non-empty string."
            )
        for field_name in ("sub", "client_id", "azp"):
            if field_name == configured_claim:
                continue
            value = claims.get(field_name)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise MachineJwtAuthenticationError(
            "Machine JWT token did not include a usable username claim."
        )

    def _role_from_claims(self, claims: dict[str, Any]) -> tuple[UserRole, bool]:
        if not self.role_claim:
            return self.default_role, False
        raw_role = claims.get(self.role_claim)
        if raw_role is None:
            return self.default_role, False
        if not isinstance(raw_role, str):
            raise MachineJwtAuthenticationError(
                f"Machine JWT role claim '{self.role_claim}' must be a string."
            )
        normalized = raw_role.strip().lower()
        role = _ROLE_BY_NAME.get(normalized)
        if role is None:
            raise MachineJwtAuthorizationError(
                f"Machine JWT role claim '{self.role_claim}' contains unsupported role '{normalized}'."
            )
        return role, True

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
                    raise MachineJwtAuthenticationError(
                        f"Machine JWT permissions claim '{self.permissions_claim}' "
                        "must contain only string values."
                    )
                permissions.append(value)
            return normalize_permission_grants(permissions)
        if isinstance(raw_permissions, str) and raw_permissions.strip():
            return normalize_permission_grants(
                [part for part in raw_permissions.split(",")]
            )
        raise MachineJwtAuthenticationError(
            f"Machine JWT permissions claim '{self.permissions_claim}' must be a "
            "string or list of strings."
        )

    def _scopes_from_claims(self, claims: dict[str, Any]) -> tuple[str, ...]:
        if not self.scopes_claim:
            return ()
        raw_scopes = claims.get(self.scopes_claim)
        if raw_scopes is None:
            return ()
        values: list[str] = []
        if isinstance(raw_scopes, str):
            values.extend(part for part in re.split(r"[,\s]+", raw_scopes) if part.strip())
        elif isinstance(raw_scopes, list):
            for value in raw_scopes:
                if not isinstance(value, str):
                    raise MachineJwtAuthenticationError(
                        f"Machine JWT scopes claim '{self.scopes_claim}' must contain only string values."
                    )
                values.append(value)
        else:
            raise MachineJwtAuthenticationError(
                f"Machine JWT scopes claim '{self.scopes_claim}' must be a string or list of strings."
            )
        normalized = {scope.strip().lower() for scope in values if scope.strip()}
        if not normalized:
            return ()
        unknown = normalized.difference(SERVICE_TOKEN_SCOPES)
        if unknown:
            raise MachineJwtAuthenticationError(
                "Machine JWT scopes include unsupported value(s): "
                f"{', '.join(sorted(unknown))}."
            )
        return tuple(scope for scope in SERVICE_TOKEN_SCOPES if scope in normalized)

    def _load_discovery(self) -> dict[str, Any]:
        if self._discovery is not None:
            return self._discovery
        metadata_url = f"{self.issuer_url}/.well-known/openid-configuration"
        response = self._http.get(metadata_url)
        if response.status_code >= 400:
            if self.jwks_url is not None:
                self._discovery = {}
                return self._discovery
            raise MachineJwtAuthenticationError(
                "Machine JWT discovery failed; configure "
                "HOMELAB_ANALYTICS_MACHINE_JWT_JWKS_URL or provide a reachable "
                "OIDC discovery endpoint."
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise MachineJwtAuthenticationError(
                "Machine JWT discovery response was not a JSON object."
            )
        discovered_issuer = str(payload.get("issuer", "")).rstrip("/")
        if discovered_issuer and discovered_issuer != self.issuer_url:
            raise MachineJwtAuthenticationError(
                "Machine JWT discovery issuer does not match configured issuer."
            )
        self._discovery = payload
        return payload

    def _load_jwks(self) -> dict[str, Any]:
        if self._jwks is not None:
            return self._jwks
        jwks_url = self.jwks_url
        if not jwks_url:
            discovery = self._load_discovery()
            discovered_jwks_uri = discovery.get("jwks_uri")
            if not isinstance(discovered_jwks_uri, str) or not discovered_jwks_uri:
                raise MachineJwtAuthenticationError(
                    "Machine JWT discovery response is missing jwks_uri."
                )
            jwks_url = discovered_jwks_uri
        response = self._http.get(jwks_url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise MachineJwtAuthenticationError(
                "Machine JWT JWKS response was not a JSON object."
            )
        self._jwks = payload
        return payload

    def _decode_token(self, token: str) -> dict[str, Any]:
        jwks = self._load_jwks()
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise MachineJwtAuthenticationError(
                "Machine JWT token validation failed."
            ) from exc
        key = _resolve_jwt_key(header, jwks)
        allowed_algorithms: list[str] = []
        discovery = self._load_discovery()
        raw_supported_algorithms = discovery.get("id_token_signing_alg_values_supported")
        if isinstance(raw_supported_algorithms, list):
            allowed_algorithms = [str(value) for value in raw_supported_algorithms]
        if not allowed_algorithms:
            allowed_algorithms = [str(header.get("alg", "RS256"))]
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=allowed_algorithms,
                audience=self.audience,
                issuer=self.issuer_url,
            )
        except jwt.PyJWTError as exc:
            raise MachineJwtAuthenticationError(
                "Machine JWT token validation failed."
            ) from exc
        if not isinstance(claims, dict):
            raise MachineJwtAuthenticationError(
                "Machine JWT decoded claims were not a JSON object."
            )
        return claims
