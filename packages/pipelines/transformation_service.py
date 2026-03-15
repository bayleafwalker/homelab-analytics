"""Transformation service — loads canonical transactions and subscriptions into DuckDB.

Orchestrates:
1. Dimension extraction and SCD-2 upsert (dim_account, dim_counterparty, dim_contract, dim_category)
2. Fact table insert (fact_transaction, fact_subscription_charge)
3. Mart materialisation (mart_monthly_cashflow, mart_monthly_cashflow_by_counterparty, mart_subscription_summary)
4. Transformation audit (transformation_audit)
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
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
from packages.pipelines.normalization import (
    normalize_currency_code,
    normalize_timestamp_utc,
    normalize_unit,
)
from packages.pipelines.subscription_models import (
    CURRENT_DIM_CATEGORY_VIEW,
    CURRENT_DIM_CONTRACT_VIEW,
    DIM_CATEGORY,
    DIM_CONTRACT,
    FACT_SUBSCRIPTION_CHARGE_COLUMNS,
    FACT_SUBSCRIPTION_CHARGE_TABLE,
    MART_SUBSCRIPTION_SUMMARY_COLUMNS,
    MART_SUBSCRIPTION_SUMMARY_TABLE,
    extract_contracts,
    subscription_charge_id,
)
from packages.pipelines.transaction_models import (
    CURRENT_DIM_ACCOUNT_VIEW,
    CURRENT_DIM_COUNTERPARTY_VIEW,
    DIM_ACCOUNT,
    DIM_COUNTERPARTY,
    FACT_TRANSACTION_COLUMNS,
    FACT_TRANSACTION_TABLE,
    MART_CASHFLOW_BY_COUNTERPARTY_COLUMNS,
    MART_CASHFLOW_BY_COUNTERPARTY_TABLE,
    MART_MONTHLY_CASHFLOW_COLUMNS,
    MART_MONTHLY_CASHFLOW_TABLE,
    TRANSFORMATION_AUDIT_COLUMNS,
    TRANSFORMATION_AUDIT_TABLE,
    extract_accounts,
    extract_counterparties,
)
from packages.pipelines.utility_models import (
    CURRENT_DIM_METER_VIEW,
    DIM_METER,
    FACT_BILL_COLUMNS,
    FACT_BILL_TABLE,
    FACT_UTILITY_USAGE_COLUMNS,
    FACT_UTILITY_USAGE_TABLE,
    MART_UTILITY_COST_SUMMARY_COLUMNS,
    MART_UTILITY_COST_SUMMARY_TABLE,
    extract_meters_from_bills,
    extract_meters_from_usage,
    utility_bill_id,
    utility_usage_id,
)
from packages.storage.control_plane import SourceLineageCreate, SourceLineageStore
from packages.storage.duckdb_store import DuckDBStore


class TransformationService:
    """Loads validated landing data into the transformation and reporting layers."""

    def __init__(
        self,
        store: DuckDBStore,
        *,
        control_plane_store: SourceLineageStore | None = None,
    ) -> None:
        self._store = store
        self._control_plane_store = control_plane_store
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._store.ensure_dimension(DIM_ACCOUNT)
        self._store.ensure_dimension(DIM_COUNTERPARTY)
        self._store.ensure_current_dimension_view(DIM_ACCOUNT, CURRENT_DIM_ACCOUNT_VIEW)
        self._store.ensure_current_dimension_view(
            DIM_COUNTERPARTY,
            CURRENT_DIM_COUNTERPARTY_VIEW,
        )
        self._store.ensure_table(FACT_TRANSACTION_TABLE, FACT_TRANSACTION_COLUMNS)
        self._store.ensure_table(MART_MONTHLY_CASHFLOW_TABLE, MART_MONTHLY_CASHFLOW_COLUMNS)
        self._store.ensure_table(
            MART_CASHFLOW_BY_COUNTERPARTY_TABLE,
            MART_CASHFLOW_BY_COUNTERPARTY_COLUMNS,
        )
        self._store.ensure_table(TRANSFORMATION_AUDIT_TABLE, TRANSFORMATION_AUDIT_COLUMNS)
        # Subscription domain
        self._store.ensure_dimension(DIM_CATEGORY)
        self._store.ensure_dimension(DIM_CONTRACT)
        self._store.ensure_current_dimension_view(DIM_CATEGORY, CURRENT_DIM_CATEGORY_VIEW)
        self._store.ensure_current_dimension_view(DIM_CONTRACT, CURRENT_DIM_CONTRACT_VIEW)
        self._store.ensure_table(
            FACT_SUBSCRIPTION_CHARGE_TABLE, FACT_SUBSCRIPTION_CHARGE_COLUMNS
        )
        self._store.ensure_table(
            MART_SUBSCRIPTION_SUMMARY_TABLE, MART_SUBSCRIPTION_SUMMARY_COLUMNS
        )
        self._store.ensure_table(FACT_CONTRACT_PRICE_TABLE, FACT_CONTRACT_PRICE_COLUMNS)
        self._store.ensure_table(
            MART_CONTRACT_PRICE_CURRENT_TABLE,
            MART_CONTRACT_PRICE_CURRENT_COLUMNS,
        )
        self._store.ensure_table(
            MART_ELECTRICITY_PRICE_CURRENT_TABLE,
            MART_ELECTRICITY_PRICE_CURRENT_COLUMNS,
        )
        self._store.ensure_dimension(DIM_METER)
        self._store.ensure_current_dimension_view(DIM_METER, CURRENT_DIM_METER_VIEW)
        self._store.ensure_table(FACT_UTILITY_USAGE_TABLE, FACT_UTILITY_USAGE_COLUMNS)
        self._store.ensure_table(FACT_BILL_TABLE, FACT_BILL_COLUMNS)
        self._store.ensure_table(
            MART_UTILITY_COST_SUMMARY_TABLE,
            MART_UTILITY_COST_SUMMARY_COLUMNS,
        )

    # -- public API ----------------------------------------------------------

    # -- PLT-08: normalisation helpers -------------------------------------

    @staticmethod
    def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of *row* with PLT-08 normalisation applied.

        Current rules:
        - preserve the source currency string as ``currency``
        - derive canonical ISO-4217 ``normalized_currency``
        - force ``direction`` to the lowercase enum derived from amount sign
        """
        amount = row.get("amount", 0)
        if isinstance(amount, str):
            amount = Decimal(amount)
        elif isinstance(amount, float):
            amount = Decimal(str(amount))

        currency = str(row.get("currency", "")).strip()
        normalized_currency = normalize_currency_code(currency)

        direction = "income" if amount >= 0 else "expense"

        return {
            **row,
            "currency": currency,
            "normalized_currency": normalized_currency,
            "direction": direction,
        }

    def _record_lineage(
        self,
        *,
        run_id: str | None,
        source_system: str | None,
        records: list[tuple[str, str, int | None]],
    ) -> None:
        if run_id is None or self._control_plane_store is None:
            return
        self._control_plane_store.record_source_lineage(
            tuple(
                SourceLineageCreate(
                    lineage_id=uuid.uuid4().hex[:16],
                    input_run_id=run_id,
                    source_run_id=run_id,
                    source_system=source_system,
                    target_layer="transformation",
                    target_name=target_name,
                    target_kind=target_kind,
                    row_count=row_count,
                )
                for target_name, target_kind, row_count in records
            )
        )

    # -- public API ----------------------------------------------------------

    def load_transactions(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        """Ingest a batch of canonical transaction dicts.

        Each dict must have: booked_at, account_id, counterparty_name,
        amount, currency, description.

        Returns the number of fact rows inserted.
        """
        if not rows:
            return 0

        rows = [self._normalize_row(r) for r in rows]
        eff = effective_date or date.today()
        started_at = datetime.now(UTC)

        with self._store.atomic():
            # 1. Upsert dimensions
            accounts = extract_accounts(rows)
            accounts_upserted = self._store.upsert_dimension_rows(
                DIM_ACCOUNT,
                accounts,
                effective_date=eff,
                source_system=source_system,
                source_run_id=run_id,
            )

            counterparties = extract_counterparties(rows)
            counterparties_upserted = self._store.upsert_dimension_rows(
                DIM_COUNTERPARTY,
                counterparties,
                effective_date=eff,
                source_system=source_system,
                source_run_id=run_id,
            )

            # 2. Insert facts
            fact_rows = []
            for row in rows:
                booked_at_utc = normalize_timestamp_utc(row["booked_at"])
                booked_at = booked_at_utc.date()

                amount = row["amount"]
                if isinstance(amount, str):
                    amount = Decimal(amount)
                elif isinstance(amount, float):
                    amount = Decimal(str(amount))

                booking_month = booked_at.strftime("%Y-%m")
                direction = "income" if amount >= 0 else "expense"

                # Deterministic transaction_id from content
                tid = _transaction_id(
                    booked_at, row["account_id"], row["counterparty_name"], amount
                )

                fact_rows.append(
                    {
                        "transaction_id": tid,
                        "booked_at": booked_at,
                        "booked_at_utc": booked_at_utc,
                        "booking_month": booking_month,
                        "account_id": row["account_id"],
                        "counterparty_name": row["counterparty_name"],
                        "amount": amount,
                        "currency": row["currency"],
                        "normalized_currency": row["normalized_currency"],
                        "description": row.get("description", ""),
                        "direction": direction,
                        "run_id": run_id,
                    }
                )

            inserted = self._store.insert_rows(FACT_TRANSACTION_TABLE, fact_rows)

        # 3. Write audit record (after successful commit, outside atomic block)
        completed_at = datetime.now(UTC)
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        self._store.insert_rows(
            TRANSFORMATION_AUDIT_TABLE,
            [
                {
                    "audit_id": uuid.uuid4().hex[:16],
                    "input_run_id": run_id,
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "duration_ms": duration_ms,
                    "fact_rows": inserted,
                    "accounts_upserted": accounts_upserted,
                    "counterparties_upserted": counterparties_upserted,
                }
            ],
        )
        self._record_lineage(
            run_id=run_id,
            source_system=source_system,
            records=[
                ("dim_account", "dimension", accounts_upserted),
                ("dim_counterparty", "dimension", counterparties_upserted),
                ("fact_transaction", "fact", inserted),
            ],
        )
        return inserted

    def refresh_monthly_cashflow(self) -> int:
        """Rebuild ``mart_monthly_cashflow`` from fact_transaction.

        Returns number of mart rows written.
        """
        self._store.execute(f"DELETE FROM {MART_MONTHLY_CASHFLOW_TABLE}")

        sql = f"""
            INSERT INTO {MART_MONTHLY_CASHFLOW_TABLE}
                (booking_month, income, expense, net, transaction_count)
            SELECT
                booking_month,
                COALESCE(SUM(CASE WHEN amount >= 0 THEN amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) AS expense,
                COALESCE(SUM(amount), 0) AS net,
                COUNT(*) AS transaction_count
            FROM {FACT_TRANSACTION_TABLE}
            GROUP BY booking_month
            ORDER BY booking_month
        """
        self._store.execute(sql)
        result = self._store.fetchall(
            f"SELECT COUNT(*) FROM {MART_MONTHLY_CASHFLOW_TABLE}"
        )
        return result[0][0]

    def get_monthly_cashflow(
        self,
        from_month: str | None = None,
        to_month: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read the materialised monthly cashflow mart with optional date-range filters.

        *from_month* and *to_month* are inclusive bounds in ``YYYY-MM`` format.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if from_month is not None:
            clauses.append("booking_month >= ?")
            params.append(from_month)
        if to_month is not None:
            clauses.append("booking_month <= ?")
            params.append(to_month)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return self._store.fetchall_dicts(
            f"SELECT * FROM {MART_MONTHLY_CASHFLOW_TABLE} {where_sql} ORDER BY booking_month",
            params,
        )

    def get_transactions(self) -> list[dict[str, Any]]:
        """Read all fact transactions."""
        return self._store.fetchall_dicts(
            f"SELECT * FROM {FACT_TRANSACTION_TABLE} ORDER BY booked_at, account_id"
        )

    def count_transactions(self, run_id: str | None = None) -> int:
        """Return persisted fact count, optionally scoped to one input run."""
        if run_id is None:
            return self._store.fetchall(
                f"SELECT COUNT(*) FROM {FACT_TRANSACTION_TABLE}"
            )[0][0]
        return self._store.fetchall(
            f"SELECT COUNT(*) FROM {FACT_TRANSACTION_TABLE} WHERE run_id = ?",
            [run_id],
        )[0][0]

    def count_subscriptions(self, run_id: str | None = None) -> int:
        """Return persisted subscription fact count, optionally scoped to one input run."""
        if run_id is None:
            return self._store.fetchall(
                f"SELECT COUNT(*) FROM {FACT_SUBSCRIPTION_CHARGE_TABLE}"
            )[0][0]
        return self._store.fetchall(
            f"SELECT COUNT(*) FROM {FACT_SUBSCRIPTION_CHARGE_TABLE} WHERE run_id = ?",
            [run_id],
        )[0][0]

    def count_contract_prices(self, run_id: str | None = None) -> int:
        """Return persisted contract-price fact count, optionally scoped to one input run."""
        if run_id is None:
            return self._store.fetchall(
                f"SELECT COUNT(*) FROM {FACT_CONTRACT_PRICE_TABLE}"
            )[0][0]
        return self._store.fetchall(
            f"SELECT COUNT(*) FROM {FACT_CONTRACT_PRICE_TABLE} WHERE run_id = ?",
            [run_id],
        )[0][0]

    def count_utility_usage(self, run_id: str | None = None) -> int:
        if run_id is None:
            return self._store.fetchall(
                f"SELECT COUNT(*) FROM {FACT_UTILITY_USAGE_TABLE}"
            )[0][0]
        return self._store.fetchall(
            f"SELECT COUNT(*) FROM {FACT_UTILITY_USAGE_TABLE} WHERE run_id = ?",
            [run_id],
        )[0][0]

    def count_bills(self, run_id: str | None = None) -> int:
        if run_id is None:
            return self._store.fetchall(f"SELECT COUNT(*) FROM {FACT_BILL_TABLE}")[0][0]
        return self._store.fetchall(
            f"SELECT COUNT(*) FROM {FACT_BILL_TABLE} WHERE run_id = ?",
            [run_id],
        )[0][0]

    # -- ANA-01: counterparty cashflow breakdown --------------------------------

    def refresh_monthly_cashflow_by_counterparty(self) -> int:
        """Rebuild ``mart_monthly_cashflow_by_counterparty`` from fact_transaction.

        Returns number of mart rows written.
        """
        self._store.execute(f"DELETE FROM {MART_CASHFLOW_BY_COUNTERPARTY_TABLE}")
        sql = f"""
            INSERT INTO {MART_CASHFLOW_BY_COUNTERPARTY_TABLE}
                (booking_month, counterparty_name, income, expense, net, transaction_count)
            SELECT
                booking_month,
                counterparty_name,
                COALESCE(SUM(CASE WHEN amount >= 0 THEN amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) AS expense,
                COALESCE(SUM(amount), 0) AS net,
                COUNT(*) AS transaction_count
            FROM {FACT_TRANSACTION_TABLE}
            GROUP BY booking_month, counterparty_name
            ORDER BY booking_month, counterparty_name
        """
        self._store.execute(sql)
        result = self._store.fetchall(
            f"SELECT COUNT(*) FROM {MART_CASHFLOW_BY_COUNTERPARTY_TABLE}"
        )
        return result[0][0]

    def get_monthly_cashflow_by_counterparty(
        self,
        from_month: str | None = None,
        to_month: str | None = None,
        counterparty_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read the materialised counterparty-breakdown cashflow mart.

        *from_month* and *to_month* are inclusive ``YYYY-MM`` bounds.
        *counterparty_name* filters to a specific counterparty.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if from_month is not None:
            clauses.append("booking_month >= ?")
            params.append(from_month)
        if to_month is not None:
            clauses.append("booking_month <= ?")
            params.append(to_month)
        if counterparty_name is not None:
            clauses.append("counterparty_name = ?")
            params.append(counterparty_name)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return self._store.fetchall_dicts(
            f"SELECT * FROM {MART_CASHFLOW_BY_COUNTERPARTY_TABLE}"
            f" {where_sql} ORDER BY booking_month, counterparty_name",
            params,
        )

    # -- PLT-17: transformation audit ------------------------------------------

    def get_transformation_audit(
        self,
        input_run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return transformation audit records, optionally filtered by input run ID."""
        if input_run_id is not None:
            return self._store.fetchall_dicts(
                f"SELECT * FROM {TRANSFORMATION_AUDIT_TABLE}"
                " WHERE input_run_id = ?"
                " ORDER BY started_at DESC",
                [input_run_id],
            )
        return self._store.fetchall_dicts(
            f"SELECT * FROM {TRANSFORMATION_AUDIT_TABLE} ORDER BY started_at DESC"
        )

    # -- PLT-11: current dimension views (reporting snapshot) ---------------

    def get_current_accounts(self) -> list[dict[str, Any]]:
        """Return the published reporting view over current dim_account rows."""
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_ACCOUNT_VIEW} ORDER BY account_id"
        )

    def get_current_counterparties(self) -> list[dict[str, Any]]:
        """Return the published reporting view over current dim_counterparty rows."""
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_COUNTERPARTY_VIEW}"
            " ORDER BY counterparty_name"
        )

    def get_current_contracts(self) -> list[dict[str, Any]]:
        """Return the published reporting view over current dim_contract rows."""
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_CONTRACT_VIEW} ORDER BY contract_name"
        )

    def get_current_categories(self) -> list[dict[str, Any]]:
        """Return the published reporting view over current dim_category rows."""
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_CATEGORY_VIEW} ORDER BY category_id"
        )

    def get_current_meters(self) -> list[dict[str, Any]]:
        return self._store.fetchall_dicts(
            f"SELECT * FROM {CURRENT_DIM_METER_VIEW} ORDER BY meter_id"
        )

    def get_current_dimension_rows(self, dimension_name: str) -> list[dict[str, Any]]:
        if dimension_name == "dim_account":
            return self.get_current_accounts()
        if dimension_name == "dim_counterparty":
            return self.get_current_counterparties()
        if dimension_name == "dim_contract":
            return self.get_current_contracts()
        if dimension_name == "dim_category":
            return self.get_current_categories()
        if dimension_name == "dim_meter":
            return self.get_current_meters()
        raise KeyError(f"Unknown current dimension: {dimension_name}")

    @property
    def store(self) -> DuckDBStore:
        return self._store

    # -- Subscription domain (Phase 2) ----------------------------------------

    def load_subscriptions(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        """Ingest a batch of canonical subscription dicts.

        Each dict must have: contract_id, service_name, provider, billing_cycle,
        amount, currency, start_date. end_date is optional (None = active).

        Returns the number of fact rows inserted.
        """
        if not rows:
            return 0

        eff = effective_date or date.today()

        with self._store.atomic():
            # 1. Upsert dim_contract
            contracts = extract_contracts(rows)
            contracts_upserted = self._store.upsert_dimension_rows(
                DIM_CONTRACT,
                contracts,
                effective_date=eff,
                source_system=source_system,
                source_run_id=run_id,
            )

            # 2. Insert fact rows
            fact_rows = []
            for row in rows:
                charge_id = subscription_charge_id(
                    row["service_name"],
                    row.get("billing_cycle", "monthly"),
                    row.get("start_date"),
                )
                fact_rows.append(
                    {
                        "charge_id": charge_id,
                        "contract_id": row["contract_id"],
                        "contract_name": row["service_name"],
                        "provider": row.get("provider", ""),
                        "billing_cycle": row.get("billing_cycle", "monthly"),
                        "amount": row["amount"],
                        "currency": row.get("currency", ""),
                        "start_date": row["start_date"],
                        "end_date": row.get("end_date"),
                        "run_id": run_id,
                    }
                )

            inserted = self._store.insert_rows(FACT_SUBSCRIPTION_CHARGE_TABLE, fact_rows)

        self._record_lineage(
            run_id=run_id,
            source_system=source_system,
            records=[
                ("dim_contract", "dimension", contracts_upserted),
                ("fact_subscription_charge", "fact", inserted),
            ],
        )
        return inserted

    def refresh_subscription_summary(self) -> int:
        """Rebuild ``mart_subscription_summary`` from fact_subscription_charge.

        Computes monthly_equivalent for each billing cycle and derives an
        active/inactive status based on whether end_date is in the past.

        Returns number of mart rows written.
        """
        self._store.execute(f"DELETE FROM {MART_SUBSCRIPTION_SUMMARY_TABLE}")

        sql = f"""
            INSERT INTO {MART_SUBSCRIPTION_SUMMARY_TABLE} (
                contract_id, contract_name, provider, billing_cycle, amount, currency,
                start_date, end_date, monthly_equivalent, status
            )
            SELECT
                contract_id,
                contract_name,
                provider,
                billing_cycle,
                amount,
                currency,
                start_date,
                end_date,
                CASE billing_cycle
                    WHEN 'monthly' THEN CAST(amount AS DECIMAL(18,4))
                    WHEN 'annual'  THEN ROUND(amount / 12, 4)
                    WHEN 'weekly'  THEN ROUND(amount * 52 / 12, 4)
                    ELSE CAST(amount AS DECIMAL(18,4))
                END AS monthly_equivalent,
                CASE
                    WHEN end_date IS NULL OR end_date >= current_date THEN 'active'
                    ELSE 'inactive'
                END AS status
            FROM {FACT_SUBSCRIPTION_CHARGE_TABLE}
            ORDER BY contract_name
        """
        self._store.execute(sql)
        result = self._store.fetchall(
            f"SELECT COUNT(*) FROM {MART_SUBSCRIPTION_SUMMARY_TABLE}"
        )
        return result[0][0]

    def get_subscription_summary(
        self,
        status: str | None = None,
        currency: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read the materialised subscription summary mart.

        *status* filters to 'active' or 'inactive'.
        *currency* filters to a specific ISO currency code.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if currency is not None:
            clauses.append("currency = ?")
            params.append(currency)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return self._store.fetchall_dicts(
            f"SELECT * FROM {MART_SUBSCRIPTION_SUMMARY_TABLE}"
            f" {where_sql} ORDER BY contract_name",
            params,
        )

    # -- Contract pricing / electricity domain ---------------------------------

    def load_contract_prices(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        if not rows:
            return 0

        eff = effective_date or date.today()

        with self._store.atomic():
            contracts = extract_contract_rows(rows)
            contracts_upserted = self._store.upsert_dimension_rows(
                DIM_CONTRACT,
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

            inserted = self._store.insert_rows(FACT_CONTRACT_PRICE_TABLE, fact_rows)

        self._record_lineage(
            run_id=run_id,
            source_system=source_system,
            records=[
                ("dim_contract", "dimension", contracts_upserted),
                ("fact_contract_price", "fact", inserted),
            ],
        )
        return inserted

    def refresh_contract_price_current(self) -> int:
        self._store.execute(f"DELETE FROM {MART_CONTRACT_PRICE_CURRENT_TABLE}")
        self._store.execute(f"DELETE FROM {MART_ELECTRICITY_PRICE_CURRENT_TABLE}")

        sql = f"""
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
        self._store.execute(sql)
        self._store.execute(
            f"""
            INSERT INTO {MART_ELECTRICITY_PRICE_CURRENT_TABLE}
            SELECT *
            FROM {MART_CONTRACT_PRICE_CURRENT_TABLE}
            WHERE contract_type = 'electricity'
            ORDER BY contract_name, price_component, valid_from
            """
        )
        return self._store.fetchall(
            f"SELECT COUNT(*) FROM {MART_CONTRACT_PRICE_CURRENT_TABLE}"
        )[0][0]

    def get_contract_price_current(
        self,
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
        return self._store.fetchall_dicts(
            f"SELECT * FROM {MART_CONTRACT_PRICE_CURRENT_TABLE}"
            f" {where_sql} ORDER BY contract_type, contract_name, price_component, valid_from",
            params,
        )

    def get_electricity_price_current(self) -> list[dict[str, Any]]:
        return self._store.fetchall_dicts(
            f"SELECT * FROM {MART_ELECTRICITY_PRICE_CURRENT_TABLE}"
            " ORDER BY contract_name, price_component, valid_from"
        )

    # -- Utility usage / bills domain ----------------------------------------

    def load_utility_usage(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        if not rows:
            return 0

        eff = effective_date or date.today()

        with self._store.atomic():
            meters = extract_meters_from_usage(rows)
            meters_upserted = self._store.upsert_dimension_rows(
                DIM_METER,
                meters,
                effective_date=eff,
                source_system=source_system,
                source_run_id=run_id,
            )

            fact_rows = []
            for row in rows:
                usage_quantity = row["usage_quantity"]
                if isinstance(usage_quantity, str):
                    usage_quantity = Decimal(usage_quantity)
                elif isinstance(usage_quantity, float):
                    usage_quantity = Decimal(str(usage_quantity))

                usage_start = _coerce_date(row["usage_start"])
                usage_end = _coerce_date(row["usage_end"])
                usage_unit = normalize_unit(str(row["usage_unit"])).value

                fact_rows.append(
                    {
                        "usage_id": utility_usage_id(
                            row["meter_id"],
                            usage_start,
                            usage_end,
                            usage_quantity,
                        ),
                        "meter_id": row["meter_id"],
                        "meter_name": row["meter_name"],
                        "utility_type": row["utility_type"],
                        "usage_start": usage_start,
                        "usage_end": usage_end,
                        "usage_quantity": usage_quantity,
                        "usage_unit": usage_unit,
                        "reading_source": row.get("reading_source"),
                        "run_id": run_id,
                    }
                )

            inserted = self._store.insert_rows(FACT_UTILITY_USAGE_TABLE, fact_rows)

        self._record_lineage(
            run_id=run_id,
            source_system=source_system,
            records=[
                ("dim_meter", "dimension", meters_upserted),
                ("fact_utility_usage", "fact", inserted),
            ],
        )
        return inserted

    def load_bills(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        if not rows:
            return 0

        eff = effective_date or date.today()

        with self._store.atomic():
            meters = extract_meters_from_bills(rows)
            meters_upserted = self._store.upsert_dimension_rows(
                DIM_METER,
                meters,
                effective_date=eff,
                source_system=source_system,
                source_run_id=run_id,
            )

            fact_rows = []
            for row in rows:
                billed_amount = row["billed_amount"]
                if isinstance(billed_amount, str):
                    billed_amount = Decimal(billed_amount)
                elif isinstance(billed_amount, float):
                    billed_amount = Decimal(str(billed_amount))

                billed_quantity = row.get("billed_quantity")
                if isinstance(billed_quantity, str) and billed_quantity:
                    billed_quantity = Decimal(billed_quantity)
                elif isinstance(billed_quantity, float):
                    billed_quantity = Decimal(str(billed_quantity))
                elif billed_quantity in {"", None}:
                    billed_quantity = None

                usage_unit = row.get("usage_unit")
                normalized_usage_unit = (
                    normalize_unit(str(usage_unit)).value if usage_unit else None
                )

                fact_rows.append(
                    {
                        "bill_id": utility_bill_id(
                            row["meter_id"],
                            _coerce_date(row["billing_period_start"]),
                            _coerce_date(row["billing_period_end"]),
                            str(row.get("provider", "")),
                            billed_amount,
                        ),
                        "meter_id": row["meter_id"],
                        "meter_name": row["meter_name"],
                        "provider": row.get("provider", ""),
                        "utility_type": row["utility_type"],
                        "billing_period_start": _coerce_date(
                            row["billing_period_start"]
                        ),
                        "billing_period_end": _coerce_date(row["billing_period_end"]),
                        "billed_amount": billed_amount,
                        "currency": normalize_currency_code(str(row["currency"])),
                        "billed_quantity": billed_quantity,
                        "usage_unit": normalized_usage_unit,
                        "invoice_date": (
                            _coerce_date(row["invoice_date"])
                            if row.get("invoice_date")
                            else None
                        ),
                        "run_id": run_id,
                    }
                )

            inserted = self._store.insert_rows(FACT_BILL_TABLE, fact_rows)

        self._record_lineage(
            run_id=run_id,
            source_system=source_system,
            records=[
                ("dim_meter", "dimension", meters_upserted),
                ("fact_bill", "fact", inserted),
            ],
        )
        return inserted

    def refresh_utility_cost_summary(self) -> int:
        self._store.execute(f"DELETE FROM {MART_UTILITY_COST_SUMMARY_TABLE}")

        self._store.execute(
            f"""
            INSERT INTO {MART_UTILITY_COST_SUMMARY_TABLE} (
                period_start, period_end, period_day, period_month, meter_id, meter_name,
                utility_type, usage_quantity, usage_unit, billed_amount, currency,
                unit_cost, bill_count, usage_record_count, coverage_status
            )
            SELECT
                b.billing_period_start AS period_start,
                b.billing_period_end AS period_end,
                b.billing_period_start AS period_day,
                strftime(b.billing_period_start, '%Y-%m') AS period_month,
                b.meter_id,
                b.meter_name,
                b.utility_type,
                COALESCE(SUM(u.usage_quantity), 0) AS usage_quantity,
                COALESCE(any_value(u.usage_unit), any_value(b.usage_unit)) AS usage_unit,
                SUM(b.billed_amount) AS billed_amount,
                b.currency,
                CASE
                    WHEN COALESCE(SUM(u.usage_quantity), 0) > 0
                    THEN ROUND(SUM(b.billed_amount) / SUM(u.usage_quantity), 4)
                    ELSE NULL
                END AS unit_cost,
                COUNT(DISTINCT b.bill_id) AS bill_count,
                COUNT(DISTINCT u.usage_id) AS usage_record_count,
                CASE
                    WHEN COUNT(DISTINCT u.usage_id) > 0 THEN 'matched'
                    ELSE 'bill_only'
                END AS coverage_status
            FROM {FACT_BILL_TABLE} b
            LEFT JOIN {FACT_UTILITY_USAGE_TABLE} u
                ON u.meter_id = b.meter_id
                AND u.utility_type = b.utility_type
                AND u.usage_start >= b.billing_period_start
                AND u.usage_end <= b.billing_period_end
            GROUP BY
                b.billing_period_start,
                b.billing_period_end,
                b.meter_id,
                b.meter_name,
                b.utility_type,
                b.currency
            ORDER BY b.billing_period_start, b.meter_id
            """
        )

        self._store.execute(
            f"""
            INSERT INTO {MART_UTILITY_COST_SUMMARY_TABLE} (
                period_start, period_end, period_day, period_month, meter_id, meter_name,
                utility_type, usage_quantity, usage_unit, billed_amount, currency,
                unit_cost, bill_count, usage_record_count, coverage_status
            )
            SELECT
                u.usage_start AS period_start,
                u.usage_end AS period_end,
                u.usage_start AS period_day,
                strftime(u.usage_start, '%Y-%m') AS period_month,
                u.meter_id,
                u.meter_name,
                u.utility_type,
                SUM(u.usage_quantity) AS usage_quantity,
                any_value(u.usage_unit) AS usage_unit,
                CAST(0 AS DECIMAL(18,4)) AS billed_amount,
                NULL AS currency,
                NULL AS unit_cost,
                0 AS bill_count,
                COUNT(*) AS usage_record_count,
                'usage_only' AS coverage_status
            FROM {FACT_UTILITY_USAGE_TABLE} u
            WHERE NOT EXISTS (
                SELECT 1
                FROM {FACT_BILL_TABLE} b
                WHERE b.meter_id = u.meter_id
                    AND b.utility_type = u.utility_type
                    AND u.usage_start >= b.billing_period_start
                    AND u.usage_end <= b.billing_period_end
            )
            GROUP BY
                u.usage_start,
                u.usage_end,
                u.meter_id,
                u.meter_name,
                u.utility_type
            ORDER BY u.usage_start, u.meter_id
            """
        )

        return self._store.fetchall(
            f"SELECT COUNT(*) FROM {MART_UTILITY_COST_SUMMARY_TABLE}"
        )[0][0]

    def get_utility_cost_summary(
        self,
        *,
        utility_type: str | None = None,
        meter_id: str | None = None,
        from_period: date | str | None = None,
        to_period: date | str | None = None,
        granularity: str = "month",
    ) -> list[dict[str, Any]]:
        if granularity not in {"day", "month"}:
            raise ValueError(f"Unsupported granularity: {granularity!r}")

        clauses: list[str] = []
        params: list[Any] = []
        if utility_type is not None:
            clauses.append("utility_type = ?")
            params.append(utility_type)
        if meter_id is not None:
            clauses.append("meter_id = ?")
            params.append(meter_id)
        if from_period is not None:
            clauses.append("period_start >= ?")
            params.append(_coerce_date(from_period))
        if to_period is not None:
            clauses.append("period_end <= ?")
            params.append(_coerce_date(to_period))
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        if granularity == "day":
            return self._store.fetchall_dicts(
                f"""
                SELECT
                    period_day AS period,
                    period_start,
                    period_end,
                    meter_id,
                    meter_name,
                    utility_type,
                    usage_quantity,
                    usage_unit,
                    billed_amount,
                    currency,
                    unit_cost,
                    bill_count,
                    usage_record_count,
                    coverage_status
                FROM {MART_UTILITY_COST_SUMMARY_TABLE}
                {where_sql}
                ORDER BY period_day, meter_id
                """,
                params,
            )

        return self._store.fetchall_dicts(
            f"""
            SELECT
                period_month AS period,
                MIN(period_start) AS period_start,
                MAX(period_end) AS period_end,
                meter_id,
                any_value(meter_name) AS meter_name,
                utility_type,
                SUM(usage_quantity) AS usage_quantity,
                any_value(usage_unit) AS usage_unit,
                SUM(billed_amount) AS billed_amount,
                any_value(currency) AS currency,
                CASE
                    WHEN SUM(usage_quantity) > 0
                    THEN ROUND(SUM(billed_amount) / SUM(usage_quantity), 4)
                    ELSE NULL
                END AS unit_cost,
                SUM(bill_count) AS bill_count,
                SUM(usage_record_count) AS usage_record_count,
                CASE
                    WHEN SUM(bill_count) > 0 AND SUM(usage_record_count) > 0 THEN 'matched'
                    WHEN SUM(bill_count) > 0 THEN 'bill_only'
                    ELSE 'usage_only'
                END AS coverage_status
            FROM {MART_UTILITY_COST_SUMMARY_TABLE}
            {where_sql}
            GROUP BY period_month, meter_id, utility_type
            ORDER BY period_month, meter_id
            """,
            params,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _transaction_id(
    booked_at: date, account_id: str, counterparty_name: str, amount: Decimal
) -> str:
    """Create a deterministic transaction ID based on content."""
    raw = f"{booked_at.isoformat()}|{account_id}|{counterparty_name}|{amount}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _coerce_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
