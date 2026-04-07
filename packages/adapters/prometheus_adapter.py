"""Prometheus metrics adapter — renders platform metrics in Prometheus text format.

Implements the Renderer protocol so Prometheus scrape output can be routed
through the standard adapter/renderer pipeline.
"""

from __future__ import annotations

from packages.adapters.contracts import AdapterPack, RenderedOutput, RendererManifest, TrustLevel
from packages.shared.metrics import MetricsRegistry

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
    display_name="Prometheus Metrics",
    version="1.0",
    trust_level=TrustLevel.VERIFIED,
    adapters=(),
    renderers=(PROMETHEUS_RENDERER_MANIFEST,),
    description="Platform-shipped Prometheus metrics renderer. Renders MetricsRegistry state as Prometheus text exposition format.",
)
