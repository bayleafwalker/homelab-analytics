"""Prometheus federation ingest worker.

Pulls cluster metrics from a Prometheus server via the /federate endpoint
(text exposition format) and lands them into ``fact_cluster_metric`` through
:func:`load_cluster_metric_rows`.

Design rules
------------
- Federation was chosen over remote-read: the text-exposition response is
  parseable without protobuf/snappy dependencies and matches how homelab
  Prometheus instances already expose federated metrics.
- The worker keeps no long-lived socket. A ``sync()`` call performs one
  request/parse/load cycle. Higher-level orchestration schedules the polling
  cadence — the worker itself stays test-friendly.
- Only single-sample-per-line exposition is supported (federation output).
  HELP/TYPE/comment lines and empty lines are skipped.
- Sample normalisation folds each sample's ``instance`` label into the
  ``hostname`` mart column (port stripped), preserves ``__name__`` as
  ``metric_name``, and uses a millisecond timestamp when the exposition
  carries one; otherwise ``recorded_at`` is set to the worker's clock.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

import httpx

from packages.platform.adapter_runtime_status import AdapterRuntimeStatus

logger = logging.getLogger("homelab_analytics.prometheus_federation")

SOURCE_SYSTEM = "prometheus"


@dataclass(frozen=True)
class PrometheusSample:
    """One parsed exposition sample."""

    metric_name: str
    labels: dict[str, str]
    value: Decimal
    timestamp_ms: int | None = None


# ---------------------------------------------------------------------------
# Text-format parser
# ---------------------------------------------------------------------------


def parse_prometheus_exposition(text: str) -> list[PrometheusSample]:
    """Parse a Prometheus text exposition payload.

    Supports the shape emitted by ``/federate``: one sample per non-empty,
    non-comment line, optional millisecond timestamp trailing the value.
    ``HELP`` and ``TYPE`` comment lines are ignored.

    Parameters
    ----------
    text:
        Raw response body from ``GET /federate?match[]=...``.

    Returns
    -------
    list[PrometheusSample]
        Parsed samples, preserving source order. Lines that fail to parse
        are skipped and logged at DEBUG.
    """
    samples: list[PrometheusSample] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parsed = _parse_sample_line(line)
        if parsed is not None:
            samples.append(parsed)
    return samples


def _parse_sample_line(line: str) -> PrometheusSample | None:
    """Parse a single ``metric{labels} value [timestamp_ms]`` line."""
    labels: dict[str, str] = {}
    lb = line.find("{")
    if lb == -1:
        # No labels; split on whitespace.
        name, _, rest = line.partition(" ")
        rest = rest.strip()
        if not name or not rest:
            return None
    else:
        name = line[:lb].strip()
        rb = _find_labels_close(line, lb)
        if rb == -1:
            logger.debug("prom_federation: unclosed label section: %r", line)
            return None
        labels = _parse_label_block(line[lb + 1 : rb])
        rest = line[rb + 1 :].strip()
    return _finish_sample(name, labels, rest)


def _find_labels_close(line: str, lb: int) -> int:
    """Find the matching ``}`` for the label block, respecting quotes."""
    in_quote = False
    escape = False
    for idx in range(lb + 1, len(line)):
        ch = line[idx]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_quote = not in_quote
            continue
        if ch == "}" and not in_quote:
            return idx
    return -1


def _parse_label_block(block: str) -> dict[str, str]:
    """Parse the inner text of ``{ ... }`` into a label dict."""
    labels: dict[str, str] = {}
    i = 0
    while i < len(block):
        # Skip commas and whitespace between labels.
        while i < len(block) and block[i] in ", \t":
            i += 1
        eq = block.find("=", i)
        if eq == -1:
            break
        key = block[i:eq].strip()
        # Value is a quoted string.
        if eq + 1 >= len(block) or block[eq + 1] != '"':
            break
        j = eq + 2
        value_chars: list[str] = []
        while j < len(block):
            ch = block[j]
            if ch == "\\" and j + 1 < len(block):
                nxt = block[j + 1]
                if nxt == "n":
                    value_chars.append("\n")
                elif nxt == "\\":
                    value_chars.append("\\")
                elif nxt == '"':
                    value_chars.append('"')
                else:
                    value_chars.append(nxt)
                j += 2
                continue
            if ch == '"':
                j += 1
                break
            value_chars.append(ch)
            j += 1
        if key:
            labels[key] = "".join(value_chars)
        i = j
    return labels


def _finish_sample(
    name: str, labels: dict[str, str], rest: str
) -> PrometheusSample | None:
    parts = rest.split()
    if not parts:
        return None
    try:
        value = Decimal(parts[0])
    except InvalidOperation:
        # Prometheus text format uses "NaN", "+Inf", "-Inf" for non-numeric
        # samples. We drop these — they are not useful for the mart.
        logger.debug("prom_federation: non-numeric sample dropped: %r", rest)
        return None
    if not value.is_finite():
        # Decimal accepts "NaN"/"Infinity"; skip these — the mart column is
        # a fixed-precision DECIMAL and cannot represent them.
        logger.debug("prom_federation: non-finite sample dropped: %r", rest)
        return None
    ts_ms: int | None = None
    if len(parts) >= 2:
        try:
            ts_ms = int(parts[1])
        except ValueError:
            ts_ms = None
    return PrometheusSample(
        metric_name=name,
        labels=labels,
        value=value,
        timestamp_ms=ts_ms,
    )


# ---------------------------------------------------------------------------
# Sample → mart-row normalisation
# ---------------------------------------------------------------------------


def normalize_samples_to_cluster_rows(
    samples: list[PrometheusSample],
    *,
    default_recorded_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Map exposition samples onto ``fact_cluster_metric`` row dicts.

    Rules
    -----
    - ``hostname`` comes from the ``instance`` label with its port suffix
      stripped. If the sample has no ``instance`` label, it is skipped —
      the cluster mart is keyed on host identity.
    - ``node_name`` prefers a ``nodename`` label; otherwise it falls back
      to ``hostname``.
    - ``metric_unit`` uses a ``unit`` label when the exposition carries one.
    - ``recorded_at`` uses the exposition timestamp when present, else the
      caller-supplied ``default_recorded_at`` (typically the sync clock).
    """
    now = default_recorded_at or datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    for sample in samples:
        instance = sample.labels.get("instance", "").strip()
        if not instance:
            continue
        hostname = instance.split(":", 1)[0]
        if not hostname:
            continue
        node_name = sample.labels.get("nodename") or hostname
        recorded_at = (
            datetime.fromtimestamp(sample.timestamp_ms / 1000, tz=UTC)
            if sample.timestamp_ms is not None
            else now
        )
        rows.append(
            {
                "hostname": hostname,
                "node_name": node_name,
                "recorded_at": recorded_at,
                "metric_name": sample.metric_name,
                "metric_value": sample.value,
                "metric_unit": sample.labels.get("unit", ""),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Federation worker
# ---------------------------------------------------------------------------


LoadClusterMetricRowsFn = Callable[..., int]
"""Callable with the signature of
``packages.domains.homelab.pipelines.transformation_infrastructure.load_cluster_metric_rows``.
"""


@dataclass
class PrometheusFederationConfig:
    """Config for the federation worker."""

    prom_url: str
    match_selectors: tuple[str, ...]
    bearer_token: str | None = None
    request_timeout_seconds: float = 15.0


class PrometheusFederationWorker:
    """Polling worker that federates Prometheus samples into ``fact_cluster_metric``.

    The worker is deliberately synchronous. ``sync()`` performs a single
    federate/parse/load cycle and returns the number of fact rows written.
    Higher-level orchestration decides how often to call ``sync()``.
    """

    def __init__(
        self,
        load_rows_fn: LoadClusterMetricRowsFn,
        *,
        config: PrometheusFederationConfig,
        http_client: httpx.Client | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._load_rows = load_rows_fn
        self._config = config
        self._http = http_client
        self._owns_http = http_client is None
        self._clock = clock

        # Status fields.
        self.connected: bool = False
        self.last_sync_at: str | None = None
        self.last_sample_count: int = 0
        self.last_row_count: int = 0
        self.sync_count: int = 0
        self.error_count: int = 0
        self.last_error: str | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """Return the worker's current status snapshot."""
        return {
            "connected": self.connected,
            "last_sync_at": self.last_sync_at,
            "sync_count": self.sync_count,
            "last_sample_count": self.last_sample_count,
            "last_row_count": self.last_row_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
        }

    def get_runtime_status(self) -> AdapterRuntimeStatus:
        """Return the typed adapter runtime status."""
        return AdapterRuntimeStatus(
            enabled=True,
            connected=self.connected,
            last_activity_at=self.last_sync_at,
            error_count=self.error_count,
            extra={
                "sync_count": self.sync_count,
                "last_sample_count": self.last_sample_count,
                "last_row_count": self.last_row_count,
                "last_error": self.last_error,
            },
        )

    def close(self) -> None:
        """Release the HTTP client if the worker owns it."""
        if self._owns_http and self._http is not None:
            self._http.close()
            self._http = None

    def sync(
        self,
        *,
        run_id: str | None = None,
        record_lineage: Callable[..., None] | None = None,
        store: Any = None,
    ) -> int:
        """Run one federation cycle and load samples into the mart.

        Parameters
        ----------
        run_id:
            Optional run identifier propagated into the fact rows.
        record_lineage:
            Callable matching the signature expected by
            ``load_cluster_metric_rows``. When ``None``, a no-op is used.
        store:
            DuckDB store the load function writes into. Optional so the
            worker can be exercised with an in-memory or fake store.

        Returns
        -------
        int
            The number of fact rows inserted this cycle.
        """
        record_lineage = record_lineage or (lambda **_: None)
        try:
            text = self._fetch_federate()
        except httpx.HTTPError as exc:
            self.connected = False
            self.error_count += 1
            self.last_error = f"http_error:{exc.__class__.__name__}"
            logger.warning("prom_federation: HTTP error: %s", exc)
            return 0

        samples = parse_prometheus_exposition(text)
        rows = normalize_samples_to_cluster_rows(
            samples, default_recorded_at=self._clock()
        )
        inserted = self._load_rows(
            store,
            rows=rows,
            record_lineage=record_lineage,
            run_id=run_id,
            source_system=SOURCE_SYSTEM,
        )

        self.connected = True
        self.last_sync_at = self._clock().isoformat()
        self.sync_count += 1
        self.last_sample_count = len(samples)
        self.last_row_count = inserted
        self.last_error = None
        return inserted

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fetch_federate(self) -> str:
        """Issue one federate request and return the response body."""
        client = self._ensure_client()
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("match[]", selector) for selector in self._config.match_selectors
        ]
        headers: dict[str, str] = {}
        if self._config.bearer_token:
            headers["Authorization"] = f"Bearer {self._config.bearer_token}"
        url = self._config.prom_url.rstrip("/") + "/federate"
        response = client.get(
            url,
            params=params,
            headers=headers,
            timeout=self._config.request_timeout_seconds,
        )
        response.raise_for_status()
        return response.text

    def _ensure_client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(timeout=self._config.request_timeout_seconds)
        return self._http
