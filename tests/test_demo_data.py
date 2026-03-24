from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

pytest.importorskip("reportlab")

from apps.worker.main import main
from packages.demo.bundle import (
    COMMON_ACCOUNT_ARTIFACT_ID,
    PERSONAL_ACCOUNT_ARTIFACT_ID,
    REVOLUT_ACCOUNT_ARTIFACT_ID,
    load_demo_manifest,
    write_demo_bundle,
)
from packages.demo.seeder import (
    DEMO_ACCOUNT_CONTRACT_ID,
    _build_transformation_service,
    _ensure_demo_account_bindings,
    seed_demo_data,
)
from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.promotion import promote_source_asset_run
from packages.platform.runtime.builder import build_container
from packages.shared.settings import AppSettings


def _make_settings(temp_root: Path) -> AppSettings:
    return AppSettings(
        data_dir=temp_root / "data",
        landing_root=temp_root / "landing",
        metadata_database_path=temp_root / "metadata" / "runs.db",
        account_transactions_inbox_dir=temp_root / "inbox" / "account-transactions",
        processed_files_dir=temp_root / "processed" / "account-transactions",
        failed_files_dir=temp_root / "failed" / "account-transactions",
        api_host="127.0.0.1",
        api_port=8090,
        web_host="127.0.0.1",
        web_port=8091,
        worker_poll_interval_seconds=1,
    )


def test_demo_bundle_generation_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    first_dir = tmp_path / "demo-a"
    second_dir = tmp_path / "demo-b"

    first_manifest = write_demo_bundle(first_dir)
    second_manifest = write_demo_bundle(second_dir)

    assert first_manifest == second_manifest
    assert {row["artifact_id"] for row in first_manifest["artifacts"]} >= {
        PERSONAL_ACCOUNT_ARTIFACT_ID,
        COMMON_ACCOUNT_ARTIFACT_ID,
        REVOLUT_ACCOUNT_ARTIFACT_ID,
    }
    required_fields = {
        "artifact_id",
        "relative_path",
        "source_family",
        "format",
        "intended_dataset_name",
        "ingest_support",
        "sha256",
        "size_bytes",
    }
    for row in first_manifest["artifacts"]:
        assert required_fields.issubset(row.keys())


