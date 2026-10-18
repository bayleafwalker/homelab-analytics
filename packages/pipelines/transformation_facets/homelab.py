"""Homelab services, backups, storage, workloads, and infrastructure."""

from __future__ import annotations

from typing import Any

from packages.domains.homelab.pipelines.transformation_homelab import (
    count_backup_run_rows,
    count_service_health_rows,
    count_storage_sensor_rows,
    count_workload_sensor_rows,
    load_backup_run_rows,
    load_service_health_rows,
    load_storage_sensor_rows,
    load_workload_sensor_rows,
)
from packages.domains.homelab.pipelines.transformation_infrastructure import (
    count_cluster_metric_rows,
    count_power_consumption_rows,
    load_cluster_metric_rows,
    load_power_consumption_rows,
)
from packages.pipelines.transformation_facets.base import TransformationFacetBase


class HomelabTransformationMixin(TransformationFacetBase):
    """Homelab services, backups, storage, workloads, and infrastructure."""

    def load_service_health(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_service_health_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            source_system=source_system,
        )

    def load_backup_runs(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_backup_run_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            source_system=source_system,
        )

    def load_storage_sensors(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_storage_sensor_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            source_system=source_system,
        )

    def load_workload_sensors(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_workload_sensor_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            source_system=source_system,
        )

    def load_cluster_metrics(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_cluster_metric_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            source_system=source_system,
        )

    def load_power_consumption(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        source_system: str | None = None,
    ) -> int:
        return load_power_consumption_rows(
            self._store,
            rows=rows,
            record_lineage=self._record_lineage,
            run_id=run_id,
            source_system=source_system,
        )

    def count_cluster_metric_rows(self, run_id: str | None = None) -> int:
        return count_cluster_metric_rows(self._store, run_id=run_id)

    def count_power_consumption_rows(self, run_id: str | None = None) -> int:
        return count_power_consumption_rows(self._store, run_id=run_id)

    def count_service_health_rows(self, run_id: str | None = None) -> int:
        return count_service_health_rows(self._store, run_id=run_id)

    def count_backup_run_rows(self, run_id: str | None = None) -> int:
        return count_backup_run_rows(self._store, run_id=run_id)

    def count_storage_sensor_rows(self, run_id: str | None = None) -> int:
        return count_storage_sensor_rows(self._store, run_id=run_id)

    def count_workload_sensor_rows(self, run_id: str | None = None) -> int:
        return count_workload_sensor_rows(self._store, run_id=run_id)
