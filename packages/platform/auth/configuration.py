"""Auth configuration validation and local admin bootstrap."""
from __future__ import annotations

import uuid
from ipaddress import ip_network

from packages.platform.auth.crypto import hash_password
from packages.shared.auth_modes import is_cookie_auth_mode
from packages.shared.settings import AppSettings
from packages.storage.auth_store import AuthStore, LocalUserCreate, LocalUserRecord, UserRole


def validate_auth_configuration(settings: AppSettings) -> None:
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

    auth_mode = settings.resolved_auth_mode
    identity_mode = settings.resolved_identity_mode
    if auth_mode == "proxy":
        raise ValueError(
            "Proxy auth mode is reserved but not implemented yet. Use OIDC until trusted proxy identity headers are supported."
        )
    if is_cookie_auth_mode(auth_mode) and not settings.session_secret:
        raise ValueError(
            "Cookie-backed authentication requires HOMELAB_ANALYTICS_SESSION_SECRET to be configured."
        )
    if settings.break_glass_enabled and identity_mode != "local_single_user":
        raise ValueError(
            "Break-glass settings require HOMELAB_ANALYTICS_IDENTITY_MODE=local_single_user (or HOMELAB_ANALYTICS_AUTH_MODE=local_single_user)."
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
