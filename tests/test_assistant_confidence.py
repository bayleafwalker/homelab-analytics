"""Tests for assistant answer confidence enrichment."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from apps.api.response_models import AssistantSourceModel
from apps.api.routes.assistant_routes import _build_answer_confidence, _publication_source
from packages.platform.publication_confidence import (
    ConfidenceVerdict,
    FreshnessState,
    PublicationConfidenceSnapshot,
    SourceFreshnessSnapshot,
)
from packages.platform.source_freshness import SourceFreshnessState


def _make_snapshot(
    publication_key: str,
    verdict: ConfidenceVerdict,
    freshness: FreshnessState,
) -> PublicationConfidenceSnapshot:
    return PublicationConfidenceSnapshot(
        snapshot_id="test-snap",
        publication_key=publication_key,
        assessed_at=datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc),
        freshness_state=freshness,
        completeness_pct=100,
        source_freshness_states={
            "src": SourceFreshnessSnapshot(
                source_asset_id="src",
                freshness_state=SourceFreshnessState.CURRENT,
            )
        },
        confidence_verdict=verdict,
    )


class PublicationSourceConfidenceTests(unittest.TestCase):
    def test_source_with_confidence_snapshot(self) -> None:
        snap = _make_snapshot("mart_monthly_cashflow", ConfidenceVerdict.TRUSTWORTHY, FreshnessState.CURRENT)
        source = _publication_source(
            {},
            "mart_monthly_cashflow",
            rationale="test",
            confidence_by_key={"mart_monthly_cashflow": snap},
        )
        self.assertEqual(source.confidence_verdict, "trustworthy")
        self.assertEqual(source.freshness_state, "current")
        self.assertIsNotNone(source.assessed_at)

    def test_source_without_confidence_data(self) -> None:
        source = _publication_source(
            {},
            "mart_monthly_cashflow",
            rationale="test",
            confidence_by_key=None,
        )
        self.assertIsNone(source.confidence_verdict)
        self.assertIsNone(source.freshness_state)
        self.assertIsNone(source.assessed_at)

    def test_source_missing_from_confidence_dict(self) -> None:
        source = _publication_source(
            {},
            "mart_monthly_cashflow",
            rationale="test",
            confidence_by_key={"mart_other": _make_snapshot("mart_other", ConfidenceVerdict.TRUSTWORTHY, FreshnessState.CURRENT)},
        )
        self.assertIsNone(source.confidence_verdict)


class BuildAnswerConfidenceTests(unittest.TestCase):
    def _source(
        self,
        key: str,
        verdict: str | None = None,
        freshness: str | None = None,
    ) -> AssistantSourceModel:
        return AssistantSourceModel(
            publication_key=key,
            publication_display_name=key,
            publication_index_path=f"/contracts/publication-index/{key}",
            summary="test",
            rationale="test",
            confidence_verdict=verdict,
            freshness_state=freshness,
        )

    def test_returns_none_when_no_confidence_data(self) -> None:
        sources = [self._source("a"), self._source("b")]
        result = _build_answer_confidence(sources)
        self.assertIsNone(result)

    def test_trustworthy_when_all_current(self) -> None:
        sources = [
            self._source("a", verdict="trustworthy"),
            self._source("b", verdict="trustworthy"),
        ]
        result = _build_answer_confidence(sources)
        assert result is not None
        self.assertEqual(result.overall_verdict, "trustworthy")
        self.assertEqual(result.stale_source_count, 0)
        self.assertEqual(result.total_source_count, 2)
        self.assertIsNone(result.note)

    def test_worst_case_roll_up(self) -> None:
        sources = [
            self._source("a", verdict="trustworthy"),
            self._source("b", verdict="degraded"),
            self._source("c", verdict="unreliable"),
        ]
        result = _build_answer_confidence(sources)
        assert result is not None
        self.assertEqual(result.overall_verdict, "unreliable")
        self.assertEqual(result.stale_source_count, 2)
        self.assertEqual(result.total_source_count, 3)
        self.assertIsNotNone(result.note)

    def test_stale_note_included_when_verdict_degraded(self) -> None:
        sources = [self._source("a", verdict="degraded")]
        result = _build_answer_confidence(sources)
        assert result is not None
        self.assertIsNotNone(result.note)
        self.assertIn("indicative", result.note)

    def test_mixed_none_and_real_verdicts(self) -> None:
        """Sources without confidence data are excluded from the summary count."""
        sources = [
            self._source("a", verdict="trustworthy"),
            self._source("b"),  # no confidence data
        ]
        result = _build_answer_confidence(sources)
        assert result is not None
        self.assertEqual(result.total_source_count, 1)
        self.assertEqual(result.overall_verdict, "trustworthy")


if __name__ == "__main__":
    unittest.main()
