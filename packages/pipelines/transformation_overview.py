"""Cross-domain overview composition — reads from existing domain marts."""
from __future__ import annotations

from typing import Any

from packages.pipelines.overview_models import (
    MART_CURRENT_OPERATING_BASELINE_COLUMNS,
    MART_CURRENT_OPERATING_BASELINE_TABLE,
    MART_HOUSEHOLD_OVERVIEW_COLUMNS,
    MART_HOUSEHOLD_OVERVIEW_TABLE,
    MART_OPEN_ATTENTION_ITEMS_COLUMNS,
    MART_OPEN_ATTENTION_ITEMS_TABLE,
    MART_RECENT_SIGNIFICANT_CHANGES_COLUMNS,
    MART_RECENT_SIGNIFICANT_CHANGES_TABLE,
)
from packages.pipelines.subscription_models import (
    MART_SUBSCRIPTION_SUMMARY_TABLE,
    MART_UPCOMING_FIXED_COSTS_30D_TABLE,
)
from packages.pipelines.transaction_models import (
    MART_ACCOUNT_BALANCE_TREND_TABLE,
    MART_MONTHLY_CASHFLOW_TABLE,
    MART_RECENT_LARGE_TRANSACTIONS_TABLE,
    MART_SPEND_BY_CATEGORY_MONTHLY_TABLE,
    MART_TRANSACTION_ANOMALIES_CURRENT_TABLE,
)
from packages.pipelines.utility_models import (
    MART_CONTRACT_RENEWAL_WATCHLIST_TABLE,
    MART_CONTRACT_REVIEW_CANDIDATES_TABLE,
    MART_UTILITY_COST_TREND_MONTHLY_TABLE,
)
from packages.storage.duckdb_store import DuckDBStore

# Suppress unused import — MART_RECENT_LARGE_TRANSACTIONS_TABLE is available for
# future overview use (e.g. notable transactions surface).
_ = MART_RECENT_LARGE_TRANSACTIONS_TABLE


def ensure_overview_storage(store: DuckDBStore) -> None:
    store.ensure_table(MART_HOUSEHOLD_OVERVIEW_TABLE, MART_HOUSEHOLD_OVERVIEW_COLUMNS)
    store.ensure_table(MART_OPEN_ATTENTION_ITEMS_TABLE, MART_OPEN_ATTENTION_ITEMS_COLUMNS)
    store.ensure_table(
        MART_RECENT_SIGNIFICANT_CHANGES_TABLE, MART_RECENT_SIGNIFICANT_CHANGES_COLUMNS
    )
    store.ensure_table(
        MART_CURRENT_OPERATING_BASELINE_TABLE, MART_CURRENT_OPERATING_BASELINE_COLUMNS
    )


