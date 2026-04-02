from __future__ import annotations

from typing import Iterable

from packages.pipelines.household_packages import (
    BUILTIN_TRANSFORMATION_PACKAGE_SPECS_BY_ID,
)
from packages.storage.ingestion_config import (
    DatasetContractConfigRecord,
    SourceAssetRecord,
)

_BUILTIN_CONTRACT_TO_PACKAGE_ID = {
    "account_transactions": "builtin_account_transactions",
    "subscriptions": "builtin_subscriptions",
    "contract_prices": "builtin_contract_prices",
    "budgets": "builtin_budgets",
    "loan_repayments": "builtin_loan_repayments",
    "home_assistant_states_json_v1": "builtin_homelab",
}

_DERIVED_PUBLICATION_NAMES = {
    "mart_household_overview": "Household overview mart",
    "mart_open_attention_items": "Open attention items mart",
    "mart_recent_significant_changes": "Recent significant changes mart",
    "mart_current_operating_baseline": "Current operating baseline mart",
    "mart_household_cost_model": "Household cost model mart",
    "mart_cost_trend_12m": "Cost trend (12 months) mart",
    "mart_affordability_ratios": "Affordability ratios mart",
    "mart_recurring_cost_baseline": "Recurring cost baseline mart",
}


def attach_publication_preview(
    detection: dict[str, object],
    *,
    source_assets_by_id: dict[str, SourceAssetRecord],
    dataset_contracts_by_id: dict[str, DatasetContractConfigRecord],
) -> dict[str, object]:
    """Attach publication-preview metadata to detection candidates."""
    enriched = dict(detection)
    enriched["candidate"] = _candidate_with_preview(
        detection.get("candidate"),
        source_assets_by_id=source_assets_by_id,
        dataset_contracts_by_id=dataset_contracts_by_id,
    )
    alternatives = detection.get("alternatives")
    if isinstance(alternatives, list):
        enriched["alternatives"] = [
            _candidate_with_preview(
                candidate,
                source_assets_by_id=source_assets_by_id,
                dataset_contracts_by_id=dataset_contracts_by_id,
            )
            for candidate in alternatives
        ]
    return enriched


def _candidate_with_preview(
    candidate: object,
    *,
    source_assets_by_id: dict[str, SourceAssetRecord],
    dataset_contracts_by_id: dict[str, DatasetContractConfigRecord],
) -> object:
    if not isinstance(candidate, dict):
        return candidate
    preview = _resolve_publication_preview(
        candidate,
        source_assets_by_id=source_assets_by_id,
        dataset_contracts_by_id=dataset_contracts_by_id,
    )
    enriched = dict(candidate)
    enriched["publication_preview"] = preview
    return enriched


def _resolve_publication_preview(
    candidate: dict[str, object],
    *,
    source_assets_by_id: dict[str, SourceAssetRecord],
    dataset_contracts_by_id: dict[str, DatasetContractConfigRecord],
) -> dict[str, object]:
    package_id = _resolve_package_id(
        candidate,
        source_assets_by_id=source_assets_by_id,
        dataset_contracts_by_id=dataset_contracts_by_id,
    )
    if not package_id:
        return {"transformation_package_id": None, "direct": [], "derived": []}
    spec = BUILTIN_TRANSFORMATION_PACKAGE_SPECS_BY_ID.get(package_id)
    if spec is None:
        return {
            "transformation_package_id": package_id,
            "direct": [],
            "derived": [],
        }

    direct = [
        {
            "publication_key": publication.publication_key,
            "name": publication.name,
        }
        for publication in spec.publications
    ]
    direct_keys = {entry["publication_key"] for entry in direct}
    derived_keys = _dedupe(
        key
        for key in spec.refresh_publication_keys
        if key not in direct_keys
    )
    derived = [
        {
            "publication_key": key,
            "name": _derived_publication_name(key),
        }
        for key in derived_keys
    ]
    return {
        "transformation_package_id": package_id,
        "direct": direct,
        "derived": derived,
    }


def _resolve_package_id(
    candidate: dict[str, object],
    *,
    source_assets_by_id: dict[str, SourceAssetRecord],
    dataset_contracts_by_id: dict[str, DatasetContractConfigRecord],
) -> str | None:
    source_asset_id = str(candidate.get("source_asset_id") or "")
    source_asset = source_assets_by_id.get(source_asset_id)
    if source_asset and source_asset.transformation_package_id:
        return source_asset.transformation_package_id

    contract_id = str(candidate.get("contract_id") or "")
    builtin_package_id = _BUILTIN_CONTRACT_TO_PACKAGE_ID.get(contract_id)
    if builtin_package_id:
        return builtin_package_id

    dataset_contract = dataset_contracts_by_id.get(contract_id)
    if dataset_contract is not None:
        inferred = _infer_package_id_from_dataset_name(dataset_contract.dataset_name)
        if inferred:
            return inferred

    return _infer_package_id_from_dataset_name(contract_id)


def _infer_package_id_from_dataset_name(name: str) -> str | None:
    token = name.strip().lower()
    if not token:
        return None

    if "account_transaction" in token:
        return "builtin_account_transactions"
    if "subscription" in token:
        return "builtin_subscriptions"
    if "contract_price" in token:
        return "builtin_contract_prices"
    if "budget" in token:
        return "builtin_budgets"
    if "loan_repayment" in token or token.startswith("loan_"):
        return "builtin_loan_repayments"
    if "home_assistant" in token or token.startswith("ha_"):
        return "builtin_homelab"
    if "utility_bill" in token:
        return "builtin_utility_bills"
    if "utility_usage" in token or token.startswith("utility_"):
        return "builtin_utility_usage"
    if "asset" in token:
        return "builtin_asset_register"
    return None


def _derived_publication_name(publication_key: str) -> str:
    known = _DERIVED_PUBLICATION_NAMES.get(publication_key)
    if known:
        return known
    title = publication_key.replace("_", " ").strip()
    return title.capitalize() if title else publication_key


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
