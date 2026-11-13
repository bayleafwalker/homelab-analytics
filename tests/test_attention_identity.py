from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from packages.domains.finance.pipelines.subscription_models import subscription_charge_id
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.migration_runner import apply_pending_duckdb_migrations

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations/duckdb"


def _seed(s: TransformationService) -> tuple[set[str], list[str]]:
    today = date.today()
    # Seven days apart gives the same next weekly occurrence, with distinct IDs.
    starts = [today - timedelta(days=14), today - timedelta(days=7)]
    subscriptions = [
        {"contract_id": "sub", "service_name": "Same", "provider": "P",
         "billing_cycle": "weekly", "amount": "10", "currency": "EUR",
         "start_date": str(start), "end_date": None}
        for start in starts
    ]
    s.load_subscriptions(subscriptions, run_id="subscriptions")
    prices = [
        {"contract_id": "utility", "contract_name": "Electric", "provider": "Power",
         "contract_type": "electricity", "price_component": component,
         "billing_cycle": "monthly", "unit_price": "1", "currency": "EUR",
         "quantity_unit": "kWh", "valid_from": str(today - timedelta(days=400)),
         "valid_to": str(today + timedelta(days=days))}
        for component, days in [("energy", 10), ("transfer", 10), ("tax", 20)]
    ]
    prices.append({**prices[0], "contract_id": "other", "contract_name": "Other",
                   "price_component": "energy"})
    s.load_contract_prices(prices, run_id="prices")
    s.load_transactions([
        {"booked_at": str(today), "account_id": "bank", "counterparty_name": "New",
         "amount": "-1000", "currency": "EUR", "description": "purchase"},
    ], run_id="transactions")
    return ({subscription_charge_id("Same", "weekly", str(start)) for start in starts},
            [str(today + timedelta(days=n)) for n in (10, 20)])


def _refresh(s: TransformationService) -> None:
    s.refresh_publications([
        "mart_subscription_summary", "mart_upcoming_fixed_costs_30d",
        "mart_contract_price_current", "mart_contract_review_candidates",
        "mart_contract_renewal_watchlist", "mart_transaction_anomalies_current",
        "mart_open_attention_items",
    ])


def test_identity_survives_reporting_and_exact_component_duplicates_collapse() -> None:
    s = TransformationService(DuckDBStore.memory())
    ids, dates = _seed(s)
    _refresh(s)
    reporting = ReportingService(s)
    summary = reporting.get_subscription_summary()
    upcoming = reporting.get_upcoming_fixed_costs_30d()
    assert {r["charge_id"] for r in summary} == ids
    assert {r["charge_id"] for r in upcoming} == ids
    assert len({(r["contract_name"], r["expected_date"], r["expected_amount"]) for r in upcoming}) == 1
    attention = reporting.get_open_attention_items()
    payments = [r for r in attention if r["item_type"] == "upcoming_cost"]
    assert {r["item_id"] for r in payments} == {f"upcoming_{i}_{date.today()}" for i in ids}
    reviews = [r for r in attention if r["item_type"] == "contract_review"
               and r["item_id"].startswith("review_utility_")]
    assert len(reviews) == 1
    renewals = [r for r in attention if r["item_type"] == "contract_renewal"
                and r["item_id"].startswith("renewal_utility_")]
    assert {r["item_id"] for r in renewals} == {f"renewal_utility_{d}" for d in dates}
    assert len(renewals) == 2
    assert s.store.fetchall("SELECT COUNT(*) FROM fact_contract_price")[0][0] == 4
    anomalies = s.store.fetchall_dicts("SELECT transaction_id FROM mart_transaction_anomalies_current")
    assert anomalies
    assert {r["item_id"] for r in attention if r["item_type"] == "anomaly"} == {
        f"anomaly_{r['transaction_id']}" for r in anomalies
    }
    assert {r["source_domain"] for r in attention} == {"finance", "utilities"}


def test_populated_prechange_marts_require_canonical_rebuild(tmp_path: Path) -> None:
    old = tmp_path / "old"
    old.mkdir()
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        if migration.name < "0019":
            (old / migration.name).write_text(migration.read_text())
    store = DuckDBStore.memory()
    apply_pending_duckdb_migrations(store.connection, old)
    s = TransformationService(store)
    ids, _ = _seed(s)
    store.execute("""INSERT INTO mart_subscription_summary
        SELECT contract_id, contract_name, provider, billing_cycle, amount, currency,
               start_date, end_date, amount, 'active' FROM fact_subscription_charge""")
    store.execute("""INSERT INTO mart_upcoming_fixed_costs_30d
        SELECT contract_name, provider, billing_cycle, amount, currency, CURRENT_DATE, 'high'
        FROM fact_subscription_charge""")
    assert apply_pending_duckdb_migrations(store.connection, MIGRATIONS) == [
        "0019_subscription_charge_identity"
    ]
    assert all(r["charge_id"] is None for r in ReportingService(s).get_upcoming_fixed_costs_30d())
    with pytest.raises(ValueError, match="Refresh subscription summary"):
        s.refresh_publications(["mart_open_attention_items"])
    _refresh(s)
    assert {r["charge_id"] for r in ReportingService(s).get_upcoming_fixed_costs_30d()} == ids
