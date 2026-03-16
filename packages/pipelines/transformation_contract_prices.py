from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from packages.pipelines.contract_price_models import (
    FACT_CONTRACT_PRICE_COLUMNS,
    FACT_CONTRACT_PRICE_TABLE,
    MART_CONTRACT_PRICE_CURRENT_COLUMNS,
    MART_CONTRACT_PRICE_CURRENT_TABLE,
    MART_ELECTRICITY_PRICE_CURRENT_COLUMNS,
    MART_ELECTRICITY_PRICE_CURRENT_TABLE,
    contract_price_id,
    extract_contract_rows,
)
from packages.storage.duckdb_store import DuckDBStore

RecordLineage = Callable[..., None]


def ensure_contract_price_storage(store: DuckDBStore) -> None:
    store.ensure_table(FACT_CONTRACT_PRICE_TABLE, FACT_CONTRACT_PRICE_COLUMNS)
    store.ensure_table(
        MART_CONTRACT_PRICE_CURRENT_TABLE,
        MART_CONTRACT_PRICE_CURRENT_COLUMNS,
    )
    store.ensure_table(
        MART_ELECTRICITY_PRICE_CURRENT_TABLE,
        MART_ELECTRICITY_PRICE_CURRENT_COLUMNS,
    )


def load_contract_prices(
    store: DuckDBStore,
    *,
    rows: list[dict[str, Any]],
    record_lineage: RecordLineage,
    dim_contract,
    run_id: str | None = None,
    effective_date: date | None = None,
    source_system: str | None = None,
) -> int:
    if not rows:
        return 0

    eff = effective_date or date.today()

    with store.atomic():
        contracts = extract_contract_rows(rows)
        contracts_upserted = store.upsert_dimension_rows(
            dim_contract,
            contracts,
            effective_date=eff,
            source_system=source_system,
            source_run_id=run_id,
        )

        fact_rows = []
        for row in rows:
            fact_rows.append(
                {
                    "price_id": contract_price_id(
                        row["contract_id"],
                        row.get("price_component", "base"),
                        row.get("valid_from"),
                        row.get("billing_cycle", "monthly"),
                    ),
                    "contract_id": row["contract_id"],
                    "contract_name": row["contract_name"],
                    "provider": row.get("provider", ""),
                    "contract_type": row.get("contract_type", "general"),
                    "price_component": row.get("price_component", "base"),
                    "billing_cycle": row.get("billing_cycle", "monthly"),
                    "unit_price": row["unit_price"],
                    "currency": row.get("currency", ""),
                    "quantity_unit": row.get("quantity_unit"),
                    "valid_from": row["valid_from"],
                    "valid_to": row.get("valid_to"),
                    "run_id": run_id,
                }
            )

        inserted = store.insert_rows(FACT_CONTRACT_PRICE_TABLE, fact_rows)

    record_lineage(
        run_id=run_id,
        source_system=source_system,
        records=[
            ("dim_contract", "dimension", contracts_upserted),
            ("fact_contract_price", "fact", inserted),
        ],
    )
    return inserted


def refresh_contract_price_current(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_CONTRACT_PRICE_CURRENT_TABLE}")
    store.execute(f"DELETE FROM {MART_ELECTRICITY_PRICE_CURRENT_TABLE}")

    store.execute(
        f"""
        INSERT INTO {MART_CONTRACT_PRICE_CURRENT_TABLE} (
            contract_id, contract_name, provider, contract_type, price_component,
            billing_cycle, unit_price, currency, quantity_unit, valid_from, valid_to, status
        )
        SELECT
            contract_id,
            contract_name,
            provider,
            contract_type,
            price_component,
            billing_cycle,
            unit_price,
            currency,
            quantity_unit,
            valid_from,
            valid_to,
            CASE
                WHEN valid_to IS NULL OR valid_to >= current_date THEN 'active'
                ELSE 'inactive'
            END AS status
        FROM {FACT_CONTRACT_PRICE_TABLE}
        WHERE valid_to IS NULL OR valid_to >= current_date
        ORDER BY contract_type, contract_name, price_component, valid_from
        """
    )
    store.execute(
        f"""
        INSERT INTO {MART_ELECTRICITY_PRICE_CURRENT_TABLE}
        SELECT *
        FROM {MART_CONTRACT_PRICE_CURRENT_TABLE}
        WHERE contract_type = 'electricity'
        ORDER BY contract_name, price_component, valid_from
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_CONTRACT_PRICE_CURRENT_TABLE}"
    )[0][0]


def get_contract_price_current(
    store: DuckDBStore,
    *,
    contract_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if contract_type is not None:
        clauses.append("contract_type = ?")
        params.append(contract_type)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_CONTRACT_PRICE_CURRENT_TABLE}"
        f" {where_sql} ORDER BY contract_type, contract_name, price_component, valid_from",
        params,
    )


def get_electricity_price_current(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_ELECTRICITY_PRICE_CURRENT_TABLE}"
        " ORDER BY contract_name, price_component, valid_from"
    )


def count_contract_prices(
    store: DuckDBStore,
    *,
    run_id: str | None = None,
) -> int:
    if run_id is None:
        return store.fetchall(f"SELECT COUNT(*) FROM {FACT_CONTRACT_PRICE_TABLE}")[0][0]
    return store.fetchall(
        f"SELECT COUNT(*) FROM {FACT_CONTRACT_PRICE_TABLE} WHERE run_id = ?",
        [run_id],
    )[0][0]
