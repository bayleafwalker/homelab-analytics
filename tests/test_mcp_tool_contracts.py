"""Contract tests for what an agent sees through the MCP tool surface.

The "UI" of an agent is the tool list, the schemas, the error messages, and
the evidence fields it gets back. These tests pin the parts that keep agent
answers honest: trust guidance, structured errors, argument validation
before any endpoint call, pagination, and draft-only proposal semantics.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.agent.mcp_server import (
    SERVER_INSTRUCTIONS,
    AgentMcpServer,
    build_tool_definitions,
    validate_tool_arguments,
)
from apps.api.app import create_app
from packages.application.use_cases.agent_tool_catalog import AGENT_TOOL_SPECS
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository


class RecordingCaller:
    """Caller returning a canned response and recording every call."""

    def __init__(self, status: int = 200, payload: Any = None, raises: Exception | None = None) -> None:
        self.status = status
        self.payload = payload if payload is not None else {}
        self.raises = raises
        self.calls: list[tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]] = []

    def call(self, method, path, *, params=None, json_body=None):  # type: ignore[no-untyped-def]
        self.calls.append((method, path, params, json_body))
        if self.raises is not None:
            raise self.raises
        return self.status, self.payload


class InProcessCaller:
    def __init__(self, client: TestClient) -> None:
        self._client = client

    def call(self, method, path, *, params=None, json_body=None):  # type: ignore[no-untyped-def]
        response = self._client.request(method, path, params=params, json=json_body)
        return response.status_code, response.json()


def _call(server: AgentMcpServer, name: str, arguments: Any) -> dict[str, Any]:
    response = server.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
    )
    assert response is not None
    return response["result"]


def _app_client(tmp: str) -> TestClient:
    service = AccountTransactionService(
        landing_root=Path(tmp) / "landing",
        metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
    )
    return TestClient(
        create_app(service, transformation_service=TransformationService(DuckDBStore.memory()))
    )


def test_initialize_carries_honesty_instructions() -> None:
    server = AgentMcpServer(RecordingCaller())
    result = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert result is not None
    instructions = result["result"]["instructions"]
    assert instructions == SERVER_INSTRUCTIONS
    for phrase in ("trust.guidance", "do_not_state_as_current", "trust_unknown", "operator approves"):
        assert phrase in instructions


def test_tool_definitions_are_described_annotated_and_match_catalog() -> None:
    definitions = build_tool_definitions()
    assert [tool["name"] for tool in definitions] == [spec.name for spec in AGENT_TOOL_SPECS]
    for tool, spec in zip(definitions, AGENT_TOOL_SPECS):
        assert tool["title"]
        assert len(tool["description"]) > 80, tool["name"]
        assert "structuredContent.error" in tool["description"]
        assert tool["inputSchema"]["additionalProperties"] is False
        annotations = tool["annotations"]
        assert annotations["readOnlyHint"] is (spec.effect == "read")
        assert annotations["destructiveHint"] is False
        assert annotations["openWorldHint"] is False
        if spec.effect == "draft":
            assert any(
                word in tool["description"] for word in ("approval", "review", "disabled")
            ), tool["name"]


@pytest.mark.parametrize(
    "name,arguments,fragment",
    [
        ("get_publication_summary", {}, "missing required argument 'publication_key'"),
        ("list_publications", {"q": "cash"}, "unknown argument 'q'"),
        ("list_publications", {"limit": "ten"}, "must be of type integer"),
        ("list_publications", {"limit": 1000}, "must be <= 100"),
        ("propose_scenario", {"scenario_kind": "lottery-win", "parameters": {}}, "must be one of"),
        (
            "propose_action",
            {"origin": "a", "title": "t", "verdict": "notify", "idempotency_key": "no spaces!"},
            "must match",
        ),
        (
            "propose_action",
            {"origin": "a", "title": "t", "verdict": "notify", "publication_keys": [1]},
            "items must be of type string",
        ),
        ("list_publications", ["not", "an", "object"], "arguments must be an object"),
        ("list_proposal_changes", {"limit": 501}, "must be <= 500"),
        ("list_proposal_changes", {"since": "apf.0"}, "unknown argument 'since'"),
    ],
)
def test_invalid_arguments_are_rejected_before_any_endpoint_call(
    name: str, arguments: Any, fragment: str
) -> None:
    caller = RecordingCaller()
    result = _call(AgentMcpServer(caller), name, arguments)
    assert result["isError"] is True
    error = result["structuredContent"]["error"]
    assert error["code"] == "invalid_arguments"
    assert fragment in error["message"]
    assert error["retryable"] is False
    assert caller.calls == []


@pytest.mark.parametrize(
    "status,payload,code,retryable,hint_fragment",
    [
        (404, {"detail": "Unknown publication: x"}, "not_found", False, "list_publications"),
        (403, {"detail": "admin:write scope required."}, "forbidden", False, "Do not retry"),
        (401, {"detail": "Authentication required."}, "unauthenticated", False, "token"),
        (409, {"detail": "already approved"}, "conflict", False, "re-read"),
        (500, {"detail": "boom"}, "upstream_error", True, "retry once"),
        (
            422,
            {"detail": [{"loc": ["body", "verdict"], "msg": "Field required"}]},
            "invalid_arguments",
            False,
            "inputSchema",
        ),
    ],
)
def test_http_failures_map_to_structured_errors(
    status: int, payload: Any, code: str, retryable: bool, hint_fragment: str
) -> None:
    server = AgentMcpServer(RecordingCaller(status=status, payload=payload))
    result = _call(server, "get_publication_summary", {"publication_key": "x"})
    assert result["isError"] is True
    error = result["structuredContent"]["error"]
    assert (error["code"], error["http_status"], error["retryable"]) == (code, status, retryable)
    assert hint_fragment in error["hint"]
    if status == 422:
        assert error["message"] == "body.verdict: Field required"
    assert result["content"][0]["text"].startswith(f"{code}: ")


def test_transport_failure_is_unavailable_not_a_crash() -> None:
    server = AgentMcpServer(RecordingCaller(raises=ConnectionError("refused")))
    result = _call(server, "list_publications", {})
    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "unavailable"
    assert result["structuredContent"]["error"]["retryable"] is True


def test_unknown_tool_lists_available_tools() -> None:
    response = AgentMcpServer(RecordingCaller()).handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "drop_tables"}}
    )
    assert response is not None
    assert "Available tools: get_proposal" in response["error"]["message"]


def test_list_publications_pages_with_trust() -> None:
    with TemporaryDirectory() as tmp:
        server = AgentMcpServer(InProcessCaller(_app_client(tmp)))
        first = _call(server, "list_publications", {"limit": 2})
        assert first["isError"] is False
        page = first["structuredContent"]
        assert len(page["publications"]) == 2
        assert page["total"] > 2
        assert page["next_cursor"]
        assert all(
            entry["trust"]["guidance"] == "trust_unknown" for entry in page["publications"]
        )
        second = _call(
            server, "list_publications", {"limit": 2, "cursor": page["next_cursor"]}
        )["structuredContent"]
        first_keys = {entry["publication_key"] for entry in page["publications"]}
        assert not first_keys & {entry["publication_key"] for entry in second["publications"]}

        bad_cursor = _call(server, "list_publications", {"cursor": "garbage"})
        assert bad_cursor["structuredContent"]["error"]["code"] == "invalid_arguments"


def test_publication_summary_surfaces_answer_guidance() -> None:
    with TemporaryDirectory() as tmp:
        server = AgentMcpServer(InProcessCaller(_app_client(tmp)))
        result = _call(server, "get_publication_summary", {"publication_key": "monthly_cashflow"})
        assert result["isError"] is False
        guidance = result["structuredContent"]["answer_guidance"]
        assert guidance["guidance"] == "trust_unknown"
        assert "do not claim" in guidance["guidance_detail"]


def test_propose_action_is_idempotent_and_says_it_is_only_a_draft() -> None:
    with TemporaryDirectory() as tmp:
        client = _app_client(tmp)
        server = AgentMcpServer(InProcessCaller(client))
        arguments = {
            "origin": "mcp:budget-agent",
            "title": "Review subscriptions",
            "verdict": "notify",
            "publication_keys": ["monthly_cashflow"],
            "idempotency_key": "budget-review-2026-10",
        }
        first = _call(server, "propose_action", arguments)["structuredContent"]
        second = _call(server, "propose_action", arguments)["structuredContent"]
        assert first["action_id"] == second["action_id"] == "agent_budget-review-2026-10"
        assert "Nothing has been executed" in first["agent_guidance"]
        pending = client.get("/api/actions/proposals", params={"status": "pending"}).json()
        assert len(pending["proposals"]) == 1

        client.post(
            f"/api/actions/proposals/{first['action_id']}/dismiss",
            json={"reason": "already handled"},
        )
        status = _call(server, "get_proposal", {"action_id": first["action_id"]})
        assert status["structuredContent"]["status"] == "dismissed"
        assert status["structuredContent"]["resolution_reason"] == "already handled"


def test_lineage_tool_reaches_lineage_route() -> None:
    caller = RecordingCaller(payload={"nodes": [], "edges": []})
    result = _call(AgentMcpServer(caller), "get_publication_lineage", {"publication_key": "monthly_cashflow"})
    assert result["isError"] is False
    assert caller.calls[0][:2] == ("GET", "/api/lineage/publication/monthly_cashflow")


def test_proposal_changes_tool_forwards_only_given_arguments() -> None:
    feed = {
        "schema_version": "resource-changes/v1",
        "reference": "action-proposals",
        "next_cursor": "apf.3",
        "events": [],
    }
    caller = RecordingCaller(payload=feed)
    server = AgentMcpServer(caller)
    result = _call(server, "list_proposal_changes", {})
    assert result["isError"] is False
    # The strict resource-changes/v1 envelope reaches the agent unchanged.
    assert result["structuredContent"] == feed
    _call(server, "list_proposal_changes", {"cursor": "apf.3", "limit": 10, "action_id": "a1"})
    assert caller.calls == [
        ("GET", "/api/actions/proposals/changes", {}, None),
        (
            "GET",
            "/api/actions/proposals/changes",
            {"cursor": "apf.3", "limit": 10, "action_id": "a1"},
            None,
        ),
    ]


def test_proposal_changes_tool_limits_match_the_route() -> None:
    from packages.application.use_cases import action_proposal_changes, agent_tool_catalog

    assert agent_tool_catalog.DEFAULT_CHANGES_LIMIT == action_proposal_changes.DEFAULT_LIMIT
    assert agent_tool_catalog.MAX_CHANGES_LIMIT == action_proposal_changes.MAX_LIMIT


def test_proposal_changes_tool_reports_a_foreign_cursor_as_invalid_arguments() -> None:
    with TemporaryDirectory() as tmp:
        server = AgentMcpServer(InProcessCaller(_app_client(tmp)))
        result = _call(server, "list_proposal_changes", {"cursor": "o12"})
        assert result["isError"] is True
        assert result["structuredContent"]["error"]["code"] == "invalid_arguments"


def test_validator_accepts_minimal_valid_arguments() -> None:
    for spec in AGENT_TOOL_SPECS:
        minimal: dict[str, Any] = {}
        for name in spec.input_schema.get("required", []):
            kind = spec.input_schema["properties"][name].get("type")
            enum = spec.input_schema["properties"][name].get("enum")
            minimal[name] = enum[0] if enum else {"object": {}, "array": []}.get(kind, "x")
        assert validate_tool_arguments(spec.input_schema, minimal) == [], spec.name
