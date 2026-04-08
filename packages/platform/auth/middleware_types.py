"""Shared middleware result and callback types."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi.responses import Response

from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal

AuthEventRecorder = Callable[..., None]


@dataclass(frozen=True)
class AuthenticationOutcome:
    principal: AuthenticatedPrincipal | None
    auth_via_cookie: bool = False
    response: Response | None = None
