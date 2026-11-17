"""Cross-domain overview composition — reads from existing domain marts."""
from __future__ import annotations

from typing import Any

from packages.domains.finance.pipelines.loan_models import MART_LOAN_OVERVIEW_TABLE
from packages.domains.finance.pipelines.subscription_models import (
    MART_SUBSCRIPTION_SUMMARY_TABLE,
    MART_UPCOMING_FIXED_COSTS_30D_TABLE,
)
from packages.domains.finance.pipelines.transaction_models import (
    FACT_TRANSACTION_CURRENT_TABLE,
    MART_MONTHLY_CASHFLOW_TABLE,
    MART_RECENT_LARGE_TRANSACTIONS_TABLE,
    MART_SPEND_BY_CATEGORY_MONTHLY_TABLE,
    MART_TRANSACTION_ANOMALIES_CURRENT_TABLE,
)
from packages.domains.homelab.pipelines.homelab_models import (
    MART_SERVICE_HEALTH_CURRENT_TABLE,
    MART_WORKLOAD_COST_7D_TABLE,
)
from packages.domains.overview.pipelines.overview_models import (
    MART_AFFORDABILITY_RATIOS_COLUMNS,
    MART_AFFORDABILITY_RATIOS_TABLE,
    MART_COST_TREND_12M_COLUMNS,
    MART_COST_TREND_12M_TABLE,
    MART_CURRENT_OPERATING_BASELINE_COLUMNS,
    MART_CURRENT_OPERATING_BASELINE_TABLE,
    MART_HOMELAB_ROI_COLUMNS,
    MART_HOMELAB_ROI_TABLE,
    MART_HOUSEHOLD_COST_MODEL_COLUMNS,
    MART_HOUSEHOLD_COST_MODEL_TABLE,
    MART_HOUSEHOLD_OVERVIEW_COLUMNS,
    MART_HOUSEHOLD_OVERVIEW_TABLE,
    MART_OPEN_ATTENTION_ITEMS_COLUMNS,
    MART_OPEN_ATTENTION_ITEMS_TABLE,
    MART_RECENT_SIGNIFICANT_CHANGES_COLUMNS,
    MART_RECENT_SIGNIFICANT_CHANGES_TABLE,
    MART_RECURRING_COST_BASELINE_COLUMNS,
    MART_RECURRING_COST_BASELINE_TABLE,
)
from packages.domains.utilities.pipelines.utility_models import (
    MART_CONTRACT_RENEWAL_WATCHLIST_TABLE,
    MART_CONTRACT_REVIEW_CANDIDATES_TABLE,
    MART_UTILITY_COST_TREND_MONTHLY_TABLE,
)
from packages.storage.duckdb_store import DuckDBStore

# Suppress unused import — MART_RECENT_LARGE_TRANSACTIONS_TABLE is available for
# future overview use (e.g. notable transactions surface).
_ = MART_RECENT_LARGE_TRANSACTIONS_TABLE


def _ensure_column(
    store: DuckDBStore,
    table_name: str,
    column_name: str,
    column_type: str,
) -> None:
    existing_columns = {
        row[1] for row in store.connection.execute(
            f"PRAGMA table_info('{table_name}')"
        ).fetchall()
    }
    if column_name not in existing_columns:
        store.connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )


def ensure_overview_storage(store: DuckDBStore) -> None:
    store.ensure_table(MART_HOUSEHOLD_OVERVIEW_TABLE, MART_HOUSEHOLD_OVERVIEW_COLUMNS)
    store.ensure_table(MART_HOMELAB_ROI_TABLE, MART_HOMELAB_ROI_COLUMNS)
    store.ensure_table(MART_OPEN_ATTENTION_ITEMS_TABLE, MART_OPEN_ATTENTION_ITEMS_COLUMNS)
    store.ensure_table(
        MART_RECENT_SIGNIFICANT_CHANGES_TABLE, MART_RECENT_SIGNIFICANT_CHANGES_COLUMNS
    )
    store.ensure_table(
        MART_CURRENT_OPERATING_BASELINE_TABLE, MART_CURRENT_OPERATING_BASELINE_COLUMNS
    )
    store.ensure_table(MART_HOUSEHOLD_COST_MODEL_TABLE, MART_HOUSEHOLD_COST_MODEL_COLUMNS)
    store.ensure_table(MART_COST_TREND_12M_TABLE, MART_COST_TREND_12M_COLUMNS)
    store.ensure_table(MART_AFFORDABILITY_RATIOS_TABLE, MART_AFFORDABILITY_RATIOS_COLUMNS)
    store.ensure_table(
        MART_RECURRING_COST_BASELINE_TABLE, MART_RECURRING_COST_BASELINE_COLUMNS
    )
    _ensure_column(store, MART_AFFORDABILITY_RATIOS_TABLE, "state", "VARCHAR")


