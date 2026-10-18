"""End-to-end lineage graph API.

Exposes a single read endpoint:

- ``GET /api/lineage/publication/{publication_key}`` — return the
  publication-rooted lineage graph as typed nodes and edges assembled from
  ``PublicationAuditRecord`` + ``SourceLineageRecord`` in the control plane.
  ``run_limit`` bounds how many of the most recent runs are walked; the
  response says ``truncated`` (with ``total_runs``) when older runs were left
  out.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Query

from packages.platform.lineage_graph import (
    DEFAULT_RUN_LIMIT,
    MAX_RUN_LIMIT,
    build_publication_lineage_graph,
)
from packages.storage.control_plane import ControlPlaneStore


def register_lineage_routes(
    app: FastAPI,
    *,
    control_plane_store: ControlPlaneStore,
) -> None:
    """Register lineage graph API routes."""

    @app.get("/api/lineage/publication/{publication_key}")
    async def get_publication_lineage(
        publication_key: str,
        run_limit: int = Query(
            DEFAULT_RUN_LIMIT,
            ge=1,
            le=MAX_RUN_LIMIT,
            description="Walk only this many of the most recent runs behind the publication.",
        ),
    ) -> dict[str, Any]:
        graph = build_publication_lineage_graph(
            control_plane_store,
            publication_key=publication_key,
            run_limit=run_limit,
        )
        return graph.as_dict()
