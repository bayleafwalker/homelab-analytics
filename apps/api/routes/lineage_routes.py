"""End-to-end lineage graph API.

Exposes a single read endpoint:

- ``GET /api/lineage/publication/{publication_key}`` — return the
  publication-rooted lineage graph as typed nodes and edges assembled from
  ``PublicationAuditRecord`` + ``SourceLineageRecord`` in the control plane.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from packages.platform.lineage_graph import build_publication_lineage_graph
from packages.storage.control_plane import ControlPlaneStore


def register_lineage_routes(
    app: FastAPI,
    *,
    control_plane_store: ControlPlaneStore,
) -> None:
    """Register lineage graph API routes."""

    @app.get("/api/lineage/publication/{publication_key}")
    async def get_publication_lineage(publication_key: str) -> dict[str, Any]:
        graph = build_publication_lineage_graph(
            control_plane_store,
            publication_key=publication_key,
        )
        return graph.as_dict()
