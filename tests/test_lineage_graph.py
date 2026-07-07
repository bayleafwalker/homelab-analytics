"""Tests for the publication lineage graph builder."""

from __future__ import annotations

from datetime import UTC, datetime

from packages.platform.lineage_graph import (
    EDGE_PRODUCES,
    EDGE_PUBLISHES,
    EDGE_SOURCES,
    NODE_PUBLICATION,
    NODE_RELATION,
    NODE_RUN,
    NODE_SOURCE,
    build_publication_lineage_graph,
)
from packages.storage.control_plane import (
    PublicationAuditRecord,
    SourceLineageRecord,
)


class _FakeStore:
    """Minimal fake conforming to the LineageStore Protocol."""

    def __init__(
        self,
        *,
        audit: list[PublicationAuditRecord] | None = None,
        lineage: list[SourceLineageRecord] | None = None,
    ) -> None:
        self._audit = list(audit or [])
        self._lineage = list(lineage or [])
        self.audit_calls: list[dict[str, str | None]] = []
        self.lineage_calls: list[dict[str, str | None]] = []

    def list_publication_audit(
        self,
        *,
        run_id: str | None = None,
        publication_key: str | None = None,
    ) -> list[PublicationAuditRecord]:
        self.audit_calls.append({"run_id": run_id, "publication_key": publication_key})
        return [
            record
            for record in self._audit
            if (run_id is None or record.run_id == run_id)
            and (publication_key is None or record.publication_key == publication_key)
        ]

    def list_source_lineage(
        self,
        *,
        input_run_id: str | None = None,
        target_layer: str | None = None,
        target_name: str | None = None,
        source_asset_id: str | None = None,
    ) -> list[SourceLineageRecord]:
        self.lineage_calls.append(
            {
                "input_run_id": input_run_id,
                "target_layer": target_layer,
                "target_name": target_name,
                "source_asset_id": source_asset_id,
            }
        )
        return [
            record
            for record in self._lineage
            if (input_run_id is None or record.input_run_id == input_run_id)
            and (target_layer is None or record.target_layer == target_layer)
            and (target_name is None or record.target_name == target_name)
        ]


def _audit(
    *,
    audit_id: str,
    publication_key: str,
    relation_name: str,
    run_id: str | None,
    status: str = "published",
    published_at: datetime | None = None,
) -> PublicationAuditRecord:
    return PublicationAuditRecord(
        publication_audit_id=audit_id,
        run_id=run_id,
        publication_key=publication_key,
        relation_name=relation_name,
        status=status,
        published_at=published_at or datetime(2026, 6, 1, tzinfo=UTC),
    )


def _lineage(
    *,
    lineage_id: str,
    input_run_id: str | None,
    target_layer: str,
    target_name: str,
    target_kind: str = "mart",
    row_count: int | None = 100,
    source_system: str | None = None,
    source_run_id: str | None = None,
    recorded_at: datetime | None = None,
) -> SourceLineageRecord:
    return SourceLineageRecord(
        lineage_id=lineage_id,
        input_run_id=input_run_id,
        target_layer=target_layer,
        target_name=target_name,
        target_kind=target_kind,
        row_count=row_count,
        source_system=source_system,
        source_run_id=source_run_id,
        recorded_at=recorded_at or datetime(2026, 6, 1, tzinfo=UTC),
    )


class TestBuildLineageGraphShape:
    def test_publication_node_always_present(self):
        store = _FakeStore()
        graph = build_publication_lineage_graph(
            store, publication_key="mart_monthly_cashflow"
        )
        assert graph.publication_key == "mart_monthly_cashflow"
        publications = [n for n in graph.nodes if n.type == NODE_PUBLICATION]
        assert len(publications) == 1
        assert publications[0].attributes["key"] == "mart_monthly_cashflow"

    def test_empty_result_when_no_records(self):
        store = _FakeStore()
        graph = build_publication_lineage_graph(store, publication_key="x")
        assert len(graph.nodes) == 1  # only the publication node
        assert graph.edges == ()

    def test_audit_query_filters_by_publication_key(self):
        store = _FakeStore()
        build_publication_lineage_graph(store, publication_key="mart_x")
        assert store.audit_calls == [
            {"run_id": None, "publication_key": "mart_x"}
        ]


