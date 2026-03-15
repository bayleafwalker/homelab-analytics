from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class _MetricSample:
    name: str
    help_text: str
    metric_type: str
    value: float


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._help: dict[str, str] = {}
        self._types: dict[str, str] = {}
        self._values: defaultdict[str, float] = defaultdict(float)

    def inc(self, name: str, amount: float = 1.0, *, help_text: str, metric_type: str = "counter") -> None:
        with self._lock:
            self._help[name] = help_text
            self._types[name] = metric_type
            self._values[name] += float(amount)

    def set(self, name: str, value: float, *, help_text: str, metric_type: str = "gauge") -> None:
        with self._lock:
            self._help[name] = help_text
            self._types[name] = metric_type
            self._values[name] = float(value)

    def snapshot(self) -> list[_MetricSample]:
        with self._lock:
            return [
                _MetricSample(
                    name=name,
                    help_text=self._help[name],
                    metric_type=self._types[name],
                    value=self._values[name],
                )
                for name in sorted(self._values)
            ]

    def clear(self) -> None:
        with self._lock:
            self._help.clear()
            self._types.clear()
            self._values.clear()

    def render_prometheus_text(self) -> str:
        lines: list[str] = []
        for sample in self.snapshot():
            lines.append(f"# HELP {sample.name} {sample.help_text}")
            lines.append(f"# TYPE {sample.name} {sample.metric_type}")
            value = int(sample.value) if sample.value.is_integer() else sample.value
            lines.append(f"{sample.name} {value}")
        return "\n".join(lines) + ("\n" if lines else "")


metrics_registry = MetricsRegistry()
