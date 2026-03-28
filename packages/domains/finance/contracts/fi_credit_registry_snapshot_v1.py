"""Finnish positive credit registry snapshot contract parser."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from packages.domains.finance.contracts.base import (
    FinanceDatasetType,
    ParseResult,
)
from packages.pipelines.csv_validation import ValidationIssue, ValidationResult

CONTRACT_ID = "fi_positive_credit_registry_snapshot_v1"
DATASET_TYPE = FinanceDatasetType.EXTERNAL_RECONCILIATION_SNAPSHOT

_SNAPSHOT_TITLE_RE = re.compile(
    r"^Luottotietorekisteriote - (?P<requestor_name>.+?), (?P<snapshot_at>\d{4}-\d{2}-\d{2})$"
)
_CREDIT_SECTION_RE = re.compile(r"^Luotto \d+$")
_INCOME_SECTION_RE = re.compile(r"^Tulo \d+$")
_INCOME_AMOUNT_RE = re.compile(
    r"^Raportoitu tulo:\s*(?P<amount>-?[\d\s.,]+)\s*(?P<currency>[A-Z]{3})?$"
)


@dataclass(frozen=True)
class PositiveCreditRegistrySnapshotRecord:
    record_type: str
    snapshot_id: str
    snapshot_at: date
    report_reference: str
    requester_id: str
    requestor_name: str | None = None
    person_id_masked: str | None = None
    credit_count: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_type": self.record_type,
            "snapshot_id": self.snapshot_id,
            "snapshot_at": self.snapshot_at,
            "report_reference": self.report_reference,
            "requester_id": self.requester_id,
            "requestor_name": self.requestor_name,
            "person_id_masked": self.person_id_masked,
            "credit_count": self.credit_count,
        }


@dataclass(frozen=True)
class PositiveCreditRegistryCreditRecord:
    record_type: str
    snapshot_id: str
    snapshot_at: date
    credit_type: str
    creditor: str
    credit_identifier: str
    agreement_date: date | None
    granted_amount: Decimal | None
    balance: Decimal | None
    monthly_payment: Decimal | None
    source_row_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_type": self.record_type,
            "snapshot_id": self.snapshot_id,
            "snapshot_at": self.snapshot_at,
            "credit_type": self.credit_type,
            "creditor": self.creditor,
            "credit_identifier": self.credit_identifier,
            "agreement_date": self.agreement_date,
            "granted_amount": self.granted_amount,
            "balance": self.balance,
            "monthly_payment": self.monthly_payment,
            "source_row_fingerprint": self.source_row_fingerprint,
        }


@dataclass(frozen=True)
class PositiveCreditRegistryIncomeRecord:
    record_type: str
    snapshot_id: str
    snapshot_at: date
    income_month: str
    reported_amount: Decimal
    currency: str
    source_row_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_type": self.record_type,
            "snapshot_id": self.snapshot_id,
            "snapshot_at": self.snapshot_at,
            "income_month": self.income_month,
            "reported_amount": self.reported_amount,
            "currency": self.currency,
            "source_row_fingerprint": self.source_row_fingerprint,
        }


class PositiveCreditRegistrySnapshotParser:
    """Parse the registry's structured text export into snapshot records."""

    contract_id = CONTRACT_ID
    dataset_type = DATASET_TYPE

    def detect(self, file_name: str, header_bytes: bytes) -> bool:
        if not file_name.lower().endswith((".txt", ".text")):
            return False
        first_block = header_bytes.decode("utf-8-sig", errors="ignore")
        return "Luottotietorekisteriote" in first_block

    def parse(self, source_bytes: bytes, file_name: str) -> ParseResult:
        del file_name
        source_text = source_bytes.decode("utf-8-sig")
        lines = [line.strip() for line in source_text.splitlines()]
        warnings: list[ValidationIssue] = []
        records: list[dict[str, Any]] = []

        if not any(lines):
            warnings.append(
                ValidationIssue(
                    code="empty_file",
                    message="Positive credit registry export is empty.",
                )
            )
            return ParseResult(
                dataset_type=self.dataset_type,
                records=[],
                warnings=warnings,
                metadata={"contract_id": self.contract_id},
                raw_sha256=_sha256(source_bytes),
            )

        snapshot_at: date | None = None
        requestor_name: str | None = None
        requester_id: str | None = None
        report_reference: str | None = None
        person_id_masked: str | None = None
        expected_credit_count: int | None = None
        credits: list[PositiveCreditRegistryCreditRecord] = []
        incomes: list[PositiveCreditRegistryIncomeRecord] = []
        current_credit: dict[str, Any] | None = None
        current_income: dict[str, Any] | None = None
        section: str | None = None

        def flush_credit() -> None:
            nonlocal current_credit
            if current_credit is None:
                return
            required_fields = [
                "credit_type",
                "creditor",
                "credit_identifier",
            ]
            if not all(current_credit.get(field) for field in required_fields):
                warnings.append(
                    ValidationIssue(
                        code="missing_credit_fields",
                        message="Incomplete registry credit record encountered.",
                    )
                )
                current_credit = None
                return
            credits.append(
                PositiveCreditRegistryCreditRecord(
                    record_type="credit",
                    snapshot_id=_build_snapshot_id(
                        snapshot_at=snapshot_at,
                        report_reference=report_reference,
                        requester_id=requester_id,
                    ),
                    snapshot_at=snapshot_at or date.min,
                    credit_type=current_credit.get("credit_type", ""),
                    creditor=current_credit.get("creditor", ""),
                    credit_identifier=current_credit.get("credit_identifier", ""),
                    agreement_date=current_credit.get("agreement_date"),
                    granted_amount=current_credit.get("granted_amount"),
                    balance=current_credit.get("balance"),
                    monthly_payment=current_credit.get("monthly_payment"),
                    source_row_fingerprint=_row_fingerprint(current_credit),
                )
            )
            current_credit = None

        def flush_income() -> None:
            nonlocal current_income
            if current_income is None:
                return
            required_fields = ["income_month", "reported_amount"]
            if not all(current_income.get(field) for field in required_fields):
                warnings.append(
                    ValidationIssue(
                        code="missing_income_fields",
                        message="Incomplete registry income record encountered.",
                    )
                )
                current_income = None
                return
            incomes.append(
                PositiveCreditRegistryIncomeRecord(
                    record_type="income",
                    snapshot_id=_build_snapshot_id(
                        snapshot_at=snapshot_at,
                        report_reference=report_reference,
                        requester_id=requester_id,
                    ),
                    snapshot_at=snapshot_at or date.min,
                    income_month=current_income["income_month"],
                    reported_amount=current_income["reported_amount"],
                    currency=current_income.get("currency", "EUR"),
                    source_row_fingerprint=_row_fingerprint(current_income),
                )
            )
            current_income = None

        for raw_line in lines:
            if not raw_line:
                continue
            title_match = _SNAPSHOT_TITLE_RE.match(raw_line)
            if title_match is not None:
                requestor_name = title_match.group("requestor_name").strip()
                snapshot_at = date.fromisoformat(title_match.group("snapshot_at"))
                section = "header"
                continue
            if raw_line == "Tilauksen tiedot":
                section = "header"
                continue
            if raw_line == "Luottojen tiedot":
                flush_credit()
                flush_income()
                section = "credits"
                continue
            if raw_line == "Tulotiedot":
                flush_credit()
                flush_income()
                section = "income"
                continue
            if _CREDIT_SECTION_RE.match(raw_line) and section == "credits":
                flush_credit()
                current_credit = {}
                continue
            if _INCOME_SECTION_RE.match(raw_line) and section == "income":
                flush_income()
                current_income = {}
                continue

            if raw_line.startswith("Tilaajan tunniste:"):
                requester_id = raw_line.split(":", 1)[1].strip()
                continue
            if raw_line.startswith("Otteen viite:"):
                report_reference = raw_line.split(":", 1)[1].strip()
                continue
            if raw_line.startswith("Henkilötunnus:"):
                person_id_masked = raw_line.split(":", 1)[1].strip()
                continue
            if raw_line.startswith("Luottoja yhteensä:"):
                try:
                    expected_credit_count = int(raw_line.split(":", 1)[1].strip())
                except ValueError:
                    warnings.append(
                        ValidationIssue(
                            code="invalid_credit_count",
                            message="Registry credit count is not an integer.",
                        )
                    )
                continue

            if current_credit is not None and section == "credits":
                _parse_credit_line(current_credit, raw_line, warnings)
                continue

            if current_income is not None and section == "income":
                _parse_income_line(current_income, raw_line, warnings)
                continue

        flush_credit()
        flush_income()

        if snapshot_at is None or requester_id is None or report_reference is None:
            warnings.append(
                ValidationIssue(
                    code="missing_snapshot_header",
                    message="Registry snapshot header is incomplete.",
                )
            )

        if expected_credit_count is not None and expected_credit_count != len(credits):
            warnings.append(
                ValidationIssue(
                    code="credit_count_mismatch",
                    message=(
                        "Registry credit count does not match the number of parsed credit records."
                    ),
                )
            )

        snapshot_record = PositiveCreditRegistrySnapshotRecord(
            record_type="snapshot",
            snapshot_id=_build_snapshot_id(
                snapshot_at=snapshot_at,
                report_reference=report_reference,
                requester_id=requester_id,
            ),
            snapshot_at=snapshot_at or date.min,
            report_reference=report_reference or "",
            requester_id=requester_id or "",
            requestor_name=requestor_name,
            person_id_masked=person_id_masked,
            credit_count=len(credits),
        )
        records.append(snapshot_record.as_dict())
        records.extend(credit.as_dict() for credit in credits)
        records.extend(income.as_dict() for income in incomes)

        metadata = {
            "contract_id": self.contract_id,
            "source_format": "positive-credit-registry-text",
            "requestor_name": requestor_name,
            "snapshot_at": snapshot_at,
            "report_reference": report_reference,
            "requester_id": requester_id,
            "person_id_masked": person_id_masked,
            "expected_credit_count": expected_credit_count,
            "parsed_credit_count": len(credits),
            "parsed_income_count": len(incomes),
            "snapshot_id": snapshot_record.snapshot_id,
        }
        return ParseResult(
            dataset_type=self.dataset_type,
            records=records,
            warnings=warnings,
            metadata=metadata,
            raw_sha256=_sha256(source_bytes),
        )

    def validate(self, result: ParseResult) -> ValidationResult:
        issues = list(result.warnings)
        snapshot_metadata = result.metadata

        if result.dataset_type != self.dataset_type:
            issues.append(
                ValidationIssue(
                    code="unexpected_dataset_type",
                    message=(
                        "Expected external reconciliation snapshot dataset type for registry export."
                    ),
                )
            )

        for field_name in ("snapshot_at", "report_reference", "requester_id"):
            if snapshot_metadata.get(field_name) in (None, ""):
                issues.append(
                    ValidationIssue(
                        code="missing_snapshot_metadata",
                        message=f"Registry snapshot metadata is missing '{field_name}'.",
                    )
                )

        snapshot_records = [
            record for record in result.records if record.get("record_type") == "snapshot"
        ]
        if len(snapshot_records) != 1:
            issues.append(
                ValidationIssue(
                    code="missing_snapshot_record",
                    message="Registry export must produce exactly one snapshot record.",
                )
            )

        credit_records = [
            record for record in result.records if record.get("record_type") == "credit"
        ]
        expected_credit_count = snapshot_metadata.get("expected_credit_count")
        if expected_credit_count is not None and expected_credit_count != len(credit_records):
            issues.append(
                ValidationIssue(
                    code="credit_count_mismatch",
                    message="Parsed registry credit count differs from header metadata.",
                )
            )

        return ValidationResult(
            header=["snapshot_at", "report_reference", "requester_id", "credit_count"],
            row_count=len(result.records),
            issues=issues,
        )


