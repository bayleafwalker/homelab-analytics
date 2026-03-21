"""Tests for the per-source identity resolution strategy."""

from __future__ import annotations

import pytest

from packages.pipelines.identity_strategy import (
    IdentityStrategy,
    IdentityTier,
    resolve_entity_key,
)
from packages.pipelines.transaction_models import BANK_TRANSACTION_IDENTITY_STRATEGY

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_STRATEGY = IdentityStrategy(
    strategy_id="test_v1",
    tiers=(
        IdentityTier(tier=1, fields=("account_id", "provider_ref")),
        IdentityTier(tier=2, fields=("date", "account_id", "amount")),
    ),
    fallback_mode="reject",
)

_FUZZY_STRATEGY = IdentityStrategy(
    strategy_id="test_fuzzy",
    tiers=(
        IdentityTier(tier=1, fields=("account_id", "provider_ref")),
    ),
    fallback_mode="fuzzy",
)


# ---------------------------------------------------------------------------
# Tier matching
# ---------------------------------------------------------------------------


def test_tier1_matches_when_all_fields_present() -> None:
    row = {"account_id": "CHK-001", "provider_ref": "TXN-999", "date": "2025-01-15"}
    result = resolve_entity_key(row, _STRATEGY)
    assert result.match_tier == 1
    assert result.confidence == 1.0
    assert len(result.entity_key) == 16


def test_tier2_used_when_tier1_field_missing() -> None:
    row = {"account_id": "CHK-001", "date": "2025-01-15", "amount": "84.00"}
    result = resolve_entity_key(row, _STRATEGY)
    assert result.match_tier == 2
    assert result.confidence == 1.0


def test_tier2_used_when_tier1_field_empty_string() -> None:
    row = {"account_id": "CHK-001", "provider_ref": "", "date": "2025-01-15", "amount": "84.00"}
    result = resolve_entity_key(row, _STRATEGY)
    assert result.match_tier == 2


def test_tier2_used_when_tier1_field_none() -> None:
    row = {"account_id": "CHK-001", "provider_ref": None, "date": "2025-01-15", "amount": "84.00"}
    result = resolve_entity_key(row, _STRATEGY)
    assert result.match_tier == 2


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_same_inputs_produce_same_key() -> None:
    row = {"account_id": "CHK-001", "provider_ref": "TXN-999"}
    r1 = resolve_entity_key(row, _STRATEGY)
    r2 = resolve_entity_key(row, _STRATEGY)
    assert r1.entity_key == r2.entity_key


def test_different_inputs_produce_different_keys() -> None:
    row_a = {"account_id": "CHK-001", "provider_ref": "TXN-001"}
    row_b = {"account_id": "CHK-001", "provider_ref": "TXN-002"}
    assert resolve_entity_key(row_a, _STRATEGY).entity_key != resolve_entity_key(row_b, _STRATEGY).entity_key


def test_field_order_does_not_affect_key() -> None:
    """Key is stable regardless of dict insertion order."""
    row_a = {"account_id": "CHK-001", "provider_ref": "TXN-999"}
    row_b = {"provider_ref": "TXN-999", "account_id": "CHK-001"}
    # Tier 1 encodes fields in declared order, so keys should match.
    assert resolve_entity_key(row_a, _STRATEGY).entity_key == resolve_entity_key(row_b, _STRATEGY).entity_key


# ---------------------------------------------------------------------------
# Reject fallback
# ---------------------------------------------------------------------------


def test_reject_mode_raises_when_no_tier_matches() -> None:
    row = {"unrelated_field": "value"}
    with pytest.raises(ValueError, match="No identity tier matched"):
        resolve_entity_key(row, _STRATEGY)


# ---------------------------------------------------------------------------
# Fuzzy fallback
# ---------------------------------------------------------------------------


def test_fuzzy_fallback_returns_tier_99_with_zero_confidence() -> None:
    row = {"some_field": "value"}
    result = resolve_entity_key(row, _FUZZY_STRATEGY)
    assert result.match_tier == 99
    assert result.confidence == 0.0
    assert len(result.entity_key) == 16


def test_fuzzy_fallback_is_deterministic() -> None:
    row = {"some_field": "value", "another": "thing"}
    r1 = resolve_entity_key(row, _FUZZY_STRATEGY)
    r2 = resolve_entity_key(row, _FUZZY_STRATEGY)
    assert r1.entity_key == r2.entity_key


# ---------------------------------------------------------------------------
# BANK_TRANSACTION_IDENTITY_STRATEGY contract
# ---------------------------------------------------------------------------


def test_bank_strategy_id() -> None:
    assert BANK_TRANSACTION_IDENTITY_STRATEGY.strategy_id == "bank_transaction_v1"


def test_bank_strategy_has_two_tiers() -> None:
    tiers = sorted(BANK_TRANSACTION_IDENTITY_STRATEGY.tiers, key=lambda t: t.tier)
    assert len(tiers) == 2
    assert tiers[0].tier == 1
    assert tiers[1].tier == 2


def test_bank_strategy_tier1_requires_provider_ref() -> None:
    tier1 = next(t for t in BANK_TRANSACTION_IDENTITY_STRATEGY.tiers if t.tier == 1)
    assert "provider_transaction_ref" in tier1.fields
    assert "account_id" in tier1.fields


def test_bank_strategy_tier2_composite_key() -> None:
    tier2 = next(t for t in BANK_TRANSACTION_IDENTITY_STRATEGY.tiers if t.tier == 2)
    required = {"booked_at", "account_id", "amount", "currency", "counterparty_name"}
    assert required.issubset(set(tier2.fields))


def test_bank_strategy_tier2_matches_standard_csv_row() -> None:
    row = {
        "booked_at": "2025-01-15",
        "account_id": "CHK-001",
        "amount": "-84.15",
        "currency": "EUR",
        "counterparty_name": "Electric Utility",
        "description": "Monthly bill",
    }
    result = resolve_entity_key(row, BANK_TRANSACTION_IDENTITY_STRATEGY)
    assert result.match_tier == 2
    assert result.confidence == 1.0
    assert len(result.entity_key) == 16


def test_bank_strategy_tier1_wins_when_provider_ref_present() -> None:
    row = {
        "booked_at": "2025-01-15",
        "account_id": "CHK-001",
        "amount": "-84.15",
        "currency": "EUR",
        "counterparty_name": "Electric Utility",
        "provider_transaction_ref": "BKREF-20250115-001",
    }
    result = resolve_entity_key(row, BANK_TRANSACTION_IDENTITY_STRATEGY)
    assert result.match_tier == 1


def test_bank_strategy_rejects_incomplete_row() -> None:
    row = {"account_id": "CHK-001"}  # missing booked_at, amount, currency, counterparty
    with pytest.raises(ValueError):
        resolve_entity_key(row, BANK_TRANSACTION_IDENTITY_STRATEGY)


def test_bank_strategy_fallback_mode_is_reject() -> None:
    assert BANK_TRANSACTION_IDENTITY_STRATEGY.fallback_mode == "reject"
