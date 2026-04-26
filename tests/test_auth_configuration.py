import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest

from apps.api.auth_runtime import AuthContext, build_auth_context
from packages.platform.auth.configuration import validate_auth_configuration
from packages.shared.auth_modes import is_cookie_auth_mode
from packages.shared.metrics import metrics_registry
from packages.shared.settings import AppSettings
from packages.storage.ingestion_config import IngestionConfigRepository


def test_validate_auth_configuration_warns_on_legacy_auth_mode_fallback() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        settings = AppSettings.from_env(
            {
                "HOMELAB_ANALYTICS_AUTH_MODE": "local",
                "HOMELAB_ANALYTICS_SESSION_SECRET": "session-secret",
            }
        )
        validate_auth_configuration(settings)

    warning_messages = [
        str(warning.message)
        for warning in caught
        if warning.category is DeprecationWarning
    ]
    assert any(
        "HOMELAB_ANALYTICS_AUTH_MODE is a legacy compatibility input"
        in message
        for message in warning_messages
    )
    assert any(
        "warning window=v0.1.x" in message for message in warning_messages
    )
    assert any(
        "error window=v0.2.x" in message for message in warning_messages
    )
    assert any(
        "removal target=v0.3.0" in message for message in warning_messages
    )


def test_validate_auth_configuration_records_legacy_fallback_metric() -> None:
    metrics_registry.clear()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            settings = AppSettings.from_env(
                {
                    "HOMELAB_ANALYTICS_AUTH_MODE": "local",
                    "HOMELAB_ANALYTICS_SESSION_SECRET": "session-secret",
                }
            )
            validate_auth_configuration(settings)

        metrics_text = metrics_registry.render_prometheus_text()
        assert "auth_legacy_mode_fallback_startups_total 1" in metrics_text
    finally:
        metrics_registry.clear()


def test_validate_auth_configuration_uses_identity_mode_without_legacy_warning() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        settings = AppSettings.from_env(
            {
                "HOMELAB_ANALYTICS_AUTH_MODE": "local",
                "HOMELAB_ANALYTICS_IDENTITY_MODE": "local_single_user",
                "HOMELAB_ANALYTICS_SESSION_SECRET": "session-secret",
                "HOMELAB_ANALYTICS_BREAK_GLASS_ENABLED": "true",
            }
        )
        validate_auth_configuration(settings)

    assert all(
        "HOMELAB_ANALYTICS_AUTH_MODE is a legacy compatibility input"
        not in str(warning.message)
        for warning in caught
        if warning.category is DeprecationWarning
    )


def test_validate_auth_configuration_rejects_legacy_auth_mode_fallback_when_strict() -> None:
    settings = AppSettings.from_env(
        {
            "HOMELAB_ANALYTICS_AUTH_MODE": "local",
            "HOMELAB_ANALYTICS_AUTH_MODE_LEGACY_STRICT": "true",
            "HOMELAB_ANALYTICS_SESSION_SECRET": "session-secret",
        }
    )

    try:
        validate_auth_configuration(settings)
    except ValueError as exc:
        message = str(exc)
        assert "HOMELAB_ANALYTICS_AUTH_MODE_LEGACY_STRICT=true" in message
        assert "warning window=v0.1.x" in message
        assert "error window=v0.2.x" in message
        assert "removal target=v0.3.0" in message
    else:
        raise AssertionError("Expected strict legacy auth-mode guard to raise ValueError.")


def test_validate_auth_configuration_rejects_break_glass_outside_local_single_user_mode() -> None:
    settings = AppSettings.from_env(
        {
            "HOMELAB_ANALYTICS_IDENTITY_MODE": "local",
            "HOMELAB_ANALYTICS_SESSION_SECRET": "session-secret",
            "HOMELAB_ANALYTICS_BREAK_GLASS_ENABLED": "true",
        }
    )

    try:
        validate_auth_configuration(settings)
    except ValueError as exc:
        message = str(exc)
        assert "HOMELAB_ANALYTICS_IDENTITY_MODE=local_single_user" in message
        assert "HOMELAB_ANALYTICS_AUTH_MODE" not in message
    else:
        raise AssertionError(
            "Expected break-glass validation outside local_single_user to raise ValueError."
        )


