"""Tests for AdapterInstanceRegistry."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from packages.adapters.instance_registry import AdapterInstanceRegistry
from packages.platform.adapter_runtime_status import AdapterRuntimeStatus


def _stub_reporter(**status_kwargs):
    reporter = MagicMock()
    reporter.get_status.return_value = AdapterRuntimeStatus(
        enabled=status_kwargs.get("enabled", True),
        connected=status_kwargs.get("connected", True),
        last_activity_at=status_kwargs.get("last_activity_at"),
        error_count=status_kwargs.get("error_count", 0),
        extra=status_kwargs.get("extra", {}),
    )
    return reporter


def test_register_and_lookup():
    registry = AdapterInstanceRegistry()
    reporter = _stub_reporter()
    registry.register("prom_ingest", reporter)
    assert registry.get("prom_ingest") is reporter


def test_register_empty_key_rejected():
    registry = AdapterInstanceRegistry()
    with pytest.raises(ValueError):
        registry.register("", _stub_reporter())


def test_get_missing_returns_none():
    registry = AdapterInstanceRegistry()
    assert registry.get("nope") is None


def test_unregister_is_idempotent():
    registry = AdapterInstanceRegistry()
    registry.register("prom_ingest", _stub_reporter())
    registry.unregister("prom_ingest")
    registry.unregister("prom_ingest")  # second call must not raise
    assert registry.get("prom_ingest") is None


def test_status_returns_snapshot():
    registry = AdapterInstanceRegistry()
    registry.register(
        "prom_ingest",
        _stub_reporter(last_activity_at="2026-06-01T00:00:00Z", extra={"sync_count": 5}),
    )
    status = registry.status("prom_ingest")
    assert status is not None
    assert status.last_activity_at == "2026-06-01T00:00:00Z"
    assert status.extra["sync_count"] == 5


def test_status_missing_returns_none():
    registry = AdapterInstanceRegistry()
    assert registry.status("nope") is None


def test_keys_are_sorted():
    registry = AdapterInstanceRegistry()
    registry.register("b", _stub_reporter())
    registry.register("a", _stub_reporter())
    registry.register("c", _stub_reporter())
    assert registry.keys() == ["a", "b", "c"]


def test_statuses_returns_map_of_all_registered():
    registry = AdapterInstanceRegistry()
    registry.register("a", _stub_reporter(extra={"sync_count": 1}))
    registry.register("b", _stub_reporter(extra={"sync_count": 2}))
    result = registry.statuses()
    assert set(result.keys()) == {"a", "b"}
    assert result["a"].extra["sync_count"] == 1
    assert result["b"].extra["sync_count"] == 2


def test_re_register_overwrites():
    registry = AdapterInstanceRegistry()
    first = _stub_reporter(extra={"gen": 1})
    second = _stub_reporter(extra={"gen": 2})
    registry.register("prom_ingest", first)
    registry.register("prom_ingest", second)
    status = registry.status("prom_ingest")
    assert status is not None
    assert status.extra["gen"] == 2