def load_positive_credit_registry_snapshot_bytes(
    source_bytes: bytes,
) -> list[dict[str, Any]]:
    parser = PositiveCreditRegistrySnapshotParser()
    return parser.parse(source_bytes, "positive-credit-registry.txt").records


def _parse_credit_line(
    credit: dict[str, Any],
    raw_line: str,
    warnings: list[ValidationIssue],
) -> None:
    if raw_line.startswith("Luoton tyyppi:"):
        credit["credit_type"] = raw_line.split(":", 1)[1].strip()
    elif raw_line.startswith("Luotonantaja:"):
        credit["creditor"] = raw_line.split(":", 1)[1].strip()
    elif raw_line.startswith("Luoton tunniste:"):
        credit["credit_identifier"] = raw_line.split(":", 1)[1].strip()
    elif raw_line.startswith("Luotto myönnetty:"):
        credit["agreement_date"] = _parse_date_text(raw_line.split(":", 1)[1].strip(), warnings)
    elif raw_line.startswith("Pääoma:"):
        credit["granted_amount"] = _parse_currency_amount(
            raw_line.split(":", 1)[1].strip(),
            warnings,
        )
    elif raw_line.startswith("Saldo:"):
        credit["balance"] = _parse_currency_amount(raw_line.split(":", 1)[1].strip(), warnings)
    elif raw_line.startswith("Kuukausierä:"):
        credit["monthly_payment"] = _parse_currency_amount(
            raw_line.split(":", 1)[1].strip(),
            warnings,
        )


