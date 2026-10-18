"""OIDC provider: login redirect, token exchange, and callback authentication.

Authorization-code flow with PKCE (S256), built for Authentik but standard:

- discovery from ``<issuer>/.well-known/openid-configuration`` (or an explicit
  discovery URL); the configured issuer must match the advertised one, and
  tokens are validated against the advertised issuer exactly (Authentik's
  issuer ends in ``/``)
- the ``state``, ``nonce`` and PKCE ``code_verifier`` travel in a signed,
  HttpOnly state cookie; the verifier is sent on the code exchange
- ID tokens are verified against the IdP's JWKS with asymmetric algorithms
  only (never ``none`` or HMAC); discovery and JWKS are cached for
  ``oidc_jwks_cache_seconds`` and an unknown ``kid`` triggers one early JWKS
  refetch so key rotation does not lock users out
- logout is RP-initiated when the IdP advertises ``end_session_endpoint``
  (:meth:`OidcProvider.build_end_session_url`), and local-only otherwise
- groups map to reader/operator/admin roles (and optional permission grants);
  the session cookie is the app's own signed session, so nothing downstream
  needs to know the user signed in through OIDC except the recorded
  ``auth_provider="oidc"``
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from collections.abc import Callable
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
from packages.shared.secrets import (
    EnvironmentSecretResolver,
    SecretReference,
    SecretResolver,
)
from packages.shared.settings import AppSettings

OIDC_STATE_COOKIE_NAME = "homelab_analytics_oidc_state"
OIDC_STATE_MAX_AGE_SECONDS = 60 * 10
# ID tokens must be signed with a public-key algorithm. HMAC (HS*) would make
# the client secret a token-forging key, and "none" is unsigned.
ASYMMETRIC_SIGNING_ALGORITHMS = (
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
    "EdDSA",
)
# Minimum spacing between JWKS refetches triggered by an unknown key id, so a
# flood of tokens with bogus kids cannot hammer the IdP.
JWKS_UNKNOWN_KID_REFRESH_SECONDS = 10.0


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
    code_verifier: str


def pkce_code_challenge(code_verifier: str) -> str:
    """RFC 7636 S256 challenge: base64url(sha256(verifier)) without padding."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def parse_secret_reference(raw: str) -> SecretReference:
    name, separator, key = raw.strip().partition("/")
    if not separator or not name.strip() or not key.strip():
        raise ValueError(
            "HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET_REF must look like '<secret_name>/<secret_key>'."
        )
    return SecretReference(secret_name=name.strip(), secret_key=key.strip())


