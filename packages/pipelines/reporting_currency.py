"""Currency-separated reporting: relation registry and the stale-schema guard.

Monetary publications keep one row per denomination and never convert between
currencies. Stores created before that change hold blended amounts in tables
that have no ``currency`` column. ``upgrade-reporting`` (see
``packages/pipelines/reporting_upgrade.py``) is the only supported way to move
such a store forward; ordinary reads refuse a relation that still has the
legacy shape instead of serving blended or unlabelled amounts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from packages.domains.finance.pipelines.transaction_models import (
    MART_ACCOUNT_BALANCE_TREND_TABLE,
    MART_CASHFLOW_BY_COUNTERPARTY_TABLE,
    MART_MONTHLY_CASHFLOW_TABLE,
    MART_SPEND_BY_CATEGORY_MONTHLY_TABLE,
    MART_SPEND_BY_WEEKDAY_HOUR_TABLE,
    MART_TRANSACTION_ANOMALIES_CURRENT_TABLE,
)
from packages.domains.overview.pipelines.overview_models import (
    MART_RECENT_SIGNIFICANT_CHANGES_TABLE,
)
from packages.domains.utilities.pipelines.utility_models import (
    MART_USAGE_VS_PRICE_SUMMARY_TABLE,
)

# Relations whose legacy shape lacks ``currency``. The upgrade adds the column
# (appended, nullable in an upgraded legacy table) and rebuilds the rows from
# facts. ``True``: every row of the relation must carry a currency. ``False``:
# a NULL currency is valid (usage with no bill) and only a missing column is
# stale.
CURRENCY_COLUMN_RELATIONS: Mapping[str, bool] = {
    MART_MONTHLY_CASHFLOW_TABLE: True,
    MART_CASHFLOW_BY_COUNTERPARTY_TABLE: True,
    MART_SPEND_BY_CATEGORY_MONTHLY_TABLE: True,
    MART_ACCOUNT_BALANCE_TREND_TABLE: True,
    MART_SPEND_BY_WEEKDAY_HOUR_TABLE: True,
    MART_TRANSACTION_ANOMALIES_CURRENT_TABLE: True,
    MART_RECENT_SIGNIFICANT_CHANGES_TABLE: True,
    MART_USAGE_VS_PRICE_SUMMARY_TABLE: False,
}

UPGRADE_COMMAND = "python -m apps.worker.main upgrade-reporting"


class StaleReportingSchemaError(RuntimeError):
    """A reporting relation still has the pre-currency (blended) legacy shape."""

    def __init__(self, relation_name: str) -> None:
        super().__init__(
            f"Reporting relation {relation_name} predates currency-separated "
            f"totals and cannot be served; run `{UPGRADE_COMMAND}` "
            "(use --check to inspect first)."
        )
        self.relation_name = relation_name


def assert_currency_column_present(
    relation_name: str, columns: Sequence[str]
) -> None:
    """Refuse a currency-grouped relation whose schema lacks ``currency``.

    The per-row check (:func:`assert_currency_current`) cannot see an empty
    legacy relation: with no rows it asserts nothing, yet an empty relation of
    the old shape still has no ``currency`` column and must not be served as a
    valid empty current relation. This schema-level check is what distinguishes
    the two at the store/reporting/API boundary. An empty ``columns`` list
    means the relation does not exist at all, which is not stale.
    """
    if relation_name not in CURRENCY_COLUMN_RELATIONS:
        return
    if not columns:
        return
    names = {name.lower() for name in columns}
    if "currency" not in names:
        raise StaleReportingSchemaError(relation_name)


def assert_currency_current(
    relation_name: str, rows: Sequence[Mapping[str, Any]]
) -> None:
    """Refuse legacy rows of a currency-grouped relation.

    A legacy relation has no ``currency`` column at all, so its rows (from
    ``SELECT *``) lack the key; a legacy-upgraded but not yet rebuilt DuckDB
    table has the column with NULLs. The schema-level check
    (:func:`assert_currency_column_present`) is what refuses an empty legacy
    relation; this row-level check catches a relation that has rows but no (or
    a null) currency on each row.
    """
    required_per_row = CURRENCY_COLUMN_RELATIONS.get(relation_name)
    if required_per_row is None or not rows:
        return
    for row in rows:
        if "currency" not in row:
            raise StaleReportingSchemaError(relation_name)
        if required_per_row and not row["currency"]:
            raise StaleReportingSchemaError(relation_name)
