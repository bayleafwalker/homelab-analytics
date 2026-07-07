"""Prometheus adapter pack — federation ingest and metrics renderer.

Two adapters share the ``prometheus_core`` pack:

- :class:`PrometheusIngestAdapter` wraps a
  :class:`~packages.domains.homelab.pipelines.prometheus_federation.PrometheusFederationWorker`
  and lands cluster metrics into ``fact_cluster_metric``.
- :class:`PrometheusRenderer` implements the Renderer protocol so platform
  metrics can be rendered in the Prometheus text exposition format.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from packages.adapters.contracts import (
    AdapterDirection,
    AdapterManifest,
    AdapterPack,
    RenderedOutput,
    RendererManifest,
    TrustLevel,
)
from packages.platform.adapter_runtime_status import AdapterRuntimeStatus
from packages.shared.metrics import MetricsRegistry

if TYPE_CHECKING:
    from packages.domains.homelab.pipelines.prometheus_federation import (
        PrometheusFederationWorker,
    )


PROMETHEUS_INGEST_MANIFEST = AdapterManifest(
    adapter_key="prom_ingest",
    display_name="Prometheus — Ingest (federation)",
    version="1.0",
    supported_directions=(AdapterDirection.INGEST,),
    supported_entity_classes=("cluster_metric",),
    credential_requirements=("prom_url",),
    health_check_contract=(
        "connected=True after the most recent federate poll succeeded; "
        "last_activity_at reflects the last completed sync"
    ),
    target_capabilities=("federation", "text_exposition"),
)


class PrometheusIngestAdapter:
    """IngestAdapter wrapping :class:`PrometheusFederationWorker`.

    Conforms to the ``IngestAdapter`` protocol from
    :mod:`packages.adapters.contracts`.
    """

    manifest: AdapterManifest = PROMETHEUS_INGEST_MANIFEST

    def __init__(self, worker: PrometheusFederationWorker) -> None:
        self._worker = worker

    def get_status(self) -> AdapterRuntimeStatus:
        raw: dict[str, Any] = self._worker.get_status()
        return AdapterRuntimeStatus(
            enabled=True,
            connected=raw.get("connected", False),
            last_activity_at=raw.get("last_sync_at"),
            error_count=raw.get("error_count", 0),
            extra={
                "sync_count": raw.get("sync_count", 0),
                "last_sample_count": raw.get("last_sample_count", 0),
                "last_row_count": raw.get("last_row_count", 0),
                "last_error": raw.get("last_error"),
            },
        )


PROMETHEUS_RENDERER_MANIFEST = RendererManifest(
    renderer_key="prometheus_metrics",
    display_name="Prometheus Metrics Renderer",
    version="1.0",
    supported_formats=("prometheus_text",),
    supported_publication_keys=(),  # platform-wide, not publication-scoped
)


class PrometheusRenderer:
    """Renderer that outputs platform metrics in Prometheus text format.

    Conforms to the Renderer protocol from packages.adapters.contracts.
    """

    manifest: RendererManifest = PROMETHEUS_RENDERER_MANIFEST

    def __init__(self, metrics_registry: MetricsRegistry) -> None:
        """Initialize the renderer with a metrics registry.

        Parameters
        ----------
        metrics_registry : MetricsRegistry
            The platform metrics registry to render.
        """
        self._registry = metrics_registry

    def render(self, publication_key: str, rows: list[dict]) -> RenderedOutput:
        """Render platform metrics as Prometheus text format.

        The publication_key and rows parameters are ignored — metrics come
        from the registry.

        Parameters
        ----------
        publication_key : str
            Ignored for this renderer (metrics are platform-wide).
        rows : list[dict]
            Ignored for this renderer (metrics come from the registry).

        Returns
        -------
        RenderedOutput
            Rendered output in Prometheus text format.
        """
        content = self._registry.render_prometheus_text().encode("utf-8")
        return RenderedOutput(
            format="prometheus_text",
            content=content,
            content_type="text/plain; version=0.0.4",
        )


PROMETHEUS_ADAPTER_PACK = AdapterPack(
    pack_key="prometheus_core",
    display_name="Prometheus Core",
    version="1.1",
    trust_level=TrustLevel.VERIFIED,
    adapters=(PROMETHEUS_INGEST_MANIFEST,),
    renderers=(PROMETHEUS_RENDERER_MANIFEST,),
    description=(
        "Platform-shipped Prometheus adapter pack. Covers federation ingest "
        "into fact_cluster_metric and metrics renderer for Prometheus text "
        "exposition."
    ),
)