def test_demo_bundle_outputs_are_public_and_privacy_safe(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo"
    write_demo_bundle(output_dir)

    forbidden_markers = [
        b"Huotari",
        b"JUHA",
        b"Hyttitie",
        b"positiivinenluottotietorekisteri.fi/extracts/",
        b"47611153958",
    ]
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        content = path.read_bytes()
        for marker in forbidden_markers:
            assert marker not in content, f"Found private marker {marker!r} in {path}"


def test_generated_op_and_revolut_sources_preview_and_promote(tmp_path: Path) -> None:
    demo_dir = tmp_path / "demo"
    write_demo_bundle(demo_dir)
    settings = _make_settings(tmp_path)
    container = build_container(
        settings,
        capability_packs=[FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK],
    )
    manifest = load_demo_manifest(demo_dir)
    artifact_by_id = {
        str(row["artifact_id"]): row for row in manifest["artifacts"] if "artifact_id" in row
    }
    _, asset_ids = _ensure_demo_account_bindings(
        container.control_plane_store,
        input_dir=demo_dir,
        artifact_by_id=artifact_by_id,
    )
    transformation_service = _build_transformation_service(settings, container)
    configured_csv_service = ConfiguredCsvIngestionService(
        landing_root=settings.landing_root,
        metadata_repository=container.run_metadata_store,
        config_repository=container.control_plane_store,
        blob_store=container.blob_store,
        function_registry=container.function_registry,
    )

    preview = configured_csv_service.preview_mapping(
        source_bytes=(
            demo_dir / str(artifact_by_id[PERSONAL_ACCOUNT_ARTIFACT_ID]["relative_path"])
        ).read_bytes(),
        source_system_id="demo_op_personal_export",
        dataset_contract_id=DEMO_ACCOUNT_CONTRACT_ID,
        column_mapping_id="demo_op_personal_mapping_v1",
        preview_limit=2,
    )
    assert preview.source_header[0] == "Kirjauspäivä"
    assert preview.mapped_header == [
        "booked_at",
        "account_id",
        "counterparty_name",
        "amount",
        "currency",
        "description",
    ]
    assert preview.issues == []

    revolut_preview = configured_csv_service.preview_mapping(
        source_bytes=(
            demo_dir / str(artifact_by_id[REVOLUT_ACCOUNT_ARTIFACT_ID]["relative_path"])
        ).read_bytes(),
        source_system_id="demo_revolut_export",
        dataset_contract_id=DEMO_ACCOUNT_CONTRACT_ID,
        column_mapping_id="demo_revolut_mapping_v1",
        preview_limit=2,
    )
    assert revolut_preview.source_header[:3] == ["Type", "Product", "Started Date"]
    assert revolut_preview.issues == []

    for artifact_id in (
        PERSONAL_ACCOUNT_ARTIFACT_ID,
        COMMON_ACCOUNT_ARTIFACT_ID,
        REVOLUT_ACCOUNT_ARTIFACT_ID,
    ):
        source_asset = container.control_plane_store.get_source_asset(asset_ids[artifact_id])
        source_path = demo_dir / str(artifact_by_id[artifact_id]["relative_path"])
        run = configured_csv_service.ingest_file(
            source_path=source_path,
            source_system_id=source_asset.source_system_id,
            dataset_contract_id=source_asset.dataset_contract_id,
            column_mapping_id=source_asset.column_mapping_id,
            source_asset_id=source_asset.source_asset_id,
            source_name=str(artifact_by_id[artifact_id]["source_name"]),
        )
        assert run.passed
        promotion = promote_source_asset_run(
            run.run_id,
            source_asset=source_asset,
            config_repository=container.control_plane_store,
            landing_root=settings.landing_root,
            metadata_repository=container.run_metadata_store,
            transformation_service=transformation_service,
            blob_store=container.blob_store,
            extension_registry=container.extension_registry,
            promotion_handler_registry=container.promotion_handler_registry,
        )
        assert not promotion.skipped

    assert len(transformation_service.get_monthly_cashflow()) > 0


def test_seed_demo_data_populates_reporting_and_is_idempotent(tmp_path: Path) -> None:
    demo_dir = tmp_path / "demo"
    write_demo_bundle(demo_dir)
    settings = _make_settings(tmp_path)

    first_summary = seed_demo_data(settings, demo_dir)
    assert first_summary["reporting_counts"]["monthly_cashflow"] > 0
    assert first_summary["reporting_counts"]["subscription_summary"] > 0
    assert first_summary["reporting_counts"]["utility_cost_summary"] > 0
    assert first_summary["reporting_counts"]["budget_variance"] > 0
    assert first_summary["reporting_counts"]["loan_overview"] > 0

    second_summary = seed_demo_data(settings, demo_dir)
    assert second_summary["reporting_counts"] == first_summary["reporting_counts"]
    assert any(run["duplicate"] for run in second_summary["runs"])


def test_worker_cli_can_generate_and_seed_demo_data(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    output_dir = tmp_path / "demo-cli"

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = main(
        ["generate-demo-data", "--output-dir", str(output_dir)],
        stdout=stdout,
        stderr=stderr,
        settings=settings,
    )
    assert exit_code == 0
    generate_payload = json.loads(stdout.getvalue())
    assert generate_payload["artifact_count"] >= 10
    assert (output_dir / "manifest.json").exists()

    stdout = io.StringIO()
    exit_code = main(
        ["seed-demo-data", "--input-dir", str(output_dir)],
        stdout=stdout,
        stderr=stderr,
        settings=settings,
    )
    assert exit_code == 0
    seed_payload = json.loads(stdout.getvalue())
    assert seed_payload["reporting_counts"]["monthly_cashflow"] > 0
