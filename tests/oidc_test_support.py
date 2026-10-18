from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


@dataclass
class MockOidcIssuer:
    issuer_url: str = "https://issuer.example.test/oidc"
    client_id: str = "homelab-analytics"
    client_secret: str = "oidc-client-secret"
    api_audience: str = "homelab-analytics-api"
    signing_kid: str = "test-kid"
    # Advertised discovery metadata; Authentik-shaped tests override these.
    signing_algs: tuple[str, ...] = ("RS256",)
    code_challenge_methods: tuple[str, ...] | None = ("S256",)
    token_auth_methods: tuple[str, ...] | None = None
    # When true the token endpoint refuses codes registered without PKCE.
    require_pkce: bool = False
    _codes: dict[str, dict[str, Any]] = field(default_factory=dict)
    token_requests: list[dict[str, Any]] = field(default_factory=list)
    jwks_fetches: int = 0
    discovery_fetches: int = 0

    def __post_init__(self) -> None:
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._public_jwk = self._jwk_for(self._private_key, self.signing_kid)
        self._published_jwks: list[dict[str, Any]] = [self._public_jwk]

    @staticmethod
    def _jwk_for(private_key: Any, kid: str) -> dict[str, Any]:
        public_numbers = private_key.public_key().public_numbers()
        return {
            "kty": "RSA",
            "kid": kid,
            "use": "sig",
            "alg": "RS256",
            "n": _b64url_uint(public_numbers.n),
            "e": _b64url_uint(public_numbers.e),
        }

    def rotate_signing_key(self, new_kid: str, *, keep_previous: bool = False) -> None:
        """Sign with a new key and publish it (optionally alongside the old one)."""
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.signing_kid = new_kid
        self._public_jwk = self._jwk_for(self._private_key, new_kid)
        self._published_jwks = (
            [*self._published_jwks, self._public_jwk] if keep_previous else [self._public_jwk]
        )

    @property
    def metadata_url(self) -> str:
        return f"{self.issuer_url.rstrip('/')}/.well-known/openid-configuration"

    @property
    def authorization_endpoint(self) -> str:
        return f"{self.issuer_url.rstrip('/')}/authorize"

    @property
    def token_endpoint(self) -> str:
        return f"{self.issuer_url.rstrip('/')}/token"

    @property
    def jwks_uri(self) -> str:
        return f"{self.issuer_url.rstrip('/')}/jwks"

    def issue_token(
        self,
        *,
        subject: str,
        username: str,
        audience: str,
        groups: tuple[str, ...] = (),
        nonce: str | None = None,
        extra_claims: dict[str, Any] | None = None,
        expires_in: int = 3600,
    ) -> str:
        now = int(datetime.now(UTC).timestamp())
        claims: dict[str, Any] = {
            "iss": self.issuer_url,
            "sub": subject,
            "aud": audience,
            "preferred_username": username,
            "groups": list(groups),
            "iat": now,
            "exp": now + expires_in,
        }
        if nonce is not None:
            claims["nonce"] = nonce
        if extra_claims:
            claims.update(extra_claims)
        return jwt.encode(
            claims,
            self._private_key,
            algorithm="RS256",
            headers={"kid": self.signing_kid},
        )

    def register_code(
        self,
        code: str,
        *,
        subject: str,
        username: str,
        nonce: str,
        groups: tuple[str, ...] = (),
        extra_claims: dict[str, Any] | None = None,
        code_challenge: str | None = None,
    ) -> None:
        self._codes[code] = {
            "subject": subject,
            "username": username,
            "nonce": nonce,
            "groups": groups,
            "extra_claims": extra_claims or {},
            "code_challenge": code_challenge,
        }

    def http_client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self._handle_request))

    def _handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == self.metadata_url:
            self.discovery_fetches += 1
            metadata: dict[str, Any] = {
                "issuer": self.issuer_url,
                "authorization_endpoint": self.authorization_endpoint,
                "token_endpoint": self.token_endpoint,
                "jwks_uri": self.jwks_uri,
                "id_token_signing_alg_values_supported": list(self.signing_algs),
            }
            if self.code_challenge_methods is not None:
                metadata["code_challenge_methods_supported"] = list(self.code_challenge_methods)
            if self.token_auth_methods is not None:
                metadata["token_endpoint_auth_methods_supported"] = list(self.token_auth_methods)
            return httpx.Response(200, json=metadata)
        if url == self.jwks_uri:
            self.jwks_fetches += 1
            return httpx.Response(200, json={"keys": list(self._published_jwks)})
        if url == self.token_endpoint:
            form = dict(parse_qsl(request.content.decode("utf-8")))
            self.token_requests.append(
                {"form": form, "authorization": request.headers.get("authorization")}
            )
            client_id, client_secret = form.get("client_id"), form.get("client_secret")
            basic = request.headers.get("authorization", "")
            if basic.startswith("Basic "):
                decoded = base64.b64decode(basic.removeprefix("Basic ")).decode("utf-8")
                client_id, _, client_secret = decoded.partition(":")
            if client_id != self.client_id or client_secret != self.client_secret:
                return httpx.Response(401, json={"error": "invalid_client"})
            code = form.get("code", "")
            registered = self._codes.get(code)
            if registered is None:
                return httpx.Response(400, json={"error": "invalid_grant"})
            challenge = registered.get("code_challenge")
            if challenge is None and self.require_pkce:
                return httpx.Response(400, json={"error": "invalid_request"})
            if challenge is not None:
                verifier = form.get("code_verifier", "")
                expected = (
                    base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
                    .decode("ascii")
                    .rstrip("=")
                )
                if expected != challenge:
                    return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(
                200,
                json={
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "access_token": self.issue_token(
                        subject=str(registered["subject"]),
                        username=str(registered["username"]),
                        audience=self.api_audience,
                        groups=tuple(registered["groups"]),
                        extra_claims=dict(registered["extra_claims"]),
                    ),
                    "id_token": self.issue_token(
                        subject=str(registered["subject"]),
                        username=str(registered["username"]),
                        audience=self.client_id,
                        groups=tuple(registered["groups"]),
                        nonce=str(registered["nonce"]),
                        extra_claims=dict(registered["extra_claims"]),
                    ),
                },
            )
        return httpx.Response(404, json={"detail": f"Unhandled mock OIDC URL: {url}"})
