from __future__ import annotations

from decimal import Decimal

from packages.domains.homelab.manifest import HOMELAB_PACK
from packages.pipelines.ha_contract_renderer import (
    HaContractRenderer,
    build_ha_publication_entities,
)
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from tests.test_homelab_domain import (
    _backup_rows,
    _service_rows,
    _storage_rows,
    _workload_rows,
)


def _reporting_service() -> ReportingService:
    transformation_service = TransformationService(DuckDBStore.memory())
    transformation_service.load_service_health(_service_rows(), run_id="run-hl-services")
    transformation_service.refresh_service_health_current()
    transformation_service.load_backup_runs(_backup_rows(), run_id="run-hl-backups")
    transformation_service.refresh_backup_freshness()
    transformation_service.load_storage_sensors(_storage_rows(), run_id="run-hl-storage")
    transformation_service.refresh_storage_risk()
    transformation_service.load_workload_sensors(_workload_rows(), run_id="run-hl-workloads")
    transformation_service.refresh_workload_cost_7d()
    return ReportingService(transformation_service)


def test_build_ha_publication_entities_uses_contract_metadata() -> None:
    entities = build_ha_publication_entities((HOMELAB_PACK,))
    by_publication = {entity.entity.publication_key: entity for entity in entities}

    assert set(by_publication) == {
        "service_health_current",
        "backup_freshness",
        "storage_risk",
        "workload_cost_7d",
    }
    assert (
        by_publication["service_health_current"].entity.object_id
        == "homelab_analytics_services_unhealthy"
    )
    assert by_publication["service_health_current"].filter_values == ("degraded", "stopped")
    assert (
        by_publication["workload_cost_7d"].state_field
        == "est_monthly_cost"
    )
    assert (
        by_publication["workload_cost_7d"].entity.ui_descriptor_key
        == "homelab-workloads"
    )


def test_ha_contract_renderer_renders_publication_summary_states() -> None:
    renderer = HaContractRenderer(
        _reporting_service(),
        capability_packs=(HOMELAB_PACK,),
    )

    states = renderer.render_states()

    assert states["homelab_analytics_services_unhealthy"] == 2
    assert states["homelab_analytics_backups_stale"] == 2
    assert states["homelab_analytics_storage_risk_devices"] == 2
    assert Decimal(str(states["homelab_analytics_workload_cost_estimate"])) > 0


def test_ha_contract_renderer_workload_cost_matches_reporting_rows() -> None:
    reporting_service = _reporting_service()
    renderer = HaContractRenderer(
        reporting_service,
        capability_packs=(HOMELAB_PACK,),
    )

    rendered_value = Decimal(
        str(renderer.render_states()["homelab_analytics_workload_cost_estimate"])
    )
    expected_value = sum(
        Decimal(str(row["est_monthly_cost"]))
        for row in reporting_service.get_relation_rows("mart_workload_cost_7d")
    )

    assert rendered_value == expected_value
