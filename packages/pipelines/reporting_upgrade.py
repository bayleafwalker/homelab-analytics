"""Supported upgrade of an installed reporting store to currency-separated totals.

Entrypoint: ``python -m apps.worker.main upgrade-reporting [--check]``.

Monetary marts used to blend currencies into one row per month. Installed
stores keep that shape: ``DuckDBStore.ensure_table`` only creates missing
tables and the PostgreSQL publisher never evolves an existing table, so
changing table definitions alone does not upgrade them. This module is the one
supported path. It is deliberately explicit:

1. **Preflight (read-only).** Every affected relation in the selected DuckDB
   file and PostgreSQL schema must be in a *known* state: absent, the exact
   legacy column list, or the exact current column list. Unknown drift, a
   table the connected role does not own, or PostgreSQL dependants (views,
   rules, triggers, row security policies, foreign keys) that a change of
   grain would silently alter are refused before anything is modified.
2. **DuckDB.** Add the new columns in one transaction, then rebuild every
   currency-affected mart from the immutable facts.
3. **PostgreSQL.** Add the new columns in one transaction (ALTER keeps owner,
   privileges and dependants), then republish the rebuilt marts that exist in
   the selected schema.
4. **Verify.** Fact rows and historical snapshot rows must be byte-identical to
   what preflight saw; published row counts must match the rebuilt marts.

``complete`` is reported only after all of that succeeded. A failure leaves an
``incomplete`` receipt; the command is idempotent, so re-running it is the
recovery (it re-evaluates the known states, rebuilds from facts and
republishes). Until then ordinary reads refuse legacy-shaped relations (see
``packages/pipelines/reporting_currency.py``) rather than serve blended data.

Stores are selected only through ``AppSettings`` environment variables; no
control plane, run-metadata store or extension registry is opened.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

from packages.domains.finance.pipelines.transaction_models import (
    MART_ACCOUNT_BALANCE_TREND_COLUMNS,
    MART_ACCOUNT_BALANCE_TREND_TABLE,
    MART_CASHFLOW_BY_COUNTERPARTY_COLUMNS,
    MART_CASHFLOW_BY_COUNTERPARTY_TABLE,
    MART_MONTHLY_CASHFLOW_COLUMNS,
    MART_MONTHLY_CASHFLOW_TABLE,
    MART_SPEND_BY_CATEGORY_MONTHLY_COLUMNS,
    MART_SPEND_BY_CATEGORY_MONTHLY_TABLE,
    MART_SPEND_BY_WEEKDAY_HOUR_COLUMNS,
    MART_SPEND_BY_WEEKDAY_HOUR_TABLE,
    MART_TRANSACTION_ANOMALIES_CURRENT_COLUMNS,
    MART_TRANSACTION_ANOMALIES_CURRENT_TABLE,
)
from packages.domains.overview.pipelines.overview_models import (
    MART_AFFORDABILITY_RATIOS_COLUMNS,
    MART_AFFORDABILITY_RATIOS_TABLE,
    MART_COST_TREND_12M_COLUMNS,
    MART_COST_TREND_12M_TABLE,
    MART_CURRENT_OPERATING_BASELINE_COLUMNS,
    MART_CURRENT_OPERATING_BASELINE_TABLE,
    MART_HOUSEHOLD_COST_MODEL_COLUMNS,
    MART_HOUSEHOLD_COST_MODEL_TABLE,
    MART_HOUSEHOLD_OVERVIEW_COLUMNS,
    MART_HOUSEHOLD_OVERVIEW_TABLE,
    MART_RECENT_SIGNIFICANT_CHANGES_COLUMNS,
    MART_RECENT_SIGNIFICANT_CHANGES_TABLE,
)
from packages.domains.utilities.pipelines.utility_models import (
    MART_USAGE_VS_PRICE_SUMMARY_COLUMNS,
    MART_USAGE_VS_PRICE_SUMMARY_TABLE,
    MART_UTILITY_COST_SUMMARY_COLUMNS,
    MART_UTILITY_COST_SUMMARY_TABLE,
    MART_UTILITY_COST_TREND_MONTHLY_COLUMNS,
    MART_UTILITY_COST_TREND_MONTHLY_TABLE,
)
from packages.pipelines.reporting_currency import CURRENCY_COLUMN_RELATIONS, UPGRADE_COMMAND
from packages.pipelines.reporting_service import ReportingAccessMode, ReportingService
from packages.pipelines.reporting_snapshots import SNAPSHOT_COLUMNS, SNAPSHOT_TABLE
from packages.pipelines.transformation_service import TransformationService
from packages.shared.settings import AppSettings
from packages.storage.duckdb_store import DuckDBStore, WarehouseBusyError
from packages.storage.postgres_reporting import PostgresReportingStore
from packages.storage.postgres_support import connect_with_retry, validate_identifier

MIGRATION_VERSION = "0020_currency_separated_marts"

EXIT_COMPLETE = 0
EXIT_FAILED = 1
EXIT_REFUSED = 2

# Rebuilt from facts, in dependency order. Relations that were never
# published to PostgreSQL stay unpublished (unavailable), not invented.
REBUILD_KEYS: tuple[str, ...] = (
    "mart_monthly_cashflow",
    "mart_monthly_cashflow_by_counterparty",
    "mart_spend_by_category_monthly",
    "mart_account_balance_trend",
    "mart_spend_by_weekday_hour",
    "mart_transaction_anomalies_current",
    "mart_utility_cost_summary",
    "mart_utility_cost_trend_monthly",
    "mart_usage_vs_price_summary",
    "mart_household_cost_model",
    "mart_household_overview",
    "mart_cost_trend_12m",
    "mart_affordability_ratios",
    "mart_current_operating_baseline",
    "mart_recent_significant_changes",
)

# Immutable evidence: never altered; hashed before and after.
FACT_TABLES: tuple[tuple[str, str], ...] = (
    ("fact_transaction", "transaction_id"),
    ("fact_bill", "bill_id"),
    ("fact_utility_usage", "usage_id"),
)

_SNAPSHOT_EVIDENCE_COLUMNS = (
    "publication_key, reference_month, captured_at, run_id, row_count, rows_json"
)

_PG_TYPES = {
    "VARCHAR": "text",
    "TEXT": "text",
    "DECIMAL": "numeric",
    "NUMERIC": "numeric",
    "INTEGER": "integer",
    "DATE": "date",
}


@dataclass(frozen=True)
class _Relation:
    """A relation whose legacy shape lacks its last (added) column."""

    name: str
    columns: list[tuple[str, str]]
    # Runtime columns the storage self-heals (not part of the currency schema).
    # Keys are column names, values their documented declared type. They may be
    # absent; when present they must keep that type or the relation is unknown
    # drift (never silently erased).
    optional: dict[str, str] = field(default_factory=dict)

    @property
    def added(self) -> str:
        return self.columns[-1][0]


_RELATIONS: tuple[_Relation, ...] = (
    _Relation(MART_MONTHLY_CASHFLOW_TABLE, MART_MONTHLY_CASHFLOW_COLUMNS),
    _Relation(MART_CASHFLOW_BY_COUNTERPARTY_TABLE, MART_CASHFLOW_BY_COUNTERPARTY_COLUMNS),
    _Relation(MART_SPEND_BY_CATEGORY_MONTHLY_TABLE, MART_SPEND_BY_CATEGORY_MONTHLY_COLUMNS),
    _Relation(MART_ACCOUNT_BALANCE_TREND_TABLE, MART_ACCOUNT_BALANCE_TREND_COLUMNS),
    _Relation(MART_SPEND_BY_WEEKDAY_HOUR_TABLE, MART_SPEND_BY_WEEKDAY_HOUR_COLUMNS),
    _Relation(
        MART_TRANSACTION_ANOMALIES_CURRENT_TABLE, MART_TRANSACTION_ANOMALIES_CURRENT_COLUMNS
    ),
    _Relation(
        MART_RECENT_SIGNIFICANT_CHANGES_TABLE, MART_RECENT_SIGNIFICANT_CHANGES_COLUMNS
    ),
    _Relation(MART_USAGE_VS_PRICE_SUMMARY_TABLE, MART_USAGE_VS_PRICE_SUMMARY_COLUMNS),
    _Relation(MART_UTILITY_COST_SUMMARY_TABLE, MART_UTILITY_COST_SUMMARY_COLUMNS),
    _Relation(SNAPSHOT_TABLE, SNAPSHOT_COLUMNS),
)
assert {r.name for r in _RELATIONS if r.added == "currency"} == set(CURRENCY_COLUMN_RELATIONS)

# Relations the upgrade rebuilds (and, for PostgreSQL, republishes) without an
# in-place ALTER: their columns are the exact current list and there is no
# supported legacy shape. Unknown drift here would be silently erased by the
# rebuild/republish, so it is refused up front just like an altered relation.
_REBUILD_ONLY_RELATIONS: tuple[_Relation, ...] = (
    _Relation(MART_UTILITY_COST_TREND_MONTHLY_TABLE, MART_UTILITY_COST_TREND_MONTHLY_COLUMNS),
    _Relation(MART_HOUSEHOLD_COST_MODEL_TABLE, MART_HOUSEHOLD_COST_MODEL_COLUMNS),
    _Relation(MART_HOUSEHOLD_OVERVIEW_TABLE, MART_HOUSEHOLD_OVERVIEW_COLUMNS),
    _Relation(MART_COST_TREND_12M_TABLE, MART_COST_TREND_12M_COLUMNS),
    # ``state`` is self-healed by ensure_overview_storage at runtime, so it may
    # be absent (pre-heal) or present (post-heal) with its documented type.
    _Relation(
        MART_AFFORDABILITY_RATIOS_TABLE,
        [column for column in MART_AFFORDABILITY_RATIOS_COLUMNS if column[0] != "state"],
        optional={"state": "VARCHAR"},
    ),
    _Relation(MART_CURRENT_OPERATING_BASELINE_TABLE, MART_CURRENT_OPERATING_BASELINE_COLUMNS),
)
# Every relation the upgrade rebuilds/republishes is recognised up front.
assert set(REBUILD_KEYS) == ({r.name for r in _RELATIONS} - {SNAPSHOT_TABLE}) | {
    r.name for r in _REBUILD_ONLY_RELATIONS
}
assert {r.name for r in _REBUILD_ONLY_RELATIONS}.isdisjoint({r.name for r in _RELATIONS})


@dataclass
class _Report:
    status: str = "pending"
    mode: str = "upgrade"
    phase: str = "preflight"
    refusals: list[str] = field(default_factory=list)
    duckdb: dict[str, Any] = field(default_factory=dict)
    postgres: dict[str, Any] = field(default_factory=dict)
    facts: dict[str, Any] = field(default_factory=dict)
    snapshots: dict[str, Any] = field(default_factory=dict)
    rebuilt: list[str] = field(default_factory=list)
    published: list[str] = field(default_factory=list)
    error: str | None = None
    next_step: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "phase": self.phase,
            "refusals": self.refusals,
            "duckdb": self.duckdb,
            "postgres": self.postgres,
            "facts": self.facts,
            "snapshots": self.snapshots,
            "rebuilt_marts": self.rebuilt,
            "published_relations": self.published,
            "error": self.error,
            "next_step": self.next_step,
        }


class _Refused(Exception):
    """Preflight found a state the upgrade will not touch."""


# ---------------------------------------------------------------------------
# Shape recognition
# ---------------------------------------------------------------------------


def _declared_base(declared: str) -> str:
    text = declared.upper().replace(" NOT NULL", "").replace(" PRIMARY KEY", "").strip()
    return text


def _pg_type(declared: str) -> str:
    declared = _declared_base(declared)
    base = declared.split("(")[0].strip()
    try:
        mapped = _PG_TYPES[base]
    except KeyError as exc:  # pragma: no cover - guarded by the registry assert
        raise ValueError(f"No PostgreSQL type mapping for {declared!r}") from exc
    if mapped == "numeric" and "(" in declared:
        # Preserve the numeric precision/scale so an incompatible typmod (e.g.
        # NUMERIC(18,0) where the publication declares 18,4) is refused rather
        # than silently truncating cents.
        return f"numeric{declared[declared.index('('):]}"
    return mapped


def classify_shape(
    observed: list[tuple[str, str]],
    relation_columns: list[tuple[str, str]],
    *,
    postgres: bool,
) -> str:
    """``absent`` | ``legacy`` | ``current`` | ``unknown`` for an observed table."""
    if not observed:
        return "absent"

    def _normalise(columns: list[tuple[str, str]]) -> list[tuple[str, str]]:
        return [
            (name.lower(), _pg_type(dtype) if postgres else _declared_base(dtype).lower())
            for name, dtype in columns
        ]

    seen = [(name.lower(), dtype.lower()) for name, dtype in observed]
    if seen == _normalise(relation_columns[:-1]):
        return "legacy"
    if seen == _normalise(relation_columns):
        return "current"
    return "unknown"


def classify_rebuild_only_shape(
    observed: list[tuple[str, str]],
    relation_columns: list[tuple[str, str]],
    *,
    postgres: bool,
    optional: dict[str, str] | None = None,
) -> str:
    """``absent`` | ``current`` | ``unknown`` for a relation never altered in place.

    A rebuild-only relation has no supported legacy shape: anything that is not
    the exact current column list (extra columns, missing columns, type drift)
    is ``unknown`` and must be refused before the rebuild erases it. Columns in
    ``optional`` are self-healed at runtime, so they may be absent; when present
    they must keep their documented type or the relation is refused.
    """
    if not observed:
        return "absent"

    optional = optional or {}
    optional_names = {name.lower() for name in optional}

    def _norm_dtype(dtype: str) -> str:
        return _pg_type(dtype) if postgres else _declared_base(dtype).lower()

    def _normalise(columns: list[tuple[str, str]]) -> list[tuple[str, str]]:
        return [(name.lower(), _norm_dtype(dtype)) for name, dtype in columns]

    seen = [
        (name.lower(), dtype.lower())
        for name, dtype in observed
        if name.lower() not in optional_names
    ]
    if seen != _normalise(relation_columns):
        return "unknown"
    for name, dtype in observed:
        key = name.lower()
        if key in optional_names and dtype.lower() != _norm_dtype(optional[key]):
            return "unknown"
    return "current"


# ---------------------------------------------------------------------------
# DuckDB side
# ---------------------------------------------------------------------------


def _duck_table_exists(store: DuckDBStore, table: str) -> bool:
    return bool(
        store.fetchall(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_name = ?",
            [table],
        )
    )


def _duck_observed(store: DuckDBStore, table: str) -> list[tuple[str, str]]:
    if not _duck_table_exists(store, table):
        return []
    return [(str(row[1]), str(row[2])) for row in store.fetchall(f"PRAGMA table_info('{table}')")]


def _duck_states(store: DuckDBStore) -> dict[str, str]:
    states = {
        relation.name: classify_shape(
            _duck_observed(store, relation.name), relation.columns, postgres=False
        )
        for relation in _RELATIONS
    }
    states.update(
        {
            relation.name: classify_rebuild_only_shape(
                _duck_observed(store, relation.name),
                relation.columns,
                postgres=False,
                optional=relation.optional,
            )
            for relation in _REBUILD_ONLY_RELATIONS
        }
    )
    return states


def _digest(rows: list[Any]) -> str:
    return hashlib.sha256(
        json.dumps(rows, default=str, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _fact_evidence(store: DuckDBStore) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for table, key in FACT_TABLES:
        if not _duck_table_exists(store, table):
            continue
        rows = [list(row) for row in store.fetchall(f"SELECT * FROM {table} ORDER BY {key}")]
        evidence[table] = {"rows": len(rows), "sha256": _digest(rows)}
    return evidence


def _duck_snapshot_evidence(store: DuckDBStore) -> dict[str, Any]:
    if not _duck_table_exists(store, SNAPSHOT_TABLE):
        return {"rows": 0, "sha256": None}
    rows = [
        list(row)
        for row in store.fetchall(
            f"SELECT {_SNAPSHOT_EVIDENCE_COLUMNS} FROM {SNAPSHOT_TABLE} "
            "ORDER BY publication_key, reference_month, captured_at"
        )
    ]
    return {"rows": len(rows), "sha256": _digest(rows)}


# ---------------------------------------------------------------------------
# PostgreSQL side
# ---------------------------------------------------------------------------


def _qualified(conn: psycopg.Connection[Any], schema: str, table: str) -> str:
    return sql.Identifier(schema, table).as_string(conn)


def _pg_schema_exists(conn: psycopg.Connection[Any], schema: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s", (schema,)
        ).fetchone()
        is not None
    )


def _pg_observed(
    conn: psycopg.Connection[Any], schema: str, table: str
) -> list[tuple[str, str]]:
    rows = conn.execute(
        "SELECT column_name, data_type, numeric_precision, numeric_scale "
        "FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
        (schema, table),
    ).fetchall()
    observed: list[tuple[str, str]] = []
    for column_name, data_type, numeric_precision, numeric_scale in rows:
        dtype = str(data_type)
        if dtype == "numeric" and numeric_precision is not None and numeric_scale is not None:
            dtype = f"numeric({int(numeric_precision)},{int(numeric_scale)})"
        observed.append((str(column_name), dtype))
    return observed


def _pg_blockers(conn: psycopg.Connection[Any], schema: str, table: str) -> list[str]:
    """Reasons an in-place ALTER of ``schema.table`` must be refused."""
    regclass = _qualified(conn, schema, table)
    blockers: list[str] = []
    head = conn.execute(
        "SELECT c.relkind, pg_has_role(current_user, c.relowner, 'MEMBER'), c.relrowsecurity "
        "FROM pg_class c WHERE c.oid = %s::regclass",
        (regclass,),
    ).fetchone()
    if head is None:
        return [f"{schema}.{table}: not found"]
    relkind, can_alter, row_security = head
    if relkind != "r":
        blockers.append(f"{schema}.{table}: not an ordinary table (relkind {relkind})")
    if not can_alter:
        blockers.append(f"{schema}.{table}: connected role does not own the table")
    if row_security:
        blockers.append(f"{schema}.{table}: row-level security is enabled")
    checks = (
        (
            "dependent view or rule",
            "SELECT DISTINCT dep.relname FROM pg_depend d "
            "JOIN pg_rewrite r ON r.oid = d.objid "
            "JOIN pg_class dep ON dep.oid = r.ev_class "
            "WHERE d.classid = 'pg_rewrite'::regclass "
            "AND d.refclassid = 'pg_class'::regclass AND d.refobjid = %s::regclass "
            "AND dep.oid <> d.refobjid",
        ),
        (
            "trigger",
            "SELECT tgname FROM pg_trigger WHERE tgrelid = %s::regclass AND NOT tgisinternal",
        ),
        (
            "foreign key referencing the table",
            "SELECT conname FROM pg_constraint WHERE confrelid = %s::regclass",
        ),
        (
            "row-level security policy",
            "SELECT polname FROM pg_policy WHERE polrelid = %s::regclass",
        ),
    )
    for label, query in checks:
        for row in conn.execute(query, (regclass,)).fetchall():
            blockers.append(f"{schema}.{table}: {label} {row[0]}")
    return blockers


def _pg_republish_blockers(
    conn: psycopg.Connection[Any], schema: str, table: str
) -> list[str]:
    """Reasons a TRUNCATE + INSERT republish of ``schema.table`` must be refused.

    A republish does not change the schema, so dependent views and grants stay
    compatible. It still mutates every row, so triggers, rules, row-level
    security, referencing foreign keys, non-ordinary relations and ownership
    are refused before any warehouse write.
    """
    regclass = _qualified(conn, schema, table)
    blockers: list[str] = []
    head = conn.execute(
        "SELECT c.relkind, pg_has_role(current_user, c.relowner, 'MEMBER'), c.relrowsecurity "
        "FROM pg_class c WHERE c.oid = %s::regclass",
        (regclass,),
    ).fetchone()
    if head is None:
        return [f"{schema}.{table}: not found"]
    relkind, owns, row_security = head
    if relkind != "r":
        blockers.append(f"{schema}.{table}: not an ordinary table (relkind {relkind})")
    if not owns:
        blockers.append(f"{schema}.{table}: connected role does not own the table")
    if row_security:
        blockers.append(f"{schema}.{table}: row-level security is enabled")
    checks = (
        (
            "trigger",
            "SELECT tgname FROM pg_trigger WHERE tgrelid = %s::regclass AND NOT tgisinternal",
        ),
        (
            "rule",
            "SELECT rulename FROM pg_rewrite WHERE ev_class = %s::regclass "
            "AND rulename <> '_RETURN'",
        ),
        (
            "foreign key referencing the table",
            "SELECT conname FROM pg_constraint WHERE confrelid = %s::regclass",
        ),
        (
            "row-level security policy",
            "SELECT polname FROM pg_policy WHERE polrelid = %s::regclass",
        ),
    )
    for label, query in checks:
        for row in conn.execute(query, (regclass,)).fetchall():
            blockers.append(f"{schema}.{table}: {label} {row[0]}")
    return blockers


def _pg_privileges(conn: psycopg.Connection[Any], schema: str, table: str) -> list[Any]:
    row = conn.execute(
        "SELECT pg_get_userbyid(c.relowner), c.relacl::text FROM pg_class c "
        "WHERE c.oid = %s::regclass",
        (_qualified(conn, schema, table),),
    ).fetchone()
    return list(row) if row is not None else []


def _pg_table_exists(conn: psycopg.Connection[Any], schema: str, table: str) -> bool:
    row = conn.execute(
        "SELECT to_regclass(%s)", (_qualified(conn, schema, table),)
    ).fetchone()
    return row is not None and row[0] is not None


def _pg_snapshot_evidence(
    conn: psycopg.Connection[Any], schema: str
) -> dict[str, Any]:
    if not _pg_table_exists(conn, schema, SNAPSHOT_TABLE):
        return {"rows": 0, "sha256": None}
    query = sql.SQL(
        "SELECT {cols} FROM {table} ORDER BY publication_key, reference_month, captured_at"
    ).format(
        cols=sql.SQL(_SNAPSHOT_EVIDENCE_COLUMNS),
        table=sql.Identifier(schema, SNAPSHOT_TABLE),
    )
    rows = [list(row) for row in conn.execute(query).fetchall()]
    return {"rows": len(rows), "sha256": _digest(rows)}


@dataclass
class _PgPlan:
    schema: str
    states: dict[str, str]
    alter: list[_Relation]
    existing_keys: list[str]


def _pg_preflight(conn: psycopg.Connection[Any], schema: str) -> _PgPlan:
    if not _pg_schema_exists(conn, schema):
        raise _Refused(
            f"PostgreSQL schema {schema!r} does not exist; set "
            "HOMELAB_ANALYTICS_REPORTING_SCHEMA to the existing reporting schema"
        )
    states: dict[str, str] = {}
    alter: list[_Relation] = []
    problems: list[str] = []
    for relation in _RELATIONS:
        state = classify_shape(
            _pg_observed(conn, schema, relation.name), relation.columns, postgres=True
        )
        states[relation.name] = state
        if state == "unknown":
            problems.append(
                f"{schema}.{relation.name}: unrecognised column set "
                "(neither the legacy nor the current shape); refusing to modify it"
            )
        elif state == "legacy":
            problems.extend(_pg_blockers(conn, schema, relation.name))
            alter.append(relation)
    for relation in _REBUILD_ONLY_RELATIONS:
        state = classify_rebuild_only_shape(
            _pg_observed(conn, schema, relation.name),
            relation.columns,
            postgres=True,
            optional=relation.optional,
        )
        states[relation.name] = state
        if state == "unknown":
            problems.append(
                f"{schema}.{relation.name}: unrecognised column set "
                "(not the exact current shape); refusing to republish it"
            )
    existing = [key for key in REBUILD_KEYS if _pg_table_exists(conn, schema, key)]
    for key in existing:
        problems.extend(_pg_republish_blockers(conn, schema, key))
    if problems:
        raise _Refused("; ".join(problems))
    return _PgPlan(schema=schema, states=states, alter=alter, existing_keys=existing)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_upgrade(settings: AppSettings, *, check_only: bool) -> tuple[int, dict[str, Any]]:
    """Run (or, with ``check_only``, only inspect) the upgrade; never raises."""
    report = _Report(mode="check" if check_only else "upgrade")
    try:
        code = _run(settings, report, check_only=check_only)
    except _Refused as exc:
        report.status = "refused"
        report.refusals.append(str(exc))
        report.next_step = "No store was changed. Resolve the refusal and re-run."
        code = EXIT_REFUSED
    except WarehouseBusyError as exc:
        report.status = "refused"
        report.refusals.append(
            f"The DuckDB warehouse is locked by another process ({exc}). Stop the API "
            "and worker, then re-run."
        )
        code = EXIT_REFUSED
    except Exception as exc:  # noqa: BLE001 - reported verbatim in the receipt
        report.status = "incomplete"
        report.error = f"{type(exc).__name__}: {exc}"
        report.next_step = (
            f"Upgrade incomplete after phase {report.phase!r}; not every store is "
            f"upgraded and republished. Recover by re-running `{UPGRADE_COMMAND}` "
            "(idempotent: it re-evaluates the known states, rebuilds from facts and "
            "republishes). Until it exits 0, reads of legacy-shaped relations are refused."
        )
        code = EXIT_FAILED
    return code, report.as_dict()


def _run(settings: AppSettings, report: _Report, *, check_only: bool) -> int:
    warehouse = settings.resolved_analytics_database_path
    if not Path(warehouse).is_file():
        raise _Refused(
            f"DuckDB warehouse {warehouse} does not exist; set "
            "HOMELAB_ANALYTICS_ANALYTICS_DATABASE_PATH to the existing file "
            "(the upgrade never creates one)"
        )
    backend = settings.reporting_backend.lower()
    dsn: str | None = None
    schema = settings.reporting_schema
    if backend == "postgres":
        dsn = settings.resolved_reporting_postgres_dsn
        if not dsn:
            raise _Refused(
                "HOMELAB_ANALYTICS_REPORTING_BACKEND=postgres requires "
                "HOMELAB_ANALYTICS_REPORTING_POSTGRES_DSN (or HOMELAB_ANALYTICS_POSTGRES_DSN)"
            )
        validate_identifier(schema, kind="schema")
    elif backend != "duckdb":
        raise _Refused(f"Unsupported reporting backend: {settings.reporting_backend!r}")
    report.duckdb = {"path": str(warehouse)}
    report.postgres = (
        {"schema": schema, "status": "selected"}
        if dsn
        else {"status": "not_configured", "note": "reporting backend is duckdb"}
    )

    if check_only:
        return _check(Path(warehouse), dsn, schema, report)

    lock = _acquire_pg_lock(dsn, schema) if dsn else None
    try:
        return _upgrade(Path(warehouse), dsn, schema, report)
    finally:
        if lock is not None:
            lock.close()


def _acquire_pg_lock(dsn: str, schema: str) -> psycopg.Connection[Any]:
    lock = connect_with_retry(dsn)
    lock.autocommit = True
    row = lock.execute(
        "SELECT pg_try_advisory_lock(hashtext(%s))",
        (f"homelab-analytics-reporting-upgrade:{schema}",),
    ).fetchone()
    if row is None or not row[0]:
        lock.close()
        raise _Refused(
            f"Another upgrade-reporting run holds the lock for schema {schema!r}"
        )
    return lock


def _check(warehouse: Path, dsn: str | None, schema: str, report: _Report) -> int:
    store = DuckDBStore.open(str(warehouse), read_only=True)
    try:
        report.duckdb["states"] = _duck_states(store)
        unknown = [name for name, state in report.duckdb["states"].items() if state == "unknown"]
        if unknown:
            raise _Refused(
                "DuckDB relation(s) have an unrecognised column set: " + ", ".join(unknown)
            )
        report.facts["before"] = _fact_evidence(store)
        report.snapshots["duckdb"] = _duck_snapshot_evidence(store)
    finally:
        store.close()
    if dsn:
        conn = connect_with_retry(dsn)
        try:
            conn.read_only = True
            plan = _pg_preflight(conn, schema)
            report.postgres.update(
                states=plan.states,
                would_alter=[r.name for r in plan.alter],
                would_republish=plan.existing_keys,
            )
            report.snapshots["postgres"] = _pg_snapshot_evidence(conn, schema)
        finally:
            conn.rollback()
            conn.close()
    pending = sorted(
        {n for n, s in report.duckdb["states"].items() if s == "legacy"}
        | {n for n, s in report.postgres.get("states", {}).items() if s == "legacy"}
    )
    report.status = "check_ok"
    report.phase = "check"
    report.next_step = (
        f"Run without --check to upgrade (legacy relations: {pending})."
        if pending
        else "Stores already have the current shape; running without --check "
        "still rebuilds from facts and republishes."
    )
    return EXIT_COMPLETE


def _upgrade(warehouse: Path, dsn: str | None, schema: str, report: _Report) -> int:
    # Phase 1: preflight both stores before touching either.
    report.phase = "preflight"
    store = DuckDBStore.open(str(warehouse))
    pg_conn: psycopg.Connection[Any] | None = None
    try:
        states = _duck_states(store)
        report.duckdb["states_before"] = states
        unknown = [name for name, state in states.items() if state == "unknown"]
        if unknown:
            raise _Refused(
                "DuckDB relation(s) have an unrecognised column set: " + ", ".join(unknown)
            )
        plan: _PgPlan | None = None
        if dsn:
            pg_conn = connect_with_retry(dsn)
            plan = _pg_preflight(pg_conn, schema)
            report.postgres["states_before"] = plan.states
            report.snapshots["postgres_before"] = _pg_snapshot_evidence(pg_conn, schema)
            pg_conn.rollback()
        report.facts["before"] = _fact_evidence(store)
        report.snapshots["duckdb_before"] = _duck_snapshot_evidence(store)

        # Phase 2: DuckDB schema (one transaction), then rebuild from facts.
        report.phase = "duckdb_schema"
        legacy = [r for r in _RELATIONS if states[r.name] == "legacy"]
        if legacy:
            with store.atomic():
                for relation in legacy:
                    store.execute(
                        f"ALTER TABLE {relation.name} ADD COLUMN IF NOT EXISTS "
                        f"{relation.added} VARCHAR"
                    )
        report.duckdb["altered"] = [r.name for r in legacy]
        # Installed warehouses are created by ``ensure_table`` and normally have
        # no ``schema_migrations`` table; the upgrade never depends on one. If a
        # store was bootstrapped through the migration chain it does have one,
        # and recording 0020 keeps a later ``apply_pending_duckdb_migrations``
        # consistent (the migration is idempotent either way).
        if _duck_table_exists(store, "schema_migrations"):
            store.execute(
                "INSERT INTO schema_migrations (version, applied_at) "
                "SELECT ?, ? WHERE NOT EXISTS "
                "(SELECT 1 FROM schema_migrations WHERE version = ?)",
                [MIGRATION_VERSION, datetime.now(UTC).isoformat(), MIGRATION_VERSION],
            )
            report.duckdb["migration_recorded"] = MIGRATION_VERSION
        report.phase = "duckdb_rebuild"
        transformation = TransformationService(store)
        report.rebuilt = transformation.refresh_publications(list(REBUILD_KEYS))
        _verify_duckdb(store)

        # Phase 3: PostgreSQL schema (one transaction), then republish.
        if dsn and plan is not None and pg_conn is not None:
            report.phase = "postgres_schema"
            before_privileges = {
                r.name: _pg_privileges(pg_conn, schema, r.name) for r in plan.alter
            }
            pg_conn.rollback()
            with pg_conn.transaction():
                pg_conn.execute("SET LOCAL lock_timeout = '5s'")
                for relation in plan.alter:
                    pg_conn.execute(
                        sql.SQL("ALTER TABLE {} ADD COLUMN {} TEXT").format(
                            sql.Identifier(schema, relation.name),
                            sql.Identifier(relation.added),
                        )
                    )
            after_privileges = {
                r.name: _pg_privileges(pg_conn, schema, r.name) for r in plan.alter
            }
            pg_conn.rollback()
            if before_privileges != after_privileges:
                raise RuntimeError(
                    "owner or privileges of an altered publication changed unexpectedly"
                )
            report.postgres["altered"] = [r.name for r in plan.alter]
            report.postgres["privileges_preserved"] = True

            report.phase = "postgres_republish"
            reporting = ReportingService(
                transformation,
                publication_store=PostgresReportingStore(dsn, schema=schema),
                access_mode=ReportingAccessMode.PUBLISHED,
            )
            report.published = reporting.publish_publications(list(plan.existing_keys))
            _verify_published(store, pg_conn, schema, report.published)
            report.snapshots["postgres_after"] = _pg_snapshot_evidence(pg_conn, schema)
            pg_conn.rollback()
            if report.snapshots["postgres_after"] != report.snapshots["postgres_before"]:
                raise RuntimeError("historical PostgreSQL snapshot rows changed")

        # Phase 4: evidence must be unchanged.
        report.phase = "verify"
        report.facts["after"] = _fact_evidence(store)
        report.snapshots["duckdb_after"] = _duck_snapshot_evidence(store)
        if report.facts["after"] != report.facts["before"]:
            raise RuntimeError("fact rows changed during the upgrade")
        if report.snapshots["duckdb_after"] != report.snapshots["duckdb_before"]:
            raise RuntimeError("historical DuckDB snapshot rows changed")
        report.status = "complete"
        report.phase = "done"
        return EXIT_COMPLETE
    finally:
        if pg_conn is not None:
            pg_conn.close()
        store.close()


def _verify_duckdb(store: DuckDBStore) -> None:
    for relation, per_row in CURRENCY_COLUMN_RELATIONS.items():
        if not per_row:
            continue
        missing = store.fetchall(
            f"SELECT COUNT(*) FROM {relation} WHERE currency IS NULL OR currency = ''"
        )[0][0]
        if missing:
            raise RuntimeError(f"{relation} still has {missing} row(s) without a currency")

    missing_usage = store.fetchall(
        f"SELECT COUNT(*) FROM {MART_UTILITY_COST_SUMMARY_TABLE} WHERE usage_observations IS NULL"
    )[0][0]
    if missing_usage:
        raise RuntimeError(
            f"{MART_UTILITY_COST_SUMMARY_TABLE} still has rows without usage provenance"
        )


def _verify_published(
    store: DuckDBStore,
    conn: psycopg.Connection[Any],
    schema: str,
    keys: list[str],
) -> None:
    for key in keys:
        validate_identifier(key, kind="table")
        warehouse_rows = store.fetchall(f"SELECT COUNT(*) FROM {key}")[0][0]
        published_rows = conn.execute(
            sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(schema, key))
        ).fetchone()
        if published_rows is None or published_rows[0] != warehouse_rows:
            raise RuntimeError(
                f"published {key} has {published_rows and published_rows[0]} rows; "
                f"the rebuilt mart has {warehouse_rows}"
            )
