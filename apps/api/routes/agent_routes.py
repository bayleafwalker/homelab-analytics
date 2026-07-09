"""Agent-facing retrieval surface (Stage 10).

Serves the LLM-shaped semantic index derived from publication contracts:

- ``GET /api/agent/semantic-index`` — every publication with description,
  column glossary, and bounded sample values; ``query`` filters entries the
  same way as the renderer-facing publication index.
- ``GET /api/agent/semantic-index/{publication_key}`` — one publication.

The stable endpoint contract is versioned via ``schema_version`` in the
payload and validated by
``packages.platform.agent_semantic_index.validate_agent_semantic_index_payload``.
Contract shapes are computed once at registration; sample values are fetched
per request so agents see current data without a redeploy.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException

from packages.pipelines.composition.publication_contract_inputs import (
    HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS,
    build_household_publication_relation_map,
)
from packages.pipelines.reporting_service import ReportingService
from packages.platform.agent_semantic_index import (
    AGENT_SEMANTIC_INDEX_SCHEMA_VERSION,
    DEFAULT_SAMPLE_ROW_LIMIT,
    build_agent_semantic_index,
)
from packages.platform.capability_types import CapabilityPack
from packages.platform.publication_contracts import (
    build_publication_contracts,
    build_ui_descriptor_contracts,
)
from packages.platform.publication_index import (
    build_publication_semantic_index,
    filter_publication_semantic_index,
)
from packages.shared.extensions import ExtensionRegistry


def register_agent_routes(
    app: FastAPI,
    *,
    capability_packs: tuple[CapabilityPack, ...],
    extension_registry: ExtensionRegistry,
    resolved_reporting_service: ReportingService | None = None,
    sample_row_limit: int = DEFAULT_SAMPLE_ROW_LIMIT,
) -> None:
    """Register the agent semantic index routes."""
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
    publication_semantic_index = build_publication_semantic_index(
        publication_contracts,
        ui_descriptors,
    )

    def _sample_fetcher(
        relation_name: str,
    ) -> tuple[list[dict[str, Any]], int | None] | None:
        if resolved_reporting_service is None:
            return None
        return resolved_reporting_service.sample_publication_rows(
            relation_name,
            limit=sample_row_limit,
        )

    def _payload(entries: list[Any]) -> dict[str, Any]:
        return {
            "schema_version": AGENT_SEMANTIC_INDEX_SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "publications": [entry.as_dict() for entry in entries],
        }

    @app.get("/api/agent/semantic-index")
    async def get_agent_semantic_index(query: str | None = None) -> dict[str, Any]:
        entries = filter_publication_semantic_index(
            publication_semantic_index,
            query=query,
        )
        return _payload(
            build_agent_semantic_index(
                entries,
                sample_fetcher=_sample_fetcher,
                sample_row_limit=sample_row_limit,
            )
        )

    @app.get("/api/agent/semantic-index/{publication_key}")
    async def get_agent_semantic_index_entry(publication_key: str) -> dict[str, Any]:
        entries = [
            entry
            for entry in publication_semantic_index
            if entry.publication.publication_key == publication_key
        ]
        if not entries:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown publication: {publication_key}",
            )
        payload = _payload(
            build_agent_semantic_index(
                entries,
                sample_fetcher=_sample_fetcher,
                sample_row_limit=sample_row_limit,
            )
        )
        return {
            "schema_version": payload["schema_version"],
            "generated_at": payload["generated_at"],
            "publication": payload["publications"][0],
        }
