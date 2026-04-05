from __future__ import annotations

from typing import Any, Callable, cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from apps.api.models import TerminalExecutionRequest
from apps.api.response_models import (
    TerminalCommandsResponseModel,
    TerminalExecutionResponseModel,
)
from packages.application.use_cases.control_terminal import (
    TerminalCommandRejected,
    TerminalExecutionContext,
    execute_terminal_command,
    failed_terminal_execution,
    rejected_terminal_execution,
    terminal_command_specs,
)
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.promotion_registry import PromotionHandlerRegistry
from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal
from packages.shared.extensions import ExtensionRegistry
from packages.shared.function_registry import FunctionRegistry
from packages.storage.control_plane import ControlPlaneStore


def register_control_terminal_routes(
    app: FastAPI,
    *,
    service: AccountTransactionService,
    resolved_config_repository: ControlPlaneStore,
    extension_registry: ExtensionRegistry,
    function_registry: FunctionRegistry,
    promotion_handler_registry: PromotionHandlerRegistry,
    require_unsafe_admin: Callable[[], None],
    build_operational_summary: Callable[[], dict[str, Any]],
    record_auth_event: Callable[..., None],
    to_jsonable: Callable[[Any], Any],
) -> None:
    execution_context = TerminalExecutionContext(
        service=service,
        config_repository=resolved_config_repository,
        extension_registry=extension_registry,
        function_registry=function_registry,
        promotion_handler_registry=promotion_handler_registry,
        build_operational_summary=build_operational_summary,
        to_jsonable=to_jsonable,
    )

    @app.get(
        "/control/terminal/commands",
        response_model=TerminalCommandsResponseModel,
    )
    async def list_terminal_commands() -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "commands": [to_jsonable(command) for command in terminal_command_specs()]
        }

    @app.post(
        "/control/terminal/execute",
        response_model=TerminalExecutionResponseModel,
        responses={
            400: {"model": TerminalExecutionResponseModel},
            500: {"model": TerminalExecutionResponseModel},
        },
    )
    async def execute_terminal_command_endpoint(
        request: Request,
        payload: TerminalExecutionRequest,
    ) -> JSONResponse | dict[str, Any]:
        require_unsafe_admin()
        principal = cast(
            AuthenticatedPrincipal | None,
            getattr(request.state, "principal", None),
        )
        try:
            execution = execute_terminal_command(payload.command_line, execution_context)
        except TerminalCommandRejected as exc:
            execution = rejected_terminal_execution(
                payload.command_line,
                str(exc),
            )
            record_auth_event(
                request,
                event_type="terminal_command_rejected",
                success=False,
                actor=principal,
                detail=(
                    f"command={execution.normalized_command or payload.command_line.strip()} "
                    f"reason={str(exc)}"
                ),
            )
            return JSONResponse(
                status_code=400,
                content={"execution": to_jsonable(execution)},
            )
        except Exception as exc:
            execution = failed_terminal_execution(payload.command_line, str(exc))
            record_auth_event(
                request,
                event_type="terminal_command_failed",
                success=False,
                actor=principal,
                detail=(
                    f"command={execution.normalized_command or payload.command_line.strip()} "
                    f"reason={str(exc)}"
                ),
            )
            return JSONResponse(
                status_code=500,
                content={"execution": to_jsonable(execution)},
            )

        record_auth_event(
            request,
            event_type=(
                "terminal_command_succeeded"
                if execution.status == "succeeded"
                else "terminal_command_failed"
            ),
            success=execution.status == "succeeded",
            actor=principal,
            detail=(
                f"command={execution.normalized_command} "
                f"exit_code={execution.exit_code} "
                f"mutating={str(execution.mutating).lower()}"
            ),
        )
        return {"execution": to_jsonable(execution)}
