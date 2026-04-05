from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from packages.storage.duckdb_store import DimensionColumn, DimensionDefinition

DIM_ASSET = DimensionDefinition(
    table_name="dim_asset",
    natural_key_columns=("asset_id",),
    attribute_columns=(
        DimensionColumn("asset_name", "VARCHAR"),
        DimensionColumn("asset_type", "VARCHAR"),
        DimensionColumn("purchase_date", "DATE"),
        DimensionColumn("purchase_price", "DECIMAL(18,4)"),
        DimensionColumn("currency", "VARCHAR"),
        DimensionColumn("location", "VARCHAR"),
    ),
)

CURRENT_DIM_ASSET_VIEW = "rpt_current_dim_asset"

FACT_ASSET_EVENT_TABLE = "fact_asset_event"

FACT_ASSET_EVENT_COLUMNS: list[tuple[str, str]] = [
    ("asset_event_id", "VARCHAR PRIMARY KEY"),
    ("run_id", "VARCHAR"),
    ("asset_id", "VARCHAR NOT NULL"),
    ("asset_name", "VARCHAR NOT NULL"),
    ("event_date", "DATE NOT NULL"),
    ("event_type", "VARCHAR NOT NULL"),
    ("amount", "DECIMAL(18,4) NOT NULL"),
    ("currency", "VARCHAR NOT NULL"),
    ("notes", "VARCHAR"),
    ("source_system", "VARCHAR"),
]


def asset_event_id(
    asset_id: str,
    event_date: object,
    event_type: str,
    amount: object,
) -> str:
    raw = f"{asset_id}|{event_date}|{event_type}|{amount}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_asset_id(row: dict[str, Any]) -> str:
    raw = "|".join(
        (
            str(row.get("asset_name", "")),
            str(row.get("asset_type", "")),
            str(_coerce_date(row.get("purchase_date"))) if row.get("purchase_date") else "",
            str(row.get("location", "")),
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def extract_assets_from_register(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        asset_id = str(row.get("asset_id") or build_asset_id(row))
        seen[asset_id] = {
            "asset_id": asset_id,
            "asset_name": str(row["asset_name"]),
            "asset_type": str(row.get("asset_type", "unknown")),
            "purchase_date": _coerce_date(row.get("purchase_date")),
            "purchase_price": _coerce_decimal(row.get("purchase_price")),
            "currency": str(row.get("currency", "")),
            "location": str(row.get("location", "")),
        }
    return list(seen.values())


def extract_asset_register_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        asset_id = str(row.get("asset_id") or build_asset_id(row))
        events.append(
            {
                "asset_event_id": asset_event_id(
                    asset_id,
                    _coerce_date(row["purchase_date"]),
                    "acquisition",
                    _coerce_decimal(row["purchase_price"]),
                ),
                "asset_id": asset_id,
                "asset_name": str(row["asset_name"]),
                "event_date": _coerce_date(row["purchase_date"]),
                "event_type": "acquisition",
                "amount": _coerce_decimal(row["purchase_price"]),
                "currency": str(row["currency"]),
                "notes": row.get("notes"),
            }
        )
    return events


def extract_asset_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        asset_id = str(row.get("asset_id") or build_asset_id(row))
        asset_name = str(row.get("asset_name", asset_id))
        events.append(
            {
                "asset_event_id": row.get(
                    "asset_event_id",
                    asset_event_id(
                        asset_id,
                        _coerce_date(row["event_date"]),
                        str(row["event_type"]),
                        _coerce_decimal(row["amount"]),
                    ),
                ),
                "asset_id": asset_id,
                "asset_name": asset_name,
                "event_date": _coerce_date(row["event_date"]),
                "event_type": str(row["event_type"]),
                "amount": _coerce_decimal(row["amount"]),
                "currency": str(row["currency"]),
                "notes": row.get("notes"),
            }
        )
    return events


def _coerce_date(value: object | None) -> date | None:
    if value in {None, ""}:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _coerce_decimal(value: object | None) -> Decimal | None:
    if value in {None, ""}:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