def refresh_household_overview(store: DuckDBStore) -> int:
    store.execute(f"DELETE FROM {MART_HOUSEHOLD_OVERVIEW_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_HOUSEHOLD_OVERVIEW_TABLE} (
            current_month, cashflow_income, cashflow_expense, cashflow_net,
            utility_cost_total, subscription_total_monthly,
            account_balance_direction, balance_net_change, currency
        )
        -- One row per denomination. A currency appears when any source
        -- observed it; a source that did not observe it contributes numeric
        -- zero, so consumers must read ``currency`` with each amount. Usage with
        -- no bill has no currency and never creates a (zero-bill) row.
        WITH
        latest_month AS (
            SELECT MAX(booking_month) AS booking_month
            FROM {MART_MONTHLY_CASHFLOW_TABLE}
        ),
        latest_cashflow AS (
            SELECT currency, income, expense, net
            FROM {MART_MONTHLY_CASHFLOW_TABLE}
            WHERE booking_month = (SELECT booking_month FROM latest_month)
        ),
        latest_utility AS (
            SELECT currency, SUM(total_cost) AS utility_total
            FROM {MART_UTILITY_COST_TREND_MONTHLY_TABLE}
            WHERE currency IS NOT NULL
              AND billing_month = (
                SELECT MAX(billing_month) FROM {MART_UTILITY_COST_TREND_MONTHLY_TABLE}
                WHERE currency IS NOT NULL
              )
            GROUP BY currency
        ),
        active_subscriptions AS (
            SELECT currency, SUM(monthly_equivalent) AS subscription_total
            FROM {MART_SUBSCRIPTION_SUMMARY_TABLE}
            WHERE status = 'active' AND currency IS NOT NULL
            GROUP BY currency
        ),
        latest_balance AS (
            SELECT normalized_currency AS currency, SUM(amount) AS net_change
            FROM {FACT_TRANSACTION_CURRENT_TABLE}
            WHERE booking_month = (
                SELECT MAX(booking_month) FROM {FACT_TRANSACTION_CURRENT_TABLE}
            )
            GROUP BY normalized_currency
        ),
        currencies AS (
            SELECT currency FROM latest_cashflow
            UNION SELECT currency FROM latest_utility
            UNION SELECT currency FROM active_subscriptions
            UNION SELECT currency FROM latest_balance
        )
        SELECT
            COALESCE((SELECT booking_month FROM latest_month), '')        AS current_month,
            COALESCE(cf.income, 0)                                        AS cashflow_income,
            COALESCE(cf.expense, 0)                                       AS cashflow_expense,
            COALESCE(cf.net, 0)                                           AS cashflow_net,
            COALESCE(lu.utility_total, 0)                                 AS utility_cost_total,
            COALESCE(sub.subscription_total, 0)                           AS subscription_total_monthly,
            CASE
                WHEN COALESCE(lb.net_change, 0) > 0 THEN 'up'
                WHEN COALESCE(lb.net_change, 0) < 0 THEN 'down'
                ELSE 'flat'
            END                                                           AS account_balance_direction,
            COALESCE(lb.net_change, 0)                                    AS balance_net_change,
            c.currency                                                    AS currency
        FROM currencies c
        LEFT JOIN latest_cashflow cf ON cf.currency = c.currency
        LEFT JOIN latest_utility lu ON lu.currency = c.currency
        LEFT JOIN active_subscriptions sub ON sub.currency = c.currency
        LEFT JOIN latest_balance lb ON lb.currency = c.currency
        UNION ALL
        SELECT '', 0, 0, 0, 0, 0, 'flat', 0, ''
        WHERE NOT EXISTS (SELECT 1 FROM currencies)
        ORDER BY currency
        """
    )
    return store.fetchall(f"SELECT COUNT(*) FROM {MART_HOUSEHOLD_OVERVIEW_TABLE}")[0][0]


def get_household_overview(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(f"SELECT * FROM {MART_HOUSEHOLD_OVERVIEW_TABLE}")


def refresh_homelab_roi(store: DuckDBStore) -> int:
    """Summarize homelab service value against workload cost as a reporting mart."""
    store.execute(f"DELETE FROM {MART_HOMELAB_ROI_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_HOMELAB_ROI_TABLE} (
            service_count,
            healthy_service_count,
            needs_attention_count,
            tracked_workload_count,
            healthy_service_share,
            monthly_workload_cost,
            cost_per_healthy_service,
            cost_per_tracked_workload,
            largest_workload_share,
            roi_score,
            roi_state,
            decision_cue
        )
        WITH
        service_summary AS (
            SELECT
                COUNT(*) AS service_count,
                SUM(CASE WHEN state = 'running' THEN 1 ELSE 0 END) AS healthy_service_count,
                SUM(CASE WHEN state <> 'running' THEN 1 ELSE 0 END) AS needs_attention_count
            FROM {MART_SERVICE_HEALTH_CURRENT_TABLE}
        ),
        workload_summary AS (
            SELECT
                COUNT(*) AS tracked_workload_count,
                COALESCE(SUM(est_monthly_cost), 0) AS monthly_workload_cost,
                COALESCE(MAX(est_monthly_cost), 0) AS top_workload_cost
            FROM {MART_WORKLOAD_COST_7D_TABLE}
        ),
        derived AS (
            SELECT
                COALESCE(s.service_count, 0) AS service_count,
                COALESCE(s.healthy_service_count, 0) AS healthy_service_count,
                COALESCE(s.needs_attention_count, 0) AS needs_attention_count,
                COALESCE(w.tracked_workload_count, 0) AS tracked_workload_count,
                CASE
                    WHEN COALESCE(s.service_count, 0) > 0 THEN ROUND(
                        CAST(COALESCE(s.healthy_service_count, 0) AS DECIMAL)
                        / COALESCE(s.service_count, 0),
                        4
                    )
                    ELSE NULL
                END AS healthy_service_share,
                COALESCE(w.monthly_workload_cost, 0) AS monthly_workload_cost,
                CASE
                    WHEN COALESCE(s.healthy_service_count, 0) > 0 THEN ROUND(
                        COALESCE(w.monthly_workload_cost, 0)
                        / COALESCE(s.healthy_service_count, 0),
                        4
                    )
                    ELSE NULL
                END AS cost_per_healthy_service,
                CASE
                    WHEN COALESCE(w.tracked_workload_count, 0) > 0 THEN ROUND(
                        COALESCE(w.monthly_workload_cost, 0)
                        / COALESCE(w.tracked_workload_count, 0),
                        4
                    )
                    ELSE NULL
                END AS cost_per_tracked_workload,
                CASE
                    WHEN COALESCE(w.monthly_workload_cost, 0) > 0 THEN ROUND(
                        COALESCE(w.top_workload_cost, 0)
                        / COALESCE(w.monthly_workload_cost, 0),
                        4
                    )
                    ELSE NULL
                END AS largest_workload_share,
                CASE
                    WHEN COALESCE(w.monthly_workload_cost, 0) > 0 THEN ROUND(
                        CAST(COALESCE(s.healthy_service_count, 0) AS DECIMAL)
                        / COALESCE(w.monthly_workload_cost, 0),
                        6
                    )
                    ELSE NULL
                END AS roi_score
            FROM service_summary s
            CROSS JOIN workload_summary w
        )
        SELECT
            service_count,
            healthy_service_count,
            needs_attention_count,
            tracked_workload_count,
            healthy_service_share,
            monthly_workload_cost,
            cost_per_healthy_service,
            cost_per_tracked_workload,
            largest_workload_share,
            roi_score,
            CASE
                WHEN service_count = 0 AND tracked_workload_count = 0 THEN 'empty'
                WHEN service_count = 0 THEN 'needs_action'
                WHEN tracked_workload_count = 0 THEN 'warning'
                WHEN needs_attention_count > 0 THEN 'needs_action'
                WHEN largest_workload_share >= 0.5 THEN 'warning'
                WHEN healthy_service_share IS NOT NULL AND healthy_service_share < 0.8 THEN 'warning'
                ELSE 'good'
            END AS roi_state,
            CASE
                WHEN service_count = 0 AND tracked_workload_count = 0 THEN
                    'No homelab service or workload rows are published yet.'
                WHEN service_count = 0 THEN
                    'No homelab services are published yet.'
                WHEN tracked_workload_count = 0 THEN
                    'No workload cost rows are published yet.'
                WHEN needs_attention_count > 0 THEN
                    'Healthy services are outnumbered by services needing attention.'
                WHEN largest_workload_share >= 0.5 THEN
                    'One workload dominates the current cost profile.'
                WHEN healthy_service_share IS NOT NULL AND healthy_service_share < 0.8 THEN
                    'Most services are healthy, but the overall value ratio is still soft.'
                ELSE
                    'Operational value is broadly aligned with the current workload cost base.'
            END AS decision_cue
        FROM derived
        """
    )
    return store.fetchall(f"SELECT COUNT(*) FROM {MART_HOMELAB_ROI_TABLE}")[0][0]


