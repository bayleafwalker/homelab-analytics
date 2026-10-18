"""Typed response models for the agent semantic-index routes.

``GET /api/agent/semantic-index`` and ``GET /api/agent/semantic-index/{key}``
declare these as their ``response_model`` so OpenAPI (and the generated
frontend types) describe the payload instead of an untyped object.

Source of truth: ``validate_agent_semantic_index_payload`` in
``packages.platform.agent_semantic_index`` stays the contract agents rely on.
These models mirror it rule for rule — strict types (no coercion, booleans
are not integers), the same non-empty and non-negative bounds, and the same
cross-field sample rules. ``tests/test_agent_semantic_index_models.py`` keeps
the two from drifting: for valid payloads and for every single-field mutation
of them, the validator and the models must agree on accept or reject, and the
model fields must match the keys the builder emits.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NonEmptyText = Annotated[str, Field(min_length=1)]
TrustGuidance = Literal[
    "state_as_current",
    "state_with_caveat",
    "do_not_state_as_current",
    "trust_unknown",
]
# Kept equal to AGENT_SEMANTIC_INDEX_SCHEMA_VERSION (pinned by the drift test).
SchemaVersion = Literal["1.1.0"]


class _StrictModel(BaseModel):
    # Strict, like the validator's isinstance checks: "3" is not an int and
    # True is not an int. Unknown keys are ignored, as the validator ignores them.
    model_config = ConfigDict(strict=True)


class AgentColumnGlossaryModel(_StrictModel):
    name: NonEmptyText
    json_type: NonEmptyText
    description: str
    semantic_role: NonEmptyText
    nullable: bool
    unit: NonEmptyText | None = None
    grain: NonEmptyText | None = None
    aggregation: NonEmptyText | None = None

    @field_validator("description")
    @classmethod
    def _description_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("description must be a non-empty string")
        return value


class AgentPublicationSampleModel(_StrictModel):
    rows: list[dict[str, Any]]
    row_count_bound: int = Field(gt=0)
    total_row_count: int | None = Field(default=None, ge=0)
    truncated: bool

    @model_validator(mode="after")
    def _bounded_and_honest(self) -> AgentPublicationSampleModel:
        if len(self.rows) > self.row_count_bound:
            raise ValueError("sample.rows exceeds row_count_bound")
        if self.total_row_count is not None and self.truncated != (
            self.total_row_count > len(self.rows)
        ):
            raise ValueError(
                "sample.truncated must be true exactly when total_row_count "
                "exceeds the returned rows"
            )
        return self


class AgentPublicationTrustModel(_StrictModel):
    publication_key: NonEmptyText
    confidence_verdict: str | None = None
    freshness_state: str | None = None
    completeness_pct: int | None = Field(default=None, ge=0)
    validation_state: str | None = None
    completeness_state: str | None = None
    assessed_at: str | None = None
    guidance: TrustGuidance
    guidance_detail: str


class AgentSemanticIndexEntryModel(_StrictModel):
    publication_key: NonEmptyText
    display_name: NonEmptyText
    summary: NonEmptyText
    schema_name: NonEmptyText
    schema_version: NonEmptyText
    visibility: NonEmptyText
    pack_name: str | None = None
    pack_version: str | None = None
    supported_renderers: list[str]
    ui_descriptor_keys: list[str]
    columns: list[AgentColumnGlossaryModel]
    sample: AgentPublicationSampleModel | None = None
    contract_path: NonEmptyText
    lineage_path: NonEmptyText
    trust: AgentPublicationTrustModel | None = None


class AgentSemanticIndexPageModel(_StrictModel):
    """``GET /api/agent/semantic-index``: one page of the index."""

    schema_version: SchemaVersion
    generated_at: str
    publications: list[AgentSemanticIndexEntryModel]
    total: int = Field(ge=0)
    next_cursor: NonEmptyText | None


class AgentSemanticIndexEntryResponseModel(_StrictModel):
    """``GET /api/agent/semantic-index/{publication_key}``: one publication."""

    schema_version: SchemaVersion
    generated_at: str
    publication: AgentSemanticIndexEntryModel
