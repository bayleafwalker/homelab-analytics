from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path


@dataclass(frozen=True)
class CanonicalTransaction:
    booked_at: date
    booking_month: str
    account_id: str
    counterparty_name: str
    amount: Decimal
    currency: str
    description: str
    direction: str


def load_canonical_transactions(source_path: Path) -> list[CanonicalTransaction]:
    return load_canonical_transactions_bytes(source_path.read_bytes())


def load_canonical_transactions_bytes(source_bytes: bytes) -> list[CanonicalTransaction]:
    source_text = source_bytes.decode("utf-8")
    reader = csv.DictReader(StringIO(source_text))
    transactions = []

    for row in reader:
        booked_at = date.fromisoformat(row["booked_at"].strip())
        amount = Decimal(row["amount"].strip())
        transactions.append(
            CanonicalTransaction(
                booked_at=booked_at,
                booking_month=booked_at.strftime("%Y-%m"),
                account_id=row["account_id"].strip(),
                counterparty_name=row["counterparty_name"].strip(),
                amount=amount,
                currency=row["currency"].strip(),
                description=row.get("description", "").strip(),
                direction="income" if amount >= 0 else "expense",
            )
        )

    return transactions
