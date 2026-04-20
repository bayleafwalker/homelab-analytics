"""Transaction entity reconciliation engine.

Reconciles immutable ``transaction_observation`` rows into stable
``transaction_entity`` + ``fact_transaction_current`` projections.

Reconciliation outcomes per entity_key:

1. **New entity** — entity_key not seen before → create entity + current row.
2. **No-op** — same entity, same canonical values → bump last_seen metadata only.
3. **Richer metadata** — same entity, new observation has more detail (e.g. a
   description where the existing row had none) → update current projection,
   keep both observations.
4. **Conflict** — same entity, observation has differing amount/currency →
   mark entity ``ambiguous``, do not update current projection.
5. **Idempotent replay** — observation already linked to this entity (same
   ``current_observation_id``) → complete no-op.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from packages.domains.finance.pipelines.transaction_models import (
    FACT_TRANSACTION_CURRENT_COLUMNS,
    FACT_TRANSACTION_CURRENT_TABLE,
    TRANSACTION_ENTITY_COLUMNS,
    TRANSACTION_ENTITY_TABLE,
    TRANSACTION_OBSERVATION_TABLE,
)
from packages.pipelines.normalization import normalize_currency_code, normalize_timestamp_utc
from packages.storage.duckdb_store import DuckDBStore


@dataclass(frozen=True)
class ReconciliationResult:
    """Summary of a single reconcile_batch call."""

    batch_id: str
    new_entities: int
    noop_updates: int
    richer_updates: int
    conflicts: int
    total_observations: int


def ensure_entity_storage(store: DuckDBStore) -> None:
    """Create entity and current-projection tables if they do not exist."""
    store.ensure_table(TRANSACTION_ENTITY_TABLE, TRANSACTION_ENTITY_COLUMNS)
    store.ensure_table(FACT_TRANSACTION_CURRENT_TABLE, FACT_TRANSACTION_CURRENT_COLUMNS)


def reconcile_batch(
    store: DuckDBStore,
    batch_id: str,
    *,
    run_id: str | None = None,
) -> ReconciliationResult:
    """Reconcile all observations in *batch_id* into the entity layer.

    Observations that could not be identity-resolved (``entity_key IS NULL``)
    are skipped; they remain in the observation table as unresolved evidence.

    All writes are wrapped in a single atomic transaction.
    """
    obs_rows = store.fetchall_dicts(
        f"""
        SELECT observation_id, entity_key, batch_id, booked_at, account_id,
               counterparty_name, amount, currency, description,
               normalized_row_json, observed_at
        FROM {TRANSACTION_OBSERVATION_TABLE}
        WHERE batch_id = ? AND entity_key IS NOT NULL
        ORDER BY row_ordinal
        """,
        [batch_id],
    )

    new_entities = 0
    noop_updates = 0
    richer_updates = 0
    conflicts = 0
    now = datetime.now(UTC)

    with store.atomic():
        for obs in obs_rows:
            entity_key: str = obs["entity_key"]
            obs_id: str = obs["observation_id"]

            existing = store.fetchall_dicts(
                f"SELECT * FROM {TRANSACTION_ENTITY_TABLE} WHERE entity_key = ?",
                [entity_key],
            )

            if not existing:
                # Outcome 1: New entity
                _insert_entity(store, entity_key, obs, now)
                _insert_current(store, entity_key, obs, run_id, now)
                new_entities += 1
                continue

            entity = existing[0]

            # Idempotent replay guard
            if entity["current_observation_id"] == obs_id:
                noop_updates += 1
                continue

            current_proj = store.fetchall_dicts(
                f"SELECT * FROM {FACT_TRANSACTION_CURRENT_TABLE} WHERE entity_key = ?",
                [entity_key],
            )
            current = current_proj[0] if current_proj else None

            new_amount = _to_decimal(obs["amount"])
            cur_amount = _to_decimal(current["amount"]) if current else None

            # Conflict detection: differing amount or currency on same entity
            if current and (
                new_amount != cur_amount
                or str(obs["currency"]).strip() != str(current["currency"]).strip()
            ):
                store.execute(
                    f"UPDATE {TRANSACTION_ENTITY_TABLE}"
                    f" SET status = 'ambiguous', last_seen_batch_id = ?,"
                    f"     last_seen_at = ?, observation_count = observation_count + 1"
                    f" WHERE entity_key = ?",
                    [batch_id, now, entity_key],
                )
                conflicts += 1
                continue

            # Richer metadata: existing description is empty and new one is not
            existing_desc = str(current["description"] or "").strip() if current else ""
            new_desc = str(obs.get("description") or "").strip()
            is_richer = bool(new_desc) and not existing_desc

            if is_richer:
                # Outcome 3: update current projection with richer observation
                _update_current(store, entity_key, obs_id, obs, run_id, now)
                store.execute(
                    f"UPDATE {TRANSACTION_ENTITY_TABLE}"
                    f" SET current_observation_id = ?, last_seen_batch_id = ?,"
                    f"     last_seen_at = ?, observation_count = observation_count + 1"
                    f" WHERE entity_key = ?",
                    [obs_id, batch_id, now, entity_key],
                )
                richer_updates += 1
            else:
                # Outcome 2: no-op — bump last_seen metadata only
                store.execute(
                    f"UPDATE {TRANSACTION_ENTITY_TABLE}"
                    f" SET last_seen_batch_id = ?, last_seen_at = ?,"
                    f"     observation_count = observation_count + 1"
                    f" WHERE entity_key = ?",
                    [batch_id, now, entity_key],
                )
                noop_updates += 1

    return ReconciliationResult(
        batch_id=batch_id,
        new_entities=new_entities,
        noop_updates=noop_updates,
        richer_updates=richer_updates,
        conflicts=conflicts,
        total_observations=len(obs_rows),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _insert_entity(
    store: DuckDBStore,
    entity_key: str,
    obs: dict[str, Any],
    now: datetime,
) -> None:
    cols = [c for c, _ in TRANSACTION_ENTITY_COLUMNS if c != "status"]
    store.execute(
        f"INSERT INTO {TRANSACTION_ENTITY_TABLE}"
        f" (entity_key, first_seen_batch_id, first_seen_at, last_seen_batch_id,"
        f"  last_seen_at, observation_count, current_observation_id)"
        f" VALUES (?, ?, ?, ?, ?, 1, ?)",
        [entity_key, obs["batch_id"], now, obs["batch_id"], now, obs["observation_id"]],
    )
    _ = cols  # kept for reference


def _insert_current(
    store: DuckDBStore,
    entity_key: str,
    obs: dict[str, Any],
    run_id: str | None,
    now: datetime,
) -> None:
    booked_at = obs["booked_at"]
    booked_at_utc = normalize_timestamp_utc(booked_at)
    amount = _to_decimal(obs["amount"])
    currency = str(obs["currency"]).strip()
    store.execute(
        f"INSERT INTO {FACT_TRANSACTION_CURRENT_TABLE}"
        f" (entity_key, current_observation_id, booked_at, booked_at_utc,"
        f"  booking_month, account_id, counterparty_name, amount, currency,"
        f"  normalized_currency, description, direction, run_id, reconciled_at)"
        f" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            entity_key,
            obs["observation_id"],
            booked_at,
            booked_at_utc,
            str(booked_at)[:7],  # "YYYY-MM"
            obs["account_id"],
            obs["counterparty_name"],
            amount,
            currency,
            normalize_currency_code(currency),
            obs.get("description") or "",
            "income" if amount >= 0 else "expense",
            run_id,
            now,
        ],
    )


def _update_current(
    store: DuckDBStore,
    entity_key: str,
    obs_id: str,
    obs: dict[str, Any],
    run_id: str | None,
    now: datetime,
) -> None:
    new_desc = str(obs.get("description") or "").strip()
    store.execute(
        f"UPDATE {FACT_TRANSACTION_CURRENT_TABLE}"
        f" SET current_observation_id = ?, description = ?, run_id = ?, reconciled_at = ?"
        f" WHERE entity_key = ?",
        [obs_id, new_desc, run_id, now, entity_key],
    )