def get_homelab_roi(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(f"SELECT * FROM {MART_HOMELAB_ROI_TABLE}")


def refresh_open_attention_items(store: DuckDBStore) -> int:
    if store.fetchall(
        f"SELECT COUNT(*) FROM {MART_UPCOMING_FIXED_COSTS_30D_TABLE} WHERE charge_id IS NULL"
    )[0][0]:
        raise ValueError("Refresh subscription summary and upcoming fixed costs before attention items")
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
            SELECT DISTINCT
                'review_' || contract_id || '_' || reason        AS item_id,
                'contract_review'                                AS item_type,
                'Review contract: ' || provider                  AS title,
                reason                                           AS detail,
                score                                            AS severity,
                'utilities'                                      AS source_domain
            FROM {MART_CONTRACT_REVIEW_CANDIDATES_TABLE}
        ),
        upcoming_renewals AS (
            SELECT DISTINCT
                'renewal_' || contract_id
                    || '_' || CAST(renewal_date AS VARCHAR)      AS item_id,
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
                'upcoming_' || charge_id
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
             change_pct, direction, currency)
        WITH
        -- Changes compare amounts of one denomination only; each currency is
        -- ranked on its own and labelled in the description when the
        -- household has more than one.
        cashflow_changes AS (
            SELECT
                'cashflow_net'                          AS change_type,
                booking_month                           AS period,
                'Net cashflow'                          AS description,
                net                                     AS current_value,
                LAG(net) OVER (
                    PARTITION BY currency ORDER BY booking_month
                )                                       AS previous_value,
                currency
            FROM {MART_MONTHLY_CASHFLOW_TABLE}
        ),
        category_changes AS (
            SELECT
                'category_spend'                        AS change_type,
                booking_month                           AS period,
                'Spend: ' || counterparty_name          AS description,
                total_expense                           AS current_value,
                LAG(total_expense) OVER (
                    PARTITION BY counterparty_name, currency
                    ORDER BY booking_month
                )                                       AS previous_value,
                currency
            FROM {MART_SPEND_BY_CATEGORY_MONTHLY_TABLE}
        ),
        utility_changes AS (
            SELECT
                'utility_cost'                          AS change_type,
                billing_month                           AS period,
                'Utility: ' || utility_type             AS description,
                total_cost                              AS current_value,
                LAG(total_cost) OVER (
                    PARTITION BY utility_type, currency
                    ORDER BY billing_month
                )                                       AS previous_value,
                currency
            FROM {MART_UTILITY_COST_TREND_MONTHLY_TABLE}
            WHERE currency IS NOT NULL
        ),
        all_changes AS (
            SELECT * FROM cashflow_changes  WHERE previous_value IS NOT NULL
            UNION ALL
            SELECT * FROM category_changes  WHERE previous_value IS NOT NULL
            UNION ALL
            SELECT * FROM utility_changes   WHERE previous_value IS NOT NULL
        ),
        currency_count AS (
            SELECT COUNT(DISTINCT currency) AS n FROM all_changes
        ),
        ranked AS (
            SELECT
                change_type,
                period,
                CASE
                    WHEN (SELECT n FROM currency_count) > 1
                    THEN description || ' (' || currency || ')'
                    ELSE description
                END AS description,
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
                currency,
                ROW_NUMBER() OVER (
                    PARTITION BY change_type, currency
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
            change_pct, direction, currency
        FROM ranked
        WHERE rn = 1
        ORDER BY ABS(COALESCE(change_pct, 0)) DESC, currency, change_type
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
        -- Every baseline is computed per denomination (one row per currency).
        -- A baseline with no observation at all keeps a single numeric zero
        -- row with an empty currency, as before.
        WITH
        recent_cashflow AS (
            SELECT currency, expense, booking_month
            FROM (
                SELECT
                    currency, expense, booking_month,
                    ROW_NUMBER() OVER (
                        PARTITION BY currency ORDER BY booking_month DESC
                    ) AS rn
                FROM {MART_MONTHLY_CASHFLOW_TABLE}
            ) ranked_cashflow
            WHERE rn <= 3
        ),
        active_subs AS (
            SELECT currency, SUM(monthly_equivalent) AS total
            FROM {MART_SUBSCRIPTION_SUMMARY_TABLE}
            WHERE status = 'active' AND currency IS NOT NULL
            GROUP BY currency
        ),
        recent_utility AS (
            SELECT currency, total_cost, billing_month
            FROM (
                SELECT
                    currency,
                    SUM(total_cost) AS total_cost,
                    billing_month,
                    ROW_NUMBER() OVER (
                        PARTITION BY currency ORDER BY billing_month DESC
                    ) AS rn
                FROM {MART_UTILITY_COST_TREND_MONTHLY_TABLE}
                WHERE currency IS NOT NULL
                GROUP BY currency, billing_month
            ) ranked_utility
            WHERE rn <= 3
        ),
        account_monthly AS (
            SELECT
                booking_month,
                normalized_currency AS currency,
                SUM(SUM(amount)) OVER (
                    PARTITION BY account_id, normalized_currency
                    ORDER BY booking_month
                ) AS cumulative_balance
            FROM {FACT_TRANSACTION_CURRENT_TABLE}
            GROUP BY booking_month, account_id, normalized_currency
        ),
        latest_balance AS (
            SELECT
                currency,
                SUM(cumulative_balance) AS total,
                MAX(booking_month)      AS month
            FROM account_monthly
            WHERE booking_month = (SELECT MAX(booking_month) FROM account_monthly)
            GROUP BY currency
        )
        SELECT
            'monthly_spend'                          AS baseline_type,
            'Average monthly expense (last 3 months)' AS description,
            ROUND(AVG(expense), 2)                   AS value,
            MAX(booking_month)                       AS period_label,
            currency
        FROM recent_cashflow
        GROUP BY currency
        UNION ALL
        SELECT 'monthly_spend', 'Average monthly expense (last 3 months)', 0, '', ''
        WHERE NOT EXISTS (SELECT 1 FROM recent_cashflow)
        UNION ALL
        SELECT
            'recurring_costs',
            'Total active monthly subscriptions',
            ROUND(total, 2),
            STRFTIME(CURRENT_DATE, '%Y-%m'),
            currency
        FROM active_subs
        UNION ALL
        SELECT
            'recurring_costs', 'Total active monthly subscriptions', 0,
            STRFTIME(CURRENT_DATE, '%Y-%m'), ''
        WHERE NOT EXISTS (SELECT 1 FROM active_subs)
        UNION ALL
        SELECT
            'utility_baseline',
            'Average monthly utility cost (last 3 months)',
            ROUND(AVG(total_cost), 2),
            MAX(billing_month),
            currency
        FROM recent_utility
        GROUP BY currency
        UNION ALL
        SELECT 'utility_baseline', 'Average monthly utility cost (last 3 months)', 0, '', ''
        WHERE NOT EXISTS (SELECT 1 FROM recent_utility)
        UNION ALL
        SELECT
            'account_balance',
            'Current account balance',
            ROUND(total, 2),
            month,
            currency
        FROM latest_balance
        UNION ALL
        SELECT 'account_balance', 'Current account balance', 0, '', ''
        WHERE NOT EXISTS (SELECT 1 FROM latest_balance)
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_CURRENT_OPERATING_BASELINE_TABLE}"
    )[0][0]


