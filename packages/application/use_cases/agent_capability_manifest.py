"""Vuoro-aligned agent capability manifest, projected from the tool catalog.

HLA does not register itself anywhere: this manifest is what HLA *publishes*
so a vuoro-side consumer (catalog, agent directory, MCP edge) can discover
HLA's agent operations without scraping the MCP server. It is a projection of
``agent_tool_catalog``; there is no second registry.

Conventions borrowed from vuoro (see the alignment plan for sources):

- ``schema_version`` uses vuoro's ``<name>/v<N>`` form
- operations are named ``domain.noun.verb`` (vuoro-adapter-kit operation
  name pattern) and carry ``execution_semantics``, ``idempotency``,
  ``repo_scoped``, ``deprecation`` and ``required_client_schema_features``
- ``required_authority`` uses vuoro's ``domain:verb`` authority form; the HLA
  service-token scope it maps to is kept alongside as ``hla_scope``
- ``catalog_revision`` is the sha256 hex of the canonical operations JSON,
  like vuoro's catalog revision, so consumers can detect drift
- the approval-queue states map onto vuoro effect-intent states

Identity is reported honestly: an authority repo UUID minted locally is
``self-asserted`` until a vuoro authority issues and validates it.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from packages.application.use_cases.agent_tool_catalog import (
    AGENT_TOOL_SPECS,
    AgentToolSpec,
)

AGENT_CAPABILITY_MANIFEST_SCHEMA_VERSION = "hla-agent-capability-manifest/v1"
OWNING_DOMAIN = "hla"

# Proposal queue state -> vuoro effect-intent state.
PROPOSAL_STATE_TO_VUORO_EFFECT = {
    "pending": "proposed",
    "approved": "accepted",
    "dismissed": "rejected",
}


def _authority_for(spec: AgentToolSpec) -> str:
    return f"{OWNING_DOMAIN}:read" if spec.effect == "read" else f"{OWNING_DOMAIN}:propose"


def _operation(spec: AgentToolSpec) -> dict[str, Any]:
    return {
        "name": spec.vuoro_operation,
        "owning_domain": OWNING_DOMAIN,
        "mcp_tool": spec.name,
        "summary": spec.description,
        "input_schema": spec.input_schema,
        "result_schema": spec.output_schema or {"type": "object"},
        "required_authority": _authority_for(spec),
        "hla_scope": spec.required_scope,
        "token_reachable": spec.token_reachable,
        "execution_semantics": spec.execution_semantics,
        "idempotency": spec.idempotency,
        "repo_scoped": False,
        "approval_gated": spec.effect == "draft",
        "deprecation": {"deprecated": False, "replacement": None, "sunset_at": None},
        "required_client_schema_features": ["json-schema-draft-2020-12"],
    }


def catalog_revision(operations: list[dict[str, Any]]) -> str:
    canonical = json.dumps(operations, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_agent_capability_manifest(
    *,
    repo_id: str,
    authority_repo_uuid: str | None,
    server_name: str,
    server_version: str,
    mcp_protocol_version: str,
) -> dict[str, Any]:
    operations = [_operation(spec) for spec in AGENT_TOOL_SPECS]
    return {
        "schema_version": AGENT_CAPABILITY_MANIFEST_SCHEMA_VERSION,
        "repo_id": repo_id,
        "authority": {
            "authority_repo_uuid": authority_repo_uuid,
            "status": "self-asserted" if authority_repo_uuid else "unassigned",
            "issuer": None,
            "note": (
                "No vuoro authority has issued or validated this repository "
                "identity; treat it as display metadata, not a grant."
            ),
        },
        "service": {
            "name": server_name,
            "version": server_version,
            "transport": "mcp-stdio",
            "mcp_protocol_version": mcp_protocol_version,
        },
        "catalog_revision": catalog_revision(operations),
        "operations": operations,
        "approval": {
            "queue_path": "/api/actions/proposals",
            "changes_path": "/api/actions/proposals/changes",
            "changes_schema": "resource-changes/v1",
            "resolution": "human-only",
            "states": list(PROPOSAL_STATE_TO_VUORO_EFFECT),
            "vuoro_effect_state_map": dict(PROPOSAL_STATE_TO_VUORO_EFFECT),
        },
        "evidence": {
            "trust_field": "trust.guidance",
            "trust_guidance_values": [
                "state_as_current",
                "state_with_caveat",
                "do_not_state_as_current",
                "trust_unknown",
            ],
            "lineage_path_template": "/api/lineage/publication/{publication_key}",
        },
    }
