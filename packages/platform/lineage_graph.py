"""End-to-end lineage graph traversal.

Assemble a typed node/edge graph rooted at a publication_key by joining
``PublicationAuditRecord`` and ``SourceLineageRecord`` from the control-plane
store. The graph exposes the source→landing→transformation→publication chain
that operators need to answer "which source run produced this publication?".

Design
------
- Node types: ``publication``, ``run``, ``relation``, ``source``.
- Edge types: ``publishes`` (run → publication), ``produces`` (run → relation),
  ``sources`` (source → run).
- Relations carry their ``layer`` field ("landing", "transformation",
  "reporting", …) so a viewer can lay them out by pipeline stage.
- The graph is intentionally shallow: the current lineage schema records
  each hop as a flat (source_run_id → target) row, so we render the fan-out
  from a publication rather than walking further upstream than the recorded
  ``source_run_id`` allows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Protocol, runtime_checkable

from packages.storage.control_plane import PublicationAuditRecord, SourceLineageRecord

NODE_PUBLICATION = "publication"
NODE_RUN = "run"
NODE_RELATION = "relation"
NODE_SOURCE = "source"

EDGE_PUBLISHES = "publishes"
EDGE_PRODUCES = "produces"
EDGE_SOURCES = "sources"


@runtime_checkable
class LineageStore(Protocol):
    """Structural type for the control-plane lookups we need."""

    def list_publication_audit(
        self,
        *,
        run_id: str | None = None,
        publication_key: str | None = None,
    ) -> list[PublicationAuditRecord]:
        ...

    def list_source_lineage(
        self,
        *,
        input_run_id: str | None = None,
        target_layer: str | None = None,
        target_name: str | None = None,
        source_asset_id: str | None = None,
    ) -> list[SourceLineageRecord]:
        ...


@dataclass(frozen=True)
class LineageNode:
    """One node in the assembled lineage graph."""

    id: str
    type: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type, "attributes": dict(self.attributes)}


@dataclass(frozen=True)
class LineageEdge:
    """One directed, typed edge in the assembled lineage graph."""

    from_id: str
    to_id: str
    type: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_id,
            "to": self.to_id,
            "type": self.type,
            "attributes": dict(self.attributes),
        }


@dataclass(frozen=True)
class LineageGraph:
    """A publication-rooted lineage graph."""

    publication_key: str
    nodes: tuple[LineageNode, ...]
    edges: tuple[LineageEdge, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "publication_key": self.publication_key,
            "nodes": [node.as_dict() for node in self.nodes],
            "edges": [edge.as_dict() for edge in self.edges],
        }


def _publication_node_id(key: str) -> str:
    return f"{NODE_PUBLICATION}:{key}"


def _run_node_id(run_id: str) -> str:
    return f"{NODE_RUN}:{run_id}"


def _relation_node_id(layer: str, name: str) -> str:
    return f"{NODE_RELATION}:{layer}:{name}"


def _source_node_id(source_system: str) -> str:
    return f"{NODE_SOURCE}:{source_system}"


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def build_publication_lineage_graph(
    store: LineageStore,
    *,
    publication_key: str,
) -> LineageGraph:
    """Assemble the lineage graph rooted at ``publication_key``.

    The graph is deterministic: node and edge ordering is sorted so equal
    inputs render the same JSON on every call. Duplicate lineage rows (same
    input_run_id + target_name) collapse to one edge.
    """
    audit_records = store.list_publication_audit(publication_key=publication_key)
    nodes: dict[str, LineageNode] = {}
    edges: dict[tuple[str, str, str], LineageEdge] = {}

    publication_id = _publication_node_id(publication_key)
    nodes[publication_id] = LineageNode(
        id=publication_id,
        type=NODE_PUBLICATION,
        attributes={"key": publication_key},
    )

    relation_names: set[str] = set()

    for record in audit_records:
        if record.run_id:
            run_id = _run_node_id(record.run_id)
            if run_id not in nodes:
                nodes[run_id] = LineageNode(
                    id=run_id,
                    type=NODE_RUN,
                    attributes={"run_id": record.run_id},
                )
            edge_key = (run_id, publication_id, EDGE_PUBLISHES)
            if edge_key not in edges:
                edges[edge_key] = LineageEdge(
                    from_id=run_id,
                    to_id=publication_id,
                    type=EDGE_PUBLISHES,
                    attributes={
                        "status": record.status,
                        "relation_name": record.relation_name,
                        "published_at": _iso(record.published_at),
                    },
                )
        relation_names.add(record.relation_name)

    lineage_records = _collect_lineage_for_relations(store, relation_names)
    for lineage_record in lineage_records:
        if not lineage_record.input_run_id:
            continue
        run_id = _run_node_id(lineage_record.input_run_id)
        relation_id = _relation_node_id(lineage_record.target_layer, lineage_record.target_name)
        if run_id not in nodes:
            nodes[run_id] = LineageNode(
                id=run_id,
                type=NODE_RUN,
                attributes={"run_id": lineage_record.input_run_id},
            )
        if relation_id not in nodes:
            nodes[relation_id] = LineageNode(
                id=relation_id,
                type=NODE_RELATION,
                attributes={
                    "layer": lineage_record.target_layer,
                    "name": lineage_record.target_name,
                    "kind": lineage_record.target_kind,
                },
            )
        produce_key = (run_id, relation_id, EDGE_PRODUCES)
        if produce_key not in edges:
            edges[produce_key] = LineageEdge(
                from_id=run_id,
                to_id=relation_id,
                type=EDGE_PRODUCES,
                attributes={
                    "row_count": lineage_record.row_count,
                    "target_kind": lineage_record.target_kind,
                    "recorded_at": _iso(lineage_record.recorded_at),
                },
            )
        if lineage_record.source_system:
            source_id = _source_node_id(lineage_record.source_system)
            if source_id not in nodes:
                nodes[source_id] = LineageNode(
                    id=source_id,
                    type=NODE_SOURCE,
                    attributes={"source_system": lineage_record.source_system},
                )
            source_key = (source_id, run_id, EDGE_SOURCES)
            if source_key not in edges:
                edges[source_key] = LineageEdge(
                    from_id=source_id,
                    to_id=run_id,
                    type=EDGE_SOURCES,
                    attributes={"source_run_id": lineage_record.source_run_id},
                )

    sorted_nodes = tuple(sorted(nodes.values(), key=lambda n: (n.type, n.id)))
    sorted_edges = tuple(
        sorted(edges.values(), key=lambda e: (e.type, e.from_id, e.to_id))
    )
    return LineageGraph(
        publication_key=publication_key,
        nodes=sorted_nodes,
        edges=sorted_edges,
    )


def _collect_lineage_for_relations(
    store: LineageStore, relation_names: Iterable[str]
) -> list[SourceLineageRecord]:
    """Fetch lineage records matching any relation_name in ``relation_names``.

    Iterates each name to keep the store interface unchanged. Deduplication is
    handled by the caller via the edges dict.
    """
    seen: set[str] = set()
    collected: list[SourceLineageRecord] = []
    for name in sorted(relation_names):
        for record in store.list_source_lineage(target_name=name):
            if record.lineage_id in seen:
                continue
            seen.add(record.lineage_id)
            collected.append(record)
    return collected