def get_current_operating_baseline(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_CURRENT_OPERATING_BASELINE_TABLE}"
        " ORDER BY baseline_type, currency"
    )


def refresh_household_cost_model(store: DuckDBStore) -> int:
    """Aggregate cross-domain monthly costs into a unified cost model mart."""
    store.execute(f"DELETE FROM {MART_HOUSEHOLD_COST_MODEL_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_HOUSEHOLD_COST_MODEL_TABLE}
            (period_label, cost_type, amount, source_domain, currency)
        WITH
        -- Finance: spend by category mapped to cost types
        category_costs AS (
            SELECT
                booking_month                                      AS period_label,
                CASE LOWER(COALESCE(category, counterparty_name))
                    WHEN 'groceries'     THEN 'food'
                    WHEN 'food'          THEN 'food'
                    WHEN 'transport'     THEN 'transport'
                    WHEN 'utilities'     THEN 'utilities'
                    WHEN 'housing'       THEN 'housing'
                    ELSE 'discretionary'
                END                                                AS cost_type,
                SUM(total_expense)                                 AS amount,
                'finance'                                          AS source_domain,
                currency                                           AS currency
            FROM {MART_SPEND_BY_CATEGORY_MONTHLY_TABLE}
            WHERE total_expense > 0
            GROUP BY booking_month, currency,
                CASE LOWER(COALESCE(category, counterparty_name))
                    WHEN 'groceries'     THEN 'food'
                    WHEN 'food'          THEN 'food'
                    WHEN 'transport'     THEN 'transport'
                    WHEN 'utilities'     THEN 'utilities'
                    WHEN 'housing'       THEN 'housing'
                    ELSE 'discretionary'
                END
        ),
        -- Subscriptions: recurring fixed costs
        subscription_costs AS (
            SELECT
                STRFTIME(CURRENT_DATE, '%Y-%m')                    AS period_label,
                'subscriptions'                                    AS cost_type,
                SUM(monthly_equivalent)                            AS amount,
                'subscriptions'                                    AS source_domain,
                currency                                           AS currency
            FROM {MART_SUBSCRIPTION_SUMMARY_TABLE}
            WHERE status = 'active' AND monthly_equivalent > 0
            GROUP BY currency
        ),
        -- Utilities: monthly cost by type
        utility_costs AS (
            SELECT
                billing_month                                      AS period_label,
                'utilities'                                        AS cost_type,
                SUM(total_cost)                                    AS amount,
                'utilities'                                        AS source_domain,
                currency                                           AS currency
            FROM {MART_UTILITY_COST_TREND_MONTHLY_TABLE}
            WHERE total_cost > 0 AND currency IS NOT NULL
            GROUP BY billing_month, currency
        ),
        -- Loans: monthly payment (most recent)
        loan_costs AS (
            SELECT
                STRFTIME(CURRENT_DATE, '%Y-%m')                    AS period_label,
                'loans'                                            AS cost_type,
                SUM(monthly_payment)                               AS amount,
                'loans'                                            AS source_domain,
                currency                                           AS currency
            FROM {MART_LOAN_OVERVIEW_TABLE}
            WHERE monthly_payment > 0
            GROUP BY currency
        )
        SELECT * FROM category_costs   WHERE amount > 0
        UNION ALL
        SELECT * FROM subscription_costs WHERE amount > 0
        UNION ALL
        SELECT * FROM utility_costs    WHERE amount > 0
        UNION ALL
        SELECT * FROM loan_costs       WHERE amount > 0
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_HOUSEHOLD_COST_MODEL_TABLE}"
    )[0][0]


