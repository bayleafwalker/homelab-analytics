from __future__ import annotations

import base64
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
    _codes: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_numbers = self._private_key.public_key().public_numbers()
        self._public_jwk = {
            "kty": "RSA",
            "kid": self.signing_kid,
            "use": "sig",
            "alg": "RS256",
            "n": _b64url_uint(public_numbers.n),
            "e": _b64url_uint(public_numbers.e),
        }

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
        expires_in: int = 3600,
    ) -> str:
        now = int(datetime.now(UTC).timestamp())
        claims: dict[str, Any] = {
            "iss": self.issuer_url.rstrip("/"),
            "sub": subject,
            "aud": audience,
            "preferred_username": username,
            "groups": list(groups),
            "iat": now,
            "exp": now + expires_in,
        }
        if nonce is not None:
            claims["nonce"] = nonce
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
    ) -> None:
        self._codes[code] = {
            "subject": subject,
            "username": username,
            "nonce": nonce,
            "groups": groups,
        }

    def http_client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self._handle_request))

    def _handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == self.metadata_url:
            return httpx.Response(
                200,
                json={
                    "issuer": self.issuer_url.rstrip("/"),
                    "authorization_endpoint": self.authorization_endpoint,
                    "token_endpoint": self.token_endpoint,
                    "jwks_uri": self.jwks_uri,
                    "id_token_signing_alg_values_supported": ["RS256"],
                },
            )
        if url == self.jwks_uri:
            return httpx.Response(200, json={"keys": [self._public_jwk]})
        if url == self.token_endpoint:
            form = dict(parse_qsl(request.content.decode("utf-8")))
            if form.get("client_id") != self.client_id or form.get("client_secret") != self.client_secret:
                return httpx.Response(401, json={"error": "invalid_client"})
            code = form.get("code", "")
            registered = self._codes.get(code)
            if registered is None:
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
                    ),
                    "id_token": self.issue_token(
                        subject=str(registered["subject"]),
                        username=str(registered["username"]),
                        audience=self.client_id,
                        groups=tuple(registered["groups"]),
                        nonce=str(registered["nonce"]),
                    ),
                },
            )
        return httpx.Response(404, json={"detail": f"Unhandled mock OIDC URL: {url}"})
