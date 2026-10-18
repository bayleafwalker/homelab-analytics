"""Dated snapshots of current-only reporting publications.

Most reporting marts are rebuilt in place on every refresh. The month-keyed
ones (monthly cashflow, spend by category, utility trend) carry their own
history, but the "current state" publications — household overview,
attention items, recent changes, affordability ratios, the recurring cost
baseline and the subscription summary — only ever hold today's answer.

To give the reporting layer an honest as-of read, every publication refresh
captures the rows of those publications into ``reporting_publication_snapshot``
keyed by ``(publication_key, reference_month)``. ``reference_month`` is the
month the household's data ran through when the snapshot was taken (the latest
``booking_month`` in ``mart_monthly_cashflow``), so an as-of read for a month
returns the publication as it stood when that month was the newest published
month. A later refresh within the same reference month supersedes the earlier
snapshot; ``captured_at`` dates it.

Retention keeps the newest ``retention_months`` reference months per
publication (default 24). Months before the first capture have no snapshot,
and readers must say so rather than fall back to current rows.

The snapshot table lives wherever the reporting layer lives: the DuckDB
warehouse always holds a copy (written at refresh time, next to the marts),
and a Postgres reporting store, when configured, holds the copy that the
PUBLISHED access mode reads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, TypeVar, cast

from packages.domains.finance.pipelines.subscription_models import (
    MART_SUBSCRIPTION_SUMMARY_TABLE,
)
from packages.domains.finance.pipelines.transaction_models import (
    MART_MONTHLY_CASHFLOW_TABLE,
)
from packages.domains.overview.pipelines.overview_models import (
    MART_AFFORDABILITY_RATIOS_TABLE,
    MART_HOUSEHOLD_OVERVIEW_TABLE,
    MART_OPEN_ATTENTION_ITEMS_TABLE,
    MART_RECENT_SIGNIFICANT_CHANGES_TABLE,
    MART_RECURRING_COST_BASELINE_TABLE,
)

SNAPSHOT_TABLE = "reporting_publication_snapshot"
SNAPSHOT_COLUMNS: list[tuple[str, str]] = [
    ("publication_key", "VARCHAR NOT NULL"),
    ("reference_month", "VARCHAR NOT NULL"),
    ("captured_at", "VARCHAR NOT NULL"),
    ("run_id", "VARCHAR"),
    ("row_count", "INTEGER NOT NULL"),
    ("rows_json", "VARCHAR NOT NULL"),
]

# Publications with no history of their own. Month-keyed marts are not
# snapshotted: their rows already carry the month.
SNAPSHOT_PUBLICATIONS: frozenset[str] = frozenset(
    {
        MART_HOUSEHOLD_OVERVIEW_TABLE,
        MART_OPEN_ATTENTION_ITEMS_TABLE,
        MART_RECENT_SIGNIFICANT_CHANGES_TABLE,
        MART_AFFORDABILITY_RATIOS_TABLE,
        MART_RECURRING_COST_BASELINE_TABLE,
        MART_SUBSCRIPTION_SUMMARY_TABLE,
    }
)

DEFAULT_SNAPSHOT_RETENTION_MONTHS = 24


def is_reference_month(value: object) -> bool:
    """True for a ``YYYY-MM`` string with a real month number."""
    if not isinstance(value, str) or len(value) != 7 or value[4] != "-":
        return False
    year, month = value[:4], value[5:]
    return year.isdigit() and month.isdigit() and 1 <= int(month) <= 12


def _json_default(value: Any) -> Any:
    # Mirrors apps.api.support.to_jsonable so an as-of read serialises the
    # same way the live read did when the snapshot was taken.
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Cannot snapshot value of type {type(value).__name__}")


@dataclass(frozen=True)
class PublicationSnapshot:
    publication_key: str
    reference_month: str
    captured_at: str
    run_id: str | None
    rows: list[dict[str, Any]]

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def metadata(self) -> dict[str, Any]:
        return {
            "publication_key": self.publication_key,
            "reference_month": self.reference_month,
            "captured_at": self.captured_at,
            "run_id": self.run_id,
            "row_count": self.row_count,
        }


class PublicationSnapshotStore:
    """Snapshot table access over a DuckDB or Postgres reporting store.

    ``placeholder`` is the driver's parameter marker (``?`` for DuckDB,
    ``%s`` for psycopg). ``run_statements`` executes a list of
    ``(sql, params)`` in one transaction.
    """

    def __init__(
        self,
        store: Any,
        *,
        placeholder: str,
        run_statements: Any,
        table_exists: Any | None = None,
    ) -> None:
        self._store = store
        self._p = placeholder
        self._run_statements = run_statements
        self._table_exists = table_exists

    @classmethod
    def for_duckdb(cls, store: Any) -> PublicationSnapshotStore:
        def run_statements(statements: list[tuple[str, list[Any]]]) -> None:
            with store.atomic():
                for sql, params in statements:
                    store.execute(sql, params)

        def table_exists(table_name: str) -> bool:
            rows = store.fetchall(
                "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
                [table_name],
            )
            return bool(rows)

        return cls(
            store,
            placeholder="?",
            run_statements=run_statements,
            table_exists=table_exists,
        )

    @classmethod
    def for_postgres(cls, store: Any) -> PublicationSnapshotStore:
        return cls(
            store,
            placeholder="%s",
            run_statements=lambda statements: store.execute_statements(statements),
            table_exists=store.table_exists,
        )

    def exists(self) -> bool:
        if self._table_exists is None:
            return True
        return bool(self._table_exists(SNAPSHOT_TABLE))

    def ensure(self) -> None:
        self._store.ensure_table(SNAPSHOT_TABLE, SNAPSHOT_COLUMNS)

    def write(
        self,
        snapshot: PublicationSnapshot,
        *,
        retention_months: int,
    ) -> None:
        """Replace the snapshot for its reference month, then apply retention."""
        self.ensure()
        p = self._p
        payload = json.dumps(snapshot.rows, default=_json_default, sort_keys=True)
        statements: list[tuple[str, list[Any]]] = [
            (
                f"DELETE FROM {SNAPSHOT_TABLE} "
                f"WHERE publication_key = {p} AND reference_month = {p}",
                [snapshot.publication_key, snapshot.reference_month],
            ),
            (
                f"INSERT INTO {SNAPSHOT_TABLE} "
                "(publication_key, reference_month, captured_at, run_id, row_count, rows_json) "
                f"VALUES ({p}, {p}, {p}, {p}, {p}, {p})",
                [
                    snapshot.publication_key,
                    snapshot.reference_month,
                    snapshot.captured_at,
                    snapshot.run_id,
                    snapshot.row_count,
                    payload,
                ],
            ),
        ]
        if retention_months > 0:
            # Keep the newest N reference months for this publication.
            statements.append(
                (
                    f"DELETE FROM {SNAPSHOT_TABLE} "
                    f"WHERE publication_key = {p} AND reference_month NOT IN ("
                    f"SELECT reference_month FROM {SNAPSHOT_TABLE} "
                    f"WHERE publication_key = {p} "
                    f"ORDER BY reference_month DESC LIMIT {int(retention_months)})",
                    [snapshot.publication_key, snapshot.publication_key],
                )
            )
        self._run_statements(statements)

    def read(
        self,
        publication_key: str,
        reference_month: str,
    ) -> PublicationSnapshot | None:
        if not self.exists():
            return None
        p = self._p
        rows = self._store.fetchall_dicts(
            f"SELECT publication_key, reference_month, captured_at, run_id, rows_json "
            f"FROM {SNAPSHOT_TABLE} "
            f"WHERE publication_key = {p} AND reference_month = {p} "
            "ORDER BY captured_at DESC LIMIT 1",
            [publication_key, reference_month],
        )
        if not rows:
            return None
        row = rows[0]
        decoded = json.loads(str(row["rows_json"]))
        return PublicationSnapshot(
            publication_key=str(row["publication_key"]),
            reference_month=str(row["reference_month"]),
            captured_at=str(row["captured_at"]),
            run_id=str(row["run_id"]) if row.get("run_id") is not None else None,
            rows=[dict(item) for item in decoded] if isinstance(decoded, list) else [],
        )

    def months(self, publication_key: str) -> list[str]:
        if not self.exists():
            return []
        rows = self._store.fetchall_dicts(
            f"SELECT DISTINCT reference_month FROM {SNAPSHOT_TABLE} "
            f"WHERE publication_key = {self._p} ORDER BY reference_month",
            [publication_key],
        )
        return [str(row["reference_month"]) for row in rows]


# ---------------------------------------------------------------------------
# Warehouse copy
#
# The snapshot table sits next to the marts in DuckDB, but it is reporting
# state, not transformation behaviour, so it is reached through these
# store-level helpers rather than through TransformationService methods. Each
# helper runs as one unit on one warehouse handle: on the API's session facade
# (packages/pipelines/warehouse_session.py) that is a single lease of the
# declared mode, so the delete + insert + prune stays in one transaction and
# reads take a read-only handle.
# ---------------------------------------------------------------------------

T = TypeVar("T")


def run_on_warehouse(
    transformation_service: Any,
    label: str,
    fn: Callable[[Any], T],
    *,
    write: bool,
) -> T:
    """Run ``fn(store)`` on one warehouse handle of the requested mode."""
    sessions = getattr(transformation_service, "warehouse_sessions", None)
    if sessions is not None:
        return cast(
            T,
            sessions.call(label, lambda service: fn(service.store), write=write),
        )
    return fn(transformation_service.store)


def record_warehouse_snapshot(
    transformation_service: Any,
    snapshot: PublicationSnapshot,
    *,
    retention_months: int,
) -> None:
    run_on_warehouse(
        transformation_service,
        "reporting_snapshots.record",
        lambda store: PublicationSnapshotStore.for_duckdb(store).write(
            snapshot, retention_months=retention_months
        ),
        write=True,
    )


def read_warehouse_snapshot(
    transformation_service: Any,
    publication_key: str,
    reference_month: str,
) -> PublicationSnapshot | None:
    return run_on_warehouse(
        transformation_service,
        "reporting_snapshots.read",
        lambda store: PublicationSnapshotStore.for_duckdb(store).read(
            publication_key, reference_month
        ),
        write=False,
    )


def warehouse_snapshot_months(transformation_service: Any, publication_key: str) -> list[str]:
    return run_on_warehouse(
        transformation_service,
        "reporting_snapshots.months",
        lambda store: PublicationSnapshotStore.for_duckdb(store).months(publication_key),
        write=False,
    )


def warehouse_reference_month(transformation_service: Any) -> str | None:
    """The newest published booking month: what a snapshot is keyed by."""

    def _read(store: Any) -> str | None:
        exists = store.fetchall(
            "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
            [MART_MONTHLY_CASHFLOW_TABLE],
        )
        if not exists:
            return None
        result = store.fetchall(f"SELECT MAX(booking_month) FROM {MART_MONTHLY_CASHFLOW_TABLE}")
        value = result[0][0] if result else None
        month = str(value) if value is not None else None
        return month if is_reference_month(month) else None

    return run_on_warehouse(
        transformation_service, "reporting_snapshots.reference_month", _read, write=False
    )
