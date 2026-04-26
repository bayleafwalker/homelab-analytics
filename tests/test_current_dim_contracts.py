"""Focused contract tests for homelab and infrastructure current-dimension contracts.

Verifies that dim_node, dim_device, dim_service, and dim_workload each have an
explicit CurrentDimensionContractDefinition with required semantic metadata, and
that all four are accessible via the reporting contract path.
"""
from __future__ import annotations

import pytest

from packages.pipelines.composition.current_dimension_contracts import (
    CURRENT_DIMENSION_CONTRACTS,
)
from packages.pipelines.household_reporting import CURRENT_DIMENSION_RELATIONS

HOMELAB_DIMENSIONS = ("dim_node", "dim_device", "dim_service", "dim_workload")


@pytest.mark.parametrize("dim_name", HOMELAB_DIMENSIONS)
def test_homelab_dimension_has_contract(dim_name: str) -> None:
    assert dim_name in CURRENT_DIMENSION_CONTRACTS, (
        f"{dim_name} missing from CURRENT_DIMENSION_CONTRACTS"
    )


@pytest.mark.parametrize("dim_name", HOMELAB_DIMENSIONS)
def test_homelab_dimension_contract_has_display_name(dim_name: str) -> None:
    contract = CURRENT_DIMENSION_CONTRACTS[dim_name]
    assert contract.display_name, f"{dim_name} contract must have a non-empty display_name"


@pytest.mark.parametrize("dim_name", HOMELAB_DIMENSIONS)
def test_homelab_dimension_contract_has_description(dim_name: str) -> None:
    contract = CURRENT_DIMENSION_CONTRACTS[dim_name]
    assert contract.description, f"{dim_name} contract must have a non-empty description"


@pytest.mark.parametrize("dim_name", HOMELAB_DIMENSIONS)
def test_homelab_dimension_contract_has_field_overrides(dim_name: str) -> None:
    contract = CURRENT_DIMENSION_CONTRACTS[dim_name]
    assert contract.field_overrides, (
        f"{dim_name} contract must have at least one field_override entry"
    )


@pytest.mark.parametrize("dim_name", HOMELAB_DIMENSIONS)
def test_homelab_dimension_contract_schema_name_matches_key(dim_name: str) -> None:
    contract = CURRENT_DIMENSION_CONTRACTS[dim_name]
    assert contract.schema_name == dim_name, (
        f"{dim_name} contract schema_name ({contract.schema_name!r}) must match the dict key"
    )


@pytest.mark.parametrize("dim_name", HOMELAB_DIMENSIONS)
def test_homelab_dimension_in_current_dimension_relations(dim_name: str) -> None:
    assert dim_name in CURRENT_DIMENSION_RELATIONS, (
        f"{dim_name} missing from CURRENT_DIMENSION_RELATIONS — "
        "not accessible via ReportingService.get_current_dimension_rows()"
    )


def test_homelab_dimension_relations_map_to_rpt_views() -> None:
    for dim_name in HOMELAB_DIMENSIONS:
        view_name = CURRENT_DIMENSION_RELATIONS[dim_name]
        assert view_name.startswith("rpt_current_dim_"), (
            f"{dim_name} relation ({view_name!r}) must follow rpt_current_dim_* naming"
        )


def test_homelab_dimension_contracts_all_public() -> None:
    for dim_name in HOMELAB_DIMENSIONS:
        contract = CURRENT_DIMENSION_CONTRACTS[dim_name]
        assert contract.visibility == "public", (
            f"{dim_name} contract visibility must be 'public' for app-facing access"
        )
