"""Tests for the Prometheus federation ingest worker.

Covers:
- Text-exposition parser corner cases (labels, quotes, escapes, non-numeric samples)
- Sample → fact_cluster_metric row normalisation (instance-to-hostname, timestamps)
- End-to-end federate cycle against a fixture Prometheus (mocked httpx client)
- Status snapshot + typed AdapterRuntimeStatus derivation
- HTTP error handling and error-counter progression
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import httpx
import pytest

from packages.domains.homelab.pipelines.prometheus_federation import (
    PrometheusFederationConfig,
    PrometheusFederationWorker,
    PrometheusSample,
    normalize_samples_to_cluster_rows,
    parse_prometheus_exposition,
)
from packages.platform.adapter_runtime_status import AdapterRuntimeStatus

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class TestParser:
    def test_parses_labelled_sample(self):
        text = 'node_load1{instance="host-a:9100",job="node"} 0.42 1717200000000'
        samples = parse_prometheus_exposition(text)
        assert len(samples) == 1
        s = samples[0]
        assert s.metric_name == "node_load1"
        assert s.labels == {"instance": "host-a:9100", "job": "node"}
        assert s.value == Decimal("0.42")
        assert s.timestamp_ms == 1717200000000

    def test_parses_sample_without_timestamp(self):
        text = 'node_memory_free_bytes{instance="host-b:9100"} 12345'
        samples = parse_prometheus_exposition(text)
        assert len(samples) == 1
        assert samples[0].timestamp_ms is None
        assert samples[0].value == Decimal("12345")

    def test_skips_help_and_type_lines(self):
        text = "\n".join(
            [
                "# HELP node_load1 1-minute load average",
                "# TYPE node_load1 gauge",
                'node_load1{instance="host-a:9100"} 1.5',
                "",
                "  ",
            ]
        )
        samples = parse_prometheus_exposition(text)
        assert len(samples) == 1
        assert samples[0].metric_name == "node_load1"

    def test_parses_multiple_samples_in_order(self):
        text = "\n".join(
            [
                'a{instance="h1:1"} 1',
                'b{instance="h2:1"} 2',
                'c{instance="h3:1"} 3',
            ]
        )
        samples = parse_prometheus_exposition(text)
        assert [s.metric_name for s in samples] == ["a", "b", "c"]

    def test_drops_non_numeric_values(self):
        text = 'node_time_seconds{instance="host-a:9100"} NaN'
        samples = parse_prometheus_exposition(text)
        assert samples == []

    def test_handles_escaped_quotes_in_labels(self):
        text = r'metric{note="hello \"world\""} 1'
        samples = parse_prometheus_exposition(text)
        assert len(samples) == 1
        assert samples[0].labels == {"note": 'hello "world"'}

    def test_handles_no_label_block(self):
        text = "up 1"
        samples = parse_prometheus_exposition(text)
        assert len(samples) == 1
        assert samples[0].metric_name == "up"
        assert samples[0].labels == {}
        assert samples[0].value == Decimal("1")

    def test_ignores_line_with_unclosed_labels(self):
        text = 'broken{instance="x  1'
        samples = parse_prometheus_exposition(text)
        assert samples == []


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


class TestNormaliseSamples:
    def test_maps_instance_label_to_hostname(self):
        samples = [
            PrometheusSample(
                metric_name="node_load1",
                labels={"instance": "host-a:9100"},
                value=Decimal("0.5"),
            )
        ]
        rows = normalize_samples_to_cluster_rows(
            samples,
            default_recorded_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["hostname"] == "host-a"
        assert row["node_name"] == "host-a"
        assert row["metric_name"] == "node_load1"
        assert row["metric_value"] == Decimal("0.5")
        assert row["recorded_at"] == datetime(2026, 6, 1, tzinfo=UTC)

    def test_prefers_nodename_label_over_instance(self):
        samples = [
            PrometheusSample(
                metric_name="node_load1",
                labels={"instance": "10.0.0.1:9100", "nodename": "kube-node-1"},
                value=Decimal("1"),
            )
        ]
        rows = normalize_samples_to_cluster_rows(samples)
        assert rows[0]["hostname"] == "10.0.0.1"
        assert rows[0]["node_name"] == "kube-node-1"

    def test_uses_exposition_timestamp_when_present(self):
        samples = [
            PrometheusSample(
                metric_name="up",
                labels={"instance": "host-c:9100"},
                value=Decimal("1"),
                timestamp_ms=1_717_200_000_000,
            )
        ]
        rows = normalize_samples_to_cluster_rows(
            samples, default_recorded_at=datetime(2000, 1, 1, tzinfo=UTC)
        )
        assert rows[0]["recorded_at"] == datetime.fromtimestamp(
            1_717_200_000, tz=UTC
        )

    def test_skips_samples_without_instance_label(self):
        samples = [
            PrometheusSample(
                metric_name="up",
                labels={"job": "node"},
                value=Decimal("1"),
            )
        ]
        assert normalize_samples_to_cluster_rows(samples) == []

    def test_uses_unit_label_when_present(self):
        samples = [
            PrometheusSample(
                metric_name="node_memory_free_bytes",
                labels={"instance": "host-a:9100", "unit": "bytes"},
                value=Decimal("1024"),
            )
        ]
        rows = normalize_samples_to_cluster_rows(samples)
        assert rows[0]["metric_unit"] == "bytes"


# ---------------------------------------------------------------------------
# Worker sync cycle (with fixture Prometheus)
# ---------------------------------------------------------------------------


FIXTURE_EXPOSITION = "\n".join(
    [
        "# HELP node_load1 1-minute load average",
        "# TYPE node_load1 gauge",
        'node_load1{instance="host-a:9100",job="node"} 0.42 1717200000000',
        'node_load1{instance="host-b:9100",job="node"} 0.81 1717200000000',
        "# HELP node_memory_free_bytes free memory",
        "# TYPE node_memory_free_bytes gauge",
        'node_memory_free_bytes{instance="host-a:9100",job="node"} 12345',
        "",
    ]
)


def _make_worker(
    *,
    exposition: str = FIXTURE_EXPOSITION,
    response_status: int = 200,
    raise_exc: Exception | None = None,
    load_returns: int = 3,
):
    """Build a worker with a mocked httpx.Client returning the fixture."""
    load_fn = MagicMock(return_value=load_returns)

    if raise_exc is None:
        response = httpx.Response(
            response_status,
            text=exposition,
            request=httpx.Request("GET", "http://fixture/federate"),
        )
    else:
        response = None

    client = MagicMock()
    if raise_exc is not None:
        client.get.side_effect = raise_exc
    else:
        client.get.return_value = response

    fixed_clock = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    worker = PrometheusFederationWorker(
        load_fn,
        config=PrometheusFederationConfig(
            prom_url="http://prom.fixture:9090",
            match_selectors=("{job=\"node\"}",),
            bearer_token="TOKEN123",
        ),
        http_client=client,
        clock=lambda: fixed_clock,
    )
    return worker, load_fn, client


class TestWorkerSync:
    def test_sync_hits_federate_endpoint_with_bearer_and_match(self):
        worker, load_fn, client = _make_worker()
        result = worker.sync(run_id="run-1")
        assert result == 3

        client.get.assert_called_once()
        call = client.get.call_args
        assert call.args[0] == "http://prom.fixture:9090/federate"
        assert call.kwargs["params"] == [("match[]", '{job="node"}')]
        assert call.kwargs["headers"]["Authorization"] == "Bearer TOKEN123"

    def test_sync_passes_normalised_rows_to_loader(self):
        worker, load_fn, _client = _make_worker(load_returns=3)
        worker.sync(run_id="run-2")

        load_fn.assert_called_once()
        kwargs = load_fn.call_args.kwargs
        rows = kwargs["rows"]
        assert kwargs["run_id"] == "run-2"
        assert kwargs["source_system"] == "prometheus"
        # Three lines with instance labels → three rows.
        assert len(rows) == 3
        hostnames = sorted({row["hostname"] for row in rows})
        assert hostnames == ["host-a", "host-b"]
        metric_names = sorted({row["metric_name"] for row in rows})
        assert metric_names == ["node_load1", "node_memory_free_bytes"]

    def test_sync_updates_status_on_success(self):
        worker, _load, _client = _make_worker(load_returns=3)
        before = worker.get_status()
        assert before["connected"] is False
        assert before["sync_count"] == 0

        worker.sync()
        s = worker.get_status()
        assert s["connected"] is True
        assert s["sync_count"] == 1
        assert s["last_sample_count"] == 3
        assert s["last_row_count"] == 3
        assert s["error_count"] == 0
        assert s["last_error"] is None
        assert s["last_sync_at"] == "2026-06-01T12:00:00+00:00"

    def test_sync_reports_http_error_and_increments_error_count(self):
        worker, load_fn, _client = _make_worker(
            raise_exc=httpx.ConnectError("boom"),
        )
        result = worker.sync()
        assert result == 0
        load_fn.assert_not_called()

        s = worker.get_status()
        assert s["connected"] is False
        assert s["error_count"] == 1
        assert s["last_error"] == "http_error:ConnectError"

    def test_sync_reports_http_status_error(self):
        request = httpx.Request("GET", "http://prom.fixture:9090/federate")
        response = httpx.Response(500, text="internal error", request=request)
        client = MagicMock()
        client.get.return_value = response

        load_fn = MagicMock(return_value=0)
        worker = PrometheusFederationWorker(
            load_fn,
            config=PrometheusFederationConfig(
                prom_url="http://prom.fixture:9090",
                match_selectors=("{job=\"node\"}",),
            ),
            http_client=client,
        )
        result = worker.sync()
        assert result == 0
        load_fn.assert_not_called()
        assert worker.error_count == 1
        assert worker.last_error is not None
        assert worker.last_error.startswith("http_error:")

    def test_get_runtime_status_returns_typed_snapshot(self):
        worker, _load, _client = _make_worker(load_returns=2)
        worker.sync()

        status = worker.get_runtime_status()
        assert isinstance(status, AdapterRuntimeStatus)
        assert status.enabled is True
        assert status.connected is True
        assert status.extra["sync_count"] == 1
        assert status.extra["last_row_count"] == 2


# ---------------------------------------------------------------------------
# Adapter conformance smoke (redundant with contract tests, but keeps this
# module self-contained during federation refactors).
# ---------------------------------------------------------------------------


def test_prometheus_ingest_adapter_wraps_worker_status():
    from packages.adapters.contracts import IngestAdapter
    from packages.adapters.prometheus_adapter import PrometheusIngestAdapter

    worker, _load, _client = _make_worker(load_returns=2)
    worker.sync()

    adapter = PrometheusIngestAdapter(worker)
    assert isinstance(adapter, IngestAdapter)
    snapshot = adapter.get_status()
    assert snapshot.enabled is True
    assert snapshot.connected is True
    assert snapshot.extra["sync_count"] == 1


@pytest.fixture(autouse=True)
def _no_real_http_client(monkeypatch):
    """Guard against accidental real network use in this module."""
    real_client = httpx.Client

    def _refuse(*_args, **_kwargs):
        raise AssertionError(
            "Federation tests must inject a mocked httpx client — no real "
            "network calls allowed here."
        )

    monkeypatch.setattr(httpx, "Client", _refuse)
    yield
    monkeypatch.setattr(httpx, "Client", real_client)