def refresh_household_overview(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_HOUSEHOLD_OVERVIEW_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_HOUSEHOLD_OVERVIEW_TABLE} (
            current_month, cashflow_income, cashflow_expense, cashflow_net,
            utility_cost_total, subscription_total_monthly,
            account_balance_direction, balance_net_change, currency
        )
        WITH
        latest_cashflow AS (
            SELECT booking_month, income, expense, net
            FROM {MART_MONTHLY_CASHFLOW_TABLE}
            ORDER BY booking_month DESC
            LIMIT 1
        ),
        latest_utility AS (
            SELECT SUM(total_cost) AS utility_total, ANY_VALUE(currency) AS currency
            FROM {MART_UTILITY_COST_TREND_MONTHLY_TABLE}
            WHERE billing_month = (
                SELECT MAX(billing_month) FROM {MART_UTILITY_COST_TREND_MONTHLY_TABLE}
            )
        ),
        active_subscriptions AS (
            SELECT COALESCE(SUM(monthly_equivalent), 0) AS subscription_total
            FROM {MART_SUBSCRIPTION_SUMMARY_TABLE}
            WHERE status = 'active'
        ),
        latest_balance AS (
            SELECT
                SUM(net_change) AS net_change,
                CASE
                    WHEN SUM(net_change) > 0 THEN 'up'
                    WHEN SUM(net_change) < 0 THEN 'down'
                    ELSE 'flat'
                END AS direction
            FROM {MART_ACCOUNT_BALANCE_TREND_TABLE}
            WHERE booking_month = (
                SELECT MAX(booking_month) FROM {MART_ACCOUNT_BALANCE_TREND_TABLE}
            )
        )
        SELECT
            COALESCE((SELECT booking_month  FROM latest_cashflow), '')    AS current_month,
            COALESCE((SELECT income         FROM latest_cashflow), 0)     AS cashflow_income,
            COALESCE((SELECT expense        FROM latest_cashflow), 0)     AS cashflow_expense,
            COALESCE((SELECT net            FROM latest_cashflow), 0)     AS cashflow_net,
            COALESCE((SELECT utility_total  FROM latest_utility),  0)     AS utility_cost_total,
            COALESCE((SELECT subscription_total FROM active_subscriptions), 0)
                                                                          AS subscription_total_monthly,
            COALESCE((SELECT direction      FROM latest_balance),  'flat') AS account_balance_direction,
            COALESCE((SELECT net_change     FROM latest_balance),  0)     AS balance_net_change,
            COALESCE((SELECT currency       FROM latest_utility),  '')    AS currency
        """
    )
    return store.fetchall(f"SELECT COUNT(*) FROM {MART_HOUSEHOLD_OVERVIEW_TABLE}")[0][0]


def get_household_overview(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(f"SELECT * FROM {MART_HOUSEHOLD_OVERVIEW_TABLE}")


def refresh_open_attention_items(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_OPEN_ATTENTION_ITEMS_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_OPEN_ATTENTION_ITEMS_TABLE}
            (item_id, item_type, title, detail, severity, source_domain)
        WITH
        anomalies AS (
            SELECT
                'anomaly_' || transaction_id                     AS item_id,
                'anomaly'                                        AS item_type,
                'Unusual transaction: ' || counterparty_name    AS title,
                anomaly_type || ' — ' || anomaly_reason         AS detail,
                2                                               AS severity,
                'finance'                                       AS source_domain
            FROM {MART_TRANSACTION_ANOMALIES_CURRENT_TABLE}
        ),
        review_candidates AS (
            SELECT
                'review_' || contract_id || '_' || reason        AS item_id,
                'contract_review'                                AS item_type,
                'Review contract: ' || provider                  AS title,
                reason                                           AS detail,
                score                                            AS severity,
                'utilities'                                      AS source_domain
            FROM {MART_CONTRACT_REVIEW_CANDIDATES_TABLE}
        ),
        upcoming_renewals AS (
            SELECT
                'renewal_' || contract_id                        AS item_id,
                'contract_renewal'                               AS item_type,
                'Upcoming renewal: ' || provider                 AS title,
                'Renews in ' || days_until_renewal || ' days on '
                    || CAST(renewal_date AS VARCHAR)             AS detail,
                CASE
                    WHEN days_until_renewal <= 14 THEN 3
                    WHEN days_until_renewal <= 30 THEN 2
                    ELSE 1
                END                                              AS severity,
                'utilities'                                      AS source_domain
            FROM {MART_CONTRACT_RENEWAL_WATCHLIST_TABLE}
            WHERE days_until_renewal <= 30
        ),
        upcoming_payments AS (
            SELECT
                'upcoming_' || contract_name
                    || '_' || CAST(expected_date AS VARCHAR)     AS item_id,
                'upcoming_cost'                                  AS item_type,
                'Upcoming payment: ' || contract_name           AS title,
                frequency || ' charge of '
                    || CAST(expected_amount AS VARCHAR)
                    || ' ' || currency
                    || ' on ' || CAST(expected_date AS VARCHAR) AS detail,
                1                                               AS severity,
                'finance'                                       AS source_domain
            FROM {MART_UPCOMING_FIXED_COSTS_30D_TABLE}
            WHERE expected_date <= CURRENT_DATE + INTERVAL '7 days'
        )
        SELECT * FROM anomalies
        UNION ALL SELECT * FROM review_candidates
        UNION ALL SELECT * FROM upcoming_renewals
        UNION ALL SELECT * FROM upcoming_payments
        ORDER BY severity DESC, item_type, title
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_OPEN_ATTENTION_ITEMS_TABLE}"
    )[0][0]


def get_open_attention_items(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_OPEN_ATTENTION_ITEMS_TABLE}"
        " ORDER BY severity DESC, item_type, title"
    )


def refresh_recent_significant_changes(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_RECENT_SIGNIFICANT_CHANGES_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_RECENT_SIGNIFICANT_CHANGES_TABLE}
            (change_type, period, description, current_value, previous_value,
             change_pct, direction)
        WITH
        cashflow_changes AS (
            SELECT
                'cashflow_net'                          AS change_type,
                booking_month                           AS period,
                'Net cashflow'                          AS description,
                net                                     AS current_value,
                LAG(net) OVER (ORDER BY booking_month)  AS previous_value
            FROM {MART_MONTHLY_CASHFLOW_TABLE}
        ),
        category_changes AS (
            SELECT
                'category_spend'                        AS change_type,
                booking_month                           AS period,
                'Spend: ' || counterparty_name          AS description,
                total_expense                           AS current_value,
                LAG(total_expense) OVER (
                    PARTITION BY counterparty_name
                    ORDER BY booking_month
                )                                       AS previous_value
            FROM {MART_SPEND_BY_CATEGORY_MONTHLY_TABLE}
        ),
        utility_changes AS (
            SELECT
                'utility_cost'                          AS change_type,
                billing_month                           AS period,
                'Utility: ' || utility_type             AS description,
                total_cost                              AS current_value,
                LAG(total_cost) OVER (
                    PARTITION BY utility_type
                    ORDER BY billing_month
                )                                       AS previous_value
            FROM {MART_UTILITY_COST_TREND_MONTHLY_TABLE}
        ),
        all_changes AS (
            SELECT * FROM cashflow_changes  WHERE previous_value IS NOT NULL
            UNION ALL
            SELECT * FROM category_changes  WHERE previous_value IS NOT NULL
            UNION ALL
            SELECT * FROM utility_changes   WHERE previous_value IS NOT NULL
        ),
        ranked AS (
            SELECT
                change_type,
                period,
                description,
                current_value,
                previous_value,
                CASE
                    WHEN previous_value <> 0
                    THEN ROUND(
                        (current_value - previous_value) / ABS(previous_value) * 100, 2
                    )
                    ELSE NULL
                END AS change_pct,
                CASE
                    WHEN current_value >= previous_value THEN 'up'
                    ELSE 'down'
                END AS direction,
                ROW_NUMBER() OVER (
                    PARTITION BY change_type
                    ORDER BY ABS(
                        CASE
                            WHEN previous_value <> 0
                            THEN (current_value - previous_value) / ABS(previous_value)
                            ELSE 0
                        END
                    ) DESC
                ) AS rn
            FROM all_changes
        )
        SELECT
            change_type, period, description, current_value, previous_value,
            change_pct, direction
        FROM ranked
        WHERE rn = 1
        ORDER BY ABS(COALESCE(change_pct, 0)) DESC
        LIMIT 10
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_RECENT_SIGNIFICANT_CHANGES_TABLE}"
    )[0][0]


def get_recent_significant_changes(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_RECENT_SIGNIFICANT_CHANGES_TABLE}"
        " ORDER BY ABS(COALESCE(change_pct, 0)) DESC"
    )


def refresh_current_operating_baseline(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_CURRENT_OPERATING_BASELINE_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_CURRENT_OPERATING_BASELINE_TABLE}
            (baseline_type, description, value, period_label, currency)
        WITH
        recent_cashflow AS (
            SELECT expense, booking_month
            FROM {MART_MONTHLY_CASHFLOW_TABLE}
            ORDER BY booking_month DESC
            LIMIT 3
        ),
        active_subs AS (
            SELECT
                SUM(monthly_equivalent) AS total,
                ANY_VALUE(currency)     AS currency
            FROM {MART_SUBSCRIPTION_SUMMARY_TABLE}
            WHERE status = 'active'
        ),
        recent_utility AS (
            SELECT
                SUM(total_cost) AS total_cost,
                billing_month,
                ANY_VALUE(currency) AS currency
            FROM {MART_UTILITY_COST_TREND_MONTHLY_TABLE}
            GROUP BY billing_month
            ORDER BY billing_month DESC
            LIMIT 3
        ),
        latest_balance AS (
            SELECT
                SUM(cumulative_balance) AS total,
                MAX(booking_month)      AS month
            FROM {MART_ACCOUNT_BALANCE_TREND_TABLE}
            WHERE booking_month = (
                SELECT MAX(booking_month) FROM {MART_ACCOUNT_BALANCE_TREND_TABLE}
            )
        )
        SELECT
            'monthly_spend'                          AS baseline_type,
            'Average monthly expense (last 3 months)' AS description,
            COALESCE(ROUND((SELECT AVG(expense)         FROM recent_cashflow), 2), 0) AS value,
            COALESCE((SELECT MAX(booking_month)         FROM recent_cashflow), '')    AS period_label,
            ''                                                                        AS currency
        UNION ALL
        SELECT
            'recurring_costs',
            'Total active monthly subscriptions',
            COALESCE(ROUND((SELECT total    FROM active_subs), 2), 0),
            STRFTIME(CURRENT_DATE, '%Y-%m'),
            COALESCE((SELECT currency       FROM active_subs), '')
        UNION ALL
        SELECT
            'utility_baseline',
            'Average monthly utility cost (last 3 months)',
            COALESCE(ROUND((SELECT AVG(total_cost)      FROM recent_utility), 2), 0),
            COALESCE((SELECT MAX(billing_month)         FROM recent_utility), ''),
            COALESCE((SELECT ANY_VALUE(currency)        FROM recent_utility), '')
        UNION ALL
        SELECT
            'account_balance',
            'Current account balance',
            COALESCE(ROUND((SELECT total    FROM latest_balance), 2), 0),
            COALESCE((SELECT month          FROM latest_balance), ''),
            ''
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_CURRENT_OPERATING_BASELINE_TABLE}"
    )[0][0]


def get_current_operating_baseline(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_CURRENT_OPERATING_BASELINE_TABLE}"
        " ORDER BY baseline_type"
    )
