from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from tests.test_currency_consumer_regressions import _bill, _client, _usage


def _card_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {card["domain_key"]: card for card in payload["cards"]}


def _service(service_id: str, day: int, state: str, criticality: str = "standard") -> dict:
    return {
        "service_id": service_id,
        "service_name": service_id,
        "recorded_at": f"2026-06-{day:02d}T12:00:00+00:00",
        "state": state,
        "criticality": criticality,
    }


def test_domain_cards_report_own_observed_headlines_trends_and_attention(tmp_path: Path) -> None:
    client, ts = _client(tmp_path)
    ts.load_transactions(
        [
            {
                "booked_at": f"{month}-04T12:00:00+00:00",
                "account_id": "current",
                "counterparty_name": "Debtor",
                "amount": amount,
                "currency": currency,
                "description": "Observed payment",
            }
            for month, amount, currency in (
                ("2026-01", "20", "EUR"),
                ("2026-04", "40", "EUR"),
                ("2026-03", "60", "USD"),
            )
        ],
        run_id="money",
    )
    ts.load_bills([_bill("m1", "0", "EUR"), _bill("m2", "30", "USD")], run_id="bills")
    ts.load_utility_usage([_usage("unbilled", "40")], run_id="usage")
    ts.load_service_health(
        [_service("a", 1, "running"), _service("b", 1, "running")], run_id="old"
    )
    ts.load_service_health(
        [
            _service("a", 2, "running", "critical"),
            _service("a", 3, "stopped", "critical"),
            _service("b", 3, "degraded", "background"),
        ],
        run_id="new",
    )
    ts.refresh_publications([
        "mart_monthly_cashflow", "mart_utility_cost_summary", "mart_utility_cost_trend_monthly",
        "mart_service_health_current", "mart_service_health_history",
    ])
    table = "mart_open_attention_items"
    ts.store.insert_rows(table, [
        {
            "item_id": key, "item_type": "anomaly", "title": label,
            "detail": "", "severity": severity, "source_domain": domain,
        }
        for key, label, severity, domain in (
            ("a", "Finance lower", 1, "finance"),
            ("b", "Finance highest", 3, "finance"),
            ("c", "Utilities only", 2, "utilities"),
        )
    ])

    result = client.get("/reports/domain-cards")
    assert result.status_code == 200, result.text
    cards = _card_map(result.json())
    assert set(cards) == {"finance", "utilities", "homelab"}
    finance = cards["finance"]
    assert [(p["period"], p["unit"], Decimal(p["value"])) for p in finance["headline"]] == [
        ("2026-04", "EUR", 40), ("2026-03", "USD", 60),
    ]
    assert [(p["period"], p["unit"], Decimal(p["value"])) for p in finance["trend"]] == [
        ("2026-01", "EUR", 20), ("2026-04", "EUR", 40),
    ]
    assert finance["attention"]["key"] == "b"
    utilities = cards["utilities"]
    assert [(p["unit"], Decimal(p["value"])) for p in utilities["headline"]] == [
        ("EUR", 0), ("USD", 30),
    ]
    assert utilities["trend_state"] == "insufficient_history"
    assert utilities["attention"]["key"] == "c"
    homelab = cards["homelab"]
    assert homelab["headline"][0]["value"] == 2
    assert homelab["headline"][0]["known_count"] == 2
    assert [(p["run_id"], p["value"], p["known_count"]) for p in homelab["trend"]] == [
        ("old", 0, 2), ("new", 2, 2),
    ]
    assert homelab["attention"]["key"] == "a"
    assert homelab["attention"]["priority"] == 3


def test_domain_cards_distinguish_empty_unknown_and_noncomparable(tmp_path: Path) -> None:
    client, ts = _client(tmp_path)

    def read() -> dict[str, dict[str, Any]]:
        response = client.get("/reports/domain-cards")
        assert response.status_code == 200, response.text
        return _card_map(response.json())

    empty = read()
    assert all(card["metric_state"] == "empty" for card in empty.values())
    assert all(card["attention_state"] == "empty" for card in empty.values())
    ts.load_utility_usage([_usage("usage-only", "12")], run_id="usage")
    ts.load_service_health([_service("a", 1, "unknown")], run_id="unknown")
    ts.refresh_publications([
        "mart_utility_cost_summary", "mart_utility_cost_trend_monthly",
        "mart_service_health_current", "mart_service_health_history",
    ])
    cards = read()
    assert cards["utilities"]["headline"] == []
    assert cards["utilities"]["metric_state"] == "empty"
    assert cards["homelab"]["metric_state"] == "unavailable"
    assert cards["homelab"]["headline"] == []

    ts.load_service_health([_service("a", 2, "running")], run_id="a-only")
    ts.load_service_health([_service("b", 3, "running")], run_id="b-only")
    ts.refresh_publications(["mart_service_health_current", "mart_service_health_history"])
    homelab = read()["homelab"]
    assert homelab["headline"][0]["value"] == 0
    assert homelab["headline"][0]["known_count"] == 2
    assert homelab["trend_state"] == "insufficient_history"
    assert homelab["trend"] == []
    assert homelab["attention_state"] == "empty"
