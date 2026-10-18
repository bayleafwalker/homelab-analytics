"""OIDC mode against an Authentik-shaped fake IdP (keys generated in-test).

- PKCE S256 on the authorization-code flow; the IdP rejects a wrong verifier
- issuer with a trailing slash (Authentik's shape) validates verbatim
- only asymmetric ID-token algorithms are accepted (HS256 / none refused)
- discovery and JWKS are cached with a TTL; an unknown kid triggers one early
  refetch so key rotation does not lock users out
- the client secret can come from the SecretResolver instead of a literal
- group -> role mapping drives proposal resolution, and the resolver and the
  decision-ledger actor are the authenticated OIDC principal

No network: every IdP call goes through ``httpx.MockTransport``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.application.use_cases.decision_ledger import actor_from_principal
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.platform.auth.configuration import validate_auth_configuration
from packages.platform.auth.oidc_provider import (
    OidcAuthenticationError,
    OidcProvider,
    build_oidc_provider,
    pkce_code_challenge,
)
from packages.shared.auth import build_session_manager
from packages.shared.secrets import SecretReference
from packages.shared.settings import AppSettings
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository
from tests.oidc_test_support import MockOidcIssuer

AUTHENTIK_ISSUER = "https://auth.example.test/application/o/homelab-analytics/"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _issuer(**overrides: object) -> MockOidcIssuer:
    return MockOidcIssuer(issuer_url=AUTHENTIK_ISSUER, require_pkce=True, **overrides)  # type: ignore[arg-type]


def _settings(temp_dir: str, issuer: MockOidcIssuer, **env_overrides: str) -> AppSettings:
    env = {
        "HOMELAB_ANALYTICS_DATA_DIR": temp_dir,
        "HOMELAB_ANALYTICS_IDENTITY_MODE": "oidc",
        "HOMELAB_ANALYTICS_SESSION_SECRET": "test-session-secret",
        "HOMELAB_ANALYTICS_OIDC_ISSUER_URL": issuer.issuer_url,
        "HOMELAB_ANALYTICS_OIDC_CLIENT_ID": issuer.client_id,
        "HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET": issuer.client_secret,
        "HOMELAB_ANALYTICS_OIDC_REDIRECT_URI": "http://testserver/auth/callback",
        "HOMELAB_ANALYTICS_OIDC_API_AUDIENCE": issuer.api_audience,
        "HOMELAB_ANALYTICS_OIDC_READER_GROUPS": "hla-readers",
        "HOMELAB_ANALYTICS_OIDC_OPERATOR_GROUPS": "hla-operators",
        "HOMELAB_ANALYTICS_OIDC_ADMIN_GROUPS": "hla-admins",
    }
    env.update(env_overrides)
    return AppSettings.from_env(env)


def _provider(
    temp_dir: str, issuer: MockOidcIssuer, clock: FakeClock | None = None, **env: str
) -> OidcProvider:
    provider = build_oidc_provider(
        _settings(temp_dir, issuer, **env), http_client=issuer.http_client(), clock=clock
    )
    assert provider is not None
    return provider


def _client(temp_dir: str, issuer: MockOidcIssuer) -> TestClient:
    settings = _settings(temp_dir, issuer)
    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
    return TestClient(
        create_app(
            service,
            config_repository=repository,
            auth_store=repository,
            identity_mode="oidc",
            session_manager=build_session_manager(settings),
            oidc_provider=build_oidc_provider(settings, http_client=issuer.http_client()),
        )
    )


def _login(
    client: TestClient,
    issuer: MockOidcIssuer,
    *,
    code: str,
    username: str,
    groups: tuple[str, ...],
    tamper_challenge: bool = False,
) -> str:
    start = client.get("/auth/login?return_to=/control/agents", follow_redirects=False)
    assert start.status_code == 303
    query = parse_qs(urlparse(start.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    challenge = query["code_challenge"][0]
    issuer.register_code(
        code,
        subject=f"sub-{username}",
        username=username,
        nonce=query["nonce"][0],
        groups=groups,
        extra_claims={"azp": issuer.client_id},
        code_challenge=(pkce_code_challenge("not-the-verifier") if tamper_challenge else challenge),
    )
    callback = client.get(
        f"/auth/callback?code={code}&state={query['state'][0]}", follow_redirects=False
    )
    assert callback.status_code == 303
    return str(callback.headers["location"])


def _csrf(client: TestClient) -> dict[str, str]:
    return {"x-csrf-token": client.cookies.get("homelab_analytics_csrf") or ""}


def test_pkce_login_with_authentik_shaped_issuer() -> None:
    issuer = _issuer()
    with TemporaryDirectory() as tmp:
        client = _client(tmp, issuer)
        location = _login(
            client, issuer, code="code-1", username="olivia", groups=("hla-operators",)
        )
        assert location == "/control/agents"
        token_form = issuer.token_requests[-1]["form"]
        assert len(token_form["code_verifier"]) >= 43
        me = client.get("/auth/me").json()
        assert me["user"]["username"] == "olivia"
        assert me["user"]["role"] == "operator"
        assert me["principal"]["auth_provider"] == "oidc"


def test_wrong_pkce_verifier_fails_the_login() -> None:
    issuer = _issuer()
    with TemporaryDirectory() as tmp:
        client = _client(tmp, issuer)
        location = _login(
            client,
            issuer,
            code="code-2",
            username="mallory",
            groups=("hla-admins",),
            tamper_challenge=True,
        )
        assert location == "/login?error=oidc-failed"
        assert client.get("/auth/me").status_code == 401


def test_unmapped_groups_are_refused() -> None:
    issuer = _issuer()
    with TemporaryDirectory() as tmp:
        client = _client(tmp, issuer)
        location = _login(client, issuer, code="code-3", username="guest", groups=("visitors",))
        assert location == "/login?error=oidc-unmapped"


def test_idp_without_pkce_s256_is_refused_at_login_start() -> None:
    issuer = _issuer(code_challenge_methods=("plain",))
    with TemporaryDirectory() as tmp:
        client = _client(tmp, issuer)
        assert client.get("/auth/login", follow_redirects=False).status_code == 502


def test_oidc_resolver_and_decision_actor_are_the_authenticated_principal() -> None:
    issuer = _issuer()
    with TemporaryDirectory() as tmp:
        operator = _client(tmp, issuer)
        _login(operator, issuer, code="code-op", username="olivia", groups=("hla-operators",))
        drafted = operator.post(
            "/api/actions/proposals",
            json={"policy_id": "p", "policy_name": "P", "verdict": "notify"},
            headers=_csrf(operator),
        )
        assert drafted.status_code == 200, drafted.text
        assert drafted.json()["created_by"] == "olivia"
        action_id = drafted.json()["action_id"]

        reader = TestClient(operator.app)
        _login(reader, issuer, code="code-rd", username="rita", groups=("hla-readers",))
        denied = reader.post(
            f"/api/actions/proposals/{action_id}/approve", headers=_csrf(reader)
        )
        assert denied.status_code == 403

        approved = operator.post(
            f"/api/actions/proposals/{action_id}/approve",
            json={"reason": "evidence is fresh"},
            headers=_csrf(operator),
        )
        assert approved.status_code == 200, approved.text
        payload = approved.json()
        assert payload["resolved_by"] == "olivia"
        assert payload["history"][0]["actor_auth_provider"] == "oidc"
        assert payload["history"][-1]["actor"] == "olivia"
        assert payload["history"][-1]["actor_auth_provider"] == "oidc"

        provider = _provider(tmp, issuer)
        principal = provider.principal_from_claims(
            {"sub": "sub-olivia", "preferred_username": "olivia", "groups": ["hla-operators"]}
        )
        actor = actor_from_principal(principal)
        assert (actor.actor, actor.actor_role, actor.actor_auth_provider, actor.actor_authenticated) == (
            "olivia",
            "operator",
            "oidc",
            True,
        )


def _bearer(issuer: MockOidcIssuer, **extra: object) -> str:
    return issuer.issue_token(
        subject="sub-api",
        username="api-user",
        audience=issuer.api_audience,
        groups=("hla-readers",),
        extra_claims=dict(extra) or None,
    )


def test_jwks_and_discovery_are_cached_with_a_ttl() -> None:
    issuer = _issuer()
    clock = FakeClock()
    with TemporaryDirectory() as tmp:
        provider = _provider(tmp, issuer, clock, HOMELAB_ANALYTICS_OIDC_JWKS_CACHE_SECONDS="300")
        for _ in range(3):
            assert provider.authenticate_bearer_token(_bearer(issuer)).username == "api-user"
        assert (issuer.discovery_fetches, issuer.jwks_fetches) == (1, 1)
        clock.now += 301
        provider.authenticate_bearer_token(_bearer(issuer))
        assert (issuer.discovery_fetches, issuer.jwks_fetches) == (2, 2)


def test_unknown_kid_triggers_one_rate_limited_jwks_refetch() -> None:
    issuer = _issuer()
    clock = FakeClock()
    with TemporaryDirectory() as tmp:
        provider = _provider(tmp, issuer, clock)
        provider.authenticate_bearer_token(_bearer(issuer))
        assert issuer.jwks_fetches == 1

        issuer.rotate_signing_key("rotated-kid")
        # Within the refetch spacing the cached JWKS is authoritative.
        clock.now += 1
        with pytest.raises(OidcAuthenticationError):
            provider.authenticate_bearer_token(_bearer(issuer))
        assert issuer.jwks_fetches == 1

        clock.now += 15
        assert provider.authenticate_bearer_token(_bearer(issuer)).username == "api-user"
        assert issuer.jwks_fetches == 2


def test_symmetric_and_unsigned_tokens_are_refused() -> None:
    issuer = _issuer(signing_algs=("RS256", "HS256"))
    with TemporaryDirectory() as tmp:
        provider = _provider(tmp, issuer)
        now = int(datetime.now(UTC).timestamp())
        claims = {
            "iss": issuer.issuer_url,
            "sub": "attacker",
            "aud": issuer.api_audience,
            "preferred_username": "attacker",
            "groups": ["hla-admins"],
            "iat": now,
            "exp": now + 600,
        }
        # Forged with a client-secret-derived HMAC key, as an alg-confusion attack would.
        hmac_key = issuer.client_secret * 2
        forged = jwt.encode(claims, hmac_key, algorithm="HS256", headers={"kid": "test-kid"})
        with pytest.raises(OidcAuthenticationError, match="algorithm"):
            provider.authenticate_bearer_token(forged)
        unsigned = jwt.encode(claims, None, algorithm="none")  # type: ignore[arg-type]
        with pytest.raises(OidcAuthenticationError, match="algorithm"):
            provider.authenticate_bearer_token(unsigned)

    hmac_only = _issuer(signing_algs=("HS256",))
    with TemporaryDirectory() as tmp:
        provider = _provider(tmp, hmac_only)
        with pytest.raises(OidcAuthenticationError, match="asymmetric"):
            provider.authenticate_bearer_token(_bearer(hmac_only))


def test_issuer_audience_expiry_and_azp_are_enforced() -> None:
    issuer = _issuer()
    with TemporaryDirectory() as tmp:
        provider = _provider(tmp, issuer)
        other_issuer = issuer.issue_token(
            subject="s",
            username="u",
            audience=issuer.api_audience,
            groups=("hla-readers",),
            extra_claims={"iss": AUTHENTIK_ISSUER.rstrip("/")},
        )
        with pytest.raises(OidcAuthenticationError):
            provider.authenticate_bearer_token(other_issuer)
        wrong_audience = issuer.issue_token(
            subject="s", username="u", audience="someone-else", groups=("hla-readers",)
        )
        with pytest.raises(OidcAuthenticationError):
            provider.authenticate_bearer_token(wrong_audience)
        expired = issuer.issue_token(
            subject="s",
            username="u",
            audience=issuer.api_audience,
            groups=("hla-readers",),
            expires_in=-3600,
        )
        with pytest.raises(OidcAuthenticationError):
            provider.authenticate_bearer_token(expired)

        id_token = issuer.issue_token(
            subject="s",
            username="u",
            audience=issuer.client_id,
            groups=("hla-readers",),
            extra_claims={"aud": [issuer.client_id, "other-client"], "azp": "other-client"},
        )
        with pytest.raises(OidcAuthenticationError, match="azp"):
            provider._decode_token(
                id_token, audiences=(issuer.client_id,), require_authorized_party=True
            )


def test_client_secret_basic_is_used_when_post_is_not_offered() -> None:
    issuer = _issuer(token_auth_methods=("client_secret_basic",))
    with TemporaryDirectory() as tmp:
        client = _client(tmp, issuer)
        assert (
            _login(client, issuer, code="code-basic", username="olivia", groups=("hla-operators",))
            == "/control/agents"
        )
        request = issuer.token_requests[-1]
        assert request["authorization"].startswith("Basic ")
        assert "client_secret" not in request["form"]


class _MapResolver:
    def __init__(self, values: dict[tuple[str, str], str]) -> None:
        self.values = values

    def resolve(self, secret_ref: SecretReference) -> str:
        return self.values[(secret_ref.secret_name, secret_ref.secret_key)]


def test_client_secret_from_secret_reference() -> None:
    issuer = _issuer()
    with TemporaryDirectory() as tmp:
        settings = _settings(
            tmp,
            issuer,
            HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET="",
            HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET_REF="authentik-hla/client_secret",
        )
        validate_auth_configuration(settings)
        provider = build_oidc_provider(
            settings,
            http_client=issuer.http_client(),
            secret_resolver=_MapResolver({("authentik-hla", "client_secret"): issuer.client_secret}),
        )
        assert provider is not None and provider.client_secret == issuer.client_secret

        # The default resolver reads HOMELAB_ANALYTICS_SECRET__<NAME>__<KEY>.
        from packages.shared.secrets import EnvironmentSecretResolver

        env_resolved = build_oidc_provider(
            settings,
            http_client=issuer.http_client(),
            secret_resolver=EnvironmentSecretResolver(
                {"HOMELAB_ANALYTICS_SECRET__AUTHENTIK_HLA__CLIENT_SECRET": "from-env"}
            ),
        )
        assert env_resolved is not None and env_resolved.client_secret == "from-env"

        with pytest.raises(ValueError, match="could not be resolved"):
            build_oidc_provider(settings, secret_resolver=_MapResolver({}))
        bad_ref = _settings(
            tmp,
            issuer,
            HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET="",
            HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET_REF="no-slash",
        )
        with pytest.raises(ValueError, match="secret_name"):
            build_oidc_provider(bad_ref)
        both = _settings(
            tmp,
            issuer,
            HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET_REF="authentik-hla/client_secret",
        )
        with pytest.raises(ValueError, match="not both"):
            validate_auth_configuration(both)


def test_discovery_url_override_and_defaults() -> None:
    issuer = _issuer()
    with TemporaryDirectory() as tmp:
        default = _provider(tmp, issuer)
        assert default.discovery_url == (
            "https://auth.example.test/application/o/homelab-analytics/"
            ".well-known/openid-configuration"
        )
        override = _provider(
            tmp, issuer, HOMELAB_ANALYTICS_OIDC_DISCOVERY_URL="https://idp.internal/discovery"
        )
        assert override.discovery_url == "https://idp.internal/discovery"
    assert AppSettings.from_env({}).oidc_jwks_cache_seconds == 3600
    assert AppSettings.from_env({}).resolved_auth_mode == "disabled"
