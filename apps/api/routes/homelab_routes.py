"""Homelab domain API routes.

Exposes the four homelab mart publications as read-only endpoints:
  GET /api/homelab/services    → mart_service_health_current
  GET /api/homelab/backups     → mart_backup_freshness
  GET /api/homelab/storage     → mart_storage_risk
  GET /api/homelab/workloads   → mart_workload_cost_7d

When a ReportingService is configured (e.g. reporting_backend=postgres) it is
preferred over the TransformationService DuckDB fallback, matching the pattern
used by all other report routes.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI, HTTPException

from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService


def register_homelab_routes(
    app: FastAPI,
    *,
    transformation_service: TransformationService | None,
    resolved_reporting_service: ReportingService | None = None,
    to_jsonable: Callable[[Any], Any],
) -> None:
    def _reporting() -> ReportingService:
        if resolved_reporting_service is not None:
            return resolved_reporting_service
        if transformation_service is not None:
            return ReportingService(transformation_service)
        raise HTTPException(
            status_code=404,
            detail="Homelab reports require a transformation service.",
        )

    @app.get("/api/homelab/services")
    async def get_service_health() -> dict[str, Any]:
        rows = _reporting().get_service_health_current()
        return {"rows": to_jsonable(rows)}

    @app.get("/api/homelab/backups")
    async def get_backup_freshness() -> dict[str, Any]:
        rows = _reporting().get_backup_freshness()
        return {"rows": to_jsonable(rows)}

    @app.get("/api/homelab/storage")
    async def get_storage_risk() -> dict[str, Any]:
        rows = _reporting().get_storage_risk()
        return {"rows": to_jsonable(rows)}

    @app.get("/api/homelab/workloads")
    async def get_workload_cost_7d() -> dict[str, Any]:
        rows = _reporting().get_workload_cost_7d()
        return {"rows": to_jsonable(rows)}
