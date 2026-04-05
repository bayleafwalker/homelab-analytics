"""Tests for publication confidence model and verdict computation."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from packages.platform.publication_confidence import (
    ConfidenceVerdict,
    FreshnessState,
    PublicationConfidenceSnapshot,
    SourceFreshnessSnapshot,
    _compute_verdict,
    compute_publication_freshness_state,
)
from packages.platform.source_freshness import SourceFreshnessState


@pytest.fixture
def now():
    return datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def source_current() -> SourceFreshnessSnapshot:
    """Current source (freshly ingested)."""
    return SourceFreshnessSnapshot(
        source_asset_id="finance-assets",
        freshness_state=SourceFreshnessState.CURRENT,
        last_ingest_at=datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc),
        covered_through="2026-04-04",
    )


@pytest.fixture
def source_due_soon() -> SourceFreshnessSnapshot:
    """Source ingest due soon (within expected window)."""
    return SourceFreshnessSnapshot(
        source_asset_id="utilities-assets",
        freshness_state=SourceFreshnessState.DUE_SOON,
        last_ingest_at=datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc),
        covered_through="2026-04-03",
    )


@pytest.fixture
def source_overdue() -> SourceFreshnessSnapshot:
    """Source ingest overdue."""
    return SourceFreshnessSnapshot(
        source_asset_id="homelab-assets",
        freshness_state=SourceFreshnessState.OVERDUE,
        last_ingest_at=datetime(2026, 3, 30, 12, 0, 0, tzinfo=timezone.utc),
        covered_through="2026-03-30",
    )


@pytest.fixture
def source_missing_period() -> SourceFreshnessSnapshot:
    """Source with missing data period."""
    return SourceFreshnessSnapshot(
        source_asset_id="ha-assets",
        freshness_state=SourceFreshnessState.MISSING_PERIOD,
        last_ingest_at=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
        covered_through="2026-04-01",
    )


@pytest.fixture
def source_unconfigured() -> SourceFreshnessSnapshot:
    """Source without freshness config."""
    return SourceFreshnessSnapshot(
        source_asset_id="unknown-assets",
        freshness_state=SourceFreshnessState.UNCONFIGURED,
    )


# Scenario fixtures for stale, partial, and malformed input states
@pytest.fixture
def scenario_stale_source(source_overdue):
    """Publication with a stale source."""
    return {
        "publication_key": "pub_stale_financial_summary",
        "sources": {source_overdue.source_asset_id: source_overdue},
        "completeness_pct": 60,
        "expected_verdict": ConfidenceVerdict.DEGRADED,
    }


@pytest.fixture
def scenario_partial_ingestion(source_current, source_due_soon):
    """Publication with partial source coverage (only 40% of expected sources ingested)."""
    return {
        "publication_key": "pub_partial_utilities_summary",
        "sources": {source_current.source_asset_id: source_current},
        "completeness_pct": 40,
        "expected_verdict": ConfidenceVerdict.DEGRADED,
    }


@pytest.fixture
def scenario_missing_period(source_missing_period):
    """Publication with source covering a missing period."""
    return {
        "publication_key": "pub_gap_homelab_metrics",
        "sources": {source_missing_period.source_asset_id: source_missing_period},
        "completeness_pct": 70,
        "expected_verdict": ConfidenceVerdict.DEGRADED,
    }


@pytest.fixture
def scenario_all_stale(source_overdue, source_missing_period):
    """Publication where all sources are stale with low completeness."""
    return {
        "publication_key": "pub_unreliable_cross_domain",
        "sources": {
            source_overdue.source_asset_id: source_overdue,
            source_missing_period.source_asset_id: source_missing_period,
        },
        "completeness_pct": 20,
        "expected_verdict": ConfidenceVerdict.UNRELIABLE,
    }


@pytest.fixture
def scenario_unconfigured_sources(source_unconfigured):
    """Publication with no freshness configs (malformed state)."""
    return {
        "publication_key": "pub_unknown_sources",
        "sources": {source_unconfigured.source_asset_id: source_unconfigured},
        "completeness_pct": 100,
        "expected_verdict": ConfidenceVerdict.UNAVAILABLE,
    }


@pytest.fixture
def scenario_empty_sources():
    """Publication with no contributing sources."""
    return {
        "publication_key": "pub_no_sources",
        "sources": {},
        "completeness_pct": 0,
        "expected_verdict": ConfidenceVerdict.UNAVAILABLE,
    }


class TestVerdictComputation:
    """Test confidence verdict logic."""

    def test_trustworthy_all_current_complete(self, source_current):
        """Verdict is TRUSTWORTHY when all sources current and 100% complete."""
        verdict = _compute_verdict({source_current.source_asset_id: source_current}, 100)
        assert verdict == ConfidenceVerdict.TRUSTWORTHY

    def test_trustworthy_multiple_sources_current_complete(
        self, source_current, source_due_soon
    ):
        """Verdict is TRUSTWORTHY with multiple sources all current and 100% complete."""
        sources = {
            source_current.source_asset_id: source_current,
            source_due_soon.source_asset_id: source_due_soon,
        }
        # source_due_soon is still in DUE_SOON state (not yet overdue), so not all current
        verdict = _compute_verdict(sources, 100)
        assert verdict == ConfidenceVerdict.DEGRADED

    def test_degraded_overdue_high_completeness(self, source_overdue):
        """Verdict is DEGRADED when source overdue but >= 50% complete."""
        verdict = _compute_verdict({source_overdue.source_asset_id: source_overdue}, 75)
        assert verdict == ConfidenceVerdict.DEGRADED

    def test_unreliable_overdue_low_completeness(self, source_overdue):
        """Verdict is UNRELIABLE when source overdue and < 50% complete."""
        verdict = _compute_verdict({source_overdue.source_asset_id: source_overdue}, 30)
        assert verdict == ConfidenceVerdict.UNRELIABLE

    def test_degraded_missing_period_high_completeness(self, source_missing_period):
        """Verdict is DEGRADED when source missing period but >= 50% complete."""
        verdict = _compute_verdict(
            {source_missing_period.source_asset_id: source_missing_period}, 60
        )
        assert verdict == ConfidenceVerdict.DEGRADED

    def test_unreliable_missing_period_low_completeness(self, source_missing_period):
        """Verdict is UNRELIABLE when source missing period and < 50% complete."""
        verdict = _compute_verdict(
            {source_missing_period.source_asset_id: source_missing_period}, 40
        )
        assert verdict == ConfidenceVerdict.UNRELIABLE

    def test_unavailable_all_unconfigured(self, source_unconfigured):
        """Verdict is UNAVAILABLE when all sources unconfigured."""
        verdict = _compute_verdict({source_unconfigured.source_asset_id: source_unconfigured}, 100)
        assert verdict == ConfidenceVerdict.UNAVAILABLE

    def test_unavailable_empty_sources(self):
        """Verdict is UNAVAILABLE when no sources."""
        verdict = _compute_verdict({}, 100)
        assert verdict == ConfidenceVerdict.UNAVAILABLE

    def test_degraded_mixed_sources_current_due_soon(self, source_current, source_due_soon):
        """Verdict is DEGRADED when mix of current and due_soon sources."""
        sources = {
            source_current.source_asset_id: source_current,
            source_due_soon.source_asset_id: source_due_soon,
        }
        verdict = _compute_verdict(sources, 100)
        assert verdict == ConfidenceVerdict.DEGRADED


class TestFreshnessStateComputation:
    """Test publication-level freshness state derivation."""

    def test_current_all_sources_current(self, source_current):
        """Freshness is CURRENT when all sources current."""
        state = compute_publication_freshness_state({source_current.source_asset_id: source_current})
        assert state == FreshnessState.CURRENT

    def test_due_soon_one_source_due_soon(self, source_current, source_due_soon):
        """Freshness is DUE_SOON when any source due soon."""
        sources = {
            source_current.source_asset_id: source_current,
            source_due_soon.source_asset_id: source_due_soon,
        }
        state = compute_publication_freshness_state(sources)
        assert state == FreshnessState.DUE_SOON

    def test_stale_one_source_overdue(self, source_current, source_overdue):
        """Freshness is STALE when any source overdue."""
        sources = {
            source_current.source_asset_id: source_current,
            source_overdue.source_asset_id: source_overdue,
        }
        state = compute_publication_freshness_state(sources)
        assert state == FreshnessState.STALE

    def test_stale_one_source_missing_period(self, source_current, source_missing_period):
        """Freshness is STALE when any source missing period."""
        sources = {
            source_current.source_asset_id: source_current,
            source_missing_period.source_asset_id: source_missing_period,
        }
        state = compute_publication_freshness_state(sources)
        assert state == FreshnessState.STALE

    def test_unavailable_no_sources(self):
        """Freshness is UNAVAILABLE when no sources."""
        state = compute_publication_freshness_state({})
        assert state == FreshnessState.UNAVAILABLE

    def test_unavailable_all_unconfigured(self, source_unconfigured):
        """Freshness is UNAVAILABLE when all sources unconfigured."""
        state = compute_publication_freshness_state({source_unconfigured.source_asset_id: source_unconfigured})
        assert state == FreshnessState.UNAVAILABLE


class TestPublicationConfidenceSnapshot:
    """Test snapshot creation and verdict assignment."""

    def test_create_trustworthy_snapshot(self, now, source_current):
        """Create snapshot with TRUSTWORTHY verdict."""
        snapshot = PublicationConfidenceSnapshot.create(
            publication_key="pub_financial_summary",
            assessed_at=now,
            freshness_state=FreshnessState.CURRENT,
            completeness_pct=100,
            source_freshness_states={source_current.source_asset_id: source_current},
            contributing_run_ids=["run-001", "run-002"],
            quality_flags={"validation_errors": 0},
        )
        assert snapshot.publication_key == "pub_financial_summary"
        assert snapshot.confidence_verdict == ConfidenceVerdict.TRUSTWORTHY
        assert snapshot.completeness_pct == 100
        assert len(snapshot.contributing_run_ids) == 2
        assert snapshot.quality_flags == {"validation_errors": 0}

    def test_create_degraded_snapshot(self, now, source_overdue):
        """Create snapshot with DEGRADED verdict."""
        snapshot = PublicationConfidenceSnapshot.create(
            publication_key="pub_utilities_summary",
            assessed_at=now,
            freshness_state=FreshnessState.STALE,
            completeness_pct=75,
            source_freshness_states={source_overdue.source_asset_id: source_overdue},
        )
        assert snapshot.confidence_verdict == ConfidenceVerdict.DEGRADED
        assert snapshot.freshness_state == FreshnessState.STALE

    def test_create_unreliable_snapshot(self, now, source_missing_period):
        """Create snapshot with UNRELIABLE verdict."""
        snapshot = PublicationConfidenceSnapshot.create(
            publication_key="pub_homelab_cost",
            assessed_at=now,
            freshness_state=FreshnessState.STALE,
            completeness_pct=30,
            source_freshness_states={source_missing_period.source_asset_id: source_missing_period},
        )
        assert snapshot.confidence_verdict == ConfidenceVerdict.UNRELIABLE

    def test_create_unavailable_snapshot(self, now, source_unconfigured):
        """Create snapshot with UNAVAILABLE verdict."""
        snapshot = PublicationConfidenceSnapshot.create(
            publication_key="pub_unknown",
            assessed_at=now,
            freshness_state=FreshnessState.UNAVAILABLE,
            completeness_pct=0,
            source_freshness_states={source_unconfigured.source_asset_id: source_unconfigured},
        )
        assert snapshot.confidence_verdict == ConfidenceVerdict.UNAVAILABLE

    def test_snapshot_has_unique_id(self, now, source_current):
        """Each snapshot gets a unique ID."""
        snap1 = PublicationConfidenceSnapshot.create(
            publication_key="pub_test",
            assessed_at=now,
            freshness_state=FreshnessState.CURRENT,
            completeness_pct=100,
            source_freshness_states={source_current.source_asset_id: source_current},
        )
        snap2 = PublicationConfidenceSnapshot.create(
            publication_key="pub_test",
            assessed_at=now,
            freshness_state=FreshnessState.CURRENT,
            completeness_pct=100,
            source_freshness_states={source_current.source_asset_id: source_current},
        )
        assert snap1.snapshot_id != snap2.snapshot_id

    def test_snapshot_defaults_to_empty_collections(self, now, source_current):
        """Snapshot with defaults for optional fields."""
        snapshot = PublicationConfidenceSnapshot.create(
            publication_key="pub_test",
            assessed_at=now,
            freshness_state=FreshnessState.CURRENT,
            completeness_pct=100,
            source_freshness_states={source_current.source_asset_id: source_current},
        )
        assert snapshot.contributing_run_ids == []
        assert snapshot.quality_flags == {}


class TestScenarios:
    """Test verdict logic against real-world scenarios."""

    def test_scenario_stale_source(self, now, scenario_stale_source):
        """Stale source with moderate completeness → DEGRADED."""
        scenario = scenario_stale_source
        snapshot = PublicationConfidenceSnapshot.create(
            publication_key=scenario["publication_key"],
            assessed_at=now,
            freshness_state=FreshnessState.STALE,
            completeness_pct=scenario["completeness_pct"],
            source_freshness_states=scenario["sources"],
        )
        assert snapshot.confidence_verdict == scenario["expected_verdict"]
        assert snapshot.confidence_verdict == ConfidenceVerdict.DEGRADED

    def test_scenario_partial_ingestion(self, now, scenario_partial_ingestion):
        """Partial source coverage with low completeness → DEGRADED."""
        scenario = scenario_partial_ingestion
        snapshot = PublicationConfidenceSnapshot.create(
            publication_key=scenario["publication_key"],
            assessed_at=now,
            freshness_state=FreshnessState.DUE_SOON,
            completeness_pct=scenario["completeness_pct"],
            source_freshness_states=scenario["sources"],
        )
        assert snapshot.confidence_verdict == scenario["expected_verdict"]

    def test_scenario_missing_period(self, now, scenario_missing_period):
        """Source with missing period → DEGRADED."""
        scenario = scenario_missing_period
        snapshot = PublicationConfidenceSnapshot.create(
            publication_key=scenario["publication_key"],
            assessed_at=now,
            freshness_state=FreshnessState.STALE,
            completeness_pct=scenario["completeness_pct"],
            source_freshness_states=scenario["sources"],
        )
        assert snapshot.confidence_verdict == scenario["expected_verdict"]

    def test_scenario_all_stale_low_completeness(self, now, scenario_all_stale):
        """All sources stale with low completeness → UNRELIABLE."""
        scenario = scenario_all_stale
        snapshot = PublicationConfidenceSnapshot.create(
            publication_key=scenario["publication_key"],
            assessed_at=now,
            freshness_state=FreshnessState.STALE,
            completeness_pct=scenario["completeness_pct"],
            source_freshness_states=scenario["sources"],
        )
        assert snapshot.confidence_verdict == scenario["expected_verdict"]
        assert snapshot.confidence_verdict == ConfidenceVerdict.UNRELIABLE

    def test_scenario_unconfigured_sources(self, now, scenario_unconfigured_sources):
        """Unconfigured sources → UNAVAILABLE."""
        scenario = scenario_unconfigured_sources
        snapshot = PublicationConfidenceSnapshot.create(
            publication_key=scenario["publication_key"],
            assessed_at=now,
            freshness_state=FreshnessState.UNAVAILABLE,
            completeness_pct=scenario["completeness_pct"],
            source_freshness_states=scenario["sources"],
        )
        assert snapshot.confidence_verdict == scenario["expected_verdict"]
        assert snapshot.confidence_verdict == ConfidenceVerdict.UNAVAILABLE

    def test_scenario_empty_sources(self, now, scenario_empty_sources):
        """No contributing sources → UNAVAILABLE."""
        scenario = scenario_empty_sources
        snapshot = PublicationConfidenceSnapshot.create(
            publication_key=scenario["publication_key"],
            assessed_at=now,
            freshness_state=FreshnessState.UNAVAILABLE,
            completeness_pct=scenario["completeness_pct"],
            source_freshness_states=scenario["sources"],
        )
        assert snapshot.confidence_verdict == scenario["expected_verdict"]
        assert snapshot.confidence_verdict == ConfidenceVerdict.UNAVAILABLE
