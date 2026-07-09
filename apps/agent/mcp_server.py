"""MCP tool surface over the platform's agent-facing endpoints (Stage 10).

A minimal Model Context Protocol server speaking JSON-RPC 2.0 over
line-delimited stdio. Tools never touch storage directly — every call is
routed through the existing HTTP endpoints, so authentication, authorization,
policy checks, and the approval queue stay in charge
(``docs/architecture/agent-surfaces.md``).

Tools:

- ``list_publications`` — search the LLM semantic index
- ``get_publication_summary`` — one publication with glossary + samples
- ``propose_scenario`` — draft a what-if scenario through /api/scenarios/*
- ``propose_policy`` — draft a disabled operator policy through /control/policies
- ``propose_action`` — enter an action proposal into the shared approval queue

Run against a live API::

    python -m apps.agent.mcp_server --base-url http://localhost:8000

The protocol subset implemented (initialize, ping, tools/list, tools/call)
is the part MCP clients need for tool use; the server carries no session
state beyond the endpoint caller it is constructed with.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable, Protocol, TextIO

MCP_PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "homelab-analytics-agent"
SERVER_VERSION = "1.0.0"

JSONRPC_PARSE_ERROR = -32700
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602

# Scenario kinds an agent may propose; keys map onto /api/scenarios/{kind}.
SCENARIO_KINDS = (
    "income-change",
    "expense-shock",
    "tariff-shock",
    "loan-what-if",
    "homelab-cost-benefit",
)


class EndpointCaller(Protocol):
    """Transport used by tools to reach the existing API endpoints."""

    def call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        ...


class HttpEndpointCaller:
    """EndpointCaller over HTTP for a running API instance."""

    def __init__(self, base_url: str, *, bearer_token: str | None = None) -> None:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - httpx is a declared dependency
            raise RuntimeError(
                "httpx is required for the MCP server HTTP transport."
            ) from exc
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        self._client = httpx.Client(base_url=base_url, headers=headers, timeout=30.0)

    def call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        response = self._client.request(method, path, params=params, json=json_body)
        try:
            payload = response.json()
        except ValueError:
            payload = {"detail": response.text}
        return response.status_code, payload


def build_tool_definitions() -> list[dict[str, Any]]:
    """MCP tool definitions served by ``tools/list``."""
    return [
        {
            "name": "list_publications",
            "description": (
                "Search the semantic publication index. Returns publication "
                "keys, display names, and summaries; use "
                "get_publication_summary for columns and sample values."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Free-text filter over names, columns, and descriptions.",
                    }
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "get_publication_summary",
            "description": (
                "Retrieve one publication from the semantic index: summary, "
                "column glossary, bounded sample rows, and its contract and "
                "lineage endpoints."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "publication_key": {
                        "type": "string",
                        "description": "Publication key from list_publications.",
                    }
                },
                "required": ["publication_key"],
                "additionalProperties": False,
            },
        },
        {
            "name": "propose_scenario",
            "description": (
                "Draft a what-if scenario (income change, expense shock, "
                "tariff shock, loan what-if, or homelab cost-benefit). The "
                "scenario is computed from published data and stored for "
                "operator review; it does not change any canonical state."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "scenario_kind": {
                        "type": "string",
                        "enum": list(SCENARIO_KINDS),
                    },
                    "parameters": {
                        "type": "object",
                        "description": (
                            "Body for /api/scenarios/{scenario_kind}, e.g. "
                            '{"monthly_income_delta": "-250.00"} for income-change.'
                        ),
                    },
                },
                "required": ["scenario_kind", "parameters"],
                "additionalProperties": False,
            },
        },
        {
            "name": "propose_policy",
            "description": (
                "Draft an operator policy definition. The policy is created "
                "through the policy registry and stays subject to the "
                "platform's policy engine and review flow."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "display_name": {"type": "string"},
                    "policy_kind": {"type": "string"},
                    "rule_document": {"type": "object"},
                    "description": {"type": "string"},
                },
                "required": ["display_name", "policy_kind", "rule_document"],
                "additionalProperties": False,
            },
        },
        {
            "name": "propose_action",
            "description": (
                "Enter an action proposal into the approval queue. The "
                "proposal stays pending until an operator approves or "
                "dismisses it from the web shell; agents cannot execute "
                "actions directly."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "Identity of the proposing agent or tool.",
                    },
                    "title": {"type": "string"},
                    "verdict": {
                        "type": "string",
                        "description": "Proposed action verdict, e.g. notify or approval_required.",
                    },
                    "value": {"type": "string"},
                    "summary": {"type": "string"},
                    "publication_keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Publications consulted while drafting (provenance).",
                    },
                },
                "required": ["origin", "title", "verdict"],
                "additionalProperties": False,
            },
        },
    ]


def _compact_index(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "publications": [
            {
                "publication_key": entry.get("publication_key"),
                "display_name": entry.get("display_name"),
                "summary": entry.get("summary"),
            }
            for entry in payload.get("publications", [])
        ],
    }


class AgentMcpServer:
    """Dispatch MCP requests onto the platform endpoints."""

    def __init__(self, caller: EndpointCaller) -> None:
        self._caller = caller
        self._tool_handlers: dict[str, Callable[[dict[str, Any]], tuple[int, Any]]] = {
            "list_publications": self._list_publications,
            "get_publication_summary": self._get_publication_summary,
            "propose_scenario": self._propose_scenario,
            "propose_policy": self._propose_policy,
            "propose_action": self._propose_action,
        }

    # -- tool handlers -----------------------------------------------------

    def _list_publications(self, arguments: dict[str, Any]) -> tuple[int, Any]:
        params: dict[str, Any] = {}
        if arguments.get("query"):
            params["query"] = arguments["query"]
        status, payload = self._caller.call(
            "GET", "/api/agent/semantic-index", params=params
        )
        if status == 200 and isinstance(payload, dict):
            return status, _compact_index(payload)
        return status, payload

    def _get_publication_summary(self, arguments: dict[str, Any]) -> tuple[int, Any]:
        publication_key = arguments["publication_key"]
        return self._caller.call(
            "GET", f"/api/agent/semantic-index/{publication_key}"
        )

    def _propose_scenario(self, arguments: dict[str, Any]) -> tuple[int, Any]:
        scenario_kind = arguments["scenario_kind"]
        if scenario_kind not in SCENARIO_KINDS:
            raise ValueError(f"Unsupported scenario kind: {scenario_kind}")
        return self._caller.call(
            "POST",
            f"/api/scenarios/{scenario_kind}",
            json_body=dict(arguments["parameters"]),
        )

    def _propose_policy(self, arguments: dict[str, Any]) -> tuple[int, Any]:
        body = {
            "display_name": arguments["display_name"],
            "policy_kind": arguments["policy_kind"],
            "rule_document": dict(arguments["rule_document"]),
        }
        if arguments.get("description"):
            body["description"] = arguments["description"]
        return self._caller.call("POST", "/control/policies", json_body=body)

    def _propose_action(self, arguments: dict[str, Any]) -> tuple[int, Any]:
        body: dict[str, Any] = {
            "policy_id": arguments["origin"],
            "policy_name": arguments["title"],
            "verdict": arguments["verdict"],
            "value": arguments.get("value"),
            "adapter": "platform",
            "source_kind": "agent",
            "source_summary": arguments.get("summary"),
        }
        publication_keys = arguments.get("publication_keys") or []
        if publication_keys:
            body["provenance"] = {"publication_keys": list(publication_keys)}
        return self._caller.call("POST", "/api/actions/proposals", json_body=body)

    # -- MCP dispatch ------------------------------------------------------

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Handle one JSON-RPC message; returns None for notifications."""
        method = message.get("method")
        message_id = message.get("id")
        if message_id is None:
            # Notifications (e.g. notifications/initialized) need no reply.
            return None
        if method == "initialize":
            return self._result(
                message_id,
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION,
                    },
                },
            )
        if method == "ping":
            return self._result(message_id, {})
        if method == "tools/list":
            return self._result(message_id, {"tools": build_tool_definitions()})
        if method == "tools/call":
            return self._handle_tool_call(message_id, message.get("params") or {})
        return self._error(
            message_id, JSONRPC_METHOD_NOT_FOUND, f"Unknown method: {method}"
        )

    def _handle_tool_call(
        self, message_id: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        tool_name = params.get("name")
        handler = self._tool_handlers.get(tool_name or "")
        if handler is None:
            return self._error(
                message_id, JSONRPC_INVALID_PARAMS, f"Unknown tool: {tool_name}"
            )
        arguments = params.get("arguments") or {}
        try:
            status, payload = handler(arguments)
        except (KeyError, TypeError, ValueError) as exc:
            return self._result(
                message_id,
                {
                    "content": [{"type": "text", "text": f"Invalid arguments: {exc}"}],
                    "isError": True,
                },
            )
        is_error = status >= 400
        return self._result(
            message_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(payload, default=str, indent=2),
                    }
                ],
                "structuredContent": payload if isinstance(payload, dict) else None,
                "isError": is_error,
            },
        )

    @staticmethod
    def _result(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": message_id, "result": result}

    @staticmethod
    def _error(message_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": {"code": code, "message": message},
        }


def serve_stdio(
    server: AgentMcpServer,
    *,
    stdin: TextIO,
    stdout: TextIO,
) -> None:
    """Serve line-delimited JSON-RPC until stdin closes."""
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response: dict[str, Any] | None = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": JSONRPC_PARSE_ERROR, "message": "Parse error"},
            }
        else:
            response = server.handle_message(message)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        required=True,
        help="Base URL of a running homelab-analytics API, e.g. http://localhost:8000",
    )
    parser.add_argument(
        "--bearer-token",
        default=None,
        help="Optional bearer token forwarded on every endpoint call.",
    )
    args = parser.parse_args(argv)
    server = AgentMcpServer(
        HttpEndpointCaller(args.base_url, bearer_token=args.bearer_token)
    )
    serve_stdio(server, stdin=sys.stdin, stdout=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
