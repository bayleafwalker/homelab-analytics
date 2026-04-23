"""End-to-end test for publication confidence snapshot recording and API retrieval.

Tests the full pipeline: TransformationService.refresh_publications() calls
compute_and_record_publication_confidence(), which stores a snapshot in the
control plane. GET /control/confidence then returns that snapshot.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository

TRANSACTION_ROWS = [
    {
        "booked_at": "2026-01-02",
        "account_id": "CHK-001",
        "counterparty_name": "Electric Utility",
        "amount": "-84.15",
        "currency": "EUR",
        "description": "Monthly bill",
    },
    {
        "booked_at": "2026-01-03",
        "account_id": "CHK-001",
        "counterparty_name": "Employer",
        "amount": "2450.00",
        "currency": "EUR",
        "description": "Salary",
    },
]


def test_refresh_publications_records_confidence_and_api_returns_verdict() -> None:
    """End-to-end: refresh_publications -> snapshot stored -> API returns it."""
    with TemporaryDirectory() as temp_dir:
        # 1. Set up control plane store (SQLite)
        temp_path = Path(temp_dir)
        control_plane_store = IngestionConfigRepository(
            temp_path / "config.db"
        )

        # 2. Set up warehouse store (DuckDB in-memory)
        warehouse_store = DuckDBStore.memory()

        # 3. Create TransformationService with both stores
        transformation_service = TransformationService(
            warehouse_store,
            control_plane_store=control_plane_store,
        )

        # 4. Load some transactions to have data in the warehouse
        transformation_service.load_transactions(
            TRANSACTION_ROWS,
            run_id="run-001",
            source_system="test_bank",
        )

        # 5. Call refresh_publications() which triggers confidence snapshot recording
        refreshed = transformation_service.refresh_publications(
            ["mart_monthly_cashflow"]
        )
        assert "mart_monthly_cashflow" in refreshed

        # 6. Set up FastAPI test client with the same control plane store
        account_service = AccountTransactionService(
            landing_root=temp_path / "landing",
            metadata_repository=RunMetadataRepository(temp_path / "runs.db"),
        )
        client = TestClient(
            create_app(
                account_service,
                config_repository=control_plane_store,
                enable_unsafe_admin=True,
            )
        )

        # 7. Query the confidence API
        response = client.get("/control/confidence")
        assert response.status_code == 200

        data = response.json()
        assert "publications" in data
        assert "domain_summaries" in data

        # 8. Assert the snapshot was recorded and returned by the API
        publications = data["publications"]
        assert len(publications) > 0

        # Find the mart_monthly_cashflow publication
        monthly_cashflow_pub = next(
            (pub for pub in publications
             if pub["publication_key"] == "mart_monthly_cashflow"),
            None,
        )
        assert monthly_cashflow_pub is not None, (
            "Expected mart_monthly_cashflow in confidence snapshots; "
            "got: " + ", ".join(pub["publication_key"] for pub in publications)
        )

        # Verify the snapshot has a non-null confidence verdict
        # (may be unavailable or degraded since no real source data)
        assert "confidence_verdict" in monthly_cashflow_pub
        assert monthly_cashflow_pub["confidence_verdict"] is not None
        assert monthly_cashflow_pub["confidence_verdict"].lower() in [
            "unavailable",
            "degraded",
            "unreliable",
            "trustworthy",
        ]

        # Verify assessed_at is present (proof snapshot was computed)
        assert "assessed_at" in monthly_cashflow_pub
        assessed_at_str = monthly_cashflow_pub["assessed_at"]
        # Should be parseable as ISO datetime
        assessed_at = datetime.fromisoformat(assessed_at_str.replace("Z", "+00:00"))
        assert assessed_at is not None
