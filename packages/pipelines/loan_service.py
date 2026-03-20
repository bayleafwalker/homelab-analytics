"""LoanService — landing + canonical accessor for the loan repayment domain."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Any

from packages.pipelines.csv_validation import ColumnContract, ColumnType, DatasetContract
from packages.pipelines.run_context import RunControlContext
from packages.storage.blob import BlobStore, FilesystemBlobStore
from packages.storage.landing_service import LandingService
from packages.storage.run_metadata import IngestionRunRecord, RunMetadataStore

LOAN_REPAYMENT_CONTRACT = DatasetContract(
    dataset_name="loan_repayments",
    columns=(
        ColumnContract("loan_id", ColumnType.STRING),
        ColumnContract("repayment_date", ColumnType.DATE),
        ColumnContract("payment_amount", ColumnType.DECIMAL),
        ColumnContract("principal_portion", ColumnType.DECIMAL, required=False),
        ColumnContract("interest_portion", ColumnType.DECIMAL, required=False),
        ColumnContract("extra_amount", ColumnType.DECIMAL, required=False),
        ColumnContract("currency", ColumnType.STRING),
    ),
    allow_extra_columns=True,  # allow loan definition columns alongside repayment cols
)


@dataclass(frozen=True)
class CanonicalLoanRepayment:
    loan_id: str
    repayment_date: date
    repayment_month: str      # YYYY-MM
    payment_amount: Decimal
    principal_portion: Decimal | None
    interest_portion: Decimal | None
    extra_amount: Decimal | None
    currency: str
    # Optional loan definition fields (present when loading loan parameters)
    loan_name: str | None = None
    lender: str | None = None
    loan_type: str | None = None
    principal: Decimal | None = None
    annual_rate: Decimal | None = None
    term_months: int | None = None
    start_date: date | None = None
    payment_frequency: str | None = None


def load_canonical_loan_repayments_bytes(source_bytes: bytes) -> list[CanonicalLoanRepayment]:
    source_text = source_bytes.decode("utf-8")
    reader = csv.DictReader(StringIO(source_text))
    result: list[CanonicalLoanRepayment] = []

    for row in reader:
        repayment_date = date.fromisoformat(row["repayment_date"].strip())
        repayment_month = repayment_date.strftime("%Y-%m")

        def _decimal_or_none(val: str | None) -> Decimal | None:
            v = (val or "").strip()
            return Decimal(v) if v else None

        def _int_or_none(val: str | None) -> int | None:
            v = (val or "").strip()
            return int(v) if v else None

        def _date_or_none(val: str | None) -> date | None:
            v = (val or "").strip()
            return date.fromisoformat(v) if v else None

        result.append(
            CanonicalLoanRepayment(
                loan_id=row["loan_id"].strip(),
                repayment_date=repayment_date,
                repayment_month=repayment_month,
                payment_amount=Decimal(row["payment_amount"].strip()),
                principal_portion=_decimal_or_none(row.get("principal_portion")),
                interest_portion=_decimal_or_none(row.get("interest_portion")),
                extra_amount=_decimal_or_none(row.get("extra_amount")),
                currency=row["currency"].strip(),
                loan_name=row.get("loan_name", "").strip() or None,
                lender=row.get("lender", "").strip() or None,
                loan_type=row.get("loan_type", "").strip() or None,
                principal=_decimal_or_none(row.get("principal")),
                annual_rate=_decimal_or_none(row.get("annual_rate")),
                term_months=_int_or_none(row.get("term_months")),
                start_date=_date_or_none(row.get("start_date")),
                payment_frequency=row.get("payment_frequency", "").strip() or None,
            )
        )

    return result


class LoanService:
    """Ingest loan repayment CSVs and expose canonical rows for promotion."""

    def __init__(
        self,
        landing_root: Path,
        metadata_repository: RunMetadataStore,
        blob_store: BlobStore | None = None,
    ) -> None:
        self.landing_root = landing_root
        self.metadata_repository = metadata_repository
        self.blob_store = blob_store or FilesystemBlobStore(landing_root)
        self.landing_service = LandingService(
            blob_store=self.blob_store,
            metadata_repository=self.metadata_repository,
        )

    def ingest_file(
        self,
        source_path: Path,
        source_name: str = "manual-upload",
        run_context: RunControlContext | None = None,
    ) -> IngestionRunRecord:
        return self.ingest_bytes(
            source_bytes=source_path.read_bytes(),
            file_name=source_path.name,
            source_name=source_name,
            run_context=run_context,
        )

    def ingest_bytes(
        self,
        *,
        source_bytes: bytes,
        file_name: str,
        source_name: str = "manual-upload",
        run_context: RunControlContext | None = None,
    ) -> IngestionRunRecord:
        landing_result = self.landing_service.ingest_csv_bytes(
            source_bytes=source_bytes,
            file_name=file_name,
            source_name=source_name,
            contract=LOAN_REPAYMENT_CONTRACT,
            run_context=run_context,
        )
        return self.metadata_repository.get_run(landing_result.run_id)

    def get_run(self, run_id: str) -> IngestionRunRecord:
        return self.metadata_repository.get_run(run_id)

    def get_canonical_loan_repayments(self, run_id: str) -> list[CanonicalLoanRepayment]:
        run = self.get_run(run_id)
        if not run.passed:
            return []

        source_locator = run.raw_path
        manifest = json.loads(self.blob_store.read_bytes(run.manifest_path).decode("utf-8"))
        canonical_path = manifest.get("canonical_path")
        if canonical_path:
            source_locator = canonical_path

        source_bytes = self.blob_store.read_bytes(source_locator)
        return load_canonical_loan_repayments_bytes(source_bytes)
