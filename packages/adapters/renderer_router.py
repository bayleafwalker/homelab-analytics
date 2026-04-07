"""Multi-renderer publication routing.

Routes publication rendering requests to the correct renderer(s) based on
publication key and requested format. Resolves renderers from the active
adapter pack registry.
"""

from __future__ import annotations

from packages.adapters.contracts import RenderedOutput, Renderer
from packages.adapters.registry import AdapterRegistry


class RendererRouter:
    """Routes publication rendering to registered, active renderers.

    Renderers are sourced from packs active in the provided AdapterRegistry.
    A renderer is eligible if:
    - Its pack is active in the registry
    - Its manifest's supported_publication_keys is empty (matches all) OR
      contains the requested publication_key
    - Its manifest's supported_formats contains the requested format
    """

    def __init__(self, registry: AdapterRegistry, renderers: list[Renderer]) -> None:
        """
        Initialize the renderer router.

        Parameters
        ----------
        registry : AdapterRegistry
            Registry for activation state checks.
        renderers : list[Renderer]
            List of live Renderer instances (not manifests) available for routing.
        """
        self._registry = registry
        self._renderers = renderers

    def resolve(self, publication_key: str, format: str) -> list[Renderer]:
        """Resolve renderers eligible for the given publication_key and format.

        A renderer is eligible if:
        - Its pack (looked up by renderer.manifest.renderer_key) is active in
          the registry
        - format is in renderer.manifest.supported_formats
        - renderer.manifest.supported_publication_keys is empty OR
          publication_key is in it

        Parameters
        ----------
        publication_key : str
            The publication key to filter on.
        format : str
            The output format to filter on.

        Returns
        -------
        list[Renderer]
            List of eligible renderers (may be empty).
        """
        eligible = []

        # Get all active packs
        active_packs = self._registry.list_packs(active_only=True)
        active_pack_keys = {pack.pack_key for pack in active_packs}

        for renderer in self._renderers:
            manifest = renderer.manifest
            renderer_key = manifest.renderer_key

            # Check if renderer's pack is active
            # Find the pack containing this renderer's manifest
            pack_is_active = False
            for pack in self._registry.list_packs():
                if any(rm.renderer_key == renderer_key for rm in pack.renderers):
                    if pack.pack_key in active_pack_keys:
                        pack_is_active = True
                    break

            if not pack_is_active:
                continue

            # Check format matches
            if format not in manifest.supported_formats:
                continue

            # Check publication_key matches
            if manifest.supported_publication_keys:
                # Non-empty: must contain the publication_key
                if publication_key not in manifest.supported_publication_keys:
                    continue
            # Empty: matches all publications

            eligible.append(renderer)

        return eligible

    def render_all(
        self, publication_key: str, format: str, rows: list[dict]
    ) -> list[RenderedOutput]:
        """Render using all eligible renderers.

        Calls resolve() then calls renderer.render(publication_key, rows) on
        each eligible renderer.

        Parameters
        ----------
        publication_key : str
            The publication key to render.
        format : str
            The output format.
        rows : list[dict]
            List of row dictionaries to render.

        Returns
        -------
        list[RenderedOutput]
            List of rendered outputs from all eligible renderers (may be empty).
        """
        renderers = self.resolve(publication_key, format)
        outputs = []
        for renderer in renderers:
            output = renderer.render(publication_key, rows)
            outputs.append(output)
        return outputs

    def render_first(
        self, publication_key: str, format: str, rows: list[dict]
    ) -> RenderedOutput | None:
        """Render using the first eligible renderer.

        Like render_all() but returns only the first result, or None if no
        eligible renderers.

        Parameters
        ----------
        publication_key : str
            The publication key to render.
        format : str
            The output format.
        rows : list[dict]
            List of row dictionaries to render.

        Returns
        -------
        RenderedOutput | None
            First rendered output, or None if no eligible renderers.
        """
        renderers = self.resolve(publication_key, format)
        if not renderers:
            return None
        return renderers[0].render(publication_key, rows)
