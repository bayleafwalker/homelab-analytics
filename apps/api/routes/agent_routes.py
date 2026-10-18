"""Agent-facing retrieval surface (Stage 10) and its operator projections.

Serves the LLM-shaped semantic index derived from publication contracts:

- ``GET /api/agent/semantic-index`` — publications with description, column
  glossary, bounded sample values, and a ``trust`` block; ``query`` filters
  entries the same way as the renderer-facing publication index. ``limit``
  and ``cursor`` page the result (``next_cursor`` is null on the last page).
- ``GET /api/agent/semantic-index/{publication_key}`` — one publication.

Operator projections of the agent surface (read-only):

- ``GET /api/agent/catalog`` — the MCP tool catalog: endpoints, publication
  scope, effect, and required service-token scope of every tool.
- ``GET /api/agent/principals`` — agent identities observed in the proposal
  queue. HLA observes; it is not an agent registration authority.
- ``GET /api/agent/manifest`` — vuoro-aligned capability manifest projected
  from the tool catalog; served only when
  ``HOMELAB_ANALYTICS_AGENT_MANIFEST_ENABLED`` is set (``404`` otherwise).

The ``trust`` block mirrors confidence semantics so agents answer honestly:
publications without a confidence snapshot read as ``trust_unknown``, never
as current. The stable endpoint contract is versioned via ``schema_version``
in the payload and validated by
``packages.platform.agent_semantic_index.validate_agent_semantic_index_payload``;
the routes declare the typed models in
``packages.platform.agent_semantic_index_models``, which mirror that validator
(a drift test holds them to it) so OpenAPI describes the payload.
Contract shapes are computed once at registration; sample values and trust
are resolved per request so agents see current data without a redeploy.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from packages.application.use_cases.agent_proposal_review import (
    summarize_agent_principals,
)
from packages.application.use_cases.agent_tool_catalog import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    build_agent_tool_catalog_payload,
    decode_cursor,
    encode_cursor,
)
from packages.application.use_cases.agent_trust import (
    ConfidenceLookup,
    assess_publication_trust,
    safe_confidence_lookup,
)
from packages.pipelines.composition.publication_contract_inputs import (
    HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS,
    build_household_publication_relation_map,
)
from packages.pipelines.reporting_service import ReportingService
from packages.platform.action_proposals import ActionProposalRegistry
from packages.platform.agent_semantic_index import (
    AGENT_SEMANTIC_INDEX_SCHEMA_VERSION,
    DEFAULT_SAMPLE_ROW_LIMIT,
    build_agent_semantic_index,
)
from packages.platform.agent_semantic_index_models import (
    AgentSemanticIndexEntryResponseModel,
    AgentSemanticIndexPageModel,
)
from packages.platform.capability_types import CapabilityPack
from packages.platform.publication_contracts import (
    build_publication_contracts,
    build_ui_descriptor_contracts,
)
from packages.platform.publication_index import (
    PublicationSemanticIndexEntry,
    build_publication_semantic_index,
    filter_publication_semantic_index,
)
from packages.shared.extensions import ExtensionRegistry


class AgentToolEndpointModel(BaseModel):
    method: str
    path: str


class AgentToolCatalogEntryModel(BaseModel):
    name: str
    title: str
    description: str
    effect: Literal["read", "draft"]
    annotations: dict[str, Any]
    endpoints: list[AgentToolEndpointModel]
    publication_scope: Literal["catalog", "named", "cited", "scenario_engine", "none"]
    publications: list[str] = Field(default_factory=list)
    publication_note: str = ""
    required_scope: str
    token_reachable: bool = True
    access_note: str = ""
    vuoro_operation: str
    execution_semantics: Literal["read", "write", "enqueue", "admin"]
    idempotency: Literal["not-allowed", "optional", "required"]
    input_schema: dict[str, Any]


class AgentToolCatalogModel(BaseModel):
    schema_version: str
    tools: list[AgentToolCatalogEntryModel]


class AgentPrincipalModel(BaseModel):
    created_by: str
    origin: str
    source_kind: str
    proposal_count: int
    pending: int
    approved: int
    dismissed: int
    first_seen_at: str
    last_seen_at: str
    cited_publications: list[str] = Field(default_factory=list)


class AgentPrincipalListModel(BaseModel):
    registration_authority: Literal["none"] = "none"
    principals: list[AgentPrincipalModel]


def build_agent_publication_index(
    capability_packs: tuple[CapabilityPack, ...],
    extension_registry: ExtensionRegistry,
) -> list[PublicationSemanticIndexEntry]:
    """Publication semantic index shared by agent and proposal-review routes."""
    publication_contracts = build_publication_contracts(
        capability_packs,
        publication_relations=build_household_publication_relation_map(
            extension_registry=extension_registry,
        ),
        current_dimension_relations=(
            HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS.current_dimension_relations
        ),
        current_dimension_contracts=(
            HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS.current_dimension_contracts
        ),
    )
    ui_descriptors = build_ui_descriptor_contracts(capability_packs)
    return build_publication_semantic_index(publication_contracts, ui_descriptors)


def publication_display_names(
    entries: list[PublicationSemanticIndexEntry],
) -> Mapping[str, str]:
    """Display names keyed by contract key *and* relation name.

    Agents and policies cite either form (``monthly_cashflow`` or
    ``mart_monthly_cashflow``); both must resolve as known evidence.
    """
    names: dict[str, str] = {}
    for entry in entries:
        publication = entry.publication
        names[publication.publication_key] = publication.display_name
        names.setdefault(publication.relation_name, publication.display_name)
    return names


def register_agent_routes(
    app: FastAPI,
    *,
    capability_packs: tuple[CapabilityPack, ...],
    extension_registry: ExtensionRegistry,
    resolved_reporting_service: ReportingService | None = None,
    sample_row_limit: int = DEFAULT_SAMPLE_ROW_LIMIT,
    publication_semantic_index: list[PublicationSemanticIndexEntry] | None = None,
    confidence_lookup: ConfidenceLookup | None = None,
    action_proposal_registry: ActionProposalRegistry | None = None,
    capability_manifest: Mapping[str, Any] | None = None,
) -> None:
    """Register the agent semantic index routes and operator projections."""
    index = (
        publication_semantic_index
        if publication_semantic_index is not None
        else build_agent_publication_index(capability_packs, extension_registry)
    )
    lookup = safe_confidence_lookup(confidence_lookup)

    def _sample_fetcher(
        relation_name: str,
    ) -> tuple[list[dict[str, Any]], int | None] | None:
        if resolved_reporting_service is None:
            return None
        return resolved_reporting_service.sample_publication_rows(
            relation_name,
            limit=sample_row_limit,
        )

    def _entry_dicts(entries: list[PublicationSemanticIndexEntry]) -> list[dict[str, Any]]:
        built = build_agent_semantic_index(
            entries,
            sample_fetcher=_sample_fetcher,
            sample_row_limit=sample_row_limit,
        )
        payloads = []
        for entry in built:
            payload = entry.as_dict()
            payload["trust"] = assess_publication_trust(
                entry.publication_key, lookup(entry.publication_key)
            ).as_dict()
            payloads.append(payload)
        return payloads

    def _generated_at() -> str:
        return datetime.now(UTC).isoformat()

    @app.get("/api/agent/semantic-index", response_model=AgentSemanticIndexPageModel)
    async def get_agent_semantic_index(
        query: str | None = None,
        limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_LIMIT),
        cursor: str | None = None,
    ) -> AgentSemanticIndexPageModel:
        entries = filter_publication_semantic_index(index, query=query)
        try:
            offset = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        total = len(entries)
        page_size = limit if limit is not None else (total if cursor is None else DEFAULT_PAGE_LIMIT)
        page = entries[offset : offset + page_size] if page_size else []
        next_offset = offset + len(page)
        return AgentSemanticIndexPageModel.model_validate(
            {
                "schema_version": AGENT_SEMANTIC_INDEX_SCHEMA_VERSION,
                "generated_at": _generated_at(),
                "publications": _entry_dicts(page),
                "total": total,
                "next_cursor": encode_cursor(next_offset) if next_offset < total else None,
            }
        )

    @app.get(
        "/api/agent/semantic-index/{publication_key}",
        response_model=AgentSemanticIndexEntryResponseModel,
    )
    async def get_agent_semantic_index_entry(
        publication_key: str,
    ) -> AgentSemanticIndexEntryResponseModel:
        entries = [
            entry
            for entry in index
            if entry.publication.publication_key == publication_key
        ]
        if not entries:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Unknown publication: {publication_key}. Call "
                    "list_publications (GET /api/agent/semantic-index) for valid keys."
                ),
            )
        return AgentSemanticIndexEntryResponseModel.model_validate(
            {
                "schema_version": AGENT_SEMANTIC_INDEX_SCHEMA_VERSION,
                "generated_at": _generated_at(),
                "publication": _entry_dicts(entries)[0],
            }
        )

    @app.get("/api/agent/catalog", response_model=AgentToolCatalogModel)
    async def get_agent_tool_catalog() -> AgentToolCatalogModel:
        return AgentToolCatalogModel.model_validate(build_agent_tool_catalog_payload())

    @app.get("/api/agent/principals", response_model=AgentPrincipalListModel)
    async def get_agent_principals() -> AgentPrincipalListModel:
        proposals = (
            action_proposal_registry.list_all()
            if action_proposal_registry is not None
            else []
        )
        return AgentPrincipalListModel(
            principals=[
                AgentPrincipalModel.model_validate(item)
                for item in summarize_agent_principals(proposals)
            ]
        )

    @app.get("/api/agent/manifest")
    async def get_agent_capability_manifest() -> dict[str, Any]:
        if capability_manifest is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Agent capability manifest is disabled. Set "
                    "HOMELAB_ANALYTICS_AGENT_MANIFEST_ENABLED=true to publish it."
                ),
            )
        return dict(capability_manifest)
