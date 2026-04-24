"""Integration test for the freshness remediation → upload-in-context → recovery flow.

Sprint hearth-lantern-path (sprint #29), item #246:
  Freshness remediation flow: stale source is identified via /control/source-freshness,
  operator uploads a correction via /ingest/detect-source + /ingest/configured-csv
  (upload in context), and the freshness endpoint then reflects recovery.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.storage.run_metadata import RunMetadataRepository
from tests.account_test_support import FIXTURES as ACCOUNT_FIXTURES
from tests.control_plane_test_support import seed_source_asset_graph


def _build_client(temp_dir: str) -> TestClient:
    from packages.storage.ingestion_config import IngestionConfigRepository

    repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
    seed_source_asset_graph(repository)
    return TestClient(
        create_app(
            AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            ),
            config_repository=repository,
            enable_unsafe_admin=True,
        )
    )


def test_freshness_shows_registered_source_assets_before_any_ingest() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client(temp_dir)

        response = client.get("/control/source-freshness")
        assert response.status_code == 200
        datasets = response.json()["datasets"]
        assert len(datasets) == 1, "One registered source asset should appear even with no runs"
        asset = datasets[0]
        assert asset["dataset_name"] == "household_account_transactions"
        assert asset["freshness_state"] == "unconfigured"
        assert asset["latest_run_id"] is None
        assert asset["status"] is None
        assert asset["landed_at"] is None


def test_detect_source_identifies_upload_target_and_previews_publications() -> None:
    """Upload-in-context step: before committing, detect the source type and preview
    which publications will recover once the file lands."""
    with TemporaryDirectory() as temp_dir:
        client = _build_client(temp_dir)

        detect_response = client.post(
            "/ingest/detect-source",
            files={
                "file": (
                    "bank-export.csv",
                    (ACCOUNT_FIXTURES / "configured_account_transactions_source.csv").read_bytes(),
                    "text/csv",
                )
            },
        )
        assert detect_response.status_code == 200
        detection = detect_response.json()["detection"]
        assert detection["format"] == "csv"
        candidate = detection["candidate"]
        assert candidate is not None
        assert candidate["kind"] == "configured_csv"
        assert candidate["source_asset_id"] == "bank_partner_transactions"
        # Publication preview shows which datasets recover
        preview = candidate["publication_preview"]
        publication_keys = {e["publication_key"] for e in preview["direct"]}
        assert len(publication_keys) > 0


def test_upload_in_context_recovers_stale_source() -> None:
    """Full remediation flow:
    1. Freshness endpoint shows no datasets (stale / never loaded).
    2. Operator detects the source type and sees publication preview (upload-in-context).
    3. Operator uploads via configured-csv ingest endpoint.
    4. Freshness endpoint now shows the dataset as fresh with a landed status.
    """
    with TemporaryDirectory() as temp_dir:
        client = _build_client(temp_dir)

        # Step 1: source asset is registered but has no run history yet
        before = client.get("/control/source-freshness")
        assert before.status_code == 200
        before_datasets = before.json()["datasets"]
        assert len(before_datasets) == 1
        assert before_datasets[0]["freshness_state"] == "unconfigured"
        assert before_datasets[0]["latest_run_id"] is None

        # Step 2: detect source type as upload-in-context preflight
        detect_response = client.post(
            "/ingest/detect-source",
            files={
                "file": (
                    "bank-export.csv",
                    (ACCOUNT_FIXTURES / "configured_account_transactions_source.csv").read_bytes(),
                    "text/csv",
                )
            },
        )
        assert detect_response.status_code == 200
        candidate = detect_response.json()["detection"]["candidate"]
        assert candidate is not None
        upload_path = candidate["upload_path"]
        assert upload_path == "/upload/configured-csv"

        # Step 3: upload in context via configured-csv ingest
        ingest_response = client.post(
            "/ingest/configured-csv",
            data={
                "source_asset_id": candidate["source_asset_id"],
                "source_name": "remediation-upload",
            },
            files={
                "file": (
                    "bank-export.csv",
                    (ACCOUNT_FIXTURES / "configured_account_transactions_source.csv").read_bytes(),
                    "text/csv",
                )
            },
        )
        assert ingest_response.status_code == 201
        run = ingest_response.json()["run"]
        assert run["status"] == "landed"
        run_id = run["run_id"]

        # Step 4: freshness now reflects recovery — dataset is present and landed
        after = client.get("/control/source-freshness")
        assert after.status_code == 200
        datasets = after.json()["datasets"]
        assert len(datasets) == 1
        recovered = datasets[0]
        assert recovered["dataset_name"] == "household_account_transactions"
        assert recovered["source_asset_id"] == "bank_partner_transactions"
        assert recovered["status"] == "landed"
        assert recovered["latest_run_id"] == run_id
        assert recovered["landed_at"] is not None
        assert "freshness_state" in recovered


def test_failed_ingest_shows_rejected_state_before_remediation() -> None:
    """A rejected run leaves the source in a degraded (rejected) state visible in
    the freshness endpoint. The operator remediates by uploading a corrected file,
    and the freshness state recovers to landed."""
    with TemporaryDirectory() as temp_dir:
        client = _build_client(temp_dir)

        # Ingest a malformed file — missing required columns → 400 rejected
        bad_csv = b"booking_date,account_number,payee\n2026-03-01,FI123,Corner Shop\n"
        bad_ingest = client.post(
            "/ingest/configured-csv",
            data={
                "source_asset_id": "bank_partner_transactions",
                "source_name": "bad-upload",
            },
            files={"file": ("bad.csv", bad_csv, "text/csv")},
        )
        assert bad_ingest.status_code == 400
        assert bad_ingest.json()["run"]["status"] == "rejected"

        # Intermediate state: freshness shows the degraded run
        degraded = client.get("/control/source-freshness")
        assert degraded.status_code == 200
        degraded_datasets = degraded.json()["datasets"]
        assert len(degraded_datasets) == 1
        assert degraded_datasets[0]["status"] == "rejected", (
            "Freshness must reflect the rejected run before remediation"
        )

        # Remediate: upload the correct file
        good_ingest = client.post(
            "/ingest/configured-csv",
            data={
                "source_asset_id": "bank_partner_transactions",
                "source_name": "remediation-upload",
            },
            files={
                "file": (
                    "good.csv",
                    (ACCOUNT_FIXTURES / "configured_account_transactions_source.csv").read_bytes(),
                    "text/csv",
                )
            },
        )
        assert good_ingest.status_code == 201
        assert good_ingest.json()["run"]["status"] == "landed"

        # Recovery: freshness now shows latest run as landed
        recovered = client.get("/control/source-freshness")
        assert recovered.status_code == 200
        recovered_datasets = recovered.json()["datasets"]
        assert len(recovered_datasets) == 1
        assert recovered_datasets[0]["status"] == "landed"


def test_dry_run_previews_file_before_committing_upload() -> None:
    """Dry-run is the validation gate in the upload-in-context flow.
    Operator can preview row count, date range, and issues before confirming ingest."""
    with TemporaryDirectory() as temp_dir:
        client = _build_client(temp_dir)

        dry_run_response = client.post(
            "/ingest/dry-run",
            data={
                "upload_path": "/upload/configured-csv",
                "source_asset_id": "bank_partner_transactions",
            },
            files={
                "file": (
                    "bank-export.csv",
                    (ACCOUNT_FIXTURES / "configured_account_transactions_source.csv").read_bytes(),
                    "text/csv",
                )
            },
        )
        assert dry_run_response.status_code == 200
        preview = dry_run_response.json()["preview"]
        assert preview["ready"] is True
        assert preview["issue_count"] == 0
        assert preview["row_count"] > 0
        assert preview["date_range"] is not None

        # Confirm that the dry run did not create any ingest records
        freshness = client.get("/control/source-freshness")
        datasets = freshness.json()["datasets"]
        assert all(d["latest_run_id"] is None for d in datasets), (
            "Dry run must not land any data"
        )
