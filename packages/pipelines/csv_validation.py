from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class ColumnType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"


@dataclass(frozen=True)
class ColumnContract:
    name: str
    type: ColumnType = ColumnType.STRING
    required: bool = True


@dataclass(frozen=True)
class DatasetContract:
    dataset_name: str
    columns: tuple[ColumnContract, ...]
    allow_extra_columns: bool = True

    def column_map(self) -> dict[str, ColumnContract]:
        return {column.name: column for column in self.columns}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    column: str | None = None
    row_number: int | None = None


@dataclass(frozen=True)
class ValidationResult:
    header: list[str]
    row_count: int
    issues: list[ValidationIssue]

    @property
    def passed(self) -> bool:
        return not self.issues


def validate_csv_text(content: str, contract: DatasetContract) -> ValidationResult:
    reader = csv.reader(io.StringIO(content))
    issues: list[ValidationIssue] = []
    row_count = 0

    header_row = next(reader, None)
    if header_row is None:
        return ValidationResult(
            header=[],
            row_count=0,
            issues=[
                ValidationIssue(
                    code="empty_file",
                    message="CSV content is empty.",
                )
            ],
        )

    header = [column.strip() for column in header_row]
    contract_columns = contract.column_map()

    duplicates = _duplicate_values(header)
    for column in duplicates:
        issues.append(
            ValidationIssue(
                code="duplicate_column",
                message=f"Duplicate column '{column}' found in CSV header.",
                column=column,
            )
        )

    for column_name, column_contract in contract_columns.items():
        if column_contract.required and column_name not in header:
            issues.append(
                ValidationIssue(
                    code="missing_required_column",
                    message=f"Required column '{column_name}' is missing.",
                    column=column_name,
                )
            )

    if not contract.allow_extra_columns:
        for column_name in header:
            if column_name not in contract_columns:
                issues.append(
                    ValidationIssue(
                        code="unexpected_column",
                        message=f"Unexpected column '{column_name}' found in CSV header.",
                        column=column_name,
                    )
                )

    for offset, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue

        row_count += 1

        if len(row) != len(header):
            issues.append(
                ValidationIssue(
                    code="column_count_mismatch",
                    message="Row column count does not match the CSV header.",
                    row_number=offset,
                )
            )

        for index, column_name in enumerate(header):
            column_contract = contract_columns.get(column_name)
            if column_contract is None:
                continue

            value = row[index].strip() if index < len(row) else ""
            if not value:
                if column_contract.required:
                    issues.append(
                        ValidationIssue(
                            code="missing_required_value",
                            message=(
                                f"Required value missing for column '{column_name}'."
                            ),
                            column=column_name,
                            row_number=offset,
                        )
                    )
                continue

            issue = _validate_value(value, column_contract, row_number=offset)
            if issue is not None:
                issues.append(issue)

    return ValidationResult(
        header=header,
        row_count=row_count,
        issues=issues,
    )


def _duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []

    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)

    return duplicates


def _validate_value(
    value: str,
    column_contract: ColumnContract,
    row_number: int,
) -> ValidationIssue | None:
    validators = {
        ColumnType.STRING: _validate_string,
        ColumnType.INTEGER: _validate_integer,
        ColumnType.DECIMAL: _validate_decimal,
        ColumnType.DATE: _validate_date,
        ColumnType.DATETIME: _validate_datetime,
        ColumnType.BOOLEAN: _validate_boolean,
    }
    validator = validators[column_contract.type]
    return validator(value, column_contract.name, row_number)


def _validate_string(
    value: str,
    column_name: str,
    row_number: int,
) -> ValidationIssue | None:
    del value, column_name, row_number
    return None


def _validate_integer(
    value: str,
    column_name: str,
    row_number: int,
) -> ValidationIssue | None:
    try:
        int(value)
    except ValueError:
        return ValidationIssue(
            code="invalid_integer",
            message=f"Column '{column_name}' must contain an integer.",
            column=column_name,
            row_number=row_number,
        )
    return None


def _validate_decimal(
    value: str,
    column_name: str,
    row_number: int,
) -> ValidationIssue | None:
    try:
        Decimal(value)
    except InvalidOperation:
        return ValidationIssue(
            code="invalid_decimal",
            message=f"Column '{column_name}' must contain a decimal value.",
            column=column_name,
            row_number=row_number,
        )
    return None


def _validate_date(
    value: str,
    column_name: str,
    row_number: int,
) -> ValidationIssue | None:
    try:
        date.fromisoformat(value)
    except ValueError:
        return ValidationIssue(
            code="invalid_date",
            message=f"Column '{column_name}' must contain an ISO date.",
            column=column_name,
            row_number=row_number,
        )
    return None


def _validate_datetime(
    value: str,
    column_name: str,
    row_number: int,
) -> ValidationIssue | None:
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return ValidationIssue(
            code="invalid_datetime",
            message=f"Column '{column_name}' must contain an ISO datetime.",
            column=column_name,
            row_number=row_number,
        )
    return None


def _validate_boolean(
    value: str,
    column_name: str,
    row_number: int,
) -> ValidationIssue | None:
    normalized = value.strip().lower()
    allowed_values = {"true", "false", "1", "0", "yes", "no"}
    if normalized in allowed_values:
        return None
    return ValidationIssue(
        code="invalid_boolean",
        message=(
            f"Column '{column_name}' must contain a supported boolean value."
        ),
        column=column_name,
        row_number=row_number,
    )