def resolve_oidc_client_secret(
    settings: AppSettings,
    secret_resolver: SecretResolver | None = None,
) -> str | None:
    """The client secret, literal or resolved through the SecretResolver."""
    if settings.oidc_client_secret:
        return settings.oidc_client_secret
    if not settings.oidc_client_secret_ref:
        return None
    reference = parse_secret_reference(settings.oidc_client_secret_ref)
    resolver = secret_resolver or EnvironmentSecretResolver()
    try:
        value = resolver.resolve(reference)
    except KeyError as exc:
        raise ValueError(f"OIDC client secret reference could not be resolved: {exc}") from exc
    if not value:
        raise ValueError("OIDC client secret reference resolved to an empty value.")
    return value


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
    secret_resolver: SecretResolver | None = None,
    clock: Callable[[], float] | None = None,
) -> "OidcProvider | None":
    if settings.resolved_auth_mode != "oidc":
        return None
    client_secret = resolve_oidc_client_secret(settings, secret_resolver)
    missing = [
        variable
        for variable, value in (
            ("HOMELAB_ANALYTICS_OIDC_ISSUER_URL", settings.oidc_issuer_url),
            ("HOMELAB_ANALYTICS_OIDC_CLIENT_ID", settings.oidc_client_id),
            ("HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET (or _CLIENT_SECRET_REF)", client_secret),
            ("HOMELAB_ANALYTICS_OIDC_REDIRECT_URI", settings.oidc_redirect_uri),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"OIDC auth requires settings: {', '.join(missing)}")
    return OidcProvider(
        settings,
        http_client=http_client,
        client_secret=client_secret,
        clock=clock,
    )


class OidcProvider:
    def __init__(
        self,
        settings: AppSettings,
        *,
        http_client: httpx.Client | None = None,
        client_secret: str | None = None,
        clock: Callable[[], float] | None = None,
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
        resolved_secret = client_secret or settings.oidc_client_secret
        if not resolved_secret:
            raise ValueError("OIDC auth requires a client secret.")
        self.client_secret = str(resolved_secret)
        self.redirect_uri = str(settings.oidc_redirect_uri)
        self.discovery_url = settings.oidc_discovery_url or (
            f"{self.issuer_url.rstrip('/')}/.well-known/openid-configuration"
        )
        self.post_logout_redirect_uri = settings.oidc_post_logout_redirect_uri or None
        self.cache_seconds = float(settings.oidc_jwks_cache_seconds)
        self.clock_skew_seconds = int(settings.oidc_clock_skew_seconds)
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
        self._clock = clock or time.monotonic
        self._discovery: dict[str, Any] | None = None
        self._discovery_fetched_at = 0.0
        self._jwks: dict[str, Any] | None = None
        self._jwks_fetched_at = 0.0

    def build_login_redirect(self, return_to: str | None = None) -> OidcLoginRedirect:
        discovery = self._load_discovery()
        challenge_methods = discovery.get("code_challenge_methods_supported")
        if isinstance(challenge_methods, list) and "S256" not in challenge_methods:
            raise OidcAuthenticationError("OIDC provider does not support PKCE S256.")
        login_state = OidcLoginState(
            state=secrets.token_urlsafe(24),
            nonce=secrets.token_urlsafe(24),
            return_to=normalize_return_to(return_to),
            code_verifier=secrets.token_urlsafe(64),
        )
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": " ".join(self.scopes),
                "state": login_state.state,
                "nonce": login_state.nonce,
                "code_challenge": pkce_code_challenge(login_state.code_verifier),
                "code_challenge_method": "S256",
            }
        )
        authorization_endpoint = discovery.get("authorization_endpoint")
        if not isinstance(authorization_endpoint, str) or not authorization_endpoint:
            raise OidcAuthenticationError(
                "OIDC discovery response is missing authorization_endpoint."
            )
        separator = "&" if "?" in authorization_endpoint else "?"
        return OidcLoginRedirect(
            authorization_url=f"{authorization_endpoint}{separator}{query}",
            state_cookie_value=_encode_signed_payload(
                self._secret,
                {
                    "state": login_state.state,
                    "nonce": login_state.nonce,
                    "return_to": login_state.return_to,
                    "code_verifier": login_state.code_verifier,
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
        token_response = self._exchange_code(code, code_verifier=login_state.code_verifier)
        id_token = token_response.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise OidcAuthenticationError("OIDC token response did not include an id_token.")
        claims = self._decode_token(
            id_token,
            audiences=(self.client_id,),
            nonce=login_state.nonce,
            require_authorized_party=True,
        )
        return self.principal_from_claims(claims), login_state.return_to

    def build_end_session_url(self) -> str | None:
        """RP-initiated logout URL at the IdP's ``end_session_endpoint``.

        Returns ``None`` (the caller falls back to local logout only) when the
        IdP does not advertise the endpoint or discovery cannot be loaded:
        logging out of the app must never fail because the IdP is down. The
        app keeps no ID token, so the request identifies the client with
        ``client_id`` (OpenID RP-Initiated Logout 1.0 §2) rather than
        ``id_token_hint``; ``post_logout_redirect_uri`` is only sent when
        configured, because the IdP must have it registered.
        """
        try:
            discovery = self._load_discovery()
        except (OidcAuthenticationError, httpx.HTTPError, ValueError):
            return None
        endpoint = discovery.get("end_session_endpoint")
        if not isinstance(endpoint, str) or not endpoint.startswith(("https://", "http://")):
            return None
        params = {"client_id": self.client_id}
        if self.post_logout_redirect_uri:
            params["post_logout_redirect_uri"] = self.post_logout_redirect_uri
        separator = "&" if "?" in endpoint else "?"
        return f"{endpoint}{separator}{urlencode(params)}"

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
            required_fields={"state", "nonce", "return_to", "code_verifier", "exp"},
        )
        if payload is None:
            raise OidcAuthenticationError("OIDC login state is invalid or expired.")
        state_value = payload.get("state")
        nonce_value = payload.get("nonce")
        return_to_value = payload.get("return_to")
        verifier_value = payload.get("code_verifier")
        if (
            not isinstance(state_value, str)
            or not isinstance(nonce_value, str)
            or not isinstance(return_to_value, str)
            or not isinstance(verifier_value, str)
            or not secrets.compare_digest(state_value, state)
        ):
            raise OidcAuthenticationError("OIDC login state is invalid or expired.")
        return OidcLoginState(
            state=state_value,
            nonce=nonce_value,
            return_to=normalize_return_to(return_to_value),
            code_verifier=verifier_value,
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

    def _cache_fresh(self, fetched_at: float) -> bool:
        return self._clock() - fetched_at < self.cache_seconds

    def _load_discovery(self) -> dict[str, Any]:
        if self._discovery is not None and self._cache_fresh(self._discovery_fetched_at):
            return self._discovery
        response = self._http.get(self.discovery_url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise OidcAuthenticationError("OIDC discovery response was not a JSON object.")
        issuer = payload.get("issuer")
        if not isinstance(issuer, str) or issuer.rstrip("/") != self.issuer_url.rstrip("/"):
            raise OidcAuthenticationError("OIDC discovery issuer does not match configured issuer.")
        self._discovery = payload
        self._discovery_fetched_at = self._clock()
        return payload

    def _load_jwks(self, *, force: bool = False) -> dict[str, Any]:
        if (
            not force
            and self._jwks is not None
            and self._cache_fresh(self._jwks_fetched_at)
        ):
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
        self._jwks_fetched_at = self._clock()
        return payload

    def _signing_key(self, header: dict[str, Any]) -> Any:
        try:
            return _resolve_jwt_key(header, self._load_jwks())
        except OidcAuthenticationError:
            # An unknown kid usually means the IdP rotated its keys; refetch
            # once, but not more often than JWKS_UNKNOWN_KID_REFRESH_SECONDS.
            if self._clock() - self._jwks_fetched_at < JWKS_UNKNOWN_KID_REFRESH_SECONDS:
                raise
            return _resolve_jwt_key(header, self._load_jwks(force=True))

    def _allowed_algorithms(self, discovery: dict[str, Any]) -> list[str]:
        advertised = discovery.get("id_token_signing_alg_values_supported")
        if not isinstance(advertised, list) or not advertised:
            return ["RS256"]
        allowed = [str(value) for value in advertised if value in ASYMMETRIC_SIGNING_ALGORITHMS]
        if not allowed:
            raise OidcAuthenticationError(
                "OIDC provider advertises no asymmetric ID token signing algorithm; "
                "configure an RSA or EC signing key on the provider."
            )
        return allowed

    def _exchange_code(self, code: str, *, code_verifier: str) -> dict[str, Any]:
        discovery = self._load_discovery()
        token_endpoint = discovery.get("token_endpoint")
        if not isinstance(token_endpoint, str) or not token_endpoint:
            raise OidcAuthenticationError("OIDC discovery response is missing token_endpoint.")
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": code_verifier,
        }
        request_options: dict[str, Any] = {"headers": {"accept": "application/json"}}
        auth_methods = discovery.get("token_endpoint_auth_methods_supported")
        if (
            isinstance(auth_methods, list)
            and "client_secret_post" not in auth_methods
            and "client_secret_basic" in auth_methods
        ):
            request_options["auth"] = httpx.BasicAuth(self.client_id, self.client_secret)
        else:
            form["client_secret"] = self.client_secret
        response = self._http.post(token_endpoint, data=form, **request_options)
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
        require_authorized_party: bool = False,
    ) -> dict[str, Any]:
        discovery = self._load_discovery()
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise OidcAuthenticationError("OIDC token is malformed.") from exc
        allowed_algorithms = self._allowed_algorithms(discovery)
        if header.get("alg") not in allowed_algorithms:
            raise OidcAuthenticationError("OIDC token signing algorithm is not allowed.")
        key = self._signing_key(header)
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=allowed_algorithms,
                audience=audiences,
                # The advertised issuer, verbatim: Authentik's ends in "/".
                issuer=str(discovery["issuer"]),
                leeway=self.clock_skew_seconds,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise OidcAuthenticationError("OIDC token validation failed.") from exc
        if not isinstance(claims, dict):
            raise OidcAuthenticationError("OIDC decoded claims were not a JSON object.")
        if nonce is not None and not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise OidcAuthenticationError("OIDC token nonce did not match the login state.")
        if require_authorized_party:
            audience = claims.get("aud")
            if isinstance(audience, list) and len(audience) > 1:
                if claims.get("azp") != self.client_id:
                    raise OidcAuthenticationError(
                        "OIDC token has several audiences but azp is not this client."
                    )
            elif "azp" in claims and claims.get("azp") != self.client_id:
                raise OidcAuthenticationError("OIDC token azp is not this client.")
        return claims