def _parse_income_line(
    income: dict[str, Any],
    raw_line: str,
    warnings: list[ValidationIssue],
) -> None:
    if raw_line.startswith("Kuukausi:"):
        income["income_month"] = raw_line.split(":", 1)[1].strip()
        return

    amount_match = _INCOME_AMOUNT_RE.match(raw_line)
    if amount_match is not None:
        income["reported_amount"] = _parse_decimal_text(amount_match.group("amount"))
        income["currency"] = amount_match.group("currency") or "EUR"
        return


def _parse_currency_amount(value: str, warnings: list[ValidationIssue]) -> Decimal | None:
    cleaned = value.replace("EUR", "").strip()
    try:
        return _parse_decimal_text(cleaned)
    except ValueError:
        warnings.append(
            ValidationIssue(
                code="invalid_decimal",
                message="Invalid registry decimal value.",
            )
        )
        return None


def _parse_date_text(value: str, warnings: list[ValidationIssue]) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        warnings.append(
            ValidationIssue(
                code="invalid_date",
                message=f"Invalid registry date value: {value!r}",
            )
        )
        return None


def _parse_decimal_text(raw_value: str) -> Decimal:
    normalized = raw_value.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid registry decimal value: {raw_value!r}") from exc


def _build_snapshot_id(
    *,
    snapshot_at: date | None,
    report_reference: str | None,
    requester_id: str | None,
) -> str:
    payload = "|".join(
        [
            snapshot_at.isoformat() if snapshot_at is not None else "",
            report_reference or "",
            requester_id or "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _row_fingerprint(row: dict[str, Any]) -> str:
    payload = "|".join(f"{key}={row.get(key)!s}" for key in sorted(row))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256(source_bytes: bytes) -> str:
    return hashlib.sha256(source_bytes).hexdigest()