def get_household_cost_model(
    store: DuckDBStore,
    *,
    period_label: str | None = None,
    cost_type: str | None = None,
) -> list[dict[str, Any]]:
    conditions = []
    params: list[Any] = []
    if period_label is not None:
        conditions.append("period_label = ?")
        params.append(period_label)
    if cost_type is not None:
        conditions.append("cost_type = ?")
        params.append(cost_type)
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_HOUSEHOLD_COST_MODEL_TABLE}{where}"
        " ORDER BY period_label, cost_type",
        params,
    )


def refresh_cost_trend_12m(store: DuckDBStore) -> int:
    """12-month rolling cost trend with MoM change per cost type."""
    store.execute(f"DELETE FROM {MART_COST_TREND_12M_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_COST_TREND_12M_TABLE}
            (period_label, cost_type, amount, prev_amount, change_pct, currency)
        WITH
        recent AS (
            SELECT
                period_label,
                cost_type,
                SUM(amount)             AS amount,
                currency
            FROM {MART_HOUSEHOLD_COST_MODEL_TABLE}
            WHERE period_label >= STRFTIME(CURRENT_DATE - INTERVAL '12 months', '%Y-%m')
            GROUP BY period_label, cost_type, currency
        ),
        with_lag AS (
            SELECT
                period_label,
                cost_type,
                amount,
                LAG(amount) OVER (
                    PARTITION BY cost_type, currency ORDER BY period_label
                ) AS prev_amount,
                currency
            FROM recent
        )
        SELECT
            period_label,
            cost_type,
            amount,
            prev_amount,
            CASE
                WHEN prev_amount IS NOT NULL AND prev_amount <> 0
                THEN ROUND((amount - prev_amount) / ABS(prev_amount) * 100, 2)
                ELSE NULL
            END AS change_pct,
            currency
        FROM with_lag
        ORDER BY period_label, cost_type, currency
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_COST_TREND_12M_TABLE}"
    )[0][0]


