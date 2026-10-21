"""Closed-window Home Assistant history backfill (feeds HLA-K03 evidence)."""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from apps.worker.command_handlers import build_worker_command_handlers
from apps.worker.command_handlers.ingest_commands import handle_backfill_ha_history
from apps.worker.command_parser import build_parser
from packages.domains.homelab.pipelines.ha_history_backfill import backfill_ha_history
from packages.domains.homelab.pipelines.ha_models import (
    DIM_HA_ENTITY_TABLE,
    FACT_HA_STATE_CHANGE_TABLE,
)
from packages.domains.homelab.pipelines.ha_service import (
    ingest_ha_history_states,
    ingest_ha_states,
)
from packages.storage.duckdb_store import DuckDBStore

START = datetime(2026, 9, 1, tzinfo=UTC)
GRID = "sensor.elisa_kotiakku_grid_power"
PRICE = "sensor.elisa_kotiakku_spot_price"


def _state(entity_id: str, at: datetime, value: str = "1.2") -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "state": value,
        "attributes": {
            "unit_of_measurement": "kW",
            "period_start": at.isoformat(),
            "period_end": (at + timedelta(minutes=5)).isoformat(),
        },
        "last_changed": at.isoformat(),
    }


class FakeHistory:
    """HA ``/api/history/period`` stand-in: one list per entity, filtered by window."""

    def __init__(self, states: list[dict[str, Any]], fail_on: set[str] | None = None) -> None:
        self.states = states
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.fail_on = fail_on or set()

    def __call__(
        self, url: str, headers: dict[str, str], params: dict[str, str]
    ) -> list[list[dict[str, Any]]]:
        self.calls.append((url, params))
        assert headers == {"Authorization": "Bearer token"}
        start = datetime.fromisoformat(url.rsplit("/", 1)[1].replace("%3A", ":").replace("%2B", "+"))
        if start.isoformat() in self.fail_on:
            raise httpx.ConnectError("down")
        end = datetime.fromisoformat(params["end_time"])
        wanted = params["filter_entity_id"].split(",")
        grouped: dict[str, list[dict[str, Any]]] = {}
        for state in self.states:
            at = datetime.fromisoformat(state["last_changed"])
            if state["entity_id"] in wanted and start <= at < end:
                grouped.setdefault(state["entity_id"], []).append(state)
        return list(grouped.values())


def _two_days() -> list[dict[str, Any]]:
    return [
        _state(GRID, START + timedelta(minutes=5 * index), value="1.2")
        for index in range(2 * 288)
    ] + [_state(PRICE, START + timedelta(hours=1))]


def test_backfill_reads_chunks_with_attribute_changes_and_is_idempotent() -> None:
    store = DuckDBStore.memory()
    fake = FakeHistory(_two_days())

    def ingest(states: list[dict[str, Any]], **kwargs: Any) -> dict[str, int]:
        return ingest_ha_history_states(store, states, **kwargs)

    first = backfill_ha_history(
        ingest, ha_url="http://ha:8123/", ha_token="token", entity_ids=[GRID, PRICE, GRID],
        start=START, end=START + timedelta(days=2), fetch=fake, run_id="run-a",
    )
    assert first.chunks == 2
    assert first.inserted == 2 * 288 + 1
    assert first.states_by_entity == {GRID: 576, PRICE: 1}
    assert all(params["significant_changes_only"] == "0" for _, params in fake.calls)
    assert fake.calls[0][0].startswith("http://ha:8123/api/history/period/")
    assert fake.calls[0][1]["filter_entity_id"] == f"{GRID},{PRICE}"

    again = backfill_ha_history(
        ingest, ha_url="http://ha:8123", ha_token="token", entity_ids=[GRID, PRICE],
        start=START, end=START + timedelta(days=2), fetch=fake,
    )
    assert again.inserted == 0
    assert again.skipped_existing == 2 * 288 + 1
    count = store.fetchall(f"SELECT COUNT(*) FROM {FACT_HA_STATE_CHANGE_TABLE}")[0][0]
    assert count == 2 * 288 + 1


