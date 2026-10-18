"""DuckDB-path refreshes record the real upstream lineage and as-of snapshots.

Seeds the demo bundle through the production promotion path with the DuckDB
reporting backend (no Postgres publication store), then reads the lineage
graph and the snapshot table the API would serve.
"""

from __future__ import annotations

import pytest

pytest.importorskip("reportlab")

from packages.demo.bundle import write_demo_bundle
from packages.demo.seeder import _build_transformation_service, seed_demo_data
from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.pipelines.publication_confidence_service import (
    compute_and_record_publication_confidence,
)
from packages.pipelines.reporting_service import ReportingAccessMode, ReportingService
from packages.platform.lineage_graph import (
    EDGE_FEEDS,
    NODE_RUN,
    NODE_SOURCE,
    build_publication_lineage_graph,
)
from packages.platform.publication_confidence import (
    ConfidenceVerdict,
    get_latest_publication_confidence,
)
from packages.platform.runtime.builder import build_container
from packages.platform.source_freshness import SourceFreshnessState
from packages.shared.settings import AppSettings
from packages.storage.ingestion_catalog import SourceFreshnessConfigCreate
from tests.test_demo_data import _make_settings


@pytest.fixture(scope="module")
def seeded(tmp_path_factory: pytest.TempPathFactory) -> AppSettings:
    root = tmp_path_factory.mktemp("duckdb-path")
    demo_dir = root / "demo"
    write_demo_bundle(demo_dir)
    settings = _make_settings(root)
    seed_demo_data(settings, demo_dir)
    return settings


def _container(settings: AppSettings):
    return build_container(settings, capability_packs=[FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK])


def test_publication_lineage_reaches_source_asset_and_transformation(seeded: AppSettings) -> None:
    container = _container(seeded)
    graph = build_publication_lineage_graph(
        container.control_plane_store, publication_key="mart_monthly_cashflow"
    )
    by_type: dict[str, list] = {}
    for node in graph.nodes:
        by_type.setdefault(node.type, []).append(node)
    layers = {
        node.attributes.get("layer")
        for node in graph.nodes
        if node.type == "relation"
    }

    # More than the single publication node the DuckDB path used to return.
    assert len(by_type[NODE_RUN]) == 3  # one per demo account statement
    assert by_type[NODE_SOURCE]
    assert {"landing", "transformation", "reporting"} <= layers
    landing = [n for n in graph.nodes if n.attributes.get("layer") == "landing"]
    assert {n.attributes["kind"] for n in landing} == {"source_asset"}
    assert any(n.attributes.get("name") == "fact_transaction" for n in graph.nodes)
    assert any(e.type == EDGE_FEEDS for e in graph.edges)
    audit = container.control_plane_store.list_publication_audit(
        publication_key="mart_monthly_cashflow"
    )
    assert audit and {record.status for record in audit} == {"warehouse"}


def test_seed_captures_snapshots_for_the_newest_month_only(seeded: AppSettings) -> None:
    container = _container(seeded)
    ts = _build_transformation_service(seeded, container)
    reporting = ReportingService(ts, access_mode=ReportingAccessMode.WAREHOUSE)
    months = [row["booking_month"] for row in reporting.get_monthly_cashflow()]
    newest, older = months[-1], months[0]

    for relation in ("mart_household_overview", "mart_open_attention_items"):
        assert reporting.list_publication_snapshot_months(relation) == [newest]
    snapshot = reporting.get_publication_snapshot("mart_household_overview", newest)
    assert snapshot is not None
    assert snapshot.rows[0]["current_month"] == newest
    # The demo lands every month at once, so older months honestly have no
    # history for the current-only publications.
    assert reporting.get_publication_snapshot("mart_household_overview", older) is None



def test_confidence_attributes_runs_to_their_source_asset(seeded: AppSettings) -> None:
    """#2801: freshness is looked up by the asset each contributing run landed for.

    The seed configures no freshness schedules, so the recorded verdict is
    unavailable. Once the demo's source assets get a freshness config, the
    same DuckDB-path lineage yields a real freshness state and verdict.
    """
    container = _container(seeded)
    control_plane = container.control_plane_store
    landing_assets = {
        record.target_name
        for record in control_plane.list_source_lineage(target_layer="landing")
        if record.target_kind == "source_asset"
    }
    assert landing_assets

    seeded_snapshot = get_latest_publication_confidence(
        "mart_monthly_cashflow", control_plane
    )
    assert seeded_snapshot is not None
    # The seed's promotion recorded lineage before the final snapshot, so the
    # runs contribute; only freshness is missing.
    assert seeded_snapshot.contributing_run_ids
    assert seeded_snapshot.completeness_pct == 100
    assert seeded_snapshot.confidence_verdict == ConfidenceVerdict.UNAVAILABLE

    for source_asset_id in sorted(landing_assets):
        control_plane.create_source_freshness_config(
            SourceFreshnessConfigCreate(
                source_asset_id=source_asset_id,
                acquisition_mode="manual_export",
                expected_frequency="ad_hoc",
                coverage_kind="rolling_period",
                due_day_of_month=None,
                expected_window_days=5,
                freshness_sla_days=40,
                sensitivity_class="financial",
                reminder_channel="dashboard",
                requires_human_action=True,
            )
        )
    snapshot = compute_and_record_publication_confidence(
        "mart_monthly_cashflow",
        control_plane,
        None,
        run_metadata_store=container.run_metadata_store,
    )

    assert set(snapshot.source_freshness_states) <= landing_assets
    assert snapshot.source_freshness_states
    assert {
        state.freshness_state for state in snapshot.source_freshness_states.values()
    } == {SourceFreshnessState.CURRENT}
    assert snapshot.confidence_verdict == ConfidenceVerdict.TRUSTWORTHY
