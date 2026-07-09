"""Tests for the MCP tool surface (apps.agent.mcp_server).

A stub agent runner drives the server exactly like a local MCP client:
initialize → tools/list → tools/call. Endpoint calls are routed into a real
FastAPI app via the test client, so the tools exercise the same routes the
production server would call over HTTP.
"""
from __future__ import annotations

import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi.testclient import TestClient

from apps.agent.mcp_server import (
    AgentMcpServer,
    build_tool_definitions,
    serve_stdio,
)
from apps.api.app import create_app
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository


class InProcessEndpointCaller:
    """EndpointCaller that dispatches into a FastAPI test client."""

    def __init__(self, client: TestClient) -> None:
        self._client = client

    def call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        response = self._client.request(method, path, params=params, json=json_body)
        return response.status_code, response.json()


class StubAgentRunner:
    """Minimal local MCP client: sends JSON-RPC requests, collects replies."""

    def __init__(self, server: AgentMcpServer) -> None:
        self._server = server
        self._next_id = 0

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._next_id += 1
        response = self._server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": self._next_id,
                "method": method,
                "params": params or {},
            }
        )
        assert response is not None, f"expected a response for {method}"
        return response

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request(
            "tools/call", {"name": name, "arguments": arguments or {}}
        )


def _build_client(tmp: str, *, load_cashflow: bool = True) -> TestClient:
    from packages.domains.finance.pipelines.account_transaction_service import (
        AccountTransactionService,
    )

    service = AccountTransactionService(
        landing_root=Path(tmp) / "landing",
        metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
    )
    ts = TransformationService(DuckDBStore.memory())
    if load_cashflow:
        transactions = []
        for month in ("01", "02", "03"):
            transactions += [
                {
                    "booked_at": f"2026-{month}-03T08:00:00+00:00",
                    "account_id": "checking",
                    "counterparty_name": "Employer",
                    "amount": "3000.00",
                    "currency": "EUR",
                    "description": "salary",
                },
                {
                    "booked_at": f"2026-{month}-10T08:00:00+00:00",
                    "account_id": "checking",
                    "counterparty_name": "Landlord",
                    "amount": "-1200.00",
                    "currency": "EUR",
                    "description": "rent",
                },
            ]
        ts.load_transactions(transactions, run_id="run-mcp-001")
        ts.refresh_monthly_cashflow()
    app = create_app(service, transformation_service=ts)
    return TestClient(app)


def _runner(client: TestClient) -> StubAgentRunner:
    return StubAgentRunner(AgentMcpServer(InProcessEndpointCaller(client)))


def _structured(response: dict[str, Any]) -> dict[str, Any]:
    result = response["result"]
    assert not result.get("isError"), result["content"]
    return result["structuredContent"]


class McpHandshakeAndToolListTests(unittest.TestCase):
    def test_initialize_reports_tool_capability(self) -> None:
        with TemporaryDirectory() as tmp:
            runner = _runner(_build_client(tmp, load_cashflow=False))
            response = runner.request("initialize")
            result = response["result"]
            self.assertIn("protocolVersion", result)
            self.assertIn("tools", result["capabilities"])
            self.assertEqual(
                "homelab-analytics-agent", result["serverInfo"]["name"]
            )

    def test_tools_list_covers_retrieval_and_proposals(self) -> None:
        with TemporaryDirectory() as tmp:
            runner = _runner(_build_client(tmp, load_cashflow=False))
            tools = runner.request("tools/list")["result"]["tools"]
            self.assertEqual(
                [tool["name"] for tool in build_tool_definitions()],
                [tool["name"] for tool in tools],
            )
            names = {tool["name"] for tool in tools}
            self.assertLessEqual(
                {
                    "list_publications",
                    "get_publication_summary",
                    "propose_scenario",
                    "propose_policy",
                    "propose_action",
                },
                names,
            )
            for tool in tools:
                self.assertIn("inputSchema", tool)
                self.assertEqual("object", tool["inputSchema"]["type"])

    def test_unknown_method_returns_jsonrpc_error(self) -> None:
        with TemporaryDirectory() as tmp:
            runner = _runner(_build_client(tmp, load_cashflow=False))
            response = runner.request("resources/list")
            self.assertIn("error", response)


