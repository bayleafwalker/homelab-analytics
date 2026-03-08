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

from packages.pipelines.normalization import (
    normalize_currency_code,
    normalize_timestamp_utc,
)
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
from packages.storage.duckdb_store import DuckDBStore


class TransformationService:
    """Loads validated landing data into the transformation and reporting layers."""

    def __init__(self, store: DuckDBStore) -> None:
        self._store = store
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

    # -- public API ----------------------------------------------------------

    def load_transactions(
        self,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
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
            accounts_upserted = self._store.upsert_dimension_rows(DIM_ACCOUNT, accounts, effective_date=eff)

            counterparties = extract_counterparties(rows)
            counterparties_upserted = self._store.upsert_dimension_rows(DIM_COUNTERPARTY, counterparties, effective_date=eff)

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

    def get_current_dimension_rows(self, dimension_name: str) -> list[dict[str, Any]]:
        if dimension_name == "dim_account":
            return self.get_current_accounts()
        if dimension_name == "dim_counterparty":
            return self.get_current_counterparties()
        if dimension_name == "dim_contract":
            return self.get_current_contracts()
        if dimension_name == "dim_category":
            return self.get_current_categories()
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
            self._store.upsert_dimension_rows(DIM_CONTRACT, contracts, effective_date=eff)

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
    ) -> int:
        if not rows:
            return 0

        eff = effective_date or date.today()

        with self._store.atomic():
            contracts = extract_contract_rows(rows)
            self._store.upsert_dimension_rows(DIM_CONTRACT, contracts, effective_date=eff)

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _transaction_id(
    booked_at: date, account_id: str, counterparty_name: str, amount: Decimal
) -> str:
    """Create a deterministic transaction ID based on content."""
    raw = f"{booked_at.isoformat()}|{account_id}|{counterparty_name}|{amount}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
