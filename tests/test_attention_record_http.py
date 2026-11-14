"""HTTP regression tests for the attention-record adapter at the warehouse boundary.

The frozen ``tests/test_attention_record_api.py`` covers the public 200/404/503
contract. These tests exercise the same endpoints through the real
``WarehouseSessionManager`` lease/acquisition boundary, proving that a synthetic
driver failure is sanitized into an availability 503, a ``WarehouseBusyError``
keeps its established 503 with ``Retry-After``, and an unrelated programming
error stays a server error rather than being misreported as unavailable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

import duckdb
import pytest
from fastapi.testclient import TestClient

import packages.storage.duckdb_store as duckdb_store
from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.reporting_service import ReportingAccessMode, ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.pipelines.warehouse_session import (
    WarehouseSessionManager,
    WarehouseSessionTransformationService,
    _ReadOnlyTransformationService,
)
from packages.storage.duckdb_store import DuckDBStore, WarehouseBusyError
from packages.storage.run_metadata import RunMetadataRepository
from tests.test_attention_record_api import REFRESH_KEYS, seed, source_key


def _seed_warehouse(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "warehouse.duckdb"
    store = DuckDBStore.open(str(path))
    try:
        ts = TransformationService(store)
        seed(ts)
        ts.refresh_publications(REFRESH_KEYS)
        rows = store.fetchall_dicts("SELECT * FROM mart_transaction_anomalies_current")
        assert rows
        item_id = source_key("anomaly", rows[0])
    finally:
        store.close()
    return path, item_id


def _client(tmp_path: Path, path: Path) -> tuple[TestClient, WarehouseSessionManager]:
    def build(leased_store: Any, read_only: bool) -> TransformationService:
        if read_only:
            return _ReadOnlyTransformationService(leased_store)
        return TransformationService(leased_store)

    manager = WarehouseSessionManager(path, build, idle_timeout_seconds=0)
    session_ts = WarehouseSessionTransformationService(manager)
    reporting = ReportingService(session_ts, access_mode=ReportingAccessMode.WAREHOUSE)
    service = AccountTransactionService(
        landing_root=tmp_path / "landing",
        metadata_repository=RunMetadataRepository(tmp_path / "runs.db"),
    )
    client = TestClient(
        create_app(service, transformation_service=session_ts, reporting_service=reporting),
        raise_server_exceptions=False,
    )
    return client, manager


def _raise(exc: BaseException) -> Any:
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise exc

    return fail


def test_record_warehouse_acquisition_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, item_id = _seed_warehouse(tmp_path)
    client, manager = _client(tmp_path, path)
    url = "/reports/transaction-anomalies/records/" + quote(item_id, safe="")
    marker = "synthetic-private-acquisition-marker"
    failures = {
        "driver": duckdb.IOException(marker),
        "busy": WarehouseBusyError("synthetic", 1, RuntimeError("held")),
        "program": RuntimeError(marker),
    }
    try:
        assert client.get(url).status_code == 200
        assert manager.mode is None
        for kind, failure in failures.items():
            with monkeypatch.context() as patch:
                patch.setattr(duckdb_store, "connect_with_lock_retry", _raise(failure))
                response = client.get(url)
            assert manager.mode is None
            if kind == "driver":
                assert response.status_code == 503, response.text
                assert set(response.json()) == {"detail"}
                assert marker not in response.text
            elif kind == "busy":
                assert response.status_code == 503, response.text
                body = response.json()
                assert set(body) == {"error", "retry_after_seconds"}
                assert response.headers.get("retry-after") == str(body["retry_after_seconds"])
            else:
                assert response.status_code == 500, response.text
            assert client.get(url).status_code == 200
            assert manager.mode is None
    finally:
        manager.stop()
