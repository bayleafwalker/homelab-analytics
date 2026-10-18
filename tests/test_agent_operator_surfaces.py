"""Agent trust, catalog, principals, and proposal-review surfaces.

- semantic-index entries carry a trust block; no snapshot reads trust_unknown
- the semantic index pages with limit/cursor and stays unpaged by default
- proposals citing publications get trust stamped server-side at draft time
- /api/actions/proposals/{id}/review shows effect, diff preview, evidence
  with trust at draft vs now, and caveats
- /api/agent/catalog and /api/agent/principals expose the agent surface to
  operators
- machine principals cannot activate policies they draft
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.application.use_cases.agent_tool_catalog import (
    AGENT_TOOL_SPECS,
    VUORO_OPERATION_NAME_PATTERN,
)
from packages.application.use_cases.agent_trust import (
    assess_publication_trust,
    worst_guidance,
)
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.transformation_service import TransformationService
from packages.platform.agent_semantic_index import validate_agent_semantic_index_payload
from packages.platform.publication_confidence import (
    ConfidenceVerdict,
    FreshnessState,
    PublicationConfidenceSnapshot,
)
from packages.storage.auth_store import UserRole
from packages.storage.control_plane import PublicationConfidenceSnapshotCreate
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository

# Contract key agents cite, and the relation name the refresh path records
# confidence snapshots under.
CASHFLOW = "monthly_cashflow"
CASHFLOW_RELATION = "mart_monthly_cashflow"


def _client(tmp: str, *, stale_cashflow: bool = False) -> tuple[TestClient, IngestionConfigRepository]:
    repository = IngestionConfigRepository(Path(tmp) / "config.db")
    if stale_cashflow:
        repository.record_publication_confidence_snapshot(
            (
                PublicationConfidenceSnapshotCreate(
                    snapshot_id="snap-1",
                    publication_key=CASHFLOW_RELATION,
                    assessed_at=datetime(2026, 10, 1, tzinfo=UTC),
                    freshness_state="stale",
                    completeness_pct=100,
                    confidence_verdict="degraded",
                ),
            )
        )
    service = AccountTransactionService(
        landing_root=Path(tmp) / "landing",
        metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
    )
    app = create_app(
        service,
        config_repository=repository,
        transformation_service=TransformationService(DuckDBStore.memory()),
    )
    return TestClient(app), repository


_KNOWN_SIGNALS = {"validation_errors": 0}


def _snapshot(
    verdict: ConfidenceVerdict,
    freshness: FreshnessState,
    quality_flags: dict[str, int] | None = None,
) -> PublicationConfidenceSnapshot:
    return PublicationConfidenceSnapshot(
        snapshot_id="s",
        publication_key=CASHFLOW,
        assessed_at=datetime(2026, 10, 1, tzinfo=UTC),
        freshness_state=freshness,
        completeness_pct=100,
        quality_flags=dict(_KNOWN_SIGNALS if quality_flags is None else quality_flags),
        confidence_verdict=verdict,
    )


def test_trust_guidance_never_reads_missing_snapshot_as_current() -> None:
    assert assess_publication_trust(CASHFLOW, None).guidance == "trust_unknown"
    current = _snapshot(ConfidenceVerdict.TRUSTWORTHY, FreshnessState.CURRENT)
    assert assess_publication_trust(CASHFLOW, current).guidance == "state_as_current"
    due = _snapshot(ConfidenceVerdict.TRUSTWORTHY, FreshnessState.DUE_SOON)
    assert assess_publication_trust(CASHFLOW, due).guidance == "state_with_caveat"
    stale = _snapshot(ConfidenceVerdict.DEGRADED, FreshnessState.STALE)
    assert assess_publication_trust(CASHFLOW, stale).guidance == "do_not_state_as_current"
    assert worst_guidance(["state_as_current", "trust_unknown"]) == "trust_unknown"


def test_unknown_signals_never_upgrade_guidance() -> None:
    # A legacy "trustworthy" snapshot without a validation signal.
    legacy = _snapshot(ConfidenceVerdict.TRUSTWORTHY, FreshnessState.CURRENT, quality_flags={})
    trust = assess_publication_trust(CASHFLOW, legacy)
    assert trust.validation_state == "unknown"
    assert trust.guidance == "state_with_caveat"
    partial = _snapshot(
        ConfidenceVerdict.TRUSTWORTHY,
        FreshnessState.CURRENT,
        quality_flags={
            "validation_errors": 0,
            "completeness_expected_sources": 2,
            "completeness_unknown_sources": 1,
        },
    )
    trust = assess_publication_trust(CASHFLOW, partial)
    assert trust.completeness_state == "partial"
    assert trust.guidance == "state_with_caveat"
    assert trust.as_dict()["validation_state"] == "known"
    assert worst_guidance([]) == "trust_unknown"


def test_semantic_index_carries_trust_and_pages() -> None:
    with TemporaryDirectory() as tmp:
        client, _ = _client(tmp, stale_cashflow=True)
        full = client.get("/api/agent/semantic-index").json()
        assert validate_agent_semantic_index_payload(full) == []
        assert full["next_cursor"] is None
        assert full["total"] == len(full["publications"]) > 3
        by_key = {entry["publication_key"]: entry for entry in full["publications"]}
        assert by_key[CASHFLOW]["trust"]["guidance"] == "do_not_state_as_current"
        others = [entry for key, entry in by_key.items() if key != CASHFLOW]
        assert all(entry["trust"]["guidance"] == "trust_unknown" for entry in others)

        first = client.get("/api/agent/semantic-index", params={"limit": 2}).json()
        assert [entry["publication_key"] for entry in first["publications"]] == list(by_key)[:2]
        second = client.get(
            "/api/agent/semantic-index",
            params={"limit": 2, "cursor": first["next_cursor"]},
        ).json()
        assert [entry["publication_key"] for entry in second["publications"]] == list(by_key)[2:4]

        bad = client.get("/api/agent/semantic-index", params={"cursor": "nope"})
        assert bad.status_code == 422
        missing = client.get("/api/agent/semantic-index/not_a_publication")
        assert missing.status_code == 404
        assert "list_publications" in missing.json()["detail"]


def test_proposal_draft_stamps_trust_and_review_shows_evidence() -> None:
    with TemporaryDirectory() as tmp:
        client, _ = _client(tmp, stale_cashflow=True)
        created = client.post(
            "/api/actions/proposals",
            json={
                "policy_id": "mcp:propose_action",
                "policy_name": "Trim discretionary spend",
                "verdict": "notify",
                "value": "-150.00",
                "provenance": {
                    # The proposer claims its evidence was trustworthy; the
                    # platform stamps what the evidence actually looked like.
                    "publication_keys": [CASHFLOW, "mart_invented"],
                    "confidence_verdict_at_draft": "trustworthy",
                },
            },
        ).json()
        assert created["provenance"]["confidence_verdict_at_draft"] == "degraded"
        assert created["provenance"]["freshness_state_at_draft"] == "stale"

        review = client.get(f"/api/actions/proposals/{created['action_id']}/review")
        assert review.status_code == 200
        body = review.json()
        assert body["effect"]["kind"] == "in_registry_only"
        assert body["effect"]["external_effect"] is False
        status_row = body["change_preview"][0]
        assert (status_row["before"], status_row["after"], status_row["changes"]) == (
            "pending",
            "approved",
            True,
        )
        evidence = {item["publication_key"]: item for item in body["evidence"]}
        assert evidence[CASHFLOW]["known"] is True
        assert evidence[CASHFLOW]["now"]["guidance"] == "do_not_state_as_current"
        assert evidence[CASHFLOW]["lineage_path"] == f"/api/lineage/publication/{CASHFLOW}"
        assert evidence["mart_invented"]["known"] is False
        assert evidence["mart_invented"]["now"] is None
        assert body["trust"]["guidance"] == "do_not_state_as_current"
        caveats = " ".join(body["trust"]["caveats"])
        assert "mart_invented" in caveats
        assert "stale or unreliable" in caveats

        assert client.get("/api/actions/proposals/missing/review").status_code == 404


def test_review_flags_uncited_proposals() -> None:
    with TemporaryDirectory() as tmp:
        client, _ = _client(tmp)
        created = client.post(
            "/api/actions/proposals",
            json={"policy_id": "agent-x", "policy_name": "Do a thing", "verdict": "notify"},
        ).json()
        body = client.get(f"/api/actions/proposals/{created['action_id']}/review").json()
        assert body["evidence"] == []
        assert body["trust"]["guidance"] == "trust_unknown"
        assert "cited no publications" in body["trust"]["caveats"][0]


def test_catalog_and_principals_project_the_agent_surface() -> None:
    with TemporaryDirectory() as tmp:
        client, _ = _client(tmp)
        catalog = client.get("/api/agent/catalog").json()
        names = [tool["name"] for tool in catalog["tools"]]
        assert names == [spec.name for spec in AGENT_TOOL_SPECS]
        for tool in catalog["tools"]:
            assert VUORO_OPERATION_NAME_PATTERN.match(tool["vuoro_operation"])
            assert tool["endpoints"], tool["name"]
            assert tool["annotations"]["destructiveHint"] is False
            assert tool["annotations"]["readOnlyHint"] is (tool["effect"] == "read")
        by_name = {tool["name"]: tool for tool in catalog["tools"]}
        assert by_name["propose_policy"]["token_reachable"] is False
        assert "control.policy.write" in by_name["propose_policy"]["access_note"]

        for origin in ("agent-a", "agent-a", "agent-b"):
            client.post(
                "/api/actions/proposals",
                json={
                    "policy_id": origin,
                    "policy_name": "p",
                    "verdict": "notify",
                    "source_kind": "agent",
                    "created_by": origin,
                    "provenance": {"publication_keys": [CASHFLOW]},
                },
            )
        client.post(
            "/api/actions/proposals",
            json={"policy_id": "seed", "policy_name": "p", "verdict": "notify", "source_kind": "policy"},
        )
        principals = client.get("/api/agent/principals").json()
        assert principals["registration_authority"] == "none"
        counts = {item["origin"]: item["proposal_count"] for item in principals["principals"]}
        assert counts == {"agent-a": 2, "agent-b": 1}
        assert principals["principals"][0]["cited_publications"] == [CASHFLOW]

        agent_only = client.get("/api/actions/proposals", params={"source_kind": "agent"})
        assert len(agent_only.json()["proposals"]) == 3


def _policy_app(tmp: str, auth_provider: str | None) -> TestClient:
    """Policy routes alone, with an injected principal (no auth middleware)."""
    from fastapi import FastAPI, Request

    from apps.api.routes.policy_routes import register_policy_routes
    from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal

    app = FastAPI()

    @app.middleware("http")
    async def _inject(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.principal = (
            None
            if auth_provider is None
            else AuthenticatedPrincipal(
                user_id="p-1",
                username="mcp-agent" if auth_provider != "local" else "admin",
                role=UserRole.ADMIN,
                auth_provider=auth_provider,  # type: ignore[arg-type]
            )
        )
        return await call_next(request)

    register_policy_routes(
        app,
        resolved_config_repository=IngestionConfigRepository(Path(tmp) / "config.db"),
        known_publication_keys=frozenset({CASHFLOW}),
    )
    return TestClient(app)


_RULE = {
    "rule_kind": "publication_value_comparison",
    "publication_key": CASHFLOW,
    "field_name": "net",
    "operator": "lt",
    "threshold": 0,
}


def test_machine_principal_policy_drafts_stay_disabled() -> None:
    with TemporaryDirectory() as tmp:
        agent = _policy_app(tmp, "machine_jwt")
        drafted = agent.post(
            "/control/policies",
            json={
                "display_name": "Agent: negative cashflow",
                "policy_kind": "threshold",
                "rule_document": _RULE,
                "creator": "someone-else",
            },
        )
        assert drafted.status_code == 201, drafted.text
        policy = drafted.json()
        assert policy["enabled"] is False
        assert policy["source_kind"] == "agent"
        assert policy["creator"] == "mcp-agent"

        denied = agent.patch(f"/control/policies/{policy['policy_id']}", json={"enabled": True})
        assert denied.status_code == 403
        # Non-activation edits by the drafting agent remain possible.
        renamed = agent.patch(
            f"/control/policies/{policy['policy_id']}", json={"display_name": "Renamed"}
        )
        assert renamed.status_code == 200
        assert renamed.json()["enabled"] is False

        operator = _policy_app(tmp, "local")
        enabled = operator.patch(
            f"/control/policies/{policy['policy_id']}", json={"enabled": True}
        )
        assert enabled.status_code == 200
        assert enabled.json()["enabled"] is True


def test_operator_policy_creates_keep_enabled_default() -> None:
    with TemporaryDirectory() as tmp:
        operator = _policy_app(tmp, None)
        created = operator.post(
            "/control/policies",
            json={"display_name": "Op", "policy_kind": "threshold", "rule_document": _RULE},
        )
        assert created.status_code == 201, created.text
        assert created.json()["enabled"] is True
        assert created.json()["source_kind"] == "operator"


def test_validator_rejects_unknown_trust_guidance() -> None:
    with TemporaryDirectory() as tmp:
        client, _ = _client(tmp)
        payload = client.get("/api/agent/semantic-index", params={"limit": 1}).json()
        payload["publications"][0]["trust"]["guidance"] = "probably_fine"
        violations = validate_agent_semantic_index_payload(payload)
        assert any("trust.guidance" in violation for violation in violations)
