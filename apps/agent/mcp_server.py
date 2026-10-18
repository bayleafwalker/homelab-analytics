"""MCP tool surface over the platform's agent-facing endpoints (Stage 10).

A minimal Model Context Protocol server speaking JSON-RPC 2.0 over
line-delimited stdio. Tools never touch storage directly — every call is
routed through the existing HTTP endpoints, so authentication, authorization,
policy checks, and the approval queue stay in charge
(``docs/architecture/agent-surfaces.md``).

The tool list is built from the shared catalog
(``packages.application.use_cases.agent_tool_catalog``), the same catalog the
operator control surface shows at ``GET /api/agent/catalog``:

- ``list_publications`` — page through the semantic index, with trust
- ``get_publication_summary`` — one publication with glossary, sample, trust
- ``get_publication_lineage`` — runs, relations, and sources behind it
- ``get_proposal`` — status, resolver, and history of a drafted proposal
- ``propose_scenario`` — draft a what-if scenario through /api/scenarios/*
- ``propose_policy`` — draft a (disabled) operator policy
- ``propose_action`` — enter an action proposal into the approval queue

What the agent sees is designed for honest answers:

- every publication carries ``trust.guidance``; ``initialize`` returns
  instructions telling the agent to follow it
- arguments are validated against each tool's ``inputSchema`` before any
  endpoint call, and failures come back as ``isError`` results with a
  structured ``error`` object ``{code, http_status, message, hint, retryable}``
  instead of raw HTTP payloads
- draft tools say plainly that nothing has happened until an operator acts

Run against a live API::

    python -m apps.agent.mcp_server --base-url http://localhost:8000

The protocol subset implemented (initialize, ping, tools/list, tools/call)
is the part MCP clients need for tool use; the server carries no session
state beyond the endpoint caller it is constructed with.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Callable, Protocol, TextIO

from packages.application.use_cases.agent_tool_catalog import (
    AGENT_TOOL_SPECS,
    AGENT_TOOL_SPECS_BY_NAME,
    DEFAULT_PAGE_LIMIT,
    SCENARIO_KINDS,
)

MCP_PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "homelab-analytics-agent"
SERVER_VERSION = "1.1.0"

JSONRPC_PARSE_ERROR = -32700
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602

SERVER_INSTRUCTIONS = (
    "You are reading a household's published analytics through "
    "homelab-analytics. Rules: (1) Read only through these tools; never "
    "assume data you were not given. (2) Before stating any figure, check "
    "the publication's trust.guidance: state_as_current — you may state it "
    "as current; state_with_caveat — state it with the assessed_at date and "
    "the caveat; do_not_state_as_current or trust_unknown — say the data may "
    "be out of date and do not present it as current. (3) Samples are "
    "bounded; when sample.truncated is true, do not compute totals from it. "
    "(4) propose_* tools only draft: nothing changes until an operator "
    "approves. Never tell the user an action was taken. (5) Cite the "
    "publication_keys you used in propose_action."
)

__all__ = [
    "AgentMcpServer",
    "EndpointCaller",
    "HttpEndpointCaller",
    "SCENARIO_KINDS",
    "SERVER_INSTRUCTIONS",
    "build_tool_definitions",
    "serve_stdio",
    "validate_tool_arguments",
]


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
    return [spec.mcp_definition() for spec in AGENT_TOOL_SPECS]


# -- argument validation ------------------------------------------------------

_JSON_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
}


def _type_ok(value: Any, expected: str) -> bool:
    if expected in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _JSON_TYPES.get(expected, (object,)))


def validate_tool_arguments(schema: dict[str, Any], arguments: Any) -> list[str]:
    """Validate arguments against the subset of JSON Schema tools use.

    Covers required keys, ``additionalProperties: false``, primitive types,
    ``enum``, integer bounds, string ``pattern``, and array item types — the
    constraints declared in the catalog. Returns human-readable problems.
    """
    if not isinstance(arguments, dict):
        return ["arguments must be an object"]
    problems: list[str] = []
    properties: dict[str, Any] = schema.get("properties", {})
    for name in schema.get("required", []):
        if name not in arguments:
            problems.append(f"missing required argument {name!r}")
    if schema.get("additionalProperties") is False:
        for name in arguments:
            if name not in properties:
                allowed = ", ".join(sorted(properties)) or "none"
                problems.append(f"unknown argument {name!r} (allowed: {allowed})")
    for name, value in arguments.items():
        spec = properties.get(name)
        if spec is None:
            continue
        expected = spec.get("type")
        if isinstance(expected, str) and not _type_ok(value, expected):
            problems.append(f"argument {name!r} must be of type {expected}")
            continue
        if "enum" in spec and value not in spec["enum"]:
            problems.append(
                f"argument {name!r} must be one of {', '.join(map(str, spec['enum']))}"
            )
        if expected == "integer":
            if "minimum" in spec and value < spec["minimum"]:
                problems.append(f"argument {name!r} must be >= {spec['minimum']}")
            if "maximum" in spec and value > spec["maximum"]:
                problems.append(f"argument {name!r} must be <= {spec['maximum']}")
        if expected == "string" and "pattern" in spec:
            if not re.fullmatch(spec["pattern"], value):
                problems.append(f"argument {name!r} must match {spec['pattern']}")
        if expected == "array":
            item_type = spec.get("items", {}).get("type")
            if isinstance(item_type, str) and not all(
                _type_ok(item, item_type) for item in value
            ):
                problems.append(f"argument {name!r} items must be of type {item_type}")
    return problems


# -- error envelope -----------------------------------------------------------

_STATUS_CODES: dict[int, str] = {
    400: "invalid_arguments",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "invalid_arguments",
}

_DEFAULT_HINTS: dict[str, str] = {
    "invalid_arguments": "Fix the arguments using the tool's inputSchema and retry.",
    "unauthenticated": (
        "The MCP server's credentials were rejected; tell the user the "
        "service token needs to be configured or rotated."
    ),
    "forbidden": (
        "The configured token lacks the scope this tool needs (see the tool "
        "catalog). Do not retry; tell the user which tool was refused."
    ),
    "not_found": "Check the identifier; list_publications returns valid publication keys.",
    "conflict": "The target changed state; re-read it before deciding what to do.",
    "upstream_error": "The platform failed; retry once, then report the failure.",
    "unavailable": "The platform could not be reached; report that it is unavailable.",
}


def _error_result(
    code: str,
    message: str,
    *,
    http_status: int | None = None,
    hint: str | None = None,
) -> dict[str, Any]:
    error = {
        "code": code,
        "http_status": http_status,
        "message": message,
        "hint": hint or _DEFAULT_HINTS.get(code, ""),
        "retryable": code in ("upstream_error", "unavailable"),
    }
    text = f"{code}: {message}"
    if error["hint"]:
        text += f" Hint: {error['hint']}"
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": {"error": error},
        "isError": True,
    }


def _detail_message(payload: Any) -> str:
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list):
            parts = []
            for item in detail:
                if isinstance(item, dict):
                    location = ".".join(str(part) for part in item.get("loc", []))
                    parts.append(f"{location}: {item.get('msg', '')}".strip(": "))
            if parts:
                return "; ".join(parts)
    return json.dumps(payload, default=str)[:500]


def _http_error_result(status: int, payload: Any) -> dict[str, Any]:
    code = _STATUS_CODES.get(status, "upstream_error" if status >= 500 else "invalid_arguments")
    return _error_result(code, _detail_message(payload), http_status=status)


# -- payload shaping ----------------------------------------------------------


def _compact_trust(trust: Any) -> dict[str, Any] | None:
    if not isinstance(trust, dict):
        return None
    return {
        "guidance": trust.get("guidance"),
        "guidance_detail": trust.get("guidance_detail"),
        "confidence_verdict": trust.get("confidence_verdict"),
        "freshness_state": trust.get("freshness_state"),
        "assessed_at": trust.get("assessed_at"),
    }


def _compact_index(payload: dict[str, Any]) -> dict[str, Any]:
    publications = payload.get("publications", [])
    return {
        "schema_version": payload.get("schema_version"),
        "publications": [
            {
                "publication_key": entry.get("publication_key"),
                "display_name": entry.get("display_name"),
                "summary": entry.get("summary"),
                "trust": _compact_trust(entry.get("trust")),
            }
            for entry in publications
        ],
        "total": payload.get("total", len(publications)),
        "next_cursor": payload.get("next_cursor"),
    }


_DRAFT_GUIDANCE = (
    "This is a draft awaiting operator approval. Nothing has been executed; "
    "do not tell the user the action was taken. Use get_proposal with this "
    "action_id to check whether an operator approved or dismissed it."
)


ToolHandler = Callable[[dict[str, Any]], tuple[int, Any]]


class AgentMcpServer:
    """Dispatch MCP requests onto the platform endpoints."""

    def __init__(self, caller: EndpointCaller) -> None:
        self._caller = caller
        self._tool_handlers: dict[str, ToolHandler] = {
            "list_publications": self._list_publications,
            "get_publication_summary": self._get_publication_summary,
            "get_publication_lineage": self._get_publication_lineage,
            "get_proposal": self._get_proposal,
            "propose_scenario": self._propose_scenario,
            "propose_policy": self._propose_policy,
            "propose_action": self._propose_action,
        }
        missing = set(AGENT_TOOL_SPECS_BY_NAME) ^ set(self._tool_handlers)
        if missing:  # pragma: no cover - guarded by tests
            raise RuntimeError(f"Tool catalog and handlers disagree: {sorted(missing)}")

    # -- tool handlers -----------------------------------------------------

    def _list_publications(self, arguments: dict[str, Any]) -> tuple[int, Any]:
        params: dict[str, Any] = {"limit": arguments.get("limit", DEFAULT_PAGE_LIMIT)}
        if arguments.get("query"):
            params["query"] = arguments["query"]
        if arguments.get("cursor"):
            params["cursor"] = arguments["cursor"]
        status, payload = self._caller.call(
            "GET", "/api/agent/semantic-index", params=params
        )
        if status == 200 and isinstance(payload, dict):
            return status, _compact_index(payload)
        return status, payload

    def _get_publication_summary(self, arguments: dict[str, Any]) -> tuple[int, Any]:
        publication_key = arguments["publication_key"]
        status, payload = self._caller.call(
            "GET", f"/api/agent/semantic-index/{publication_key}"
        )
        if status == 200 and isinstance(payload, dict):
            publication = payload.get("publication") or {}
            payload = {**payload, "answer_guidance": _compact_trust(publication.get("trust"))}
        return status, payload

    def _get_publication_lineage(self, arguments: dict[str, Any]) -> tuple[int, Any]:
        return self._caller.call(
            "GET", f"/api/lineage/publication/{arguments['publication_key']}"
        )

    def _get_proposal(self, arguments: dict[str, Any]) -> tuple[int, Any]:
        return self._caller.call("GET", f"/api/actions/proposals/{arguments['action_id']}")

    def _propose_scenario(self, arguments: dict[str, Any]) -> tuple[int, Any]:
        scenario_kind = arguments["scenario_kind"]
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
        if arguments.get("idempotency_key"):
            # Same key -> same pending proposal (the registry refreshes it).
            body["action_id"] = f"agent_{arguments['idempotency_key']}"
        publication_keys = arguments.get("publication_keys") or []
        if publication_keys:
            body["provenance"] = {"publication_keys": list(publication_keys)}
        status, payload = self._caller.call("POST", "/api/actions/proposals", json_body=body)
        if status == 200 and isinstance(payload, dict):
            payload = {**payload, "agent_guidance": _DRAFT_GUIDANCE}
        return status, payload

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
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION,
                    },
                    "instructions": SERVER_INSTRUCTIONS,
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
        spec = AGENT_TOOL_SPECS_BY_NAME.get(tool_name or "")
        if handler is None or spec is None:
            known = ", ".join(sorted(self._tool_handlers))
            return self._error(
                message_id,
                JSONRPC_INVALID_PARAMS,
                f"Unknown tool: {tool_name}. Available tools: {known}",
            )
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        problems = validate_tool_arguments(spec.input_schema, arguments)
        if problems:
            return self._result(
                message_id,
                _error_result("invalid_arguments", "; ".join(problems)),
            )
        try:
            status, payload = handler(arguments)
        except (KeyError, TypeError, ValueError) as exc:
            return self._result(
                message_id, _error_result("invalid_arguments", str(exc))
            )
        except Exception as exc:  # noqa: BLE001 - transport failures become tool errors
            return self._result(
                message_id,
                _error_result("unavailable", f"{type(exc).__name__}: {exc}"),
            )
        if status >= 400:
            return self._result(message_id, _http_error_result(status, payload))
        return self._result(
            message_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(payload, default=str, indent=2),
                    }
                ],
                "structuredContent": payload if isinstance(payload, dict) else {"result": payload},
                "isError": False,
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
