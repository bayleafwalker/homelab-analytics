"""End-to-end fixture coverage for the flagship finance operator loop.

Sprint cinder-ledger-path (#508), item C5. One synthetic household account
export travels the same path an operator takes in the web UI, through the API
the web shell calls:

    detect source -> upload (configured CSV) -> promotion
      -> source freshness (/control/source-freshness)
      -> monthly finance read (/reports/monthly-cashflow)
      -> publication trust (/control/confidence) and the morning brief
      -> expense-shock scenario with baseline, projected and delta
      -> saved scenario as the next step

A second test covers the degraded branch: a rejected upload shows up as a
source-level remediation cue while the monthly finance read keeps serving the
last good publication, and a corrected upload recovers it.

Fixtures are synthetic and built in-test; nothing reads the demo bundle.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_catalog import SourceFreshnessConfigCreate
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository
from tests.control_plane_test_support import seed_source_asset_graph

SOURCE_ASSET_ID = "bank_partner_transactions"
MONTHLY_CASHFLOW_KEY = "mart_monthly_cashflow"
MONTHS = ("2026-07", "2026-08", "2026-09")
SALARY = Decimal("3000.00")
RENT = Decimal("1200.00")
GROCERIES = Decimal("400.00")

# How the morning brief turns a publication verdict into a claim.
CLAIM_FOR_VERDICT = {
    "trustworthy": "confirmed",
    "degraded": "provisional",
    "unreliable": "withheld",
    "unavailable": "withheld",
}


def _account_export_csv(months: tuple[str, ...] = MONTHS) -> bytes:
    """Synthetic bank-partner export in the source column layout."""
    lines = ["booking_date,account_number,payee,amount_eur,memo"]
    for month in months:
        lines.append(f"{month}-01,CHK-001,Employer,{SALARY},Salary")
        lines.append(f"{month}-05,CHK-001,Landlord,-{RENT},Rent")
        lines.append(f"{month}-12,CHK-001,Supermarket,-{GROCERIES},Groceries")
    return ("\n".join(lines) + "\n").encode()


@dataclass
class LoopHarness:
    client: TestClient
    control_plane: IngestionConfigRepository

    def upload(self, payload: bytes, *, file_name: str, source_name: str):
        return self.client.post(
            "/ingest/configured-csv",
            data={"source_asset_id": SOURCE_ASSET_ID, "source_name": source_name},
            files={"file": (file_name, payload, "text/csv")},
        )

    def configure_freshness(self) -> None:
        """Ad-hoc freshness config: CURRENT whenever a run has landed."""
        self.control_plane.create_source_freshness_config(
            SourceFreshnessConfigCreate(
                source_asset_id=SOURCE_ASSET_ID,
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

    def confidence(self) -> dict:
        response = self.client.get(f"/control/confidence/{MONTHLY_CASHFLOW_KEY}")
        assert response.status_code == 200
        return response.json()

    def cashflow_brief_item(self) -> dict:
        brief = self.client.get("/api/briefing")
        assert brief.status_code == 200
        money = next(
            section for section in brief.json()["sections"] if section["key"] == "money"
        )
        assert MONTHLY_CASHFLOW_KEY in money["publication_keys"]
        return next(
            item
            for item in money["items"]
            if (item.get("confidence") or {}).get("publication_key") == MONTHLY_CASHFLOW_KEY
        )

    def freshness_row(self) -> dict:
        response = self.client.get("/control/source-freshness")
        assert response.status_code == 200
        rows = [
            row
            for row in response.json()["datasets"]
            if row["source_asset_id"] == SOURCE_ASSET_ID
        ]
        assert len(rows) == 1
        return rows[0]

    def monthly_cashflow(self) -> list[dict]:
        response = self.client.get("/reports/monthly-cashflow")
        assert response.status_code == 200
        return response.json()["rows"]


@pytest.fixture
def loop() -> Iterator[LoopHarness]:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        control_plane = IngestionConfigRepository(root / "config.db")
        # Registered source asset only: no pre-seeded lineage, audit or
        # schedule, so every trust signal below comes from this upload.
        seed_source_asset_graph(
            control_plane,
            include_schedule=False,
            include_lineage=False,
            include_audit=False,
        )
        run_metadata = RunMetadataRepository(root / "runs.db")
        # Wired as the runtime builder wires the DuckDB-only path: confidence
        # reads run metadata, and reporting records lineage in the control
        # plane with no Postgres publication store.
        transformation_service = TransformationService(
            DuckDBStore.memory(),
            control_plane_store=control_plane,
            run_metadata_store=run_metadata,
        )
        client = TestClient(
            create_app(
                AccountTransactionService(
                    landing_root=root / "landing",
                    metadata_repository=run_metadata,
                ),
                config_repository=control_plane,
                transformation_service=transformation_service,
                reporting_service=ReportingService(
                    transformation_service,
                    control_plane_store=control_plane,
                ),
                enable_unsafe_admin=True,
            )
        )
        yield LoopHarness(client=client, control_plane=control_plane)


def test_finance_operator_loop_from_upload_to_expense_shock(loop: LoopHarness) -> None:
    client = loop.client
    export = _account_export_csv()

    # 1. Before any upload the source is registered but has never landed.
    before = loop.freshness_row()
    assert before["latest_run_id"] is None
    assert before["freshness_state"] == "unconfigured"
    assert loop.monthly_cashflow() == []
    # The operator gives the source asset a freshness expectation.
    loop.configure_freshness()

    # 2. Detection names the configured asset and previews the monthly
    #    finance publication the upload will refresh.
    detect = client.post(
        "/ingest/detect-source",
        files={"file": ("statement.csv", export, "text/csv")},
    )
    assert detect.status_code == 200
    candidate = detect.json()["detection"]["candidate"]
    assert candidate["source_asset_id"] == SOURCE_ASSET_ID
    assert candidate["upload_path"] == "/upload/configured-csv"
    previewed = {entry["publication_key"] for entry in candidate["publication_preview"]["direct"]}
    assert MONTHLY_CASHFLOW_KEY in previewed

    # 3. Upload lands and promotes in the same request.
    upload = loop.upload(export, file_name="statement.csv", source_name="operator-upload")
    assert upload.status_code == 201
    body = upload.json()
    run_id = body["run"]["run_id"]
    assert body["run"]["status"] == "landed"
    assert body["run"]["row_count"] == 3 * len(MONTHS)
    promotion = body["promotion"]
    assert promotion["skipped"] is False
    assert promotion["facts_loaded"] == 3 * len(MONTHS)
    assert MONTHLY_CASHFLOW_KEY in promotion["marts_refreshed"]
    assert MONTHLY_CASHFLOW_KEY in promotion["publication_keys"]

    # 4. Source freshness attributes the run to its own source asset.
    after = loop.freshness_row()
    assert after["latest_run_id"] == run_id
    assert after["status"] == "landed"
    assert after["landed_at"] is not None

    # 5. The monthly finance read reflects exactly what was uploaded.
    expected_expense = RENT + GROCERIES
    rows = loop.monthly_cashflow()
    assert [row["booking_month"] for row in rows] == list(MONTHS)
    for row in rows:
        assert Decimal(row["income"]) == SALARY
        assert Decimal(row["expense"]) == expected_expense
        assert Decimal(row["net"]) == SALARY - expected_expense
        assert row["transaction_count"] == 3

    # 6. Publication trust: confidence attributes the run to its source
    #    asset, finds that asset's freshness config, and with a clean,
    #    complete landing the monthly cashflow publication is trustworthy.
    snapshot = loop.confidence()
    verdict = snapshot["confidence_verdict"]
    assert verdict == "trustworthy"
    assert snapshot["freshness_state"] == "current"
    assert snapshot["completeness_pct"] == 100
    assert snapshot["contributing_run_ids"] == [run_id]
    assert snapshot["assessed_at"] is not None
    listed = {
        pub["publication_key"]: pub for pub in client.get("/control/confidence").json()["publications"]
    }
    assert listed[MONTHLY_CASHFLOW_KEY]["confidence_verdict"] == verdict

    # 7. The morning brief states cashflow as far as that verdict allows:
    #    confirmed, not withheld.
    cashflow_item = loop.cashflow_brief_item()
    assert cashflow_item["confidence"]["verdict"] == verdict
    assert cashflow_item["claim_status"] == CLAIM_FOR_VERDICT[verdict] == "confirmed"
    assert cashflow_item["lineage_publication_key"] == MONTHLY_CASHFLOW_KEY

    # 8. Expense shock from the same finance story: baseline, projected, delta.
    shock = client.post("/api/scenarios/expense-shock", json={"expense_pct_delta": "0.10"})
    assert shock.status_code == 200
    scenario = shock.json()
    baseline = Decimal(scenario["baseline_monthly_expense"])
    projected = Decimal(scenario["new_monthly_expense"])
    assert baseline == expected_expense
    assert projected == baseline * Decimal("1.10")
    assert Decimal(scenario["annual_additional_cost"]) == (projected - baseline) * 12
    # Income still covers the shocked expenses, so no deficit is projected.
    assert scenario["months_until_deficit"] is None
    assert scenario["is_stale"] is False

    cashflow = client.get(f"/api/scenarios/{scenario['scenario_id']}/cashflow")
    assert cashflow.status_code == 200
    projection = cashflow.json()["cashflow_rows"]
    assert projection
    for row in projection:
        assert Decimal(row["scenario_expense"]) > Decimal(row["baseline_expense"])
        assert Decimal(row["net_delta"]) < 0

    # 9. Next step: the scenario is saved and addressable for comparison.
    saved = client.get(f"/api/scenarios/{scenario['scenario_id']}")
    assert saved.status_code == 200
    assert saved.json()["scenario_id"] == scenario["scenario_id"]


def test_rejected_upload_surfaces_remediation_and_keeps_last_good_finance_read(
    loop: LoopHarness,
) -> None:
    good = loop.upload(_account_export_csv(), file_name="statement.csv", source_name="operator-upload")
    assert good.status_code == 201
    good_rows = loop.monthly_cashflow()
    assert len(good_rows) == len(MONTHS)

    # A malformed export (missing the amount column) is rejected at landing.
    bad_payload = b"booking_date,account_number,payee\n2026-10-01,CHK-001,Corner Shop\n"
    bad = loop.upload(bad_payload, file_name="broken.csv", source_name="operator-upload")
    assert bad.status_code == 400
    bad_run = bad.json()["run"]
    assert bad_run["status"] == "rejected"
    assert "promotion" not in bad.json()

    # Source-level remediation: Sources shows the rejected run, and the run
    # detail names a concrete action from the shared vocabulary.
    degraded = loop.freshness_row()
    assert degraded["latest_run_id"] == bad_run["run_id"]
    assert degraded["status"] == "rejected"
    run_detail = loop.client.get(f"/runs/{bad_run['run_id']}")
    assert run_detail.status_code == 200
    remediation = run_detail.json()["run"]["remediation"]
    assert remediation["action"] in {"fix_contract", "upload_missing_period"}
    assert remediation["reason"]

    # The monthly finance read is not corrupted by the rejected file.
    assert loop.monthly_cashflow() == good_rows

    # A corrected upload for the next month recovers the source and extends
    # the monthly finance read.
    fixed = loop.upload(
        _account_export_csv(("2026-10",)),
        file_name="statement-october.csv",
        source_name="operator-upload",
    )
    assert fixed.status_code == 201
    recovered = loop.freshness_row()
    assert recovered["status"] == "landed"
    assert recovered["latest_run_id"] == fixed.json()["run"]["run_id"]
    assert [row["booking_month"] for row in loop.monthly_cashflow()] == [*MONTHS, "2026-10"]


def test_unconfigured_source_asset_keeps_cashflow_withheld(loop: LoopHarness) -> None:
    """Without a freshness config for its asset the verdict stays unavailable."""
    upload = loop.upload(
        _account_export_csv(), file_name="statement.csv", source_name="operator-upload"
    )
    assert upload.status_code == 201
    run_id = upload.json()["run"]["run_id"]

    snapshot = loop.confidence()
    # The run is attributed (completeness is known) but its asset has no
    # freshness expectation, so trust is not claimed.
    assert snapshot["contributing_run_ids"] == [run_id]
    assert snapshot["completeness_pct"] == 100
    assert snapshot["freshness_state"] == "unavailable"
    assert snapshot["confidence_verdict"] == "unavailable"

    cashflow_item = loop.cashflow_brief_item()
    assert cashflow_item["claim_status"] == "withheld"
    assert cashflow_item["remediation"]