def get_cost_trend_12m(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_COST_TREND_12M_TABLE}"
        " ORDER BY period_label, cost_type, currency"
    )


def refresh_affordability_ratios(store: DuckDBStore) -> int:
    """Compute housing, total-cost, and debt-service affordability ratios."""
    store.execute(f"DELETE FROM {MART_AFFORDABILITY_RATIOS_TABLE}")
    # Ratios divide amounts, so numerator and income must share a denomination:
    # compute the three ratios once per currency that has income in the latest
    # month (one pass with an empty currency when there is no cashflow).
    currencies = [
        str(row[0])
        for row in store.fetchall(
            f"SELECT DISTINCT currency FROM {MART_MONTHLY_CASHFLOW_TABLE}"
            f" WHERE booking_month = (SELECT MAX(booking_month) FROM {MART_MONTHLY_CASHFLOW_TABLE})"
            " AND currency IS NOT NULL ORDER BY currency"
        )
    ] or [""]
    for currency in currencies:
        _insert_affordability_ratios(store, currency)
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_AFFORDABILITY_RATIOS_TABLE}"
    )[0][0]


def _insert_affordability_ratios(store: DuckDBStore, currency: str) -> None:
    store.execute(
        f"""
        INSERT INTO {MART_AFFORDABILITY_RATIOS_TABLE}
            (ratio_name, numerator, denominator, ratio, period_label, assessment, state, currency)
        WITH
        latest_cashflow AS (
            SELECT income, booking_month, currency
            FROM {MART_MONTHLY_CASHFLOW_TABLE}
            WHERE currency = ?
              AND booking_month = (SELECT MAX(booking_month) FROM {MART_MONTHLY_CASHFLOW_TABLE})
            LIMIT 1
        ),
        housing_cost AS (
            SELECT
                COALESCE(SUM(amount), 0) AS amount
            FROM {MART_HOUSEHOLD_COST_MODEL_TABLE}
            WHERE cost_type IN ('housing', 'loans')
              AND currency = ?
              AND period_label = (
                SELECT booking_month FROM {MART_MONTHLY_CASHFLOW_TABLE}
                ORDER BY booking_month DESC LIMIT 1
              )
        ),
        total_cost AS (
            SELECT COALESCE(SUM(amount), 0) AS amount
            FROM {MART_HOUSEHOLD_COST_MODEL_TABLE}
            WHERE currency = ?
              AND period_label = (
                SELECT booking_month FROM {MART_MONTHLY_CASHFLOW_TABLE}
                ORDER BY booking_month DESC LIMIT 1
              )
        ),
        debt_cost AS (
            SELECT COALESCE(SUM(monthly_payment), 0) AS amount
            FROM {MART_LOAN_OVERVIEW_TABLE}
            WHERE currency = ?
        )
        SELECT
            'housing_to_income'                                        AS ratio_name,
            COALESCE((SELECT amount FROM housing_cost), 0)             AS numerator,
            COALESCE((SELECT income FROM latest_cashflow), 0)          AS denominator,
            CASE
                WHEN COALESCE((SELECT income FROM latest_cashflow), 0) = 0 THEN 0
                ELSE ROUND(
                    COALESCE((SELECT amount FROM housing_cost), 0) /
                    (SELECT income FROM latest_cashflow), 4
                )
            END                                                        AS ratio,
            COALESCE((SELECT booking_month FROM latest_cashflow), '')  AS period_label,
            CASE
                WHEN COALESCE((SELECT income FROM latest_cashflow), 0) = 0 THEN 'caution'
                WHEN COALESCE((SELECT amount FROM housing_cost), 0) /
                     NULLIF((SELECT income FROM latest_cashflow), 0) <= 0.30 THEN 'healthy'
                WHEN COALESCE((SELECT amount FROM housing_cost), 0) /
                     NULLIF((SELECT income FROM latest_cashflow), 0) <= 0.40 THEN 'caution'
                ELSE 'critical'
            END                                                        AS assessment,
            CASE
                WHEN COALESCE((SELECT income FROM latest_cashflow), 0) = 0 THEN 'warning'
                WHEN COALESCE((SELECT amount FROM housing_cost), 0) /
                     NULLIF((SELECT income FROM latest_cashflow), 0) <= 0.30 THEN 'good'
                WHEN COALESCE((SELECT amount FROM housing_cost), 0) /
                     NULLIF((SELECT income FROM latest_cashflow), 0) <= 0.40 THEN 'warning'
                ELSE 'needs_action'
            END                                                        AS state,
            COALESCE((SELECT currency FROM latest_cashflow), '')       AS currency
        UNION ALL
        SELECT
            'total_cost_to_income',
            COALESCE((SELECT amount FROM total_cost), 0),
            COALESCE((SELECT income FROM latest_cashflow), 0),
            CASE
                WHEN COALESCE((SELECT income FROM latest_cashflow), 0) = 0 THEN 0
                ELSE ROUND(
                    COALESCE((SELECT amount FROM total_cost), 0) /
                    (SELECT income FROM latest_cashflow), 4
                )
            END,
            COALESCE((SELECT booking_month FROM latest_cashflow), ''),
            CASE
                WHEN COALESCE((SELECT income FROM latest_cashflow), 0) = 0 THEN 'caution'
                WHEN COALESCE((SELECT amount FROM total_cost), 0) /
                     NULLIF((SELECT income FROM latest_cashflow), 0) <= 0.60 THEN 'healthy'
                WHEN COALESCE((SELECT amount FROM total_cost), 0) /
                     NULLIF((SELECT income FROM latest_cashflow), 0) <= 0.80 THEN 'caution'
                ELSE 'critical'
            END,
            CASE
                WHEN COALESCE((SELECT income FROM latest_cashflow), 0) = 0 THEN 'warning'
                WHEN COALESCE((SELECT amount FROM total_cost), 0) /
                     NULLIF((SELECT income FROM latest_cashflow), 0) <= 0.60 THEN 'good'
                WHEN COALESCE((SELECT amount FROM total_cost), 0) /
                     NULLIF((SELECT income FROM latest_cashflow), 0) <= 0.80 THEN 'warning'
                ELSE 'needs_action'
            END,
            COALESCE((SELECT currency FROM latest_cashflow), '')
        UNION ALL
        SELECT
            'debt_service_ratio',
            COALESCE((SELECT amount FROM debt_cost), 0),
            COALESCE((SELECT income FROM latest_cashflow), 0),
            CASE
                WHEN COALESCE((SELECT income FROM latest_cashflow), 0) = 0 THEN 0
                ELSE ROUND(
                    COALESCE((SELECT amount FROM debt_cost), 0) /
                    (SELECT income FROM latest_cashflow), 4
                )
            END,
            COALESCE((SELECT booking_month FROM latest_cashflow), ''),
            CASE
                WHEN COALESCE((SELECT income FROM latest_cashflow), 0) = 0 THEN 'caution'
                WHEN COALESCE((SELECT amount FROM debt_cost), 0) /
                     NULLIF((SELECT income FROM latest_cashflow), 0) <= 0.36 THEN 'healthy'
                WHEN COALESCE((SELECT amount FROM debt_cost), 0) /
                     NULLIF((SELECT income FROM latest_cashflow), 0) <= 0.50 THEN 'caution'
                ELSE 'critical'
            END,
            CASE
                WHEN COALESCE((SELECT income FROM latest_cashflow), 0) = 0 THEN 'warning'
                WHEN COALESCE((SELECT amount FROM debt_cost), 0) /
                     NULLIF((SELECT income FROM latest_cashflow), 0) <= 0.36 THEN 'good'
                WHEN COALESCE((SELECT amount FROM debt_cost), 0) /
                     NULLIF((SELECT income FROM latest_cashflow), 0) <= 0.50 THEN 'warning'
                ELSE 'needs_action'
            END,
            COALESCE((SELECT currency FROM latest_cashflow), '')
        """,
        [currency] * 4,
    )


