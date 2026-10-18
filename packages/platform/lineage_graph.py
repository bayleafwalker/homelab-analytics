"""End-to-end lineage graph traversal.

Assemble a typed node/edge graph rooted at a publication_key by joining
``PublicationAuditRecord`` and ``SourceLineageRecord`` from the control-plane
store. The graph exposes the source→landing→transformation→publication chain
that operators need to answer "which source run produced this publication?".

Design
------
- Node types: ``publication``, ``run``, ``relation``, ``source``.
- Edge types: ``publishes`` (run → publication), ``produces`` (run → relation),
  ``sources`` (source → run), ``feeds`` (transformation relation → the
  reporting relation the same run rebuilt).
- Relations carry their ``layer`` field ("landing", "transformation",
  "reporting", …) so a viewer can lay them out by pipeline stage.
- The lineage schema records each hop as a flat (run → target) row. From the
  runs behind a publication the graph also walks each run's landing
  (source asset) and transformation rows, so a publication shows the real
  chain source asset → run → transformation relations → mart. It never walks
  past the runs themselves.
- The walk is bounded: only the ``run_limit`` most recent runs (by publication
  or lineage timestamp, default ``DEFAULT_RUN_LIMIT``) are walked and shown,
  so a publication refreshed for years does not cost one lookup per run ever
  recorded. ``truncated`` and ``total_runs`` say when runs were left out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Iterable, Protocol, runtime_checkable

from packages.storage.control_plane import PublicationAuditRecord, SourceLineageRecord

NODE_PUBLICATION = "publication"
NODE_RUN = "run"
NODE_RELATION = "relation"
NODE_SOURCE = "source"

EDGE_PUBLISHES = "publishes"
EDGE_PRODUCES = "produces"
EDGE_SOURCES = "sources"
EDGE_FEEDS = "feeds"

LAYER_LANDING = "landing"
LAYER_TRANSFORMATION = "transformation"
UPSTREAM_LAYERS = (LAYER_LANDING, LAYER_TRANSFORMATION)

# Runs walked per graph unless the caller asks for another bound.
DEFAULT_RUN_LIMIT = 50
MAX_RUN_LIMIT = 500


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
    # Runs behind the publication before the cap, and whether some were left out.
    total_runs: int = 0
    run_limit: int | None = None
    truncated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "publication_key": self.publication_key,
            "nodes": [node.as_dict() for node in self.nodes],
            "edges": [edge.as_dict() for edge in self.edges],
            "total_runs": self.total_runs,
            "run_limit": self.run_limit,
            "truncated": self.truncated,
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


def _sort_key(value: datetime) -> datetime:
    # Stores return aware timestamps; treat a naive one as UTC so the two
    # never get compared directly.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _select_runs(
    audit_records: Iterable[PublicationAuditRecord],
    lineage_records: Iterable[SourceLineageRecord],
    run_limit: int | None,
) -> tuple[set[str], int]:
    """The ``run_limit`` most recent run ids, and how many runs there are."""
    latest: dict[str, datetime] = {}
    for run_id, stamp in [
        *((r.run_id, r.published_at) for r in audit_records),
        *((r.input_run_id, r.recorded_at) for r in lineage_records),
    ]:
        if not run_id:
            continue
        stamp = _sort_key(stamp)
        if run_id not in latest or stamp > latest[run_id]:
            latest[run_id] = stamp
    ordered = sorted(latest, key=lambda run_id: (latest[run_id], run_id), reverse=True)
    if run_limit is not None:
        ordered = ordered[:run_limit]
    return set(ordered), len(latest)


def build_publication_lineage_graph(
    store: LineageStore,
    *,
    publication_key: str,
    run_limit: int | None = DEFAULT_RUN_LIMIT,
) -> LineageGraph:
    """Assemble the lineage graph rooted at ``publication_key``.

    The graph is deterministic: node and edge ordering is sorted so equal
    inputs render the same JSON on every call. Duplicate lineage rows (same
    input_run_id + target_name) collapse to one edge.

    Only the ``run_limit`` most recent runs are walked (``None`` walks all);
    older runs, their edges and their upstream rows are left out and the
    graph is marked ``truncated``.
    """
    if run_limit is not None and run_limit < 1:
        raise ValueError("run_limit must be at least 1")
    all_audit_records = store.list_publication_audit(publication_key=publication_key)
    relation_names: set[str] = {record.relation_name for record in all_audit_records}
    all_lineage_records = _collect_lineage_for_relations(store, relation_names)
    kept_runs, total_runs = _select_runs(all_audit_records, all_lineage_records, run_limit)
    audit_records = [
        record for record in all_audit_records if not record.run_id or record.run_id in kept_runs
    ]
    lineage_records = [
        record
        for record in all_lineage_records
        if not record.input_run_id or record.input_run_id in kept_runs
    ]
    nodes: dict[str, LineageNode] = {}
    edges: dict[tuple[str, str, str], LineageEdge] = {}

    publication_id = _publication_node_id(publication_key)
    nodes[publication_id] = LineageNode(
        id=publication_id,
        type=NODE_PUBLICATION,
        attributes={"key": publication_key},
    )

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

    known_ids = {record.lineage_id for record in lineage_records}
    upstream_records = [
        record
        for record in _collect_upstream_lineage(store, kept_runs)
        if record.lineage_id not in known_ids
    ]
    # run node id -> upstream (landing/transformation) and reporting relation ids
    upstream_by_run: dict[str, list[str]] = {}
    reporting_by_run: dict[str, list[str]] = {}
    for lineage_record in [*lineage_records, *upstream_records]:
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
        if lineage_record.target_layer == LAYER_TRANSFORMATION:
            upstream_by_run.setdefault(run_id, []).append(relation_id)
        elif lineage_record.target_name in relation_names:
            reporting_by_run.setdefault(run_id, []).append(relation_id)
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

    # Transformation relations a run produced feed the publication relations
    # that same run rebuilt (or the publication itself when only the audit
    # row exists).
    for run_id, upstream_ids in upstream_by_run.items():
        targets = reporting_by_run.get(run_id) or (
            [publication_id] if (run_id, publication_id, EDGE_PUBLISHES) in edges else []
        )
        for upstream_id in upstream_ids:
            for target_id in targets:
                feed_key = (upstream_id, target_id, EDGE_FEEDS)
                if feed_key not in edges:
                    edges[feed_key] = LineageEdge(
                        from_id=upstream_id,
                        to_id=target_id,
                        type=EDGE_FEEDS,
                        attributes={"run_id": nodes[run_id].attributes.get("run_id")},
                    )

    sorted_nodes = tuple(sorted(nodes.values(), key=lambda n: (n.type, n.id)))
    sorted_edges = tuple(
        sorted(edges.values(), key=lambda e: (e.type, e.from_id, e.to_id))
    )
    return LineageGraph(
        publication_key=publication_key,
        nodes=sorted_nodes,
        edges=sorted_edges,
        total_runs=total_runs,
        run_limit=run_limit,
        truncated=len(kept_runs) < total_runs,
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


def _collect_upstream_lineage(
    store: LineageStore, run_ids: Iterable[str]
) -> list[SourceLineageRecord]:
    """Landing and transformation rows recorded by the runs behind a publication.

    These carry the source asset a run landed for and the facts/dimensions it
    loaded, so the graph reads source asset → run → transformation → mart.
    """
    seen: set[str] = set()
    collected: list[SourceLineageRecord] = []
    for run_id in sorted(run_ids):
        for layer in UPSTREAM_LAYERS:
            for record in store.list_source_lineage(input_run_id=run_id, target_layer=layer):
                if record.lineage_id in seen:
                    continue
                seen.add(record.lineage_id)
                collected.append(record)
    return collected
