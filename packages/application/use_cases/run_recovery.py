from __future__ import annotations

from typing import Any

from packages.pipelines.run_context import RunControlContext
from packages.storage.run_metadata import IngestionRunRecord


def build_run_recovery(
    run: IngestionRunRecord,
    context: RunControlContext | None,
    *,
    has_subscription_service: bool,
    has_contract_price_service: bool,
) -> dict[str, Any]:
    """Determine retry capability for a completed ingestion run.

    Extracted from apps/api/app.py so that the same logic can be called from
    both the API adapter and the worker adapter without duplicating the
    domain-specific branching in a transport layer.
    """
    if (
        context is not None
        and context.source_system_id
        and context.dataset_contract_id
        and context.column_mapping_id
    ):
        return {
            "retry_supported": True,
            "retry_kind": "configured_csv",
            "reason": None,
        }
    if run.dataset_name == "account_transactions":
        return {
            "retry_supported": True,
            "retry_kind": "account_transactions",
            "reason": None,
        }
    if run.dataset_name == "subscriptions":
        return {
            "retry_supported": has_subscription_service,
            "retry_kind": "subscriptions" if has_subscription_service else None,
            "reason": (
                None
                if has_subscription_service
                else "Subscription retry is not configured in this API runtime."
            ),
        }
    if run.dataset_name == "contract_prices":
        return {
            "retry_supported": has_contract_price_service,
            "retry_kind": "contract_prices" if has_contract_price_service else None,
            "reason": (
                None
                if has_contract_price_service
                else "Contract-price retry is not configured in this API runtime."
            ),
        }
    return {
        "retry_supported": False,
        "retry_kind": None,
        "reason": (
            "Retry requires either a built-in dataset handler or saved configured-ingest"
            " binding context in the landing manifest."
        ),
    }
