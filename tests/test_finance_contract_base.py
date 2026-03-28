from __future__ import annotations

from dataclasses import FrozenInstanceError

from packages.domains.finance.contracts import (
    ParseResult,
    SourceContractParser,
    ValidationIssue,
    ValidationResult,
)


class _DummyFinanceParser:
    contract_id = "dummy_finance_contract_v1"
    dataset_type = "transaction_event_stream"

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
    assert parser.detect("example.csv", b"header")

    result = parser.parse(b"amount\n1.00\n", "example.csv")

    assert result.dataset_type == "transaction_event_stream"
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
        dataset_type="statement_snapshot",
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
