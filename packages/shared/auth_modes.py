from __future__ import annotations

from typing import Literal

ResolvedAuthMode = Literal["disabled", "local", "oidc", "proxy"]

_SUPPORTED_AUTH_MODES = frozenset(
    {
        "disabled",
        "local",
        "local_single_user",
        "oidc",
        "proxy",
    }
)


def normalize_auth_mode(raw_mode: str) -> ResolvedAuthMode:
    mode = raw_mode.strip().lower()
    if mode not in _SUPPORTED_AUTH_MODES:
        raise ValueError(f"Unsupported auth mode: {raw_mode!r}")
    if mode == "local_single_user":
        return "local"
    return mode  # type: ignore[return-value]


def is_cookie_auth_mode(mode: str) -> bool:
    return normalize_auth_mode(mode) in {"local", "oidc"}
