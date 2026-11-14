"""Exact four-kind attention source reads and their public exceptions.

The attention UI groups its open items by a whole-key identity composed across
domains: transaction anomalies (finance), contract review/renewal candidates
(utilities) and upcoming fixed costs (subscriptions). This module is the
household-overview seam for reading one complete group from the current source
publication, without landing-to-dashboard shortcuts and without warehouse
fallback when ``PUBLISHED`` mode is selected.

Whole keys are opaque. The reader binds the complete key in real source SQL
(``'prefix_' || identity || ... = ?/%s``) and never splits, guesses an
equal-looking prefix, or matches the first row.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import duckdb
import psycopg

from packages.domains.finance.pipelines.subscription_models import (
    MART_UPCOMING_FIXED_COSTS_30D_TABLE,
)
from packages.domains.finance.pipelines.transaction_models import (
    MART_TRANSACTION_ANOMALIES_CURRENT_TABLE,
)
from packages.domains.overview.pipelines.overview_models import (
    MART_OPEN_ATTENTION_ITEMS_TABLE,
)
from packages.domains.utilities.pipelines.utility_models import (
    MART_CONTRACT_RENEWAL_WATCHLIST_TABLE,
    MART_CONTRACT_REVIEW_CANDIDATES_TABLE,
)

if TYPE_CHECKING:
    from packages.pipelines.reporting_service import ReportingService


class AttentionRecordNotFoundError(KeyError):
    """A whole attention-record key is provably absent from the current publication."""


class AttentionRecordUnavailableError(RuntimeError):
    """The attention source cannot establish presence or absence for a key."""


@dataclass(frozen=True)
class _AttentionKind:
    """One attention kind: its source relation and opaque whole-key identity."""

    table: str
    identities: tuple[str, ...]
    key_expr: str
    invalid_cond: str


_ATTENTION_KINDS: dict[str, _AttentionKind] = {
    "anomaly": _AttentionKind(
        table=MART_TRANSACTION_ANOMALIES_CURRENT_TABLE,
        identities=("transaction_id",),
        key_expr="'anomaly_' || transaction_id",
        invalid_cond="transaction_id IS NULL OR transaction_id = ''",
    ),
    "contract_review": _AttentionKind(
        table=MART_CONTRACT_REVIEW_CANDIDATES_TABLE,
        identities=("contract_id", "reason"),
        key_expr="'review_' || contract_id || '_' || reason",
        invalid_cond="contract_id IS NULL OR contract_id = '' OR reason IS NULL OR reason = ''",
    ),
    "contract_renewal": _AttentionKind(
        table=MART_CONTRACT_RENEWAL_WATCHLIST_TABLE,
        identities=("contract_id", "renewal_date"),
        key_expr="'renewal_' || contract_id || '_' || CAST(renewal_date AS VARCHAR)",
        invalid_cond="contract_id IS NULL OR contract_id = ''",
    ),
    "upcoming_cost": _AttentionKind(
        table=MART_UPCOMING_FIXED_COSTS_30D_TABLE,
        identities=("charge_id", "expected_date"),
        key_expr="'upcoming_' || charge_id || '_' || CAST(expected_date AS VARCHAR)",
        invalid_cond="charge_id IS NULL OR charge_id = ''",
    ),
}


def get_open_attention_items(service: "ReportingService") -> list[dict[str, Any]]:
    """Current open attention items, preserving the reporting facade behavior."""
    return service._fetch_published_or_fallback(
        MART_OPEN_ATTENTION_ITEMS_TABLE,
        lambda: service._read_mart(MART_OPEN_ATTENTION_ITEMS_TABLE),
        ("", []),
        "ORDER BY severity, item_type",
    )


def get_attention_record(
    service: "ReportingService",
    item_type: str,
    item_id: str,
) -> list[dict[str, Any]]:
    """Return the complete group of rows for ``item_id`` in the current source.

    Raises :class:`AttentionRecordNotFoundError` when the key is provably
    absent and :class:`AttentionRecordUnavailableError` when the source cannot
    establish presence or absence (missing relation/column, driver failure, or
    a NULL/empty identity component that would fabricate a successful id).
    """
    kind = _ATTENTION_KINDS.get(item_type)
    if kind is None:
        raise ValueError(f"Unknown attention item type: {item_type!r}")
    try:
        store, placeholder = _resolve_source(service, kind)
        matching, invalid = _read_group(store, kind, item_id, placeholder)
    except (psycopg.Error, duckdb.Error):
        raise AttentionRecordUnavailableError(
            f"Attention source for {item_type!r} is unavailable"
        ) from None
    if invalid:
        valid = [row for row in matching if _identity_valid(row, kind.identities)]
        if valid:
            return valid
        raise AttentionRecordUnavailableError(
            f"Attention source for {item_type!r} carries an invalid identity"
        )
    if not matching:
        raise AttentionRecordNotFoundError(
            f"Attention record {item_id!r} not found in {kind.table}"
        )
    return matching


def _resolve_source(
    service: "ReportingService",
    kind: _AttentionKind,
) -> tuple[Any, str]:
    from packages.pipelines.reporting_service import ReportingAccessMode

    if service._access_mode == ReportingAccessMode.WAREHOUSE:
        return service._transformation_service.store, "?"
    store = service._publication_store
    if store is not None and store.table_exists(kind.table):
        return store, "%s"
    if service._access_mode == ReportingAccessMode.PUBLISHED:
        raise AttentionRecordUnavailableError(
            f"Published attention source {kind.table!r} is unavailable"
        )
    return service._transformation_service.store, "?"


def _read_group(
    store: Any,
    kind: _AttentionKind,
    item_id: str,
    placeholder: str,
) -> tuple[list[dict[str, Any]], bool]:
    matching = store.fetchall_dicts(
        f"SELECT * FROM {kind.table} WHERE {kind.key_expr} = {placeholder}",
        [item_id],
    )
    invalid = store.fetchall_dicts(
        f"SELECT 1 FROM {kind.table} WHERE {kind.invalid_cond} LIMIT 1",
        [],
    )
    return matching, bool(invalid)


def _identity_valid(row: dict[str, Any], identities: tuple[str, ...]) -> bool:
    for name in identities:
        value = row.get(name)
        if value is None or value == "":
            return False
    return True
