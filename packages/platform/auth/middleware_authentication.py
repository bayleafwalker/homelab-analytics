"""Authentication-chain evaluation for the API auth middleware."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from packages.platform.auth.credential_resolution import bearer_token_from_request
from packages.platform.auth.crypto import parse_service_token
from packages.platform.auth.machine_jwt_provider import (
    MachineJwtAuthenticationError,
    MachineJwtAuthorizationError,
    MachineJwtProvider,
)
from packages.platform.auth.middleware_metrics import (
    increment_machine_jwt_authenticated_requests_total,
    increment_machine_jwt_failed_requests_total,
    increment_service_token_authenticated_requests_total,
    increment_service_token_failed_requests_total,
)
from packages.platform.auth.middleware_types import AuthenticationOutcome, AuthEventRecorder
from packages.platform.auth.oidc_provider import (
    OidcAuthenticationError,
    OidcAuthorizationError,
    OidcProvider,
)
from packages.platform.auth.proxy_provider import (
    ProxyAuthenticationError,
    ProxyAuthorizationError,
    ProxyProvider,
)
from packages.platform.auth.role_hierarchy import (
    AuthenticatedPrincipal,
    authenticate_service_token,
)
from packages.platform.auth.session_manager import SessionManager
from packages.storage.auth_store import AuthStore


def authenticate_request(
    request: Request,
    *,
    resolved_auth_mode: str,
    resolved_auth_store: AuthStore,
    resolved_session_manager: SessionManager | None,
    resolved_oidc_provider: OidcProvider | None,
    resolved_machine_jwt_provider: MachineJwtProvider | None,
    resolved_proxy_provider: ProxyProvider | None,
    record_auth_event: AuthEventRecorder,
) -> AuthenticationOutcome:
    bearer_token = bearer_token_from_request(request)
    if bearer_token is not None:
        return _authenticate_bearer_request(
            request,
            bearer_token,
            resolved_auth_mode=resolved_auth_mode,
            resolved_auth_store=resolved_auth_store,
            resolved_oidc_provider=resolved_oidc_provider,
            resolved_machine_jwt_provider=resolved_machine_jwt_provider,
            record_auth_event=record_auth_event,
        )
    return _authenticate_cookie_or_proxy_request(
        request,
        resolved_auth_mode=resolved_auth_mode,
        resolved_auth_store=resolved_auth_store,
        resolved_session_manager=resolved_session_manager,
        resolved_proxy_provider=resolved_proxy_provider,
    )


def _authenticate_bearer_request(
    request: Request,
    bearer_token: str,
    *,
    resolved_auth_mode: str,
    resolved_auth_store: AuthStore,
    resolved_oidc_provider: OidcProvider | None,
    resolved_machine_jwt_provider: MachineJwtProvider | None,
    record_auth_event: AuthEventRecorder,
) -> AuthenticationOutcome:
    parsed_service_token = parse_service_token(bearer_token)
    principal = authenticate_service_token(bearer_token, resolved_auth_store)
    if principal is not None and principal.auth_provider == "service_token":
        increment_service_token_authenticated_requests_total()
    if principal is None and parsed_service_token is not None:
        increment_service_token_failed_requests_total()
        record_auth_event(
            request,
            event_type="service_token_auth_failed",
            success=False,
            subject_user_id=parsed_service_token[0],
            subject_username=parsed_service_token[0],
            detail="Invalid, expired, or revoked service token.",
        )
        return AuthenticationOutcome(
            principal=None,
            response=JSONResponse(
                status_code=401,
                content={"detail": "Invalid service token."},
            ),
        )

    if principal is None:
        machine_jwt_error: tuple[int, str, str] | None = None
        if resolved_machine_jwt_provider is not None:
            try:
                principal = resolved_machine_jwt_provider.authenticate_bearer_token(
                    bearer_token
                )
                increment_machine_jwt_authenticated_requests_total()
                record_auth_event(
                    request,
                    event_type="machine_jwt_auth_succeeded",
                    success=True,
                    subject_user_id=principal.user_id,
                    subject_username=principal.username,
                    detail="Machine JWT bearer authenticated.",
                )
            except MachineJwtAuthorizationError as exc:
                machine_jwt_error = (403, str(exc), str(exc))
            except MachineJwtAuthenticationError:
                machine_jwt_error = (
                    401,
                    "Invalid bearer token.",
                    "Invalid or unauthorized machine JWT bearer token.",
                )

        if principal is None and resolved_auth_mode == "oidc":
            assert resolved_oidc_provider is not None
            try:
                principal = resolved_oidc_provider.authenticate_bearer_token(
                    bearer_token
                )
            except OidcAuthorizationError as exc:
                return AuthenticationOutcome(
                    principal=None,
                    response=JSONResponse(
                        status_code=403,
                        content={"detail": str(exc)},
                    ),
                )
            except OidcAuthenticationError:
                return AuthenticationOutcome(
                    principal=None,
                    response=JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid bearer token."},
                    ),
                )
        elif principal is None and machine_jwt_error is not None:
            increment_machine_jwt_failed_requests_total()
            record_auth_event(
                request,
                event_type="machine_jwt_auth_failed",
                success=False,
                detail=machine_jwt_error[2],
            )
            return AuthenticationOutcome(
                principal=None,
                response=JSONResponse(
                    status_code=machine_jwt_error[0],
                    content={"detail": machine_jwt_error[1]},
                ),
            )

    return AuthenticationOutcome(principal=principal, auth_via_cookie=False)


def _authenticate_cookie_or_proxy_request(
    request: Request,
    *,
    resolved_auth_mode: str,
    resolved_auth_store: AuthStore,
    resolved_session_manager: SessionManager | None,
    resolved_proxy_provider: ProxyProvider | None,
) -> AuthenticationOutcome:
    principal: AuthenticatedPrincipal | None = None
    if resolved_auth_mode == "proxy":
        assert resolved_proxy_provider is not None
        try:
            principal = resolved_proxy_provider.authenticate_request(request)
        except ProxyAuthorizationError as exc:
            return AuthenticationOutcome(
                principal=None,
                response=JSONResponse(
                    status_code=403,
                    content={"detail": str(exc)},
                ),
            )
        except ProxyAuthenticationError as exc:
            return AuthenticationOutcome(
                principal=None,
                response=JSONResponse(
                    status_code=401,
                    content={"detail": str(exc)},
                ),
            )
        return AuthenticationOutcome(principal=principal, auth_via_cookie=False)

    assert resolved_session_manager is not None
    principal = resolved_session_manager.authenticate(
        request.cookies.get(resolved_session_manager.cookie_name),
        resolved_auth_store,
    )
    return AuthenticationOutcome(
        principal=principal,
        auth_via_cookie=principal is not None,
    )