class TestPublishesEdges:
    def test_run_publishes_edge_from_audit(self):
        audit = [
            _audit(
                audit_id="a1",
                publication_key="mart_monthly_cashflow",
                relation_name="mart_monthly_cashflow",
                run_id="run-1",
                published_at=datetime(2026, 6, 2, 10, tzinfo=UTC),
            )
        ]
        store = _FakeStore(audit=audit)
        graph = build_publication_lineage_graph(
            store, publication_key="mart_monthly_cashflow"
        )
        publishes = [e for e in graph.edges if e.type == EDGE_PUBLISHES]
        assert len(publishes) == 1
        edge = publishes[0]
        assert edge.from_id == f"{NODE_RUN}:run-1"
        assert edge.to_id == f"{NODE_PUBLICATION}:mart_monthly_cashflow"
        assert edge.attributes["status"] == "published"
        assert edge.attributes["relation_name"] == "mart_monthly_cashflow"
        assert edge.attributes["published_at"] == "2026-06-02T10:00:00+00:00"

    def test_multiple_runs_yield_multiple_publish_edges(self):
        audit = [
            _audit(audit_id=f"a{i}", publication_key="p", relation_name="p", run_id=f"run-{i}")
            for i in range(3)
        ]
        store = _FakeStore(audit=audit)
        graph = build_publication_lineage_graph(store, publication_key="p")
        publish_edges = [e for e in graph.edges if e.type == EDGE_PUBLISHES]
        assert len(publish_edges) == 3
        run_nodes = [n for n in graph.nodes if n.type == NODE_RUN]
        assert {n.attributes["run_id"] for n in run_nodes} == {"run-0", "run-1", "run-2"}

    def test_audit_without_run_id_still_produces_no_orphan_edge(self):
        audit = [
            _audit(audit_id="a1", publication_key="p", relation_name="p", run_id=None)
        ]
        store = _FakeStore(audit=audit)
        graph = build_publication_lineage_graph(store, publication_key="p")
        assert [e for e in graph.edges if e.type == EDGE_PUBLISHES] == []


class TestProducesEdges:
    def test_lineage_becomes_produces_edge(self):
        audit = [
            _audit(audit_id="a1", publication_key="p", relation_name="p", run_id="run-1")
        ]
        lineage = [
            _lineage(
                lineage_id="L1",
                input_run_id="run-1",
                target_layer="reporting",
                target_name="p",
                target_kind="mart",
                row_count=42,
            )
        ]
        store = _FakeStore(audit=audit, lineage=lineage)
        graph = build_publication_lineage_graph(store, publication_key="p")

        produces = [e for e in graph.edges if e.type == EDGE_PRODUCES]
        assert len(produces) == 1
        edge = produces[0]
        assert edge.from_id == f"{NODE_RUN}:run-1"
        assert edge.to_id == f"{NODE_RELATION}:reporting:p"
        assert edge.attributes["row_count"] == 42
        assert edge.attributes["target_kind"] == "mart"

    def test_relation_node_carries_layer_and_kind(self):
        audit = [_audit(audit_id="a1", publication_key="p", relation_name="p", run_id="run-1")]
        lineage = [
            _lineage(
                lineage_id="L1",
                input_run_id="run-1",
                target_layer="transformation",
                target_name="p",
                target_kind="fact",
            )
        ]
        store = _FakeStore(audit=audit, lineage=lineage)
        graph = build_publication_lineage_graph(store, publication_key="p")
        relations = [n for n in graph.nodes if n.type == NODE_RELATION]
        assert len(relations) == 1
        node = relations[0]
        assert node.attributes["layer"] == "transformation"
        assert node.attributes["name"] == "p"
        assert node.attributes["kind"] == "fact"


