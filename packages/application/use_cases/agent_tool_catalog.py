"""Single source of truth for the agent tool catalog.

The MCP server (``apps.agent.mcp_server``) builds its ``tools/list`` reply
from these specs, and the API serves the same specs to operators at
``GET /api/agent/catalog`` so the control surface can show exactly which
endpoints and publications each tool touches, what it may change, and which
service-token scope it needs. Keeping one catalog means the operator view can
never drift from what agents are actually offered.

Each spec also carries a vuoro-aligned operation name (``domain.noun.verb``,
the vuoro-adapter-kit operation-name pattern) plus ``execution_semantics`` and
``idempotency`` values from the same vocabulary, so the capability manifest
(``GET /api/agent/manifest``) is a projection of this catalog rather than a
second registry.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from packages.platform.auth.contracts import (
    SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
    SERVICE_TOKEN_SCOPE_REPORTS_READ,
)

ToolEffect = Literal["read", "draft"]
PublicationScope = Literal["catalog", "named", "cited", "scenario_engine", "none"]
ExecutionSemantics = Literal["read", "write", "enqueue", "admin"]
Idempotency = Literal["not-allowed", "optional", "required"]

AGENT_TOOL_CATALOG_SCHEMA_VERSION = "1.0.0"

# vuoro-adapter-kit operation name pattern: at least three dot-separated
# lowercase segments, e.g. ``hla.publication.list``.
VUORO_OPERATION_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*){2,}$")

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100

# Scenario kinds an agent may propose; keys map onto /api/scenarios/{kind}.
SCENARIO_KINDS = (
    "income-change",
    "expense-shock",
    "tariff-shock",
    "loan-what-if",
    "homelab-cost-benefit",
)

_TRUST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Answer-honesty guidance derived from the latest confidence snapshot. "
        "Follow `guidance`: state_as_current, state_with_caveat, "
        "do_not_state_as_current, or trust_unknown (no snapshot — never "
        "claim the data is current)."
    ),
    "properties": {
        "guidance": {
            "type": "string",
            "enum": [
                "state_as_current",
                "state_with_caveat",
                "do_not_state_as_current",
                "trust_unknown",
            ],
        },
        "guidance_detail": {"type": "string"},
        "confidence_verdict": {"type": ["string", "null"]},
        "freshness_state": {"type": ["string", "null"]},
        "assessed_at": {"type": ["string", "null"]},
    },
    "required": ["guidance", "guidance_detail"],
}

_ERROR_NOTE = (
    " Failures return isError with structuredContent.error "
    "{code, http_status, message, hint, retryable}."
)


@dataclass(frozen=True)
class AgentToolSpec:
    """One agent tool: what it is for, what it reads, what it may change."""

    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    effect: ToolEffect
    endpoints: tuple[tuple[str, str], ...]
    publication_scope: PublicationScope
    required_scope: str
    vuoro_operation: str
    execution_semantics: ExecutionSemantics
    idempotency: Idempotency
    output_schema: dict[str, Any] | None = None
    publications: tuple[str, ...] = field(default_factory=tuple)
    publication_note: str = ""
    # Whether a service token carrying ``required_scope`` can actually call
    # the tool today; ``access_note`` explains when it cannot.
    token_reachable: bool = True
    access_note: str = ""

    @property
    def annotations(self) -> dict[str, Any]:
        read_only = self.effect == "read"
        return {
            "title": self.title,
            "readOnlyHint": read_only,
            # Drafts never mutate canonical state or actuate devices; they
            # enter an approval-gated queue or a disabled policy draft.
            "destructiveHint": False,
            "idempotentHint": read_only,
            "openWorldHint": False,
        }

    def mcp_definition(self) -> dict[str, Any]:
        definition: dict[str, Any] = {
            "name": self.name,
            "title": self.title,
            "description": self.description + _ERROR_NOTE,
            "inputSchema": self.input_schema,
            "annotations": self.annotations,
        }
        if self.output_schema is not None:
            definition["outputSchema"] = self.output_schema
        return definition

    def catalog_entry(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "effect": self.effect,
            "annotations": self.annotations,
            "endpoints": [
                {"method": method, "path": path} for method, path in self.endpoints
            ],
            "publication_scope": self.publication_scope,
            "publications": list(self.publications),
            "publication_note": self.publication_note,
            "required_scope": self.required_scope,
            "token_reachable": self.token_reachable,
            "access_note": self.access_note,
            "vuoro_operation": self.vuoro_operation,
            "execution_semantics": self.execution_semantics,
            "idempotency": self.idempotency,
            "input_schema": self.input_schema,
        }


def _paged_input(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "query": {
            "type": "string",
            "description": (
                "Free-text filter over publication names, columns, and "
                "descriptions. Omit to page through every publication."
            ),
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": MAX_PAGE_LIMIT,
            "default": DEFAULT_PAGE_LIMIT,
            "description": "Page size.",
        },
        "cursor": {
            "type": "string",
            "description": "Opaque next_cursor from a previous page.",
        },
    }
    properties.update(extra or {})
    return {"type": "object", "properties": properties, "additionalProperties": False}


AGENT_TOOL_SPECS: tuple[AgentToolSpec, ...] = (
    AgentToolSpec(
        name="list_publications",
        title="List publications",
        description=(
            "Search the semantic publication index — the only data surface "
            "agents may read. Returns a page of publication keys, names, "
            "summaries, and a trust block per publication; pass next_cursor "
            "back as cursor for the next page. Use get_publication_summary "
            "for columns and sample values before quoting any figure."
        ),
        input_schema=_paged_input(),
        output_schema={
            "type": "object",
            "properties": {
                "schema_version": {"type": "string"},
                "publications": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "publication_key": {"type": "string"},
                            "display_name": {"type": "string"},
                            "summary": {"type": "string"},
                            "trust": _TRUST_SCHEMA,
                        },
                        "required": ["publication_key", "display_name", "summary"],
                    },
                },
                "total": {"type": "integer"},
                "next_cursor": {"type": ["string", "null"]},
            },
            "required": ["publications", "total", "next_cursor"],
        },
        effect="read",
        endpoints=(("GET", "/api/agent/semantic-index"),),
        publication_scope="catalog",
        publication_note="Any publication in the semantic index (contracts only).",
        required_scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        vuoro_operation="hla.publication.list",
        execution_semantics="read",
        idempotency="not-allowed",
    ),
    AgentToolSpec(
        name="get_publication_summary",
        title="Get publication summary",
        description=(
            "Retrieve one publication: summary, column glossary (types, units, "
            "grain, aggregation), a bounded sample (sample.truncated tells you "
            "it is not the full publication), the trust block, and contract "
            "and lineage paths. Check trust.guidance before stating figures."
        ),
        input_schema={
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
        output_schema={
            "type": "object",
            "properties": {
                "schema_version": {"type": "string"},
                "publication": {
                    "type": "object",
                    "properties": {
                        "publication_key": {"type": "string"},
                        "columns": {"type": "array"},
                        "sample": {"type": ["object", "null"]},
                        "trust": _TRUST_SCHEMA,
                        "lineage_path": {"type": "string"},
                        "contract_path": {"type": "string"},
                    },
                    "required": ["publication_key", "columns"],
                },
            },
            "required": ["publication"],
        },
        effect="read",
        endpoints=(("GET", "/api/agent/semantic-index/{publication_key}"),),
        publication_scope="named",
        publication_note="The publication named by publication_key.",
        required_scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        vuoro_operation="hla.publication.describe",
        execution_semantics="read",
        idempotency="not-allowed",
    ),
    AgentToolSpec(
        name="get_publication_lineage",
        title="Get publication lineage",
        description=(
            "Trace a publication back through its transformation runs, "
            "relations, and source systems. Use it to explain where a figure "
            "came from and which ingest it depends on."
        ),
        input_schema={
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
        effect="read",
        endpoints=(("GET", "/api/lineage/publication/{publication_key}"),),
        publication_scope="named",
        publication_note="Lineage metadata of the named publication; no row data.",
        required_scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        vuoro_operation="hla.publication.trace",
        execution_semantics="read",
        idempotency="not-allowed",
    ),
    AgentToolSpec(
        name="get_proposal",
        title="Get proposal status",
        description=(
            "Read one action proposal by action_id: status (pending, approved, "
            "dismissed), the resolver and reason once resolved, and its "
            "history. Agents cannot approve or dismiss; only an operator can."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action_id": {
                    "type": "string",
                    "description": "action_id returned by propose_action.",
                }
            },
            "required": ["action_id"],
            "additionalProperties": False,
        },
        effect="read",
        endpoints=(("GET", "/api/actions/proposals/{action_id}"),),
        publication_scope="none",
        required_scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        vuoro_operation="hla.proposal.get",
        execution_semantics="read",
        idempotency="not-allowed",
    ),
    AgentToolSpec(
        name="propose_scenario",
        title="Propose what-if scenario",
        description=(
            "Draft a what-if scenario (income change, expense shock, tariff "
            "shock, loan what-if, or homelab cost-benefit). The scenario is "
            "computed by the scenario engine and stored for operator review; "
            "it never changes canonical state."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "scenario_kind": {"type": "string", "enum": list(SCENARIO_KINDS)},
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
        effect="draft",
        endpoints=tuple(("POST", f"/api/scenarios/{kind}") for kind in SCENARIO_KINDS),
        publication_scope="scenario_engine",
        publication_note=(
            "Computed by the scenario engine from reporting baselines; not "
            "cited per publication."
        ),
        required_scope=SERVICE_TOKEN_SCOPE_REPORTS_READ,
        vuoro_operation="hla.scenario.propose",
        execution_semantics="write",
        idempotency="not-allowed",
    ),
    AgentToolSpec(
        name="propose_policy",
        title="Propose policy draft",
        description=(
            "Draft an operator policy definition through the policy registry. "
            "Drafts are created disabled and stay subject to operator review "
            "and the policy engine; agents cannot enable them."
        ),
        input_schema={
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
        effect="draft",
        endpoints=(("POST", "/control/policies"),),
        publication_scope="cited",
        publication_note="The publication referenced by rule_document.",
        required_scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        token_reachable=False,
        access_note=(
            "Needs the control.policy.write permission, which no service-token "
            "scope grants today; only an operator session or a machine JWT "
            "bound to that permission can call it."
        ),
        vuoro_operation="hla.policy.propose",
        execution_semantics="write",
        idempotency="not-allowed",
    ),
    AgentToolSpec(
        name="propose_action",
        title="Propose action",
        description=(
            "Enter an action proposal into the operator approval queue. It "
            "stays pending until an operator approves or dismisses it; agents "
            "cannot execute or resolve actions. List every publication you "
            "consulted in publication_keys — the platform stamps their trust "
            "state at draft time so the operator sees what you saw. Pass an "
            "idempotency_key to make retries safe."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "Stable identity of the proposing agent or tool.",
                },
                "title": {"type": "string", "description": "One-line action title."},
                "verdict": {
                    "type": "string",
                    "description": "Proposed action verdict, e.g. notify or approval_required.",
                },
                "value": {"type": "string", "description": "Proposed value, if any."},
                "summary": {
                    "type": "string",
                    "description": "Why this action: the evidence and reasoning.",
                },
                "publication_keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Publications consulted while drafting (provenance).",
                },
                "idempotency_key": {
                    "type": "string",
                    "pattern": "^[A-Za-z0-9._:-]{8,128}$",
                    "description": (
                        "Retry-safe key; the same key refreshes the same "
                        "pending proposal instead of creating a duplicate."
                    ),
                },
            },
            "required": ["origin", "title", "verdict"],
            "additionalProperties": False,
        },
        effect="draft",
        endpoints=(("POST", "/api/actions/proposals"),),
        publication_scope="cited",
        publication_note="Publications the agent lists in publication_keys.",
        required_scope=SERVICE_TOKEN_SCOPE_ADMIN_WRITE,
        vuoro_operation="hla.proposal.create",
        execution_semantics="enqueue",
        idempotency="optional",
    ),
)

AGENT_TOOL_SPECS_BY_NAME: dict[str, AgentToolSpec] = {
    spec.name: spec for spec in AGENT_TOOL_SPECS
}


def build_agent_tool_catalog_payload() -> dict[str, Any]:
    return {
        "schema_version": AGENT_TOOL_CATALOG_SCHEMA_VERSION,
        "tools": [spec.catalog_entry() for spec in AGENT_TOOL_SPECS],
    }


def encode_cursor(offset: int) -> str:
    return f"o{offset}"


def decode_cursor(cursor: str | None) -> int:
    """Decode an opaque page cursor; raises ``ValueError`` when malformed."""
    if cursor is None or cursor == "":
        return 0
    if not cursor.startswith("o") or not cursor[1:].isdigit():
        raise ValueError(f"Malformed cursor: {cursor!r}")
    return int(cursor[1:])