def get_affordability_ratios(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_AFFORDABILITY_RATIOS_TABLE} ORDER BY ratio_name, currency"
    )


def refresh_recurring_cost_baseline(store: DuckDBStore) -> int:
    """Union all confirmed recurring costs: subscriptions, utility fixed charges, loan payments."""
    store.execute(f"DELETE FROM {MART_RECURRING_COST_BASELINE_TABLE}")
    store.execute(
        f"""
        INSERT INTO {MART_RECURRING_COST_BASELINE_TABLE}
            (cost_source, counterparty_or_contract, monthly_amount, confidence,
             last_occurrence, currency)
        WITH
        subs AS (
            SELECT
                'subscription'              AS cost_source,
                contract_name               AS counterparty_or_contract,
                monthly_equivalent          AS monthly_amount,
                'confirmed'                 AS confidence,
                CAST(start_date AS VARCHAR) AS last_occurrence,
                currency
            FROM {MART_SUBSCRIPTION_SUMMARY_TABLE}
            WHERE status = 'active' AND monthly_equivalent > 0
        ),
        loans AS (
            SELECT
                'loan_payment'              AS cost_source,
                loan_name                   AS counterparty_or_contract,
                monthly_payment             AS monthly_amount,
                'confirmed'                 AS confidence,
                NULL                        AS last_occurrence,
                currency
            FROM {MART_LOAN_OVERVIEW_TABLE}
            WHERE monthly_payment > 0
        )
        SELECT * FROM subs
        UNION ALL
        SELECT * FROM loans
        ORDER BY cost_source, counterparty_or_contract
        """
    )
    return store.fetchall(
        f"SELECT COUNT(*) FROM {MART_RECURRING_COST_BASELINE_TABLE}"
    )[0][0]


def get_recurring_cost_baseline(store: DuckDBStore) -> list[dict[str, Any]]:
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_RECURRING_COST_BASELINE_TABLE}"
        " ORDER BY cost_source, counterparty_or_contract"
    )
