"""ToolBroker over the MCP tool surface for AssistantRuntime sessions.

Runtimes never call HTTP endpoints or storage: they call this broker, which
routes through :class:`apps.agent.mcp_server.AgentMcpServer` — so the same
argument validation, structured errors, auth, and approval gating apply to
the household assistant as to any external MCP agent. The broker adds the
boundary concerns the runtime must not own:

- refuse tools outside the policy's grants (defence in depth; the session
  recorder checks first)
- redact sample rows when the policy asks, so row values never reach a
  provider prompt unless explicitly allowed
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.agent.mcp_server import AgentMcpServer
from packages.application.use_cases.assistant_runtime import (
    AssistantPolicy,
    ToolOutcome,
)


class McpToolBroker:
    def __init__(self, server: AgentMcpServer, policy: AssistantPolicy) -> None:
        self._server = server
        self._policy = policy
        self._next_id = 0

    def invoke(self, tool_name: str, arguments: Mapping[str, Any]) -> ToolOutcome:
        if not self._policy.permits(tool_name):
            return ToolOutcome(
                tool_name=tool_name,
                is_error=True,
                payload={"error": {"code": "not_granted", "message": f"{tool_name} is not granted."}},
                error_code="not_granted",
            )
        self._next_id += 1
        response = self._server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": self._next_id,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": dict(arguments)},
            }
        )
        if response is None or "error" in response:
            message = (response or {}).get("error", {}).get("message", "no response")
            return ToolOutcome(
                tool_name=tool_name,
                is_error=True,
                payload={"error": {"code": "protocol_error", "message": message}},
                error_code="protocol_error",
            )
        result = response["result"]
        payload: dict[str, Any] = dict(result.get("structuredContent") or {})
        if result.get("isError"):
            code = payload.get("error", {}).get("code")
            return ToolOutcome(tool_name=tool_name, is_error=True, payload=payload, error_code=code)
        if self._policy.redact_sample_rows:
            payload = _redact_sample_rows(payload)
        return ToolOutcome(tool_name=tool_name, is_error=False, payload=payload)


def _redact_sample_rows(payload: dict[str, Any]) -> dict[str, Any]:
    publication = payload.get("publication")
    if not isinstance(publication, dict) or not isinstance(publication.get("sample"), dict):
        return payload
    sample = dict(publication["sample"])
    sample["rows"] = []
    sample["redacted"] = True
    return {**payload, "publication": {**publication, "sample": sample}}
