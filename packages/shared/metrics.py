"""In-process metrics registry rendered in the Prometheus text exposition format.

Supports counters and gauges (optionally labelled) and cumulative histograms.
Each process (API, worker) owns one module-level :data:`metrics_registry`;
values that must be consistent across processes are derived from durable
stores at scrape time instead (see ``apps/api/ops_metrics.py``).
"""

from __future__ import annotations

import hmac
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from threading import Lock

LabelSet = tuple[tuple[str, str], ...]

# Seconds. Covers sub-10ms API reads up to multi-minute publication refreshes.
DEFAULT_LATENCY_BUCKETS: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    60.0,
    120.0,
    300.0,
)


@dataclass(frozen=True)
class _MetricSample:
    name: str
    help_text: str
    metric_type: str
    value: float
    labels: LabelSet = ()


@dataclass
class _HistogramState:
    bucket_counts: list[int]
    total: float = 0.0
    count: int = 0


@dataclass
class _Family:
    help_text: str
    metric_type: str
    buckets: tuple[float, ...] = ()
    values: dict[LabelSet, float] = field(default_factory=dict)
    histograms: dict[LabelSet, _HistogramState] = field(default_factory=dict)


def _label_set(labels: Mapping[str, object] | None) -> LabelSet:
    if not labels:
        return ()
    return tuple(sorted((str(key), str(value)) for key, value in labels.items()))


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _escape_help(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n")


def _render_labels(labels: LabelSet, extra: tuple[str, str] | None = None) -> str:
    pairs = list(labels)
    if extra is not None:
        pairs.append(extra)
    if not pairs:
        return ""
    body = ",".join(f'{key}="{_escape_label_value(value)}"' for key, value in pairs)
    return "{" + body + "}"


def _format_value(value: float) -> str:
    if math.isinf(value):
        return "+Inf" if value > 0 else "-Inf"
    if math.isnan(value):
        return "NaN"
    if value.is_integer():
        return str(int(value))
    return repr(value)


def _format_bound(bound: float) -> str:
    if math.isinf(bound):
        return "+Inf"
    return repr(float(bound))


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._families: dict[str, _Family] = {}

    def _family(
        self,
        name: str,
        *,
        help_text: str,
        metric_type: str,
        buckets: tuple[float, ...] = (),
    ) -> _Family:
        family = self._families.get(name)
        if family is None or family.metric_type != metric_type:
            family = _Family(help_text=help_text, metric_type=metric_type, buckets=buckets)
            self._families[name] = family
        else:
            family.help_text = help_text
        return family

    def inc(
        self,
        name: str,
        amount: float = 1.0,
        *,
        help_text: str,
        metric_type: str = "counter",
        labels: Mapping[str, object] | None = None,
    ) -> None:
        with self._lock:
            family = self._family(name, help_text=help_text, metric_type=metric_type)
            key = _label_set(labels)
            family.values[key] = family.values.get(key, 0.0) + float(amount)

    def set(
        self,
        name: str,
        value: float,
        *,
        help_text: str,
        metric_type: str = "gauge",
        labels: Mapping[str, object] | None = None,
    ) -> None:
        with self._lock:
            family = self._family(name, help_text=help_text, metric_type=metric_type)
            family.values[_label_set(labels)] = float(value)

    def replace_series(
        self,
        name: str,
        series: Sequence[tuple[Mapping[str, object], float]],
        *,
        help_text: str,
        metric_type: str = "gauge",
    ) -> None:
        """Atomically replace every labelled series of a family.

        Used for scrape-time gauges (per-source freshness, verdict counts) so a
        source that disappears stops being exported instead of going stale.
        """
        with self._lock:
            family = self._family(name, help_text=help_text, metric_type=metric_type)
            family.values = {_label_set(labels): float(value) for labels, value in series}

    def declare_histogram(
        self,
        name: str,
        *,
        help_text: str,
        buckets: Sequence[float] = DEFAULT_LATENCY_BUCKETS,
    ) -> None:
        with self._lock:
            self._family(
                name,
                help_text=help_text,
                metric_type="histogram",
                buckets=tuple(sorted(float(bound) for bound in buckets)),
            )

    def observe(
        self,
        name: str,
        value: float,
        *,
        help_text: str,
        buckets: Sequence[float] = DEFAULT_LATENCY_BUCKETS,
        labels: Mapping[str, object] | None = None,
    ) -> None:
        with self._lock:
            family = self._family(
                name,
                help_text=help_text,
                metric_type="histogram",
                buckets=tuple(sorted(float(bound) for bound in buckets)),
            )
            key = _label_set(labels)
            state = family.histograms.get(key)
            if state is None:
                state = _HistogramState(bucket_counts=[0] * len(family.buckets))
                family.histograms[key] = state
            for index, bound in enumerate(family.buckets):
                if value <= bound:
                    state.bucket_counts[index] += 1
            state.total += float(value)
            state.count += 1

    def snapshot(self) -> list[_MetricSample]:
        """Return counter/gauge samples (histograms are rendered separately)."""
        with self._lock:
            return [
                _MetricSample(
                    name=name,
                    help_text=family.help_text,
                    metric_type=family.metric_type,
                    value=value,
                    labels=labels,
                )
                for name, family in sorted(self._families.items())
                if family.metric_type != "histogram"
                for labels, value in sorted(family.values.items())
            ]

    def value(self, name: str, labels: Mapping[str, object] | None = None) -> float | None:
        with self._lock:
            family = self._families.get(name)
            if family is None:
                return None
            return family.values.get(_label_set(labels))

    def clear(self) -> None:
        with self._lock:
            self._families.clear()

    def render_prometheus_text(self) -> str:
        lines: list[str] = []
        with self._lock:
            for name, family in sorted(self._families.items()):
                lines.append(f"# HELP {name} {_escape_help(family.help_text)}")
                lines.append(f"# TYPE {name} {family.metric_type}")
                if family.metric_type == "histogram":
                    for labels, state in sorted(family.histograms.items()):
                        for bound, bucket_count in zip(family.buckets, state.bucket_counts):
                            lines.append(
                                f"{name}_bucket"
                                f"{_render_labels(labels, ('le', _format_bound(bound)))}"
                                f" {bucket_count}"
                            )
                        lines.append(
                            f"{name}_bucket{_render_labels(labels, ('le', '+Inf'))} {state.count}"
                        )
                        lines.append(f"{name}_sum{_render_labels(labels)} {_format_value(state.total)}")
                        lines.append(f"{name}_count{_render_labels(labels)} {state.count}")
                    continue
                for labels, value in sorted(family.values.items()):
                    lines.append(f"{name}{_render_labels(labels)} {_format_value(value)}")
        return "\n".join(lines) + ("\n" if lines else "")


metrics_registry = MetricsRegistry()

# Scrape auth uses its own Authorization scheme so the API's bearer pipeline
# (service tokens, machine JWT, OIDC) never sees, logs, or rejects it.
# Prometheus: ``authorization: {type: Metrics, credentials_file: ...}``.
METRICS_AUTH_SCHEME = "Metrics"


def scrape_token_matches(authorization_header: str | None, expected_token: str | None) -> bool:
    """True when no scrape token is configured or the header carries it."""
    if not expected_token:
        return True
    if not authorization_header:
        return False
    scheme, _, credentials = authorization_header.strip().partition(" ")
    if scheme.lower() != METRICS_AUTH_SCHEME.lower():
        return False
    return hmac.compare_digest(credentials.strip().encode(), expected_token.encode())