def test_backfill_never_moves_entity_recency_backwards() -> None:
    store = DuckDBStore.memory()
    live_at = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
    ingest_ha_states(store, [_state(GRID, live_at, value="3.4")])
    ingest_ha_history_states(store, [_state(GRID, START, value="0.1")], run_id="run-b")
    row = store.fetchall_dicts(
        f"SELECT last_seen, last_state FROM {DIM_HA_ENTITY_TABLE} WHERE entity_id = ?", [GRID]
    )[0]
    assert row["last_state"] == "3.4"
    assert str(row["last_seen"]).startswith("2026-10-21")


def test_failed_chunks_are_reported_not_hidden() -> None:
    store = DuckDBStore.memory()
    fake = FakeHistory(_two_days(), fail_on={(START + timedelta(days=1)).isoformat()})
    result = backfill_ha_history(
        lambda states, **kw: ingest_ha_history_states(store, states, **kw),
        ha_url="http://ha:8123", ha_token="token", entity_ids=[GRID, "sensor.missing"],
        start=START, end=START + timedelta(days=2), fetch=fake,
    )
    payload = result.to_dict()
    assert result.inserted == 288
    assert len(payload["failed_chunks"]) == 1
    assert payload["entities_without_history"] == ["sensor.missing"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"start": START.replace(tzinfo=None)}, "timezone"),
        ({"end": START}, "after start"),
        ({"entity_ids": []}, "entity id"),
    ],
)
def test_invalid_windows_are_refused(kwargs: dict[str, Any], message: str) -> None:
    arguments: dict[str, Any] = {
        "ha_url": "http://ha:8123", "ha_token": "token", "entity_ids": [GRID],
        "start": START, "end": START + timedelta(days=1), "fetch": FakeHistory([]),
    }
    arguments.update(kwargs)
    with pytest.raises(ValueError, match=message):
        backfill_ha_history(lambda states, **kw: {}, **arguments)


def test_worker_command_is_registered_and_requires_ha_credentials() -> None:
    assert "backfill-ha-history" in build_worker_command_handlers()
    args = build_parser().parse_args(["backfill-ha-history", "--month", "2026-09"])
    assert args.month == "2026-09" and args.entity_id == []
    errors = io.StringIO()
    runtime = SimpleNamespace(
        settings=SimpleNamespace(ha_url=None, ha_token=None),
        output=io.StringIO(),
        error_output=errors,
    )
    assert handle_backfill_ha_history(args, runtime) == 1  # type: ignore[arg-type]
    assert "HOMELAB_ANALYTICS_HA_URL" in errors.getvalue()


@pytest.mark.parametrize(("actions_enabled", "expect_dispatcher"), [(True, True), (False, False)])
def test_ha_actions_switch_keeps_bridge_but_drops_dispatcher(
    actions_enabled: bool, expect_dispatcher: bool, tmp_path: Any
) -> None:
    from apps.api.ha_startup import build_ha_startup_runtime
    from packages.shared.settings import AppSettings
    from packages.storage.ingestion_config import IngestionConfigRepository

    settings = AppSettings(
        data_dir=tmp_path,
        landing_root=tmp_path / "landing",
        metadata_database_path=tmp_path / "metadata" / "runs.db",
        account_transactions_inbox_dir=tmp_path / "inbox",
        processed_files_dir=tmp_path / "processed",
        failed_files_dir=tmp_path / "failed",
        api_host="127.0.0.1",
        api_port=8090,
        web_host="127.0.0.1",
        web_port=8091,
        worker_poll_interval_seconds=1,
        ha_url="http://ha:8123",
        ha_token="token",
        ha_actions_enabled=actions_enabled,
    )
    runtime = build_ha_startup_runtime(
        settings,
        transformation_service=SimpleNamespace(
            get_budget_progress_current=lambda: [],
            get_ha_entities=lambda: [],
            ingest_ha_states=lambda *args, **kwargs: None,
        ),
        reporting_service=SimpleNamespace(),
        capability_packs=(),
        control_plane_store=IngestionConfigRepository(tmp_path / "config.db"),
    )
    assert runtime.bridge is not None
    assert (runtime.action_dispatcher is not None) is expect_dispatcher


def test_ha_actions_switch_reads_from_environment() -> None:
    from packages.shared.settings import AppSettings

    assert AppSettings.from_env({}).ha_actions_enabled is True
    assert (
        AppSettings.from_env({"HOMELAB_ANALYTICS_HA_ACTIONS_ENABLED": "false"}).ha_actions_enabled
        is False
    )
