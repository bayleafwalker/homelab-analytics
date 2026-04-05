"""Revolut personal account statement CSV contract parser."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any

from packages.domains.finance.contracts.base import (
    FinanceDatasetType,
    ParseResult,
)
from packages.pipelines.csv_validation import ValidationIssue, ValidationResult

CONTRACT_ID = "revolut_personal_account_statement_v1"
DATASET_TYPE = FinanceDatasetType.TRANSACTION_EVENT_STREAM
DEFAULT_ACCOUNT_ID = "REV-001"

_SOURCE_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "booked_at": ("Started Date", "booked_at"),
    "value_date": ("Completed Date", "value_date"),
    "provider_type": ("Type", "provider_type"),
    "counterparty_name": ("Description", "counterparty_name"),
    "amount": ("Amount", "amount"),
    "fee": ("Fee", "fee"),
    "currency": ("Currency", "currency"),
    "provider_state": ("State", "provider_state"),
    "balance": ("Balance", "balance"),
}


@dataclass(frozen=True)
class RevolutPersonalAccountStatementRecord:
    booked_at: date
    booking_month: str
    value_date: date | None
    account_id: str
    counterparty_name: str
    amount: Decimal
    currency: str
    description: str
    direction: str
    source_row_fingerprint: str
    provider_type: str | None
    provider_state: str | None
    fee: Decimal | None = None
    balance: Decimal | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "booked_at": self.booked_at,
            "booking_month": self.booking_month,
            "value_date": self.value_date,
            "account_id": self.account_id,
            "counterparty_name": self.counterparty_name,
            "amount": self.amount,
            "currency": self.currency,
            "description": self.description,
            "direction": self.direction,
            "source_row_fingerprint": self.source_row_fingerprint,
            "provider_type": self.provider_type,
            "provider_state": self.provider_state,
            "fee": self.fee,
            "balance": self.balance,
        }


class RevolutPersonalAccountStatementCsvParser:
    """Parse Revolut personal statement CSV exports into transaction rows."""

    contract_id = CONTRACT_ID
    dataset_type = DATASET_TYPE

    def detect(self, file_name: str, header_bytes: bytes) -> bool:
        if not file_name.lower().endswith(".csv"):
            return False
        header_text = header_bytes.decode("utf-8-sig", errors="ignore")
        header_line = header_text.splitlines()[0] if header_text.splitlines() else ""
        if "," not in header_line:
            return False
        normalized_header = _split_header(header_line)
        return "Started Date" in normalized_header and "Amount" in normalized_header

    def parse(self, source_bytes: bytes, file_name: str) -> ParseResult:
        del file_name
        source_text = source_bytes.decode("utf-8-sig")
        reader = csv.DictReader(StringIO(source_text))
        source_header = [column.strip() for column in (reader.fieldnames or [])]
        records: list[dict[str, Any]] = []
        warnings: list[ValidationIssue] = []

        if not source_header:
            warnings.append(
                ValidationIssue(
                    code="empty_file",
                    message="Revolut CSV content is empty.",
                )
            )
            return ParseResult(
                dataset_type=self.dataset_type,
                records=[],
                warnings=warnings,
                metadata={"contract_id": self.contract_id, "source_header": []},
                raw_sha256=_sha256(source_bytes),
            )

        missing_columns = [
            canonical_name
            for canonical_name in ("booked_at", "counterparty_name", "amount", "currency")
            if not _has_any_column(source_header, _SOURCE_HEADER_ALIASES[canonical_name])
        ]
        for canonical_name in missing_columns:
            warnings.append(
                ValidationIssue(
                    code="missing_required_column",
                    message=f"Required Revolut CSV column '{canonical_name}' is missing.",
                    column=canonical_name,
                )
            )

        for row_number, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue
            try:
                record = _parse_row(row)
            except ValueError as exc:
                warnings.append(
                    ValidationIssue(
                        code="invalid_row",
                        message=str(exc),
                        row_number=row_number,
                    )
                )
                continue
            records.append(record.as_dict())

        metadata = {
            "contract_id": self.contract_id,
            "source_header": source_header,
            "row_count": len(records),
            "source_format": "revolut-personal-csv",
            "account_id": DEFAULT_ACCOUNT_ID,
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

        if result.dataset_type != self.dataset_type:
            issues.append(
                ValidationIssue(
                    code="unexpected_dataset_type",
                    message=(
                        "Expected transaction event stream dataset type for Revolut CSV."
                    ),
                )
            )

        source_header = result.metadata.get("source_header", [])
        if not isinstance(source_header, list) or not source_header:
            issues.append(
                ValidationIssue(
                    code="missing_source_header",
                    message="Revolut CSV parse result is missing source header metadata.",
                )
            )

        return ValidationResult(
            header=list(source_header) if isinstance(source_header, list) else [],
            row_count=len(result.records),
            issues=issues,
        )


def load_revolut_personal_account_transactions_bytes(source_bytes: bytes) -> list[dict[str, Any]]:
    parser = RevolutPersonalAccountStatementCsvParser()
    return parser.parse(source_bytes, "revolut-personal-account.csv").records


def _parse_row(row: dict[str, str | None]) -> RevolutPersonalAccountStatementRecord:
    booked_at = _parse_date(row, "booked_at")
    value_date = _parse_optional_date(row, "value_date")
    amount = _parse_decimal(row, "amount")
    fee = _parse_optional_decimal(row, "fee")
    balance = _parse_optional_decimal(row, "balance")
    account_id = DEFAULT_ACCOUNT_ID
    counterparty_name = _get_value(row, "counterparty_name")
    currency = _get_value(row, "currency")
    description = counterparty_name
    provider_type = _get_optional_value(row, "provider_type")
    provider_state = _get_optional_value(row, "provider_state")
    source_row_fingerprint = _row_fingerprint(
        booked_at=booked_at,
        account_id=account_id,
        counterparty_name=counterparty_name,
        amount=amount,
        currency=currency,
        description=description,
        provider_type=provider_type,
        provider_state=provider_state,
        fee=fee,
        balance=balance,
    )

    return RevolutPersonalAccountStatementRecord(
        booked_at=booked_at,
        booking_month=booked_at.strftime("%Y-%m"),
        value_date=value_date,
        account_id=account_id,
        counterparty_name=counterparty_name,
        amount=amount,
        currency=currency,
        description=description,
        direction="income" if amount >= 0 else "expense",
        source_row_fingerprint=source_row_fingerprint,
        provider_type=provider_type,
        provider_state=provider_state,
        fee=fee,
        balance=balance,
    )


def _get_value(row: dict[str, str | None], canonical_name: str) -> str:
    value = _get_optional_value(row, canonical_name)
    if value is None:
        raise ValueError(f"Missing required Revolut CSV field '{canonical_name}'.")
    return value


def _get_optional_value(row: dict[str, str | None], canonical_name: str) -> str | None:
    for source_name in _SOURCE_HEADER_ALIASES[canonical_name]:
        raw_value = row.get(source_name)
        if raw_value is None:
            continue
        normalized = raw_value.strip()
        if normalized:
            return normalized
    return None


def _parse_date(row: dict[str, str | None], canonical_name: str) -> date:
    raw_value = _get_value(row, canonical_name)
    try:
        return datetime.fromisoformat(raw_value).date()
    except ValueError as exc:
        raise ValueError(f"Invalid Revolut CSV datetime for '{canonical_name}': {raw_value!r}") from exc


def _parse_optional_date(row: dict[str, str | None], canonical_name: str) -> date | None:
    raw_value = _get_optional_value(row, canonical_name)
    if raw_value is None:
        return None
    try:
        return datetime.fromisoformat(raw_value).date()
    except ValueError as exc:
        raise ValueError(f"Invalid Revolut CSV datetime for '{canonical_name}': {raw_value!r}") from exc


def _parse_decimal(row: dict[str, str | None], canonical_name: str) -> Decimal:
    raw_value = _get_value(row, canonical_name)
    return _parse_decimal_text(raw_value)


def _parse_optional_decimal(row: dict[str, str | None], canonical_name: str) -> Decimal | None:
    raw_value = _get_optional_value(row, canonical_name)
    if raw_value is None:
        return None
    return _parse_decimal_text(raw_value)


def _parse_decimal_text(raw_value: str) -> Decimal:
    normalized = raw_value.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid Revolut CSV decimal value: {raw_value!r}") from exc


def _row_fingerprint(
    *,
    booked_at: date,
    account_id: str,
    counterparty_name: str,
    amount: Decimal,
    currency: str,
    description: str,
    provider_type: str | None,
    provider_state: str | None,
    fee: Decimal | None,
    balance: Decimal | None,
) -> str:
    payload = "|".join(
        [
            booked_at.isoformat(),
            account_id,
            counterparty_name,
            format(amount, "f"),
            currency,
            description,
            provider_type or "",
            provider_state or "",
            format(fee, "f") if fee is not None else "",
            format(balance, "f") if balance is not None else "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256(source_bytes: bytes) -> str:
    return hashlib.sha256(source_bytes).hexdigest()


def _split_header(header_line: str) -> list[str]:
    return [column.strip() for column in header_line.split(",")]


def _has_any_column(source_header: list[str], aliases: tuple[str, ...]) -> bool:
    return any(alias in source_header for alias in aliases)
