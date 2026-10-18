"""A local MCP client drives the real server entry point over stdio.

Sprint #533 item #1967: "local MCP client can list tools and exercise each".
``apps.agent.mcp_server.main`` runs exactly as ``python -m apps.agent.mcp_server
--base-url ... --bearer-token ...`` would: CLI parsing, the HTTP endpoint
caller, and the line-delimited JSON-RPC transport. Only the HTTP client is
swapped for the API's in-process ASGI test client, so no socket is opened.

Item #1968 end to end: an MCP-originated ``propose_action`` lands in the shared
queue, is approved through ``/api/actions/proposals/{id}/approve`` (the route
the web shell's approve form posts to), and ``get_proposal`` then reports the
resolution and its history.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi.testclient import TestClient

from apps.agent.mcp_server import build_tool_definitions, main
from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.domains.finance.pipelines.transformation_transactions import refresh_monthly_cashflow
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository

WEB_SHELL_APPROVE_ROUTE = (
    Path(__file__).resolve().parents[1]
    / "apps/web/frontend/app/control/agents/proposals/[actionId]/approve/route.js"
)


def _client(tmp: str) -> TestClient:
    service = AccountTransactionService(
        landing_root=Path(tmp) / "landing",
        metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
    )
    transformation = TransformationService(DuckDBStore.memory())
    transformation.load_transactions(
        [
            {
                "booked_at": f"2026-{month}-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "3000.00",
                "currency": "EUR",
                "description": "salary",
            }
            for month in ("01", "02", "03", "04", "05", "06", "07")
        ],
        run_id="run-mcp-stdio",
    )
    refresh_monthly_cashflow(transformation.store)
    return TestClient(
        create_app(
            service,
            config_repository=IngestionConfigRepository(Path(tmp) / "config.db"),
            transformation_service=transformation,
        )
    )


def _session(client: TestClient, messages: list[dict[str, Any]]) -> dict[Any, dict[str, Any]]:
    stdin = io.StringIO("".join(json.dumps(message) + "\n" for message in messages))
    stdout = io.StringIO()
    exit_code = main(
        ["--base-url", "http://testserver", "--bearer-token", "hla_test_token"],
        stdin=stdin,
        stdout=stdout,
        http_client=client,
    )
    assert exit_code == 0
    assert client.headers["Authorization"] == "Bearer hla_test_token"
    replies = [json.loads(line) for line in stdout.getvalue().splitlines()]
    return {reply["id"]: reply for reply in replies}


def _call(message_id: int, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


def _structured(reply: dict[str, Any]) -> dict[str, Any]:
    result = reply["result"]
    assert not result.get("isError"), result["content"]
    return dict(result["structuredContent"])


def test_local_mcp_client_lists_and_exercises_every_tool_over_stdio() -> None:
    with TemporaryDirectory() as tmp:
        client = _client(tmp)
        replies = _session(
            client,
            [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                _call(3, "list_publications", {"query": "cashflow", "limit": 5}),
                _call(4, "get_publication_summary", {"publication_key": "monthly_cashflow"}),
                _call(5, "get_publication_lineage", {"publication_key": "monthly_cashflow"}),
                _call(
                    6,
                    "propose_scenario",
                    {
                        "scenario_kind": "income-change",
                        "parameters": {"monthly_income_delta": "-250.00"},
                    },
                ),
                _call(
                    7,
                    "propose_policy",
                    {
                        "display_name": "Agent drafted: negative cashflow alert",
                        "policy_kind": "threshold",
                        "rule_document": {
                            "rule_kind": "publication_value_comparison",
                            "publication_key": "monthly_cashflow",
                            "field_name": "net",
                            "operator": "lt",
                            "threshold": 0,
                            "unit": "currency",
                        },
                    },
                ),
                _call(
                    8,
                    "propose_action",
                    {
                        "origin": "mcp:budget-review-agent",
                        "title": "Review the salary trend",
                        "verdict": "notify",
                        "summary": "Seven months of steady income.",
                        "publication_keys": ["monthly_cashflow"],
                        "idempotency_key": "budget-review:2026-07",
                    },
                ),
                _call(9, "list_proposal_changes", {"limit": 50}),
            ],
        )

        assert sorted(replies) == [1, 2, 3, 4, 5, 6, 7, 8, 9]  # the notification got no reply
        assert "tools" in replies[1]["result"]["capabilities"]
        listed = {tool["name"] for tool in replies[2]["result"]["tools"]}
        assert listed == {tool["name"] for tool in build_tool_definitions()}
        assert {
            "list_publications",
            "get_publication_summary",
            "get_publication_lineage",
            "get_proposal",
            "list_proposal_changes",
            "propose_scenario",
            "propose_policy",
            "propose_action",
        } <= listed

        publications = _structured(replies[3])["publications"]
        assert "monthly_cashflow" in [entry["publication_key"] for entry in publications]
        summary = _structured(replies[4])["publication"]
        assert summary["columns"] and summary["sample"]["truncated"] is True
        assert _structured(replies[5])
        assert "scenario_id" in _structured(replies[6])
        assert "policy_id" in _structured(replies[7])
        drafted = _structured(replies[8])
        assert drafted["status"] == "pending"
        assert (drafted["adapter"], drafted["source_kind"]) == ("platform", "agent")
        action_id = drafted["action_id"]
        feed = _structured(replies[9])
        assert feed["schema_version"] == "resource-changes/v1"
        assert feed["next_cursor"].startswith("apf.")
        assert [
            (event["data"]["action_id"], event["data"]["kind"]) for event in feed["events"]
        ] == [(action_id, "drafted")]

        # The web shell's approve form posts to the generalized route.
        assert "/api/actions/proposals/" in WEB_SHELL_APPROVE_ROUTE.read_text()
        approved = client.post(
            f"/api/actions/proposals/{action_id}/approve", json={"reason": "looks right"}
        )
        assert approved.status_code == 200

        later = _session(
            client,
            [
                _call(1, "get_proposal", {"action_id": action_id}),
                _call(
                    2,
                    "list_proposal_changes",
                    {"cursor": feed["next_cursor"], "action_id": action_id},
                ),
            ],
        )
        proposal = _structured(later[1])
        proposal = proposal.get("proposal", proposal)
        assert proposal["status"] == "approved"
        assert proposal["resolution_reason"] == "looks right"
        assert [event["kind"] for event in proposal["history"]] == ["drafted", "approved"]
        # Resuming from the earlier cursor yields only the approval, as terminal.
        resumed = _structured(later[2])
        assert resumed["reference"] == f"action-proposals/{action_id}"
        assert [(event["data"]["kind"], event["terminal"]) for event in resumed["events"]] == [
            ("approved", True)
        ]
