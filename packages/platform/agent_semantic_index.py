"""LLM-shaped semantic index over publication contracts.

Derives an agent-facing view from the publication semantic index
(``packages.platform.publication_index``): per-publication descriptions, a
column glossary, and bounded sample values. The index normalizes the already
published contract model — it does not invent a second publication registry
(see ``docs/architecture/agent-surfaces.md``).

Sample values are optional and bounded: a ``sample_fetcher`` callback returns
rows for a relation, the builder truncates them to ``sample_row_limit`` and
records the bound so an agent knows it is looking at a sample, not the
publication.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Callable, Sequence

from packages.platform.publication_index import PublicationSemanticIndexEntry

# 1.1.0: additive — per-entry ``trust`` block and list paging fields
# (``total``, ``next_cursor``) served by the API route.
AGENT_SEMANTIC_INDEX_SCHEMA_VERSION = "1.1.0"
AGENT_TRUST_GUIDANCE_VALUES = (
    "state_as_current",
    "state_with_caveat",
    "do_not_state_as_current",
    "trust_unknown",
)
DEFAULT_SAMPLE_ROW_LIMIT = 5

# Rows returned by a sample fetcher, plus the total row count when the source
# can provide one cheaply (None when unknown).
SampleFetcher = Callable[[str], "tuple[list[dict[str, Any]], int | None] | None"]


@dataclass(frozen=True)
class AgentColumnGlossaryEntry:
    """One column, described for an agent rather than a renderer."""

    name: str
    json_type: str
    description: str
    semantic_role: str
    nullable: bool
    unit: str | None = None
    grain: str | None = None
    aggregation: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "json_type": self.json_type,
            "description": self.description,
            "semantic_role": self.semantic_role,
            "nullable": self.nullable,
            "unit": self.unit,
            "grain": self.grain,
            "aggregation": self.aggregation,
        }


@dataclass(frozen=True)
class AgentPublicationSample:
    """Bounded sample rows from a publication relation."""

    rows: tuple[dict[str, Any], ...]
    row_count_bound: int
    total_row_count: int | None
    truncated: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "rows": [dict(row) for row in self.rows],
            "row_count_bound": self.row_count_bound,
            "total_row_count": self.total_row_count,
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class AgentSemanticIndexEntry:
    """One publication, shaped for LLM retrieval."""

    publication_key: str
    display_name: str
    summary: str
    schema_name: str
    schema_version: str
    visibility: str
    pack_name: str | None
    pack_version: str | None
    supported_renderers: tuple[str, ...]
    ui_descriptor_keys: tuple[str, ...]
    columns: tuple[AgentColumnGlossaryEntry, ...]
    sample: AgentPublicationSample | None
    contract_path: str
    lineage_path: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "publication_key": self.publication_key,
            "display_name": self.display_name,
            "summary": self.summary,
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "visibility": self.visibility,
            "pack_name": self.pack_name,
            "pack_version": self.pack_version,
            "supported_renderers": list(self.supported_renderers),
            "ui_descriptor_keys": list(self.ui_descriptor_keys),
            "columns": [column.as_dict() for column in self.columns],
            "sample": self.sample.as_dict() if self.sample is not None else None,
            "contract_path": self.contract_path,
            "lineage_path": self.lineage_path,
        }


def _json_safe(value: Any) -> Any:
    if isinstance(value, (Decimal,)):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _build_sample(
    relation_name: str,
    sample_fetcher: SampleFetcher | None,
    sample_row_limit: int,
) -> AgentPublicationSample | None:
    if sample_fetcher is None:
        return None
    fetched = sample_fetcher(relation_name)
    if fetched is None:
        return None
    rows, total_row_count = fetched
    bounded_rows = tuple(
        {str(key): _json_safe(item) for key, item in row.items()}
        for row in rows[:sample_row_limit]
    )
    truncated = len(rows) > sample_row_limit or (
        total_row_count is not None and total_row_count > len(bounded_rows)
    )
    return AgentPublicationSample(
        rows=bounded_rows,
        row_count_bound=sample_row_limit,
        total_row_count=total_row_count,
        truncated=truncated,
    )


def build_agent_semantic_index(
    entries: Sequence[PublicationSemanticIndexEntry],
    *,
    sample_fetcher: SampleFetcher | None = None,
    sample_row_limit: int = DEFAULT_SAMPLE_ROW_LIMIT,
) -> list[AgentSemanticIndexEntry]:
    """Shape the publication semantic index for agent retrieval.

    Entries keep the ordering of the source index (sorted by publication
    key). Sample fetch failures must be handled by the fetcher itself — a
    fetcher returning ``None`` yields an entry without sample values.
    """
    agent_entries: list[AgentSemanticIndexEntry] = []
    for entry in entries:
        publication = entry.publication
        columns = tuple(
            AgentColumnGlossaryEntry(
                name=column.name,
                json_type=column.json_type,
                description=column.description,
                semantic_role=column.semantic_role,
                nullable=column.nullable,
                unit=column.unit,
                grain=column.grain,
                aggregation=column.aggregation,
            )
            for column in publication.columns
        )
        agent_entries.append(
            AgentSemanticIndexEntry(
                publication_key=publication.publication_key,
                display_name=publication.display_name,
                summary=entry.summary,
                schema_name=publication.schema_name,
                schema_version=publication.schema_version,
                visibility=publication.visibility,
                pack_name=publication.pack_name,
                pack_version=publication.pack_version,
                supported_renderers=entry.supported_renderers,
                ui_descriptor_keys=entry.ui_descriptor_keys,
                columns=columns,
                sample=_build_sample(
                    publication.relation_name, sample_fetcher, sample_row_limit
                ),
                contract_path=f"/contracts/publications/{publication.publication_key}",
                lineage_path=f"/api/lineage/publication/{publication.publication_key}",
            )
        )
    return agent_entries


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _text_or_null(value: Any, *, non_empty: bool = False) -> bool:
    return value is None or (isinstance(value, str) and (value != "" or not non_empty))


_ENTRY_STRING_FIELDS = (
    "publication_key",
    "display_name",
    "summary",
    "schema_name",
    "schema_version",
    "visibility",
    "contract_path",
    "lineage_path",
)
_TRUST_OPTIONAL_TEXT_FIELDS = (
    "confidence_verdict",
    "freshness_state",
    "validation_state",
    "completeness_state",
    "assessed_at",
)


def _validate_entry(entry: Any, where: str, check: Callable[[bool, str], bool]) -> None:
    if not check(isinstance(entry, dict), f"{where} must be an object"):
        return
    for field_name in _ENTRY_STRING_FIELDS:
        check(
            isinstance(entry.get(field_name), str) and entry.get(field_name) != "",
            f"{where}.{field_name} must be a non-empty string",
        )
    for field_name in ("pack_name", "pack_version"):
        check(
            _text_or_null(entry.get(field_name)),
            f"{where}.{field_name} must be a string or null",
        )
    for field_name in ("supported_renderers", "ui_descriptor_keys"):
        value = entry.get(field_name)
        check(
            isinstance(value, list) and all(isinstance(item, str) for item in value),
            f"{where}.{field_name} must be an array of strings",
        )
    columns = entry.get("columns")
    if check(isinstance(columns, list), f"{where}.columns must be an array"):
        for column_position, column in enumerate(columns):
            column_where = f"{where}.columns[{column_position}]"
            if not check(isinstance(column, dict), f"{column_where} must be an object"):
                continue
            for field_name in ("name", "json_type", "semantic_role"):
                check(
                    isinstance(column.get(field_name), str) and column.get(field_name) != "",
                    f"{column_where}.{field_name} must be a non-empty string",
                )
            description = column.get("description")
            check(
                isinstance(description, str) and description.strip() != "",
                f"{column_where}.description must be a non-empty string",
            )
            check(
                isinstance(column.get("nullable"), bool),
                f"{column_where}.nullable must be a boolean",
            )
            for field_name in ("unit", "grain", "aggregation"):
                check(
                    _text_or_null(column.get(field_name), non_empty=True),
                    f"{column_where}.{field_name} must be a non-empty string or null",
                )
    trust = entry.get("trust")
    if trust is not None and check(
        isinstance(trust, dict), f"{where}.trust must be an object or null"
    ):
        check(
            isinstance(trust.get("publication_key"), str)
            and trust.get("publication_key") != "",
            f"{where}.trust.publication_key must be a non-empty string",
        )
        check(
            trust.get("guidance") in AGENT_TRUST_GUIDANCE_VALUES,
            f"{where}.trust.guidance must be one of {AGENT_TRUST_GUIDANCE_VALUES}",
        )
        check(
            isinstance(trust.get("guidance_detail"), str),
            f"{where}.trust.guidance_detail must be a string",
        )
        for field_name in _TRUST_OPTIONAL_TEXT_FIELDS:
            check(
                _text_or_null(trust.get(field_name)),
                f"{where}.trust.{field_name} must be a string or null",
            )
        completeness_pct = trust.get("completeness_pct")
        check(
            completeness_pct is None or (_is_int(completeness_pct) and completeness_pct >= 0),
            f"{where}.trust.completeness_pct must be a non-negative integer or null",
        )
    sample = entry.get("sample")
    if sample is not None and check(
        isinstance(sample, dict), f"{where}.sample must be an object or null"
    ):
        rows = sample.get("rows")
        check(
            isinstance(rows, list) and all(isinstance(row, dict) for row in rows),
            f"{where}.sample.rows must be an array of objects",
        )
        bound = sample.get("row_count_bound")
        check(
            _is_int(bound) and bound > 0,
            f"{where}.sample.row_count_bound must be a positive integer",
        )
        total_row_count = sample.get("total_row_count")
        check(
            total_row_count is None or (_is_int(total_row_count) and total_row_count >= 0),
            f"{where}.sample.total_row_count must be a non-negative integer or null",
        )
        truncated = sample.get("truncated")
        check(isinstance(truncated, bool), f"{where}.sample.truncated must be a boolean")
        if isinstance(rows, list):
            if _is_int(bound):
                check(len(rows) <= bound, f"{where}.sample.rows exceeds row_count_bound")
            if _is_int(total_row_count) and isinstance(truncated, bool):
                check(
                    truncated == (total_row_count > len(rows)),
                    f"{where}.sample.truncated must be true exactly when "
                    "total_row_count exceeds the returned rows",
                )


def _validator() -> tuple[list[str], Callable[[bool, str], bool]]:
    violations: list[str] = []

    def check(condition: bool, message: str) -> bool:
        if not condition:
            violations.append(message)
        return condition

    return violations, check


def _validate_envelope(payload: dict[str, Any], check: Callable[[bool, str], bool]) -> None:
    check(
        payload.get("schema_version") == AGENT_SEMANTIC_INDEX_SCHEMA_VERSION,
        f"schema_version must be {AGENT_SEMANTIC_INDEX_SCHEMA_VERSION!r}",
    )
    check(isinstance(payload.get("generated_at"), str), "generated_at must be a string")


def validate_agent_semantic_index_payload(payload: Any) -> list[str]:
    """Validate a serialized ``GET /api/agent/semantic-index`` page.

    Returns a list of violations (empty when the payload is valid). This is
    the schema contract for the semantic index; agents may rely on every
    field validated here. The typed response models in
    ``packages.platform.agent_semantic_index_models`` mirror it and are held
    to it by ``tests/test_agent_semantic_index_models.py``.
    """
    violations, check = _validator()
    if not check(isinstance(payload, dict), "payload must be an object"):
        return violations
    _validate_envelope(payload, check)
    total = payload.get("total")
    check(_is_int(total) and total >= 0, "total must be a non-negative integer")
    check("next_cursor" in payload, "next_cursor must be present (null on the last page)")
    check(
        _text_or_null(payload.get("next_cursor"), non_empty=True),
        "next_cursor must be a non-empty string or null",
    )
    publications = payload.get("publications")
    if not check(isinstance(publications, list), "publications must be an array"):
        return violations
    for position, entry in enumerate(publications):
        _validate_entry(entry, f"publications[{position}]", check)
    return violations


def validate_agent_semantic_index_entry_payload(payload: Any) -> list[str]:
    """Validate a serialized ``GET /api/agent/semantic-index/{key}`` payload."""
    violations, check = _validator()
    if not check(isinstance(payload, dict), "payload must be an object"):
        return violations
    _validate_envelope(payload, check)
    _validate_entry(payload.get("publication"), "publication", check)
    return violations
