"""API-side observability: request metrics middleware and the /metrics handler.

Request series are labelled by the matched route *template* (``/runs/{run_id}``),
never the raw path, so cardinality stays bounded. Requests that match no
route are labelled ``route="unmatched"``.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from starlette.routing import Match

from packages.application.use_cases.ops_metrics import OpsMetricsCollector
from packages.shared.metrics import (
    METRICS_AUTH_SCHEME,
    MetricsRegistry,
    scrape_token_matches,
)

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

HTTP_REQUEST_DURATION = "homelab_analytics_http_request_duration_seconds"
HTTP_REQUESTS_TOTAL = "homelab_analytics_http_requests_total"
_DURATION_HELP = "API request latency by method, route template, and status class."
_REQUESTS_HELP = "API requests by method, route template, and status code."


def _route_template(app: Any, scope: Scope) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str):
        return path
    router = getattr(app, "router", None)
    for candidate in getattr(router, "routes", ()):
        try:
            match, _ = candidate.matches(scope)
        except Exception:  # noqa: BLE001 - matching must never fail a request
            continue
        if match == Match.FULL:
            candidate_path = getattr(candidate, "path", None)
            if isinstance(candidate_path, str):
                return candidate_path
    return "unmatched"


class HttpMetricsMiddleware:
    """Pure ASGI middleware recording request count and latency."""

    def __init__(self, app: ASGIApp, *, registry: MetricsRegistry, fastapi_app: Any) -> None:
        self._app = app
        self._registry = registry
        self._fastapi_app = fastapi_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        started = time.perf_counter()
        status_holder = {"status": 500}

        async def send_wrapper(message: Message) -> None:
            if message.get("type") == "http.response.start":
                status_holder["status"] = int(message.get("status", 500))
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            status = status_holder["status"]
            route = _route_template(self._fastapi_app, scope)
            method = str(scope.get("method", "GET")).upper()
            self._registry.observe(
                HTTP_REQUEST_DURATION,
                time.perf_counter() - started,
                help_text=_DURATION_HELP,
                labels={
                    "method": method,
                    "route": route,
                    "status_class": f"{status // 100}xx",
                },
            )
            self._registry.inc(
                HTTP_REQUESTS_TOTAL,
                1,
                help_text=_REQUESTS_HELP,
                labels={"method": method, "route": route, "status": str(status)},
            )


def install_http_metrics(app: FastAPI, registry: MetricsRegistry) -> None:
    registry.declare_histogram(HTTP_REQUEST_DURATION, help_text=_DURATION_HELP)
    app.add_middleware(HttpMetricsMiddleware, registry=registry, fastapi_app=app)


def render_metrics_response(
    request: Request,
    *,
    registry: MetricsRegistry,
    metrics_token: str | None,
    refreshers: tuple[Callable[[], None], ...] = (),
    ops_collector: OpsMetricsCollector | None = None,
) -> PlainTextResponse:
    if not scrape_token_matches(request.headers.get("authorization"), metrics_token):
        return PlainTextResponse(
            "scrape token required\n",
            status_code=401,
            headers={"WWW-Authenticate": METRICS_AUTH_SCHEME},
        )
    for refresh in refreshers:
        refresh()
    if ops_collector is not None:
        ops_collector.collect()
    return PlainTextResponse(
        registry.render_prometheus_text(),
        media_type="text/plain; version=0.0.4",
    )
