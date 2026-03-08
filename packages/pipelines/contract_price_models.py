"""Dimension, fact, and mart definitions for temporal contract pricing.

This domain captures contract pricing schedules where only the rate terms are
known for a given validity window. Electricity tariffs are represented as a
special case via ``contract_type = 'electricity'``.
"""

from __future__ import annotations

import hashlib
from typing import Any

from packages.pipelines.contracts import build_contract_id


FACT_CONTRACT_PRICE_TABLE = "fact_contract_price"

FACT_CONTRACT_PRICE_COLUMNS: list[tuple[str, str]] = [
    ("price_id", "VARCHAR PRIMARY KEY"),
    ("contract_id", "VARCHAR NOT NULL"),
    ("contract_name", "VARCHAR NOT NULL"),
    ("provider", "VARCHAR NOT NULL"),
    ("contract_type", "VARCHAR NOT NULL"),
    ("price_component", "VARCHAR NOT NULL"),
    ("billing_cycle", "VARCHAR NOT NULL"),
    ("unit_price", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
    ("quantity_unit", "VARCHAR"),
    ("valid_from", "DATE NOT NULL"),
    ("valid_to", "DATE"),
    ("run_id", "VARCHAR"),
]

MART_CONTRACT_PRICE_CURRENT_TABLE = "mart_contract_price_current"

MART_CONTRACT_PRICE_CURRENT_COLUMNS: list[tuple[str, str]] = [
    ("contract_id", "VARCHAR NOT NULL"),
    ("contract_name", "VARCHAR NOT NULL"),
    ("provider", "VARCHAR NOT NULL"),
    ("contract_type", "VARCHAR NOT NULL"),
    ("price_component", "VARCHAR NOT NULL"),
    ("billing_cycle", "VARCHAR NOT NULL"),
    ("unit_price", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
    ("quantity_unit", "VARCHAR"),
    ("valid_from", "DATE NOT NULL"),
    ("valid_to", "DATE"),
    ("status", "VARCHAR NOT NULL"),
]

MART_ELECTRICITY_PRICE_CURRENT_TABLE = "mart_electricity_price_current"

MART_ELECTRICITY_PRICE_CURRENT_COLUMNS = MART_CONTRACT_PRICE_CURRENT_COLUMNS.copy()


def extract_contract_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        contract_name = row["contract_name"]
        provider = row.get("provider", "")
        contract_type = row.get("contract_type", "general")
        contract_id = row.get("contract_id") or build_contract_id(
            contract_name,
            provider,
            contract_type,
        )
        seen[contract_id] = {
            "contract_id": contract_id,
            "contract_name": contract_name,
            "provider": provider,
            "contract_type": contract_type,
            "currency": row.get("currency", ""),
            "start_date": row.get("valid_from"),
            "end_date": row.get("valid_to"),
        }
    return list(seen.values())


def contract_price_id(
    contract_id: str,
    price_component: str,
    valid_from: object,
    billing_cycle: str,
) -> str:
    raw = f"{contract_id}|{price_component}|{billing_cycle}|{valid_from}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
