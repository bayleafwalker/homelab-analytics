import warnings

from packages.platform.auth.configuration import validate_auth_configuration
from packages.shared.metrics import metrics_registry
from packages.shared.settings import AppSettings


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
