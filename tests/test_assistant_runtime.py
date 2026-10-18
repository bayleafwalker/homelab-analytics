"""AssistantRuntime boundary: gate, grants, budget, evidence, honesty.

The deterministic runtime runs the full boundary against a real app through
the MCP tool broker, so a provider runtime written later must satisfy the
same contract.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.agent.assistant_tools import McpToolBroker
from apps.agent.mcp_server import AgentMcpServer
from apps.api.app import create_app
from packages.application.use_cases.assistant_runtime import (
    ASSISTANT_PROVIDER_CALLS_ENV,
    ASSISTANT_RUNTIME_ENV,
    AssistantContext,
    AssistantPolicy,
    AssistantRuntimeDisabled,
    AssistantRuntimeUnavailable,
    DeterministicAssistantRuntime,
    ToolOutcome,
    build_assistant_runtime,
)
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.control_plane import PublicationConfidenceSnapshotCreate
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository


class InProcessCaller:
    def __init__(self, client: TestClient) -> None:
        self._client = client

    def call(self, method, path, *, params=None, json_body=None):  # type: ignore[no-untyped-def]
        response = self._client.request(method, path, params=params, json=json_body)
        return response.status_code, response.json()


def _server(tmp: str, *, stale: bool = False) -> AgentMcpServer:
    repository = IngestionConfigRepository(Path(tmp) / "config.db")
    if stale:
        repository.record_publication_confidence_snapshot(
            (
                PublicationConfidenceSnapshotCreate(
                    snapshot_id="snap-stale",
                    publication_key="mart_monthly_cashflow",
                    assessed_at=datetime(2026, 9, 1, tzinfo=UTC),
                    freshness_state="stale",
                    completeness_pct=100,
                    confidence_verdict="unreliable",
                    quality_flags={"validation_errors": 0},
                ),
            )
        )
    service = AccountTransactionService(
        landing_root=Path(tmp) / "landing",
        metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
    )
    client = TestClient(
        create_app(
            service,
            config_repository=repository,
            transformation_service=TransformationService(DuckDBStore.memory()),
        )
    )
    return AgentMcpServer(InProcessCaller(client))


@pytest.mark.parametrize(
    "env,error",
    [
        ({}, AssistantRuntimeDisabled),
        ({ASSISTANT_RUNTIME_ENV: "disabled"}, AssistantRuntimeDisabled),
        ({ASSISTANT_RUNTIME_ENV: "opencode"}, AssistantRuntimeDisabled),
        (
            {ASSISTANT_RUNTIME_ENV: "opencode", ASSISTANT_PROVIDER_CALLS_ENV: "true"},
            AssistantRuntimeUnavailable,
        ),
        ({ASSISTANT_RUNTIME_ENV: "gpt"}, ValueError),
    ],
)
def test_runtime_gate_is_closed_by_default(env: dict[str, str], error: type[Exception]) -> None:
    with pytest.raises(error):
        build_assistant_runtime(env)


def test_deterministic_runtime_is_opt_in() -> None:
    runtime = build_assistant_runtime({ASSISTANT_RUNTIME_ENV: "deterministic"})
    assert isinstance(runtime, DeterministicAssistantRuntime)


def _run(server: AgentMcpServer, question: str, policy: AssistantPolicy | None = None):
    resolved_policy = policy or AssistantPolicy()
    runtime = DeterministicAssistantRuntime()
    session = runtime.start(
        AssistantContext(operator="admin"), resolved_policy, McpToolBroker(server, resolved_policy)
    )
    events = list(runtime.continue_session(session, question))
    return runtime, session, events


def test_answer_names_source_and_flags_stale_evidence() -> None:
    with TemporaryDirectory() as tmp:
        runtime, session, events = _run(_server(tmp, stale=True), "monthly cashflow")
        kinds = [event.kind for event in events]
        assert kinds[0] == "message" and kinds[-1] == "done"
        assert kinds.count("tool_call") == 2
        answer = [e for e in events if e.kind == "message" and e.payload.get("role") == "assistant"][-1]
        assert "monthly_cashflow" in answer.payload["citations"]
        assert "should not be read as current" in answer.payload["text"]

        evidence = runtime.export_evidence(session)
        assert evidence.cited_publications["monthly_cashflow"] == "do_not_state_as_current"
        assert evidence.untrusted_citations == ("monthly_cashflow",)
        assert evidence.usage.tool_calls == 2
        assert evidence.as_dict()["answer"] == answer.payload["text"]


def test_unanswerable_question_does_not_guess() -> None:
    with TemporaryDirectory() as tmp:
        runtime, session, events = _run(_server(tmp), "zzzz-nothing-matches-this")
        answer = [e for e in events if e.kind == "message" and e.payload.get("role") == "assistant"][-1]
        assert "will not guess" in answer.payload["text"]
        assert runtime.export_evidence(session).cited_publications == {}


def test_policy_grants_and_budget_are_enforced_at_the_boundary() -> None:
    with TemporaryDirectory() as tmp:
        server = _server(tmp)
        no_summary = AssistantPolicy(tool_grants=("list_publications",))
        _, session, events = _run(server, "monthly cashflow", no_summary)
        refusals = [event for event in events if event.kind == "refusal"]
        assert [event.payload["tool"] for event in refusals] == ["get_publication_summary"]
        assert session.usage.refused_tool_calls == 1

        budget = AssistantPolicy(max_tool_calls=1)
        _, session, events = _run(server, "monthly cashflow", budget)
        assert any(
            event.kind == "refusal" and "budget" in event.payload["reason"] for event in events
        )
        assert session.usage.tool_calls == 1


def test_broker_refuses_drafts_unless_policy_allows_and_redacts_samples() -> None:
    with TemporaryDirectory() as tmp:
        server = _server(tmp)
        read_only = AssistantPolicy(tool_grants=("propose_action", "get_publication_summary"))
        broker = McpToolBroker(server, read_only)
        refused = broker.invoke("propose_action", {"origin": "a", "title": "t", "verdict": "notify"})
        assert refused == ToolOutcome(
            tool_name="propose_action",
            is_error=True,
            payload={"error": {"code": "not_granted", "message": "propose_action is not granted."}},
            error_code="not_granted",
        )
        summary = broker.invoke("get_publication_summary", {"publication_key": "monthly_cashflow"})
        sample: dict[str, Any] | None = summary.payload["publication"]["sample"]
        if sample is not None:
            assert sample["rows"] == [] and sample["redacted"] is True

        drafting = AssistantPolicy(tool_grants=("propose_action",), allow_drafts=True)
        drafted = McpToolBroker(server, drafting).invoke(
            "propose_action", {"origin": "hla-assistant", "title": "t", "verdict": "notify"}
        )
        assert drafted.is_error is False
        assert drafted.payload["status"] == "pending"

        invalid = McpToolBroker(server, drafting).invoke("propose_action", {"origin": "x"})
        assert invalid.is_error and invalid.error_code == "invalid_arguments"


def test_cancel_and_vuoro_run_registration_shape() -> None:
    with TemporaryDirectory() as tmp:
        runtime, session, _ = _run(_server(tmp), "monthly cashflow")
        registration = session.vuoro_run_registration()
        assert set(registration) == {
            "harness_id",
            "harness_build",
            "model_id",
            "recipe_id",
            "observed_profile",
            "idempotency_key",
        }
        assert registration["harness_id"] == "hla-assistant/deterministic"
        assert len(registration["observed_profile"]["instruction_digest"]) == 64
        runtime.cancel(session)
        assert session.status == "cancelled"
        with pytest.raises(ValueError):
            list(runtime.continue_session(session, "again"))
