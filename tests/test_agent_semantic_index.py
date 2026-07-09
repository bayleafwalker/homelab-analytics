"""Tests for the LLM-shaped agent semantic index.

Covers the platform builder + payload schema validator and the API surface:

  GET /api/agent/semantic-index
  GET /api/agent/semantic-index/{publication_key}
"""
from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.transformation_service import TransformationService
from packages.platform.agent_semantic_index import (
    AGENT_SEMANTIC_INDEX_SCHEMA_VERSION,
    build_agent_semantic_index,
    validate_agent_semantic_index_payload,
)
from packages.platform.publication_contracts import (
    PublicationColumnContract,
    PublicationContract,
)
from packages.platform.publication_index import build_publication_semantic_index
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository


def _contract(publication_key: str = "mart_demo") -> PublicationContract:
    return PublicationContract(
        publication_key=publication_key,
        relation_name=publication_key,
        schema_name="reporting",
        schema_version="1.0.0",
        display_name="Demo mart",
        description="A demo mart for agent retrieval.",
        pack_name="demo",
        pack_version="1.0.0",
        visibility="household",
        retention_policy="latest",
        lineage_required=True,
        columns=(
            PublicationColumnContract(
                name="booking_month",
                storage_type="VARCHAR",
                json_type="string",
                nullable=False,
                description="Calendar month",
                semantic_role="time_bucket",
                grain="month",
            ),
            PublicationColumnContract(
                name="amount",
                storage_type="DECIMAL(18,2)",
                json_type="string",
                nullable=True,
                description="Amount in EUR",
                semantic_role="measure",
                unit="EUR",
                aggregation="sum",
            ),
        ),
    )


def _semantic_entries(publication_key: str = "mart_demo"):
    return build_publication_semantic_index([_contract(publication_key)], [])


class BuildAgentSemanticIndexTests(unittest.TestCase):
    def test_entry_without_sample_fetcher_has_no_sample(self) -> None:
        entries = build_agent_semantic_index(_semantic_entries())
        self.assertEqual(1, len(entries))
        entry = entries[0]
        self.assertIsNone(entry.sample)
        self.assertEqual("mart_demo", entry.publication_key)
        self.assertEqual("/api/lineage/publication/mart_demo", entry.lineage_path)
        self.assertEqual(
            ["booking_month", "amount"],
            [column.name for column in entry.columns],
        )
        self.assertEqual("EUR", entry.columns[1].unit)

    def test_sample_rows_are_bounded_and_json_safe(self) -> None:
        rows = [
            {"booking_month": f"2026-{month:02d}", "amount": Decimal("1200.50")}
            for month in range(1, 9)
        ]
        entries = build_agent_semantic_index(
            _semantic_entries(),
            sample_fetcher=lambda relation_name: (rows, len(rows)),
            sample_row_limit=5,
        )
        sample = entries[0].sample
        assert sample is not None
        self.assertEqual(5, len(sample.rows))
        self.assertEqual(5, sample.row_count_bound)
        self.assertEqual(8, sample.total_row_count)
        self.assertTrue(sample.truncated)
        self.assertEqual("1200.50", sample.rows[0]["amount"])

    def test_fetcher_returning_none_yields_entry_without_sample(self) -> None:
        entries = build_agent_semantic_index(
            _semantic_entries(),
            sample_fetcher=lambda relation_name: None,
        )
        self.assertIsNone(entries[0].sample)


class PayloadValidatorTests(unittest.TestCase):
    def _valid_payload(self) -> dict:
        entries = build_agent_semantic_index(
            _semantic_entries(),
            sample_fetcher=lambda relation_name: (
                [{"booking_month": "2026-01", "amount": "10.00"}],
                1,
            ),
        )
        return {
            "schema_version": AGENT_SEMANTIC_INDEX_SCHEMA_VERSION,
            "generated_at": "2026-07-09T00:00:00+00:00",
            "publications": [entry.as_dict() for entry in entries],
        }

    def test_valid_payload_passes(self) -> None:
        self.assertEqual([], validate_agent_semantic_index_payload(self._valid_payload()))

    def test_wrong_schema_version_fails(self) -> None:
        payload = self._valid_payload()
        payload["schema_version"] = "0.0.1"
        self.assertTrue(validate_agent_semantic_index_payload(payload))

    def test_missing_column_fields_fail(self) -> None:
        payload = self._valid_payload()
        del payload["publications"][0]["columns"][0]["semantic_role"]
        violations = validate_agent_semantic_index_payload(payload)
        self.assertTrue(any("semantic_role" in violation for violation in violations))

    def test_sample_rows_over_bound_fail(self) -> None:
        payload = self._valid_payload()
        sample = payload["publications"][0]["sample"]
        sample["rows"] = [{"amount": "1"}] * (sample["row_count_bound"] + 1)
        violations = validate_agent_semantic_index_payload(payload)
        self.assertTrue(any("row_count_bound" in violation for violation in violations))


def _build_client(tmp: str, *, load_cashflow: bool = False) -> TestClient:
    from packages.domains.finance.pipelines.account_transaction_service import (
        AccountTransactionService,
    )

    service = AccountTransactionService(
        landing_root=Path(tmp) / "landing",
        metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
    )
    ts = TransformationService(DuckDBStore.memory())
    if load_cashflow:
        ts.load_transactions(
            [
                {
                    "booked_at": "2026-01-03T08:00:00+00:00",
                    "account_id": "checking",
                    "counterparty_name": "Employer",
                    "amount": "3000.00",
                    "currency": "EUR",
                    "description": "salary",
                },
                {
                    "booked_at": "2026-01-10T08:00:00+00:00",
                    "account_id": "checking",
                    "counterparty_name": "Landlord",
                    "amount": "-1200.00",
                    "currency": "EUR",
                    "description": "rent",
                },
            ],
            run_id="run-agent-index-001",
        )
        ts.refresh_monthly_cashflow()
    app = create_app(service, transformation_service=ts)
    return TestClient(app)


class AgentSemanticIndexAPITests(unittest.TestCase):
    def test_index_payload_passes_schema_validation(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/api/agent/semantic-index")
            self.assertEqual(200, resp.status_code)
            payload = resp.json()
            self.assertEqual([], validate_agent_semantic_index_payload(payload))
            self.assertGreater(len(payload["publications"]), 0)

    def test_query_filters_publications(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            everything = client.get("/api/agent/semantic-index").json()
            filtered = client.get(
                "/api/agent/semantic-index", params={"query": "cashflow"}
            ).json()
            self.assertEqual([], validate_agent_semantic_index_payload(filtered))
            self.assertLess(
                len(filtered["publications"]), len(everything["publications"])
            )
            self.assertIn(
                "monthly_cashflow",
                [entry["publication_key"] for entry in filtered["publications"]],
            )

    def test_single_entry_includes_sample_rows_when_data_exists(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp, load_cashflow=True)
            resp = client.get("/api/agent/semantic-index/monthly_cashflow")
            self.assertEqual(200, resp.status_code)
            entry = resp.json()["publication"]
            self.assertEqual("monthly_cashflow", entry["publication_key"])
            sample = entry["sample"]
            self.assertIsNotNone(sample)
            self.assertGreaterEqual(len(sample["rows"]), 1)
            self.assertLessEqual(len(sample["rows"]), sample["row_count_bound"])

    def test_unknown_publication_returns_404(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/api/agent/semantic-index/not_a_publication")
            self.assertEqual(404, resp.status_code)


if __name__ == "__main__":
    unittest.main()
