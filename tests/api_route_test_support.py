from __future__ import annotations

import asyncio
import inspect
from typing import Any

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.routing import APIRoute


def call_route(
    app: FastAPI,
    path: str,
    *,
    method: str = "GET",
    **params: Any,
) -> Any:
    """Invoke a FastAPI route endpoint directly for route serialization tests."""
    route, path_params = _find_route(app, path, method)
    result = route.endpoint(**path_params, **params)
    if inspect.isawaitable(result):
        result = asyncio.run(result)
    return jsonable_encoder(result)


def _find_route(app: FastAPI, path: str, method: str) -> tuple[APIRoute, dict[str, Any]]:
    requested_method = method.upper()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if requested_method not in route.methods:
            continue
        if route.path == path:
            return route, {}
        match = route.path_regex.fullmatch(path)
        if match is None:
            continue
        path_params = {
            name: route.param_convertors[name].convert(value)
            for name, value in match.groupdict().items()
        }
        return route, path_params
    raise AssertionError(f"Route not found: {requested_method} {path}")