class TestSourcesEdges:
    def test_source_becomes_source_edge(self):
        audit = [_audit(audit_id="a1", publication_key="p", relation_name="p", run_id="run-1")]
        lineage = [
            _lineage(
                lineage_id="L1",
                input_run_id="run-1",
                target_layer="transformation",
                target_name="p",
                source_system="prometheus",
                source_run_id="prom-42",
            )
        ]
        store = _FakeStore(audit=audit, lineage=lineage)
        graph = build_publication_lineage_graph(store, publication_key="p")

        sources = [n for n in graph.nodes if n.type == NODE_SOURCE]
        assert len(sources) == 1
        assert sources[0].attributes["source_system"] == "prometheus"

        source_edges = [e for e in graph.edges if e.type == EDGE_SOURCES]
        assert len(source_edges) == 1
        edge = source_edges[0]
        assert edge.from_id == f"{NODE_SOURCE}:prometheus"
        assert edge.to_id == f"{NODE_RUN}:run-1"
        assert edge.attributes["source_run_id"] == "prom-42"

    def test_no_source_edge_when_source_system_missing(self):
        audit = [_audit(audit_id="a1", publication_key="p", relation_name="p", run_id="run-1")]
        lineage = [
            _lineage(
                lineage_id="L1",
                input_run_id="run-1",
                target_layer="reporting",
                target_name="p",
                source_system=None,
            )
        ]
        store = _FakeStore(audit=audit, lineage=lineage)
        graph = build_publication_lineage_graph(store, publication_key="p")
        assert [e for e in graph.edges if e.type == EDGE_SOURCES] == []
        assert [n for n in graph.nodes if n.type == NODE_SOURCE] == []


class TestGraphDedupAndDeterminism:
    def test_duplicate_edges_collapse(self):
        audit = [
            _audit(audit_id="a1", publication_key="p", relation_name="p", run_id="run-1"),
            _audit(audit_id="a2", publication_key="p", relation_name="p", run_id="run-1"),
        ]
        store = _FakeStore(audit=audit)
        graph = build_publication_lineage_graph(store, publication_key="p")
        publishes = [e for e in graph.edges if e.type == EDGE_PUBLISHES]
        # Two audit rows both point run-1 → p; only one edge should survive.
        assert len(publishes) == 1

    def test_output_is_deterministic_across_calls(self):
        audit = [
            _audit(audit_id="a1", publication_key="p", relation_name="p", run_id="run-2"),
            _audit(audit_id="a2", publication_key="p", relation_name="p", run_id="run-1"),
        ]
        lineage = [
            _lineage(
                lineage_id="L1",
                input_run_id="run-2",
                target_layer="reporting",
                target_name="p",
                source_system="prometheus",
                source_run_id="prom-x",
            ),
            _lineage(
                lineage_id="L2",
                input_run_id="run-1",
                target_layer="transformation",
                target_name="p",
                source_system="home_assistant",
                source_run_id="ha-y",
            ),
        ]
        store = _FakeStore(audit=audit, lineage=lineage)
        first = build_publication_lineage_graph(store, publication_key="p").as_dict()
        second = build_publication_lineage_graph(store, publication_key="p").as_dict()
        assert first == second


class TestEndToEndChain:
    def test_source_to_publication_chain_walks_source_run_id(self):
        audit = [
            _audit(
                audit_id="a1",
                publication_key="mart_cashflow",
                relation_name="mart_cashflow",
                run_id="run-100",
                published_at=datetime(2026, 6, 5, tzinfo=UTC),
            )
        ]
        lineage = [
            _lineage(
                lineage_id="L1",
                input_run_id="run-100",
                target_layer="reporting",
                target_name="mart_cashflow",
                target_kind="mart",
                source_system="home_assistant",
                source_run_id="ha-42",
                row_count=250,
            ),
        ]
        store = _FakeStore(audit=audit, lineage=lineage)
        graph = build_publication_lineage_graph(store, publication_key="mart_cashflow")

        types = {n.type for n in graph.nodes}
        assert types == {NODE_PUBLICATION, NODE_RUN, NODE_RELATION, NODE_SOURCE}

        edge_types = {e.type for e in graph.edges}
        assert edge_types == {EDGE_PUBLISHES, EDGE_PRODUCES, EDGE_SOURCES}

        # The operator can walk: source→run→publication.
        source_edge = next(e for e in graph.edges if e.type == EDGE_SOURCES)
        publish_edge = next(e for e in graph.edges if e.type == EDGE_PUBLISHES)
        assert source_edge.to_id == publish_edge.from_id  # same run bridges them
        assert source_edge.attributes["source_run_id"] == "ha-42"
