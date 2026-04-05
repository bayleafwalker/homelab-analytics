"""Protocol types for finance source contracts.

The finance ingestion model uses these shared types for lane A and lane B
parsers. Lane C manual reference inputs bypass the parser protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from packages.pipelines.csv_validation import ValidationIssue, ValidationResult


class FinanceIngestionLane(StrEnum):
    """Supported finance ingestion lanes."""

    STRUCTURED_CONTRACT = "structured_contract"
    DOCUMENT_PARSER = "document_parser"
    MANUAL_REFERENCE = "manual_reference"


class FinanceDatasetType(StrEnum):
    """Canonical dataset types produced by finance ingestion."""

    TRANSACTION_EVENT_STREAM = "transaction_event_stream"
    STATEMENT_SNAPSHOT = "statement_snapshot"
    EXTERNAL_RECONCILIATION_SNAPSHOT = "external_reconciliation_snapshot"
    MANUAL_REFERENCE_DATASET = "manual_reference_dataset"


@dataclass(frozen=True)
class FinanceContractTaxonomy:
    """Code-level summary of a finance ingestion contract class."""

    dataset_type: FinanceDatasetType
    lane: FinanceIngestionLane
    description: str
    dedupe_strategy: str
    lineage_model: str


STANDARD_FINANCE_CONTRACT_TAXONOMIES: tuple[FinanceContractTaxonomy, ...] = (
    FinanceContractTaxonomy(
        dataset_type=FinanceDatasetType.TRANSACTION_EVENT_STREAM,
        lane=FinanceIngestionLane.STRUCTURED_CONTRACT,
        description="Append-only cash movement rows from provider CSV exports.",
        dedupe_strategy="sha256 file hash + row fingerprint identity",
        lineage_model="raw file -> landing rows -> canonical transaction fact",
    ),
    FinanceContractTaxonomy(
        dataset_type=FinanceDatasetType.STATEMENT_SNAPSHOT,
        lane=FinanceIngestionLane.DOCUMENT_PARSER,
        description="Statement header plus optional line items extracted from a billing document.",
        dedupe_strategy="sha256 document hash + statement timestamp uniqueness",
        lineage_model="raw document -> extracted snapshot -> canonical statement fact",
    ),
    FinanceContractTaxonomy(
        dataset_type=FinanceDatasetType.EXTERNAL_RECONCILIATION_SNAPSHOT,
        lane=FinanceIngestionLane.DOCUMENT_PARSER,
        description="Point-in-time authority snapshot for debts, credits, or obligations.",
        dedupe_strategy="sha256 document hash + report timestamp uniqueness",
        lineage_model="raw document -> extracted snapshot -> canonical reconciliation fact",
    ),
    FinanceContractTaxonomy(
        dataset_type=FinanceDatasetType.MANUAL_REFERENCE_DATASET,
        lane=FinanceIngestionLane.MANUAL_REFERENCE,
        description="Sparse operator-entered reference facts with effective dating.",
        dedupe_strategy="entity key + effective_from versioning",
        lineage_model="versioned fact record -> canonical reference fact",
    ),
)


@dataclass(frozen=True)
class ParseResult:
    """Normalized parser output for a finance source contract."""

    dataset_type: FinanceDatasetType
    records: list[dict[str, Any]]
    warnings: list[ValidationIssue]
    metadata: dict[str, Any]
    raw_sha256: str


@runtime_checkable
class SourceContractParser(Protocol):
    """Shared interface for structured-file and document finance parsers."""

    contract_id: str
    dataset_type: FinanceDatasetType

    def detect(self, file_name: str, header_bytes: bytes) -> bool:
        """Return True when this parser should handle the file."""

    def parse(self, source_bytes: bytes, file_name: str) -> ParseResult:
        """Parse source bytes into normalized records."""

    def validate(self, result: ParseResult) -> ValidationResult:
        """Validate parser output against the contract expectations."""


__all__ = [
    "FinanceContractTaxonomy",
    "FinanceDatasetType",
    "FinanceIngestionLane",
    "ParseResult",
    "SourceContractParser",
    "STANDARD_FINANCE_CONTRACT_TAXONOMIES",
    "ValidationIssue",
    "ValidationResult",
]
