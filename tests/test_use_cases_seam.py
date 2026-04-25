"""Unit tests for the thin-transform-facade use-case seam.

Covers:
- packages/application/use_cases/source_ingestion.py
- packages/application/use_cases/run_management.py
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

from packages.application.use_cases.run_management import (
    build_run_detail,
    load_run_manifest_and_context,
    retry_ingest_run,
)
from packages.application.use_cases.source_ingestion import (
    ingest_account_transaction_bytes,
    ingest_configured_csv_bytes,
    ingest_contract_prices_bytes,
    ingest_subscription_bytes,
)
from packages.storage.run_metadata import IngestionRunRecord, IngestionRunStatus


def _make_run(*, passed: bool = True, dataset_name: str = "account_transactions") -> IngestionRunRecord:
    return IngestionRunRecord(
        run_id="run-test-001",
        source_name="test-upload",
        dataset_name=dataset_name,
        file_name="upload.csv",
        raw_path="landing/upload.csv",
        manifest_path="landing/upload.manifest.json",
        sha256="abc123",
        row_count=3,
        header=("date", "amount"),
        status=IngestionRunStatus.LANDED if passed else IngestionRunStatus.FAILED,
        passed=passed,
        issues=[],
        created_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
    )


@dataclass
class _FakeIngestService:
    """Minimal fake that records calls and returns a canned run."""
    run: IngestionRunRecord
    calls: list[dict] = field(default_factory=list)

    def ingest_bytes(self, *, source_bytes: bytes, file_name: str, source_name: str, **kwargs: Any) -> IngestionRunRecord:
        self.calls.append({"method": "ingest_bytes", "file_name": file_name, **kwargs})
        return self.run

    def ingest_file(self, source_path: Any, *, source_name: str, **kwargs: Any) -> IngestionRunRecord:
        self.calls.append({"method": "ingest_file", "source_path": source_path, **kwargs})
        return self.run


class TestSourceIngestionBytes(unittest.TestCase):
    """Tests for the ingest_*_bytes use-case functions."""

    def test_ingest_account_transaction_bytes_no_transformation_service(self) -> None:
        run = _make_run(passed=True)
        svc = _FakeIngestService(run=run)
        published: list = []

        result_run, promotion = ingest_account_transaction_bytes(
            b"data",
            "upload.csv",
            "manual",
            service=svc,  # type: ignore[arg-type]
            transformation_service=None,
            publish_reporting=lambda p: published.append(p),
        )

        self.assertIs(result_run, run)
        self.assertIsNone(promotion)
        self.assertEqual(published, [])
        self.assertEqual(len(svc.calls), 1)
        self.assertEqual(svc.calls[0]["method"], "ingest_bytes")

    def test_ingest_account_transaction_bytes_failed_run_skips_promotion(self) -> None:
        run = _make_run(passed=False)
        svc = _FakeIngestService(run=run)
        promotion_mock = MagicMock(return_value=None)

        _, promotion = ingest_account_transaction_bytes(
            b"data",
            "upload.csv",
            "manual",
            service=svc,  # type: ignore[arg-type]
            transformation_service=MagicMock(),
            publish_reporting=lambda p: None,
        )

        # Failed run → promote_run never called → promotion is None
        self.assertIsNone(promotion)

    def test_ingest_configured_csv_bytes_no_transformation_service(self) -> None:
        run = _make_run(passed=True, dataset_name="household_account_transactions")
        svc = _FakeIngestService(run=run)

        result_run, promotion = ingest_configured_csv_bytes(
            b"data",
            "file.csv",
            service=svc,  # type: ignore[arg-type]
            source_system_id="sys1",
            dataset_contract_id="dc1",
            column_mapping_id="cm1",
            source_asset_id=None,
            source_name="upload",
            source_asset=None,
            config_repository=MagicMock(),  # type: ignore[arg-type]
            transformation_service=None,
            registry=None,
            promotion_handler_registry=None,
            publish_reporting=lambda p: None,
        )

        self.assertIs(result_run, run)
        self.assertIsNone(promotion)

    def test_ingest_configured_csv_bytes_passes_run_context(self) -> None:
        run = _make_run(passed=False)
        svc = _FakeIngestService(run=run)
        ctx = MagicMock()

        ingest_configured_csv_bytes(
            b"data",
            "file.csv",
            service=svc,  # type: ignore[arg-type]
            source_system_id="sys1",
            dataset_contract_id="dc1",
            column_mapping_id="cm1",
            source_asset_id=None,
            source_name="upload",
            source_asset=None,
            config_repository=MagicMock(),  # type: ignore[arg-type]
            transformation_service=None,
            registry=None,
            promotion_handler_registry=None,
            publish_reporting=lambda p: None,
            run_context=ctx,
        )

        self.assertEqual(svc.calls[0]["run_context"], ctx)

    def test_ingest_subscription_bytes_no_transformation_service(self) -> None:
        run = _make_run(passed=True, dataset_name="subscriptions")
        svc = _FakeIngestService(run=run)

        result_run, promotion = ingest_subscription_bytes(
            b"data",
            "subs.csv",
            "manual",
            subscription_service=svc,  # type: ignore[arg-type]
            transformation_service=None,
            publish_reporting=lambda p: None,
        )

        self.assertIs(result_run, run)
        self.assertIsNone(promotion)

    def test_ingest_contract_prices_bytes_failed_run_skips_promotion(self) -> None:
        run = _make_run(passed=False, dataset_name="contract_prices")
        svc = _FakeIngestService(run=run)

        _, promotion = ingest_contract_prices_bytes(
            b"data",
            "prices.csv",
            "manual",
            contract_price_service=svc,  # type: ignore[arg-type]
            transformation_service=None,
            publish_reporting=lambda p: None,
        )

        self.assertIsNone(promotion)


class TestLoadRunManifestAndContext(unittest.TestCase):
    def test_returns_none_when_blob_store_raises_key_error(self) -> None:
        run = _make_run()
        blob_store = MagicMock()
        blob_store.read_bytes.side_effect = KeyError("not found")

        manifest, context = load_run_manifest_and_context(run, blob_store=blob_store)

        self.assertIsNone(manifest)
        self.assertIsNone(context)

    def test_returns_none_when_blob_store_raises_os_error(self) -> None:
        run = _make_run()
        blob_store = MagicMock()
        blob_store.read_bytes.side_effect = OSError("disk error")

        manifest, context = load_run_manifest_and_context(run, blob_store=blob_store)

        self.assertIsNone(manifest)
        self.assertIsNone(context)

    def test_logs_warning_on_missing_manifest(self) -> None:
        import logging
        run = _make_run()
        blob_store = MagicMock()
        blob_store.read_bytes.side_effect = KeyError("missing")
        log_mock = MagicMock(spec=logging.Logger)

        load_run_manifest_and_context(run, blob_store=blob_store, logger=log_mock)

        log_mock.warning.assert_called_once()


class TestBuildRunDetail(unittest.TestCase):
    def test_assembles_detail_from_callable_deps(self) -> None:
        run = _make_run()
        blob_store = MagicMock()
        blob_store.read_bytes.side_effect = KeyError("missing")

        serialize_fn = MagicMock(return_value={"run_id": run.run_id})
        remediation_fn = MagicMock(return_value={"action": "none", "reason": "ok"})

        result = build_run_detail(
            run,
            blob_store=blob_store,
            has_subscription_service=True,
            has_contract_price_service=False,
            serialize_run_fn=serialize_fn,
            build_run_remediation_fn=remediation_fn,
        )

        self.assertEqual(result["run_id"], run.run_id)
        serialize_fn.assert_called_once()
        remediation_fn.assert_called_once()


class TestRetryIngestRun(unittest.TestCase):
    def _make_retry_context(self) -> MagicMock:
        ctx = MagicMock()
        ctx.source_system_id = "sys1"
        ctx.dataset_contract_id = "dc1"
        ctx.column_mapping_id = "cm1"
        ctx.source_asset_id = None
        ctx.ingestion_definition_id = None
        return ctx

    def test_account_transactions_dispatches_to_service(self) -> None:
        run = _make_run(passed=True)
        svc = _FakeIngestService(run=run)

        result_run, _ = retry_ingest_run(
            run,
            "account_transactions",
            b"data",
            self._make_retry_context(),
            service=svc,  # type: ignore[arg-type]
            transformation_service=None,
            publish_reporting=lambda p: None,
        )

        self.assertIs(result_run, run)
        self.assertEqual(svc.calls[0]["method"], "ingest_bytes")

    def test_configured_csv_dispatches_to_configured_service(self) -> None:
        run = _make_run(passed=True, dataset_name="household_account_transactions")
        acct_svc = _FakeIngestService(run=_make_run())
        csv_svc = _FakeIngestService(run=run)
        ctx = self._make_retry_context()

        result_run, _ = retry_ingest_run(
            run,
            "configured_csv",
            b"data",
            ctx,
            service=acct_svc,  # type: ignore[arg-type]
            configured_ingestion_service=csv_svc,  # type: ignore[arg-type]
            config_repository=MagicMock(),  # type: ignore[arg-type]
            transformation_service=None,
            publish_reporting=lambda p: None,
        )

        self.assertIs(result_run, run)
        self.assertEqual(csv_svc.calls[0]["method"], "ingest_bytes")
        self.assertEqual(acct_svc.calls, [])

    def test_subscriptions_dispatches_to_subscription_service(self) -> None:
        run = _make_run(passed=True, dataset_name="subscriptions")
        acct_svc = _FakeIngestService(run=_make_run())
        sub_svc = _FakeIngestService(run=run)

        result_run, _ = retry_ingest_run(
            run,
            "subscriptions",
            b"data",
            self._make_retry_context(),
            service=acct_svc,  # type: ignore[arg-type]
            subscription_service=sub_svc,  # type: ignore[arg-type]
            transformation_service=None,
            publish_reporting=lambda p: None,
        )

        self.assertIs(result_run, run)
        self.assertEqual(sub_svc.calls[0]["method"], "ingest_bytes")

    def test_contract_prices_dispatches_to_contract_price_service(self) -> None:
        run = _make_run(passed=True, dataset_name="contract_prices")
        acct_svc = _FakeIngestService(run=_make_run())
        cp_svc = _FakeIngestService(run=run)

        result_run, _ = retry_ingest_run(
            run,
            "contract_prices",
            b"data",
            self._make_retry_context(),
            service=acct_svc,  # type: ignore[arg-type]
            contract_price_service=cp_svc,  # type: ignore[arg-type]
            transformation_service=None,
            publish_reporting=lambda p: None,
        )

        self.assertIs(result_run, run)
        self.assertEqual(cp_svc.calls[0]["method"], "ingest_bytes")

    def test_unknown_retry_kind_raises_value_error(self) -> None:
        run = _make_run()
        svc = _FakeIngestService(run=run)

        with self.assertRaises(ValueError, msg="Unknown retry_kind"):
            retry_ingest_run(
                run,
                "unknown_kind",
                b"data",
                self._make_retry_context(),
                service=svc,  # type: ignore[arg-type]
                transformation_service=None,
                publish_reporting=lambda p: None,
            )

    def test_run_context_forwarded_to_service(self) -> None:
        run = _make_run()
        svc = _FakeIngestService(run=run)
        ctx = self._make_retry_context()

        retry_ingest_run(
            run,
            "account_transactions",
            b"data",
            ctx,
            service=svc,  # type: ignore[arg-type]
            transformation_service=None,
            publish_reporting=lambda p: None,
        )

        self.assertEqual(svc.calls[0]["run_context"], ctx)
