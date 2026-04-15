"""OP Gold credit card invoice PDF contract parser."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

from packages.domains.finance.contracts.base import FinanceDatasetType, ParseResult
from packages.pipelines.csv_validation import ValidationIssue, ValidationResult

CONTRACT_ID = "op_gold_credit_card_invoice_pdf_v1"
DATASET_TYPE = FinanceDatasetType.STATEMENT_SNAPSHOT

_STATEMENT_DATE_RE = re.compile(r"^Statement date:\s*(?P<value>\d{4}-\d{2}-\d{2})$")
_PERIOD_RE = re.compile(
    r"^Billing period:\s*(?P<start>\d{4}-\d{2}-\d{2})\s*-\s*(?P<end>\d{4}-\d{2}-\d{2})$"
)
_DUE_DATE_RE = re.compile(r"^Due date:\s*(?P<value>\d{4}-\d{2}-\d{2})$")
_AMOUNT_RE = re.compile(
    r"^(?P<label>[A-Za-z ]+):\s*(?P<amount>-?[\d\s.,]+)\s*(?P<currency>[A-Z]{3})$"
)
_LINE_ITEM_RE = re.compile(
    r"^(?P<posted_at>\d{4}-\d{2}-\d{2})\s*\|\s*"
    r"(?P<merchant>[^|]+?)\s*\|\s*"
    r"(?P<amount>-?[\d\s.,]+)\s*(?P<currency>[A-Z]{3})"
    r"(?:\s*\|\s*confidence=(?P<confidence>high|medium|low))?$",
)


@dataclass(frozen=True)
class OPGoldCreditCardInvoiceSnapshotRecord:
    record_type: str
    statement_id: str
    statement_date: date
    period_start: date | None
    period_end: date | None
    due_date: date | None
    previous_balance: Decimal | None
    payments_total: Decimal | None
    purchases_total: Decimal | None
    interest_amount: Decimal | None
    service_fee: Decimal | None
    minimum_due: Decimal | None
    ending_balance: Decimal | None
    currency: str
    confidence: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_type": self.record_type,
            "statement_id": self.statement_id,
            "statement_date": self.statement_date,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "due_date": self.due_date,
            "previous_balance": self.previous_balance,
            "payments_total": self.payments_total,
            "purchases_total": self.purchases_total,
            "interest_amount": self.interest_amount,
            "service_fee": self.service_fee,
            "minimum_due": self.minimum_due,
            "ending_balance": self.ending_balance,
            "currency": self.currency,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class OPGoldCreditCardInvoiceLineItemRecord:
    record_type: str
    statement_id: str
    posted_at: date
    merchant: str
    amount: Decimal
    currency: str
    confidence: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_type": self.record_type,
            "statement_id": self.statement_id,
            "posted_at": self.posted_at,
            "merchant": self.merchant,
            "amount": self.amount,
            "currency": self.currency,
            "confidence": self.confidence,
        }


class OPGoldCreditCardInvoicePdfParser:
    """Parse OP Gold invoice PDFs into a statement snapshot."""

    contract_id = CONTRACT_ID
    dataset_type = DATASET_TYPE

    def detect(self, file_name: str, header_bytes: bytes) -> bool:
        if not file_name.lower().endswith(".pdf"):
            return False
        return header_bytes.startswith(b"%PDF-")

    def parse(self, source_bytes: bytes, file_name: str) -> ParseResult:
        del file_name
        warnings: list[ValidationIssue] = []
        extracted_text, extraction_method = _extract_pdf_text(source_bytes)
        lines = [line.strip() for line in extracted_text.splitlines() if line.strip()]

        if not lines:
            warnings.append(
                ValidationIssue(
                    code="empty_file",
                    message="OP Gold invoice PDF content is empty.",
                )
            )
            return ParseResult(
                dataset_type=self.dataset_type,
                records=[],
                warnings=warnings,
                metadata={
                    "contract_id": self.contract_id,
                    "source_format": "pdf",
                    "extraction_method": extraction_method,
                    "statement_id": None,
                },
                raw_sha256=_sha256(source_bytes),
            )

        statement_date: date | None = None
        period_start: date | None = None
        period_end: date | None = None
        due_date: date | None = None
        previous_balance: Decimal | None = None
        payments_total: Decimal | None = None
        purchases_total: Decimal | None = None
        interest_amount: Decimal | None = None
        service_fee: Decimal | None = None
        minimum_due: Decimal | None = None
        ending_balance: Decimal | None = None
        currency = "EUR"
        line_items: list[dict[str, Any]] = []

        for raw_line in lines:
            if raw_line in {"OP Gold credit card invoice", "Line items"}:
                continue

            if statement_date is None:
                match = _STATEMENT_DATE_RE.match(raw_line)
                if match is not None:
                    statement_date = date.fromisoformat(match.group("value"))
                    continue

            period_match = _PERIOD_RE.match(raw_line)
            if period_match is not None:
                period_start = date.fromisoformat(period_match.group("start"))
                period_end = date.fromisoformat(period_match.group("end"))
                continue

            due_match = _DUE_DATE_RE.match(raw_line)
            if due_match is not None:
                due_date = date.fromisoformat(due_match.group("value"))
                continue

            amount_match = _AMOUNT_RE.match(raw_line)
            if amount_match is not None:
                label = amount_match.group("label").strip().lower()
                amount = _parse_decimal_text(amount_match.group("amount"))
                currency = amount_match.group("currency")
                if label == "previous balance":
                    previous_balance = amount
                elif label == "payments total":
                    payments_total = amount
                elif label == "purchases total":
                    purchases_total = amount
                elif label == "interest amount":
                    interest_amount = amount
                elif label == "service fee":
                    service_fee = amount
                elif label == "minimum due":
                    minimum_due = amount
                elif label == "ending balance":
                    ending_balance = amount
                continue

            line_item_match = _LINE_ITEM_RE.match(raw_line)
            if line_item_match is not None:
                confidence = line_item_match.group("confidence") or "high"
                if confidence == "low":
                    warnings.append(
                        ValidationIssue(
                            code="low_confidence_line_item",
                            message=(
                                "OP Gold invoice line-item extraction is low confidence."
                            ),
                        )
                    )
                try:
                    amount = _parse_decimal_text(line_item_match.group("amount"))
                except ValueError as exc:
                    warnings.append(
                        ValidationIssue(
                            code="invalid_line_item_amount",
                            message=str(exc),
                        )
                    )
                    continue
                line_items.append(
                    OPGoldCreditCardInvoiceLineItemRecord(
                        record_type="line_item",
                        statement_id=_build_statement_id(statement_date, source_bytes),
                        posted_at=date.fromisoformat(line_item_match.group("posted_at")),
                        merchant=line_item_match.group("merchant").strip(),
                        amount=amount,
                        currency=line_item_match.group("currency"),
                        confidence=confidence,
                    ).as_dict()
                )
                continue

        if statement_date is None:
            warnings.append(
                ValidationIssue(
                    code="missing_statement_date",
                    message="OP Gold invoice PDF is missing the statement date.",
                )
            )
            statement_date = date.min

        statement_record = OPGoldCreditCardInvoiceSnapshotRecord(
            record_type="snapshot",
            statement_id=_build_statement_id(statement_date, source_bytes),
            statement_date=statement_date,
            period_start=period_start,
            period_end=period_end,
            due_date=due_date,
            previous_balance=previous_balance,
            payments_total=payments_total,
            purchases_total=purchases_total,
            interest_amount=interest_amount,
            service_fee=service_fee,
            minimum_due=minimum_due,
            ending_balance=ending_balance,
            currency=currency,
            confidence="high",
        )

        records = [statement_record.as_dict(), *line_items]
        metadata = {
            "contract_id": self.contract_id,
            "source_format": "op-gold-invoice-pdf",
            "extraction_method": extraction_method,
            "statement_id": statement_record.statement_id,
            "statement_date": statement_record.statement_date,
            "period_start": statement_record.period_start,
            "period_end": statement_record.period_end,
            "due_date": statement_record.due_date,
            "line_item_count": len(line_items),
        }
        return ParseResult(
            dataset_type=self.dataset_type,
            records=records,
            warnings=warnings,
            metadata=metadata,
            raw_sha256=_sha256(source_bytes),
        )

    def validate(self, result: ParseResult) -> ValidationResult:
        issues: list[ValidationIssue] = []

        if result.dataset_type != self.dataset_type:
            issues.append(
                ValidationIssue(
                    code="unexpected_dataset_type",
                    message="Expected statement snapshot dataset type for OP Gold invoice PDF.",
                )
            )

        snapshot_records = [
            record for record in result.records if record.get("record_type") == "snapshot"
        ]
        if len(snapshot_records) != 1:
            issues.append(
                ValidationIssue(
                    code="missing_snapshot_record",
                    message="OP Gold invoice PDF must produce exactly one snapshot record.",
                )
            )

        snapshot_metadata = result.metadata
        for field_name in ("statement_id", "statement_date", "due_date"):
            if snapshot_metadata.get(field_name) in (None, ""):
                issues.append(
                    ValidationIssue(
                        code="missing_snapshot_metadata",
                        message=f"OP Gold invoice PDF metadata is missing '{field_name}'.",
                    )
                )

        return ValidationResult(
            header=[
                "record_type",
                "statement_id",
                "statement_date",
                "period_start",
                "period_end",
                "due_date",
                "amount",
                "confidence",
            ],
            row_count=len(result.records),
            issues=issues,
        )


def load_op_gold_credit_card_invoice_bytes(source_bytes: bytes) -> list[dict[str, Any]]:
    parser = OPGoldCreditCardInvoicePdfParser()
    return parser.parse(source_bytes, "op-gold-invoice.pdf").records


def _extract_pdf_text(source_bytes: bytes) -> tuple[str, str]:
    try:
        from pdfplumber import open as pdfplumber_open  # type: ignore[import-untyped]
    except Exception:
                return _fallback_extract_pdf_text(source_bytes), "fallback-text"

    try:
        with pdfplumber_open(BytesIO(source_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception:
        return _fallback_extract_pdf_text(source_bytes), "fallback-text"

    text = "\n".join(page for page in pages if page.strip())
    if text.strip():
        return text, "pdfplumber"
    return _fallback_extract_pdf_text(source_bytes), "fallback-text"


def _fallback_extract_pdf_text(source_bytes: bytes) -> str:
    text = source_bytes.decode("utf-8-sig", errors="ignore")
    if "stream" in text and "endstream" in text:
        streams = re.findall(r"stream\s*(.*?)\s*endstream", text, flags=re.DOTALL)
        if streams:
            extracted_lines: list[str] = []
            for stream in streams:
                extracted_lines.extend(
                    _decode_pdf_literal(match.group(0))
                    for match in re.finditer(r"\((?:\\.|[^()])*\)", stream)
                )
            if extracted_lines:
                return "\n".join(extracted_lines)
    return text


def _decode_pdf_literal(literal: str) -> str:
    content = literal[1:-1]
    content = content.replace(r"\n", "\n").replace(r"\r", "\r").replace(r"\t", "\t")
    content = content.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
    return content


def _build_statement_id(statement_date: date | None, source_bytes: bytes) -> str:
    date_part = statement_date.isoformat() if statement_date is not None else "unknown"
    digest = hashlib.sha256(source_bytes).hexdigest()[:12]
    return f"{CONTRACT_ID}:{date_part}:{digest}"


def _parse_decimal_text(value: str) -> Decimal:
    cleaned = value.replace("\xa0", " ").replace(" ", "")
    if cleaned.count(",") == 1 and cleaned.count(".") == 0:
        cleaned = cleaned.replace(",", ".")
    elif cleaned.count(",") > 1 and cleaned.count(".") == 0:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc


def _sha256(source_bytes: bytes) -> str:
    return hashlib.sha256(source_bytes).hexdigest()
