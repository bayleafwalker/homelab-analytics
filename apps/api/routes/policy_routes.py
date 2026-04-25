"""REST CRUD routes for operator-authored policy definitions.

Exposed under /control/policies. Authentication is delegated to the route
authorization middleware (control.policy.read / control.policy.write).
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError

from packages.platform.policy_schema import RULE_SCHEMA_VERSION, parse_rule_document
from packages.storage.control_plane import (
    ControlPlaneAdminStore,
    PolicyDefinitionCreate,
    PolicyDefinitionRecord,
    PolicyDefinitionUpdate,
)


class PolicyCreateRequest(BaseModel):
    display_name: str
    policy_kind: str
    rule_document: dict[str, Any]
    description: str | None = None
    creator: str | None = None
    rule_schema_version: str = RULE_SCHEMA_VERSION

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


def register_policy_routes(
    app: FastAPI,
    *,
    resolved_config_repository: ControlPlaneAdminStore,
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

    @app.post("/control/policies", status_code=201)
    async def create_policy(body: PolicyCreateRequest) -> dict[str, Any]:
        try:
            parse_rule_document(body.rule_document)
        except (ValueError, ValidationError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

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
