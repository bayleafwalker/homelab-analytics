"""Middleware metric helpers for auth request handling."""
from __future__ import annotations

import time

from packages.shared.metrics import metrics_registry

INGESTION_DURATION_METRIC = "ingestion_duration_seconds_total"
INGESTION_DURATION_HELP = "Cumulative ingestion handling duration in seconds."
DEPRECATED_INGESTION_DURATION_METRIC = "ingestion_duration_seconds"
DEPRECATED_INGESTION_DURATION_HELP = (
    "DEPRECATED: use ingestion_duration_seconds_total. Removed after one release."
)


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
        INGESTION_DURATION_METRIC,
        duration_ms / 1000,
        help_text=INGESTION_DURATION_HELP,
    )
    # DEPRECATED alias: a counter must end in _total. Removed after one release.
    metrics_registry.inc(
        DEPRECATED_INGESTION_DURATION_METRIC,
        duration_ms / 1000,
        help_text=DEPRECATED_INGESTION_DURATION_HELP,
    )
