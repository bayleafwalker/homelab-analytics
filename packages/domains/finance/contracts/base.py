"""Protocol types for finance source contracts.

The finance ingestion model uses these shared types for lane A and lane B
parsers. Lane C manual reference inputs bypass the parser protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from packages.pipelines.csv_validation import ValidationIssue, ValidationResult


@dataclass(frozen=True)
class ParseResult:
    """Normalized parser output for a finance source contract."""

    dataset_type: str
    records: list[dict[str, Any]]
    warnings: list[ValidationIssue]
    metadata: dict[str, Any]
    raw_sha256: str


@runtime_checkable
class SourceContractParser(Protocol):
    """Shared interface for structured-file and document finance parsers."""

    contract_id: str
    dataset_type: str

    def detect(self, file_name: str, header_bytes: bytes) -> bool:
        """Return True when this parser should handle the file."""

    def parse(self, source_bytes: bytes, file_name: str) -> ParseResult:
        """Parse source bytes into normalized records."""

    def validate(self, result: ParseResult) -> ValidationResult:
        """Validate parser output against the contract expectations."""


__all__ = [
    "ParseResult",
    "SourceContractParser",
    "ValidationIssue",
    "ValidationResult",
]
