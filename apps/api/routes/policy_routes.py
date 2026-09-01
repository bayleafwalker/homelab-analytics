"""REST CRUD routes for operator-authored policy definitions.

Exposed under /control/policies. Authentication is delegated to the route
authorization middleware (control.policy.read / control.policy.write).
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError

from packages.platform.policy_schema import RULE_SCHEMA_VERSION, parse_rule_document
from packages.platform.publication_contracts import PublicationContract
from packages.storage.control_plane import (
    ControlPlaneAdminStore,
    PolicyDefinitionCreate,
    PolicyDefinitionRecord,
    PolicyDefinitionUpdate,
)

_COMPARABLE_STORAGE_TYPES = frozenset({
    "DECIMAL",
    "NUMERIC",
    "INTEGER",
    "INT",
    "BIGINT",
    "SMALLINT",
    "TINYINT",
    "DOUBLE",
    "FLOAT",
    "REAL",
})


def _is_comparable(storage_type: str) -> bool:
    """Whether a column can be read as a number for threshold comparison."""
    normalized = storage_type.upper().replace(" NOT NULL", "").strip()
    return normalized.split("(", maxsplit=1)[0].strip() in _COMPARABLE_STORAGE_TYPES


class PolicyCreateRequest(BaseModel):
    display_name: str
    policy_kind: str
    rule_document: dict[str, Any]
    description: str | None = None
    creator: str | None = None
    rule_schema_version: str = RULE_SCHEMA_VERSION

    model_config = {"extra": "forbid"}


class PolicyPreviewRequest(BaseModel):
    rule_document: dict[str, Any]

    model_config = {"extra": "forbid"}


class PolicyUpdateRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    policy_kind: str | None = None
    rule_document: dict[str, Any] | None = None
    enabled: bool | None = None
    rule_schema_version: str | None = None

    model_config = {"extra": "forbid"}


def _serialize_policy(record: PolicyDefinitionRecord) -> dict[str, Any]:
    return {
        "policy_id": record.policy_id,
        "display_name": record.display_name,
        "description": record.description,
        "policy_kind": record.policy_kind,
        "rule_schema_version": record.rule_schema_version,
        "rule_document": json.loads(record.rule_document),
        "enabled": record.enabled,
        "source_kind": record.source_kind,
        "creator": record.creator,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _validate_publication_references(
    rule_document: dict[str, Any],
    known_publication_keys: frozenset[str] | None,
) -> None:
    """Reject rules referencing publications that are not registered.

    Enforced at create, rule update, and enable so a policy can never be
    activated against a publication contract that does not exist.
    """
    if known_publication_keys is None:
        return
    if rule_document.get("rule_kind") not in {
        "publication_value_comparison",
        "publication_freshness_comparison",
    }:
        return
    publication_key = rule_document.get("publication_key")
    if publication_key not in known_publication_keys:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown publication reference: {publication_key!r}. "
                "Policies may only reference registered publication contracts."
            ),
        )


def register_policy_routes(
    app: FastAPI,
    *,
    resolved_config_repository: ControlPlaneAdminStore,
    known_publication_keys: frozenset[str] | None = None,
    referenceable_contracts: Sequence[PublicationContract] = (),
    ha_policy_evaluator: Any = None,
) -> None:
    @app.get("/control/policies")
    async def list_policies(
        source_kind: str | None = None,
        enabled_only: bool = False,
    ) -> dict[str, Any]:
        records = resolved_config_repository.list_policy_definitions(
            source_kind=source_kind,
            enabled_only=enabled_only,
        )
        return {"policies": [_serialize_policy(r) for r in records]}

    # Registered before /control/policies/{policy_id} so the literal path is
    # not captured as a policy id.
    @app.get("/control/policies/referenceable-publications")
    async def list_referenceable_publications() -> dict[str, Any]:
        """Publications a policy may reference, with their comparable fields.

        This is the list an authoring surface must offer. It is narrower than
        ``/contracts/publications``, which also advertises current-dimension
        contracts that policy evaluation cannot resolve to a relation; a
        picker driven off that wider list would offer keys that fail with 422
        on save.
        """
        return {
            # The authoring surface sends the schema version back on create, so
            # the version stays owned here rather than pinned in the frontend.
            "rule_schema_version": RULE_SCHEMA_VERSION,
            "publications": [
                {
                    "publication_key": contract.publication_key,
                    "display_name": contract.display_name,
                    "description": contract.description,
                    "columns": [
                        {
                            "name": column.name,
                            "json_type": column.json_type,
                            "description": column.description,
                            "unit": column.unit,
                            "semantic_role": column.semantic_role,
                            # Only a numerically-readable field can be
                            # threshold-compared, so the form does not offer a
                            # field whose comparison is always unavailable.
                            # Keyed off storage type, not json_type: DECIMAL
                            # carries json_type "string" but is exactly what
                            # the monetary rules compare.
                            "comparable": _is_comparable(column.storage_type),
                        }
                        for column in contract.columns
                    ],
                }
                for contract in referenceable_contracts
            ]
        }

    @app.post("/control/policies/preview")
    async def preview_policy(body: PolicyPreviewRequest) -> dict[str, Any]:
        """Evaluate a rule document without saving it.

        Same validation as create — an invalid document or an unreferenceable
        publication is a 422 here too, so the authoring form learns about a
        bad rule before it writes one.
        """
        try:
            parse_rule_document(body.rule_document)
        except (ValueError, ValidationError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        _validate_publication_references(body.rule_document, known_publication_keys)

        if ha_policy_evaluator is None:
            raise HTTPException(
                status_code=503,
                detail="Policy evaluation is unavailable, so a preview cannot be run.",
            )
        result = ha_policy_evaluator.evaluate_document(body.rule_document)
        return {"preview": result.to_dict()}

    @app.post("/control/policies", status_code=201)
    async def create_policy(body: PolicyCreateRequest) -> dict[str, Any]:
        try:
            parse_rule_document(body.rule_document)
        except (ValueError, ValidationError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        _validate_publication_references(body.rule_document, known_publication_keys)

        now = datetime.now(UTC)
        create = PolicyDefinitionCreate(
            policy_id=str(uuid.uuid4()),
            display_name=body.display_name,
            policy_kind=body.policy_kind,
            rule_schema_version=body.rule_schema_version,
            rule_document=json.dumps(body.rule_document),
            description=body.description,
            creator=body.creator,
            source_kind="operator",
            created_at=now,
            updated_at=now,
        )
        record = resolved_config_repository.create_policy_definition(create)
        return _serialize_policy(record)

    @app.get("/control/policies/{policy_id}")
    async def get_policy(policy_id: str) -> dict[str, Any]:
        try:
            record = resolved_config_repository.get_policy_definition(policy_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Policy not found: {policy_id}")
        return _serialize_policy(record)

    @app.patch("/control/policies/{policy_id}")
    async def update_policy(policy_id: str, body: PolicyUpdateRequest) -> dict[str, Any]:
        if body.rule_document is not None:
            try:
                parse_rule_document(body.rule_document)
            except (ValueError, ValidationError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            _validate_publication_references(
                body.rule_document, known_publication_keys
            )
        elif body.enabled:
            # Enabling an existing policy re-validates its stored references.
            try:
                existing = resolved_config_repository.get_policy_definition(
                    policy_id
                )
            except KeyError:
                raise HTTPException(
                    status_code=404, detail=f"Policy not found: {policy_id}"
                )
            _validate_publication_references(
                json.loads(existing.rule_document), known_publication_keys
            )

        rule_document_json: str | None = None
        if body.rule_document is not None:
            rule_document_json = json.dumps(body.rule_document)

        update = PolicyDefinitionUpdate(
            display_name=body.display_name,
            description=body.description,
            policy_kind=body.policy_kind,
            rule_schema_version=body.rule_schema_version,
            rule_document=rule_document_json,
            enabled=body.enabled,
            updated_at=datetime.now(UTC),
        )
        try:
            record = resolved_config_repository.update_policy_definition(policy_id, update)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Policy not found: {policy_id}")
        return _serialize_policy(record)

    @app.delete("/control/policies/{policy_id}", status_code=204)
    async def delete_policy(policy_id: str) -> None:
        try:
            resolved_config_repository.delete_policy_definition(policy_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Policy not found: {policy_id}")