class McpRetrievalToolTests(unittest.TestCase):
    def test_list_publications_filters_by_query(self) -> None:
        with TemporaryDirectory() as tmp:
            runner = _runner(_build_client(tmp, load_cashflow=False))
            payload = _structured(
                runner.call_tool("list_publications", {"query": "cashflow"})
            )
            keys = [entry["publication_key"] for entry in payload["publications"]]
            self.assertIn("monthly_cashflow", keys)

    def test_get_publication_summary_returns_glossary_and_sample(self) -> None:
        with TemporaryDirectory() as tmp:
            runner = _runner(_build_client(tmp))
            payload = _structured(
                runner.call_tool(
                    "get_publication_summary",
                    {"publication_key": "monthly_cashflow"},
                )
            )
            publication = payload["publication"]
            self.assertEqual("monthly_cashflow", publication["publication_key"])
            self.assertTrue(publication["columns"])
            self.assertIsNotNone(publication["sample"])
            self.assertTrue(publication["lineage_path"].startswith("/api/lineage/"))

    def test_unknown_publication_marks_tool_error(self) -> None:
        with TemporaryDirectory() as tmp:
            runner = _runner(_build_client(tmp, load_cashflow=False))
            response = runner.call_tool(
                "get_publication_summary", {"publication_key": "nope"}
            )
            self.assertTrue(response["result"]["isError"])


class McpProposalToolTests(unittest.TestCase):
    def test_propose_scenario_creates_income_change(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            runner = _runner(client)
            payload = _structured(
                runner.call_tool(
                    "propose_scenario",
                    {
                        "scenario_kind": "income-change",
                        "parameters": {"monthly_income_delta": "-250.00"},
                    },
                )
            )
            self.assertIn("scenario_id", payload)
            listed = client.get("/api/scenarios").json()["rows"]
            self.assertIn(
                payload["scenario_id"], [row["scenario_id"] for row in listed]
            )

    def test_propose_scenario_rejects_unknown_kind(self) -> None:
        with TemporaryDirectory() as tmp:
            runner = _runner(_build_client(tmp, load_cashflow=False))
            response = runner.call_tool(
                "propose_scenario",
                {"scenario_kind": "delete-everything", "parameters": {}},
            )
            self.assertTrue(response["result"]["isError"])

    def test_propose_policy_creates_policy_definition(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp, load_cashflow=False)
            runner = _runner(client)
            payload = _structured(
                runner.call_tool(
                    "propose_policy",
                    {
                        "display_name": "Agent drafted: high electricity alert",
                        "policy_kind": "threshold",
                        "rule_document": {
                            "rule_kind": "publication_value_comparison",
                            "publication_key": "monthly_cashflow",
                            "field_name": "net",
                            "operator": "lt",
                            "threshold": 0,
                            "unit": "currency",
                        },
                        "description": "Drafted from mart_utility_cost_summary.",
                    },
                )
            )
            self.assertIn("policy_id", payload)
            listed = client.get("/control/policies").json()["policies"]
            self.assertIn(
                payload["policy_id"], [row["policy_id"] for row in listed]
            )

    def test_propose_action_enters_shared_approval_queue(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp, load_cashflow=False)
            runner = _runner(client)
            payload = _structured(
                runner.call_tool(
                    "propose_action",
                    {
                        "origin": "mcp:budget-review-agent",
                        "title": "Review rising electricity tariff",
                        "verdict": "notify",
                        "summary": "Tariff rose 12% month over month.",
                        "publication_keys": ["electricity_price_current"],
                    },
                )
            )
            self.assertEqual("pending", payload["status"])
            self.assertEqual("agent", payload["source_kind"])
            self.assertEqual("platform", payload["adapter"])
            self.assertEqual(
                ["electricity_price_current"],
                payload["provenance"]["publication_keys"],
            )
            # Pending in the same queue the web shell reads and approves from.
            ha_view = client.get("/api/ha/actions/proposals").json()["proposals"]
            self.assertIn(
                payload["action_id"], [row["action_id"] for row in ha_view]
            )
            approved = client.post(
                f"/api/ha/actions/proposals/{payload['action_id']}/approve"
            )
            self.assertEqual(200, approved.status_code)
            self.assertEqual("approved", approved.json()["status"])


class McpStdioTransportTests(unittest.TestCase):
    def test_line_delimited_stdio_round_trip(self) -> None:
        with TemporaryDirectory() as tmp:
            server = AgentMcpServer(
                InProcessEndpointCaller(_build_client(tmp, load_cashflow=False))
            )
            requests = "\n".join(
                [
                    json.dumps(
                        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
                    ),
                    json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                    json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
                    "not-json",
                ]
            )
            stdout = io.StringIO()
            serve_stdio(server, stdin=io.StringIO(requests + "\n"), stdout=stdout)
            responses = [
                json.loads(line) for line in stdout.getvalue().splitlines()
            ]
            # Notification produced no reply; parse error produced one.
            self.assertEqual(3, len(responses))
            self.assertEqual(1, responses[0]["id"])
            self.assertEqual(2, responses[1]["id"])
            self.assertIn("tools", responses[1]["result"])
            self.assertEqual(-32700, responses[2]["error"]["code"])


if __name__ == "__main__":
    unittest.main()
