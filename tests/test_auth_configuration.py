import warnings

from packages.platform.auth.configuration import validate_auth_configuration
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

    assert any(
        "HOMELAB_ANALYTICS_AUTH_MODE is a legacy compatibility input"
        in str(warning.message)
        for warning in caught
        if warning.category is DeprecationWarning
    )


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