def test_validate_auth_configuration_requires_machine_jwt_issuer_and_audience() -> None:
    settings = AppSettings.from_env(
        {
            "HOMELAB_ANALYTICS_IDENTITY_MODE": "oidc",
            "HOMELAB_ANALYTICS_SESSION_SECRET": "session-secret",
            "HOMELAB_ANALYTICS_OIDC_ISSUER_URL": "https://issuer.example.test/oidc",
            "HOMELAB_ANALYTICS_OIDC_CLIENT_ID": "homelab-analytics",
            "HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET": "client-secret",
            "HOMELAB_ANALYTICS_OIDC_REDIRECT_URI": "https://analytics.example.test/auth/callback",
            "HOMELAB_ANALYTICS_MACHINE_JWT_ENABLED": "true",
        }
    )

    try:
        validate_auth_configuration(settings)
    except ValueError as exc:
        assert "HOMELAB_ANALYTICS_MACHINE_JWT_ISSUER_URL" in str(exc)
        assert "HOMELAB_ANALYTICS_MACHINE_JWT_AUDIENCE" in str(exc)
    else:
        raise AssertionError("Expected missing machine JWT settings to raise ValueError.")


# ---------------------------------------------------------------------------
# build_auth_context() contract tests
# ---------------------------------------------------------------------------

def _disabled_context(auth_store_candidate=None):
    with TemporaryDirectory() as tmp:
        store = auth_store_candidate or IngestionConfigRepository(Path(tmp) / "config.db")
        return build_auth_context(
            resolved_auth_mode="disabled",
            resolved_identity_mode="disabled",
            session_manager=None,
            oidc_provider=None,
            proxy_provider=None,
            auth_store_candidate=store,
        )


def test_build_auth_context_returns_auth_context_for_disabled_mode() -> None:
    ctx = _disabled_context()
    assert isinstance(ctx, AuthContext)
    assert ctx.break_glass_controller is None


def test_build_auth_context_raises_for_cookie_auth_without_session_manager() -> None:
    with TemporaryDirectory() as tmp:
        store = IngestionConfigRepository(Path(tmp) / "config.db")
        with pytest.raises(ValueError, match="session manager"):
            build_auth_context(
                resolved_auth_mode="local",
                resolved_identity_mode="local",
                session_manager=None,
                oidc_provider=None,
                proxy_provider=None,
                auth_store_candidate=store,
            )


def test_build_auth_context_raises_for_oidc_without_provider() -> None:
    with TemporaryDirectory() as tmp:
        store = IngestionConfigRepository(Path(tmp) / "config.db")
        with pytest.raises(ValueError, match="configured OIDC provider"):
            build_auth_context(
                resolved_auth_mode="oidc",
                resolved_identity_mode="oidc",
                session_manager=Mock(),
                oidc_provider=None,
                proxy_provider=None,
                auth_store_candidate=store,
            )


def test_build_auth_context_raises_for_proxy_without_provider() -> None:
    with TemporaryDirectory() as tmp:
        store = IngestionConfigRepository(Path(tmp) / "config.db")
        with pytest.raises(ValueError, match="configured proxy provider"):
            build_auth_context(
                resolved_auth_mode="proxy",
                resolved_identity_mode="proxy",
                session_manager=None,
                oidc_provider=None,
                proxy_provider=None,
                auth_store_candidate=store,
            )


def test_build_auth_context_raises_when_cookie_auth_store_not_auth_capable() -> None:
    non_auth_store = object()
    with pytest.raises(ValueError, match="auth-capable control-plane store"):
        build_auth_context(
            resolved_auth_mode="local",
            resolved_identity_mode="local",
            session_manager=Mock(),
            oidc_provider=None,
            proxy_provider=None,
            auth_store_candidate=non_auth_store,
        )


def test_build_auth_context_omits_break_glass_without_app_settings() -> None:
    with TemporaryDirectory() as tmp:
        store = IngestionConfigRepository(Path(tmp) / "config.db")
        ctx = build_auth_context(
            resolved_auth_mode="disabled",
            resolved_identity_mode="local_single_user",
            session_manager=None,
            oidc_provider=None,
            proxy_provider=None,
            auth_store_candidate=store,
            app_settings=None,
        )
    assert ctx.break_glass_controller is None
