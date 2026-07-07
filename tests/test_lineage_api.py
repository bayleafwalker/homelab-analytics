"""API-level tests for the /api/lineage/publication/{key} endpoint."""
from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.transformation_service import TransformationService
from packages.storage.control_plane import (
    PublicationAuditCreate,
    SourceLineageCreate,
)
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository


def _build_client(tmp: str) -> tuple[TestClient, TransformationService]:
    from packages.domains.finance.pipelines.account_transaction_service import (
        AccountTransactionService,
    )

    service = AccountTransactionService(
        landing_root=Path(tmp) / "landing",
        metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
    )
    ts = TransformationService(DuckDBStore.memory())
    app = create_app(
        service,
        transformation_service=ts,
        enable_unsafe_admin=True,
    )
    return TestClient(app), ts


def _seed_lineage(app_state) -> None:
    """Write a small lineage graph directly into the in-memory control plane.

    The default create_app path builds an IngestionConfigRepository backed by
    a temp SQLite; it satisfies the SourceLineageStore + PublicationAuditStore
    Protocols. We reuse it here so the assembly path is exercised end-to-end.
    """
    store = app_state.control_plane_store
    store.record_publication_audit(
        (
            PublicationAuditCreate(
                publication_audit_id="a1",
                run_id="run-100",
                publication_key="mart_monthly_cashflow",
                relation_name="mart_monthly_cashflow",
                status="published",
                published_at=datetime(2026, 6, 5, tzinfo=UTC),
            ),
        )
    )
    store.record_source_lineage(
        (
            SourceLineageCreate(
                lineage_id="L1",
                input_run_id="run-100",
                target_layer="reporting",
                target_name="mart_monthly_cashflow",
                target_kind="mart",
                row_count=250,
                source_system="home_assistant",
                source_run_id="ha-42",
            ),
        )
    )


class LineageGraphAPITests(unittest.TestCase):
    def test_empty_graph_returns_publication_node_only(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            resp = client.get("/api/lineage/publication/nothing_ingested_yet")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual("nothing_ingested_yet", data["publication_key"])
            self.assertEqual(1, len(data["nodes"]))
            self.assertEqual("publication", data["nodes"][0]["type"])
            self.assertEqual([], data["edges"])

    def test_seeded_graph_returns_source_run_publication_chain(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            _seed_lineage(client.app.state)

            resp = client.get("/api/lineage/publication/mart_monthly_cashflow")
            self.assertEqual(200, resp.status_code)
            data = resp.json()

            node_types = {node["type"] for node in data["nodes"]}
            self.assertEqual(
                {"publication", "run", "relation", "source"}, node_types
            )

            edge_types = {edge["type"] for edge in data["edges"]}
            self.assertEqual({"publishes", "produces", "sources"}, edge_types)

            publishes = next(e for e in data["edges"] if e["type"] == "publishes")
            self.assertEqual("run:run-100", publishes["from"])
            self.assertEqual("publication:mart_monthly_cashflow", publishes["to"])
            self.assertEqual("published", publishes["attributes"]["status"])

            source_edge = next(e for e in data["edges"] if e["type"] == "sources")
            self.assertEqual("source:home_assistant", source_edge["from"])
            self.assertEqual("run:run-100", source_edge["to"])
            self.assertEqual("ha-42", source_edge["attributes"]["source_run_id"])

    def test_graph_is_json_serialisable_and_deterministic(self) -> None:
        with TemporaryDirectory() as tmp:
            client, _ = _build_client(tmp)
            _seed_lineage(client.app.state)

            first = client.get("/api/lineage/publication/mart_monthly_cashflow").json()
            second = client.get("/api/lineage/publication/mart_monthly_cashflow").json()
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
