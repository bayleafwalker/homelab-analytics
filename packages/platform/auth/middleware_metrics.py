"""Middleware metric helpers for auth request handling."""
from __future__ import annotations

import time

from packages.shared.metrics import metrics_registry


def increment_service_token_authenticated_requests_total() -> None:
    metrics_registry.inc(
        "auth_service_token_authenticated_requests_total",
        1,
        help_text="Total successfully authenticated service-token requests observed by this API process.",
    )


def increment_service_token_failed_requests_total() -> None:
    metrics_registry.inc(
        "auth_service_token_failed_requests_total",
        1,
        help_text="Total rejected service-token bearer requests observed by this API process.",
    )


def increment_machine_jwt_authenticated_requests_total() -> None:
    metrics_registry.inc(
        "auth_machine_jwt_authenticated_requests_total",
        1,
        help_text="Total successfully authenticated machine-JWT bearer requests observed by this API process.",
    )


def increment_machine_jwt_failed_requests_total() -> None:
    metrics_registry.inc(
        "auth_machine_jwt_failed_requests_total",
        1,
        help_text="Total rejected machine-JWT bearer requests observed by this API process.",
    )


def record_ingestion_duration(started: float) -> None:
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    metrics_registry.inc(
        "ingestion_duration_seconds",
        duration_ms / 1000,
        help_text="Cumulative ingestion handling duration in seconds.",
    )
