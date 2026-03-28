from __future__ import annotations

from dataclasses import FrozenInstanceError

from packages.domains.finance import (
    FinanceDatasetType as RootFinanceDatasetType,
)
from packages.domains.finance import (
    FinanceIngestionLane as RootFinanceIngestionLane,
)
from packages.domains.finance.contracts import (
    STANDARD_FINANCE_CONTRACT_TAXONOMIES,
    FinanceContractTaxonomy,
    FinanceDatasetType,
    FinanceIngestionLane,
    ParseResult,
    SourceContractParser,
    ValidationIssue,
    ValidationResult,
)


class _DummyFinanceParser:
    contract_id = "dummy_finance_contract_v1"
    dataset_type = FinanceDatasetType.TRANSACTION_EVENT_STREAM

    def detect(self, file_name: str, header_bytes: bytes) -> bool:
        del header_bytes
        return file_name.endswith(".csv")

    def parse(self, source_bytes: bytes, file_name: str) -> ParseResult:
        del source_bytes, file_name
        warning = ValidationIssue(
            code="parser_warning",
            message="Dummy warning for protocol coverage.",
        )
        return ParseResult(
            dataset_type=self.dataset_type,
            records=[{"record_type": "transaction", "amount": "1.00"}],
            warnings=[warning],
            metadata={"parser": self.contract_id},
            raw_sha256="abc123",
        )

    def validate(self, result: ParseResult) -> ValidationResult:
        return ValidationResult(
            header=["amount"],
            row_count=len(result.records),
            issues=list(result.warnings),
        )


def test_finance_contract_parser_protocol_supports_lane_a_style_parsers() -> None:
    parser = _DummyFinanceParser()

    assert isinstance(parser, SourceContractParser)
    assert parser.dataset_type == FinanceDatasetType.TRANSACTION_EVENT_STREAM
    assert parser.detect("example.csv", b"header")

    result = parser.parse(b"amount\n1.00\n", "example.csv")

    assert result.dataset_type == FinanceDatasetType.TRANSACTION_EVENT_STREAM
    assert result.records == [{"record_type": "transaction", "amount": "1.00"}]
    assert result.metadata == {"parser": "dummy_finance_contract_v1"}
    assert result.raw_sha256 == "abc123"

    validation = parser.validate(result)

    assert validation.header == ["amount"]
    assert validation.row_count == 1
    assert validation.issues == result.warnings


def test_parse_result_is_frozen_and_holds_warning_metadata() -> None:
    warning = ValidationIssue(code="field_confidence_low", message="Check extraction.")
    result = ParseResult(
        dataset_type=FinanceDatasetType.STATEMENT_SNAPSHOT,
        records=[],
        warnings=[warning],
        metadata={"source": "op_gold_invoice_pdf_v1"},
        raw_sha256="deadbeef",
    )

    assert result.warnings == [warning]
    assert result.metadata == {"source": "op_gold_invoice_pdf_v1"}

    try:
        result.raw_sha256 = "other"
    except FrozenInstanceError:
        pass
    else:  # pragma: no cover - defensive branch
        raise AssertionError("ParseResult must remain frozen.")


def test_finance_contract_taxonomy_captures_the_four_standard_dataset_types() -> None:
    dataset_types = {entry.dataset_type for entry in STANDARD_FINANCE_CONTRACT_TAXONOMIES}

    assert dataset_types == {
        FinanceDatasetType.TRANSACTION_EVENT_STREAM,
        FinanceDatasetType.STATEMENT_SNAPSHOT,
        FinanceDatasetType.EXTERNAL_RECONCILIATION_SNAPSHOT,
        FinanceDatasetType.MANUAL_REFERENCE_DATASET,
    }
    assert {
        entry.lane for entry in STANDARD_FINANCE_CONTRACT_TAXONOMIES
    } == {
        FinanceIngestionLane.STRUCTURED_CONTRACT,
        FinanceIngestionLane.DOCUMENT_PARSER,
        FinanceIngestionLane.MANUAL_REFERENCE,
    }

    manual_reference = next(
        entry
        for entry in STANDARD_FINANCE_CONTRACT_TAXONOMIES
        if entry.dataset_type == FinanceDatasetType.MANUAL_REFERENCE_DATASET
    )

    assert isinstance(manual_reference, FinanceContractTaxonomy)
    assert manual_reference.dedupe_strategy == "entity key + effective_from versioning"


def test_finance_package_root_re_exports_the_taxonomy_types() -> None:
    assert RootFinanceDatasetType is FinanceDatasetType
    assert RootFinanceIngestionLane is FinanceIngestionLane
