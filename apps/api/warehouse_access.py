"""API wiring for short-lived warehouse handles.

- A pure ASGI hook marks request boundaries so the warehouse handle is
  released when the last in-flight request finishes.
- :class:`WarehouseBusyError` (another process held the DuckDB lock for the
  whole retry window) becomes ``503 Service Unavailable`` with ``Retry-After``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from packages.pipelines.warehouse_session import (
    WarehouseSessionManager,
    WarehouseSessionTransformationService,
)
from packages.storage.duckdb_store import WarehouseBusyError

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

RETRY_AFTER_SECONDS = 5


class WarehouseRequestScopeMiddleware:
    def __init__(self, app: ASGIApp, *, manager: WarehouseSessionManager) -> None:
        self._app = app
        self._manager = manager

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        self._manager.begin_request()
        try:
            await self._app(scope, receive, send)
        finally:
            self._manager.end_request()


def install_warehouse_access(app: FastAPI, transformation_service: Any) -> None:
    @app.exception_handler(WarehouseBusyError)
    async def handle_warehouse_busy(_, exc: WarehouseBusyError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": (
                    "The analytics warehouse is busy (another process is writing). "
                    "Retry shortly."
                ),
                "retry_after_seconds": RETRY_AFTER_SECONDS,
            },
            headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
        )

    if isinstance(transformation_service, WarehouseSessionTransformationService):
        app.state.warehouse_transformation_service = transformation_service
        app.add_middleware(
            WarehouseRequestScopeMiddleware,
            manager=transformation_service.warehouse_sessions,
        )
