"""Auth configuration validation and local admin bootstrap."""
from __future__ import annotations

import uuid
import warnings
from ipaddress import ip_network

from packages.platform.auth.contracts import UserRole
from packages.platform.auth.crypto import hash_password
from packages.shared.auth_modes import is_cookie_auth_mode
from packages.shared.metrics import metrics_registry
from packages.shared.settings import AppSettings
from packages.storage.auth_store import AuthStore, LocalUserCreate, LocalUserRecord

LEGACY_AUTH_MODE_WARN_WINDOW = "v0.1.x"
LEGACY_AUTH_MODE_ERROR_WINDOW = "v0.2.x"
LEGACY_AUTH_MODE_REMOVAL_TARGET = "v0.3.0"


def validate_auth_configuration(settings: AppSettings) -> None:
    if settings.uses_legacy_auth_mode_fallback:
        metrics_registry.inc(
            "auth_legacy_mode_fallback_startups_total",
            1,
            help_text=(
                "Total startup validations that relied on legacy "
                "HOMELAB_ANALYTICS_AUTH_MODE fallback instead of explicit "
                "HOMELAB_ANALYTICS_IDENTITY_MODE."
            ),
        )
        if settings.auth_mode_legacy_strict:
            raise ValueError(
                "HOMELAB_ANALYTICS_AUTH_MODE fallback is disabled when "
                "HOMELAB_ANALYTICS_AUTH_MODE_LEGACY_STRICT=true. Configure "
                "HOMELAB_ANALYTICS_IDENTITY_MODE explicitly. "
                f"Migration policy: warning window={LEGACY_AUTH_MODE_WARN_WINDOW}, "
                f"error window={LEGACY_AUTH_MODE_ERROR_WINDOW}, "
                f"removal target={LEGACY_AUTH_MODE_REMOVAL_TARGET}."
            )
        warnings.warn(
            (
                "HOMELAB_ANALYTICS_AUTH_MODE is a legacy compatibility input; "
                "configure HOMELAB_ANALYTICS_IDENTITY_MODE instead. "
                f"Migration policy: warning window={LEGACY_AUTH_MODE_WARN_WINDOW}, "
                f"error window={LEGACY_AUTH_MODE_ERROR_WINDOW}, "
                f"removal target={LEGACY_AUTH_MODE_REMOVAL_TARGET}."
            ),
            DeprecationWarning,
            stacklevel=3,
        )

    if settings.break_glass_ttl_minutes <= 0:
        raise ValueError(
            "Break-glass TTL must be a positive integer number of minutes."
        )
    for cidr in settings.break_glass_allowed_cidrs:
        try:
            ip_network(cidr.strip(), strict=False)
        except ValueError as exc:
            raise ValueError(
                f"Invalid break-glass CIDR entry: {cidr!r}."
            ) from exc
    for cidr in settings.proxy_trusted_cidrs:
        try:
            ip_network(cidr.strip(), strict=False)
        except ValueError as exc:
            raise ValueError(
                f"Invalid proxy trusted CIDR entry: {cidr!r}."
            ) from exc

    auth_mode = settings.resolved_auth_mode
    identity_mode = settings.resolved_identity_mode
    if is_cookie_auth_mode(auth_mode) and not settings.session_secret:
        raise ValueError(
            "Cookie-backed authentication requires HOMELAB_ANALYTICS_SESSION_SECRET to be configured."
        )
    if auth_mode == "proxy":
        if not settings.proxy_username_header:
            raise ValueError(
                "Proxy auth mode requires HOMELAB_ANALYTICS_PROXY_USERNAME_HEADER."
            )
        if not settings.proxy_role_header:
            raise ValueError(
                "Proxy auth mode requires HOMELAB_ANALYTICS_PROXY_ROLE_HEADER."
            )
        if not settings.proxy_trusted_cidrs:
            raise ValueError(
                "Proxy auth mode requires HOMELAB_ANALYTICS_PROXY_TRUSTED_CIDRS."
            )
    if settings.break_glass_enabled and identity_mode != "local_single_user":
        raise ValueError(
            "Break-glass settings require HOMELAB_ANALYTICS_IDENTITY_MODE=local_single_user."
        )
    if identity_mode == "local_single_user" and not settings.break_glass_enabled:
        raise ValueError(
            "local_single_user identity mode requires HOMELAB_ANALYTICS_BREAK_GLASS_ENABLED=true."
        )
    if auth_mode == "oidc":
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
    if settings.machine_jwt_enabled:
        missing_machine_settings = [
            variable
            for variable, value in (
                (
                    "HOMELAB_ANALYTICS_MACHINE_JWT_ISSUER_URL",
                    settings.machine_jwt_issuer_url,
                ),
                (
                    "HOMELAB_ANALYTICS_MACHINE_JWT_AUDIENCE",
                    settings.machine_jwt_audience,
                ),
            )
            if not value
        ]
        if missing_machine_settings:
            raise ValueError(
                "Machine JWT auth requires settings: "
                f"{', '.join(missing_machine_settings)}"
            )
        if settings.resolved_auth_mode == "disabled":
            raise ValueError(
                "Machine JWT auth requires authentication to be enabled. Set "
                "HOMELAB_ANALYTICS_IDENTITY_MODE to local/local_single_user, "
                "oidc, or proxy."
            )
        if not settings.machine_jwt_username_claim.strip():
            raise ValueError(
                "Machine JWT auth requires HOMELAB_ANALYTICS_MACHINE_JWT_USERNAME_CLAIM."
            )
        if settings.machine_jwt_role_claim is not None and not settings.machine_jwt_role_claim.strip():
            raise ValueError(
                "Machine JWT role claim, when set, must be a non-empty string."
            )
        if settings.machine_jwt_scopes_claim is not None and not settings.machine_jwt_scopes_claim.strip():
            raise ValueError(
                "Machine JWT scopes claim, when set, must be a non-empty string."
            )
        try:
            UserRole(settings.machine_jwt_default_role.strip().lower())
        except ValueError as exc:
            raise ValueError(
                "HOMELAB_ANALYTICS_MACHINE_JWT_DEFAULT_ROLE must be one of: "
                "reader, operator, admin."
            ) from exc
    if auth_mode != "local":
        return
    if not settings.enable_bootstrap_local_admin:
        if settings.bootstrap_admin_username or settings.bootstrap_admin_password:
            raise ValueError(
                "Bootstrap local admin requires HOMELAB_ANALYTICS_ENABLE_BOOTSTRAP_LOCAL_ADMIN=true."
            )
        return
    if not settings.bootstrap_admin_username or not settings.bootstrap_admin_password:
        raise ValueError(
            "Bootstrap local admin requires both username and password settings."
        )


def maybe_bootstrap_local_admin(
    auth_store: AuthStore,
    settings: AppSettings,
) -> LocalUserRecord | None:
    if settings.resolved_auth_mode != "local":
        return None
    if not settings.enable_bootstrap_local_admin:
        return None
    username = settings.bootstrap_admin_username
    password = settings.bootstrap_admin_password
    if not username or not password:
        raise ValueError("Bootstrap local admin requires both username and password settings.")
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
