"""Homelab freshness templates must cover HOMELAB_PACK's real source datasets."""
from types import SimpleNamespace

from packages.domains.homelab.manifest import HOMELAB_PACK
from packages.pipelines.source_freshness_bootstrap import (
    DOMAIN_FRESHNESS_CONFIGS,
    ensure_domain_freshness_configs,
)

HOMELAB_SOURCES = {source.dataset_name for source in HOMELAB_PACK.sources}
# freshness_sla_days per dataset; everything else is shared across the pack.
EXPECTED_SLA_DAYS = {
    "ha_service_states": 7,
    "ha_workload_sensors": 7,
    "ha_storage_sensors": 14,
    "ha_backup_runs": 8,
}


def test_homelab_templates_match_pack_sources():
    templates = DOMAIN_FRESHNESS_CONFIGS["homelab"]
    assert set(templates) == HOMELAB_SOURCES


def test_homelab_templates_use_weekly_pull_shape():
    for dataset_name, sla_days in EXPECTED_SLA_DAYS.items():
        template = DOMAIN_FRESHNESS_CONFIGS["homelab"][dataset_name]
        assert template["acquisition_mode"] == "pull", dataset_name
        assert template["expected_frequency"] == "weekly", dataset_name
        assert template["coverage_kind"] == "calendar_week", dataset_name
        assert template["due_day_of_month"] is None, dataset_name
        assert template["expected_window_days"] == 2, dataset_name
        assert template["freshness_sla_days"] == sla_days, dataset_name
        assert template["sensitivity_class"] == "low", dataset_name
        assert template["reminder_channel"] == "operator_dashboard", dataset_name
        assert template["requires_human_action"] is False, dataset_name


class FakeControlPlane:
    def __init__(self, asset_ids):
        self.assets = [SimpleNamespace(source_asset_id=a) for a in asset_ids]
        self.created = []

    def list_source_assets(self):
        return self.assets

    def list_source_freshness_configs(self):
        return []

    def create_source_freshness_config(self, cfg):
        self.created.append(cfg)


def test_bootstrap_creates_one_config_per_homelab_dataset():
    asset_ids = [f"hass_{dataset_name}" for dataset_name in sorted(HOMELAB_SOURCES)]
    control_plane = FakeControlPlane(asset_ids)

    created_counts = ensure_domain_freshness_configs(control_plane, (HOMELAB_PACK,))

    assert created_counts == {"homelab": len(asset_ids)}
    by_id = {config.source_asset_id: config for config in control_plane.created}
    for dataset_name, sla_days in EXPECTED_SLA_DAYS.items():
        config = by_id[f"hass_{dataset_name}"]
        assert config.expected_frequency == "weekly"
        assert config.freshness_sla_days == sla_days
