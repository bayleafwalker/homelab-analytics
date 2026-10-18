"""Second decision domain: keep or switch the electricity contract."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.domains.utilities.energy_contract_decision import (
    ENERGY_CONTRACT_DECISION,
    ENERGY_CONTRACT_VERDICTS,
    assess_energy_contract_review,
)
from packages.pipelines.household_decisions import (
    DECISION_DEFINITIONS,
    get_decision_definition,
)
from packages.pipelines.household_reporting import PUBLICATION_RELATIONS
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository

ROOT = Path(__file__).resolve().parents[1]
KEY = ENERGY_CONTRACT_DECISION.decision_key


def _price(contract_id: str, component: str, price: str, **overrides: Any) -> dict[str, Any]:
    row = {
        "contract_id": contract_id,
        "contract_name": contract_id.title(),
        "provider": f"{contract_id}-provider",
        "contract_type": "electricity",
        "price_component": component,
        "billing_cycle": "per_kwh" if component == "energy" else "monthly",
        "unit_price": price,
        "currency": "EUR",
        "quantity_unit": "kWh" if component == "energy" else None,
        "valid_from": "2025-01-01",
        "valid_to": None,
        "status": "active",
    }
    row.update(overrides)
    return row


def _prices(alternative_energy: str = "0.0600") -> list[dict[str, Any]]:
    return [
        _price("current", "energy", "0.0825"),
        _price("current", "base_fee", "5.99"),
        _price("quote", "energy", alternative_energy),
        _price("quote", "base_fee", "3.99"),
    ]


def _usage(months: int = 12, kwh: str = "400") -> list[dict[str, Any]]:
    return [
        {
            "billing_month": f"2025-{index:02d}" if index <= 12 else f"2026-{index - 12:02d}",
            "utility_type": "electricity",
            "usage_amount": kwh,
            "total_cost": "60.00",
        }
        for index in range(1, months + 1)
    ]


def _assess(**overrides: Any) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "contract_id": "current",
        "price_rows": _prices(),
        "review_candidates": [],
        "renewal_watchlist": [],
        "cost_trend_rows": _usage(),
    }
    inputs.update(overrides)
    return assess_energy_contract_review(**inputs)


def test_definition_is_registered_on_the_generic_ledger() -> None:
    assert get_decision_definition(KEY) is ENERGY_CONTRACT_DECISION
    assert set(DECISION_DEFINITIONS) == {"kotiakku_battery_plan_review", KEY}
    for key in (
        ENERGY_CONTRACT_DECISION.subject_publication_key,
        *ENERGY_CONTRACT_DECISION.supporting_publication_keys,
    ):
        assert key in PUBLICATION_RELATIONS
    assert any(option.is_non_decision for option in ENERGY_CONTRACT_DECISION.outcome_options)
    assert ENERGY_CONTRACT_DECISION.observation_window.kind == "days_after_decision"


def test_cheaper_alternative_is_an_estimate_not_a_switch_instruction() -> None:
    assessment = _assess()
    assert assessment["verdict"] == "alternative_estimated_cheaper"
    assert assessment["reason_codes"] == []
    # 4800 kWh * 0.0825 + 12 * 5.99 vs 4800 * 0.06 + 12 * 3.99
    assert assessment["estimated_annual_cost_current_eur"] == "467.88"
    assert assessment["estimated_annual_cost_best_alternative_eur"] == "335.88"
    assert assessment["estimated_annual_difference_eur"] == "132"
    assert assessment["best_alternative_contract_id"] == "quote"
    assert assessment["recommendation_scope"] == "review_only"
    assert assessment["actuation_authorized"] is False
    assert assessment["value_disclosures"]["estimated_annual_difference_eur"] == "estimated"
    assert any("not a market quote" in item for item in assessment["limitations"])


def test_competitive_contract_within_threshold() -> None:
    assessment = _assess(price_rows=_prices(alternative_energy="0.0870"))
    assert assessment["verdict"] == "current_contract_competitive"


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"cost_trend_rows": _usage(months=11)}, "usage_history_incomplete"),
        ({"price_rows": _prices()[:2]}, "no_comparable_alternative"),
        (
            {"price_rows": [*_prices()[:2], _price("quote", "energy", "0.05", currency="SEK")]},
            "currency_or_unit_mismatch",
        ),
        ({"price_rows": [_price("current", "base_fee", "5.99"), *_prices()[2:]]}, "energy_price_missing"),
        ({"contract_id": "unknown"}, "contract_not_found"),
    ],
)
def test_insufficient_evidence_guard(overrides: dict[str, Any], reason: str) -> None:
    assessment = _assess(**overrides)
    assert assessment["verdict"] == "insufficient_evidence"
    assert reason in assessment["reason_codes"]
    assert assessment["estimated_annual_difference_eur"] is None
    assert assessment["remediation"]


def test_fingerprint_is_stable_and_tracks_each_input() -> None:
    base = _assess()
    assert _assess()["assessment_id"] == base["assessment_id"]
    assert _assess(price_rows=_prices("0.0590"))["evidence_fingerprint"] != base["evidence_fingerprint"]
    assert _assess(cost_trend_rows=_usage(kwh="410"))["evidence_fingerprint"] != base[
        "evidence_fingerprint"
    ]
    assert set(base["evidence_components"]) == {"contract_terms", "alternatives", "usage_basis"}
    assert ENERGY_CONTRACT_VERDICTS[0] == "insufficient_evidence"


class _Reporting:
    """Reporting-layer stand-in returning published mart rows."""

    def __init__(self) -> None:
        self.prices = _prices()
        self.usage = _usage()

    def get_electricity_price_current(self) -> list[dict[str, Any]]:
        return list(self.prices)

    def get_contract_review_candidates(self) -> list[dict[str, Any]]:
        return [{"contract_id": "current", "reason": "above_market_average", "score": 2}]

    def get_contract_renewal_watchlist(self) -> list[dict[str, Any]]:
        return []

    def get_utility_cost_trend_monthly(
        self, *, utility_type: str | None = None
    ) -> list[dict[str, Any]]:
        return list(self.usage)


def test_energy_contract_decision_flows_through_the_generic_ledger() -> None:
    with TemporaryDirectory() as temp_dir:
        reporting = _Reporting()
        app = create_app(
            AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
            ),
            config_repository=IngestionConfigRepository(Path(temp_dir) / "config.db"),
            reporting_service=reporting,  # type: ignore[arg-type]
        )
        client = TestClient(app)
        listed = client.get(f"/control/decisions/definitions/{KEY}/subjects")
        assert listed.status_code == 200, listed.text
        subjects = {item["period"]: item for item in listed.json()["subjects"]}
        assert set(subjects) == {"current", "quote"}
        current = subjects["current"]
        assert current["verdict"] == "alternative_estimated_cheaper"
        assert current["snapshot"]["assessment"]["review_candidate_reason"] == "above_market_average"
        assert client.get(f"/control/decisions/definitions/{KEY}/subjects", params={"period": "x"}).json()[
            "subjects"
        ] == []
        assert client.get("/control/decisions/definitions/nope/subjects").status_code == 404

        created = client.post(
            "/control/decisions",
            json={
                "decision_key": KEY,
                "subject_period": "current",
                "subject_row_ref": current["row_ref"],
                "outcome": "request_new_quotes",
                "rationale": "Quote is cheaper on paper; ask for a fixed offer too.",
            },
        )
        assert created.status_code == 201, created.text
        decision = created.json()["decision"]
        assert decision["subject"]["publication_key"] == "mart_electricity_price_current"
        assert decision["commitment"]["baseline"]["values"]["estimated_annual_difference_eur"][
            "value"
        ] == "132"
        window = decision["commitment"]["observation_window"]
        assert window["review_cadence_days"] == 180

        # A new quote lands: the decision's evidence is superseded.
        reporting.prices = _prices(alternative_energy="0.0550")
        traced = client.post("/control/decisions/evidence-trace", json={"decision_key": KEY})
        [result] = traced.json()["trace"]["results"]
        assert result["status"] == "superseded"
        assert result["correction_kinds"] == ["market_reference"]

        # Insufficient evidence must be acknowledged.
        reporting.usage = _usage(months=6)
        stale = client.get(f"/control/decisions/definitions/{KEY}/subjects", params={"period": "current"})
        row_ref = stale.json()["subjects"][0]["row_ref"]
        refused = client.post(
            "/control/decisions",
            json={
                "decision_key": KEY,
                "subject_period": "current",
                "subject_row_ref": row_ref,
                "outcome": "keep_current_contract",
                "rationale": "Keep.",
            },
        )
        assert refused.status_code == 422
        assert "usage_history_incomplete" in refused.json()["detail"]


def test_energy_contract_modules_have_no_supplier_or_actuation_path() -> None:
    source = (ROOT / "packages/domains/utilities/energy_contract_decision.py").read_text()
    for token in ("requests", "httpx", "password", "api_key", "call_service"):
        assert token not in source
