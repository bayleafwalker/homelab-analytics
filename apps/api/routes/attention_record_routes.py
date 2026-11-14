"""HTTP adapter for the four attention-record source reads.

Each attention item groups one or more rows of a single source publication by
an opaque whole-key identity (for example ``review_grid/north_above_market_average``,
which contains a slash). These routes resolve that key through the reporting
service's ``get_attention_record`` facade — the same source contract the
attention UI already lists — and never re-derive identities, authority or SQL
here.

The whole key is a single path segment captured with the ``path`` converter so
an encoded slash is carried through to the source reader intact, rather than
being split at the first ``/`` or matched against an equal-looking prefix.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from apps.api.response_models import build_object_response_model
from apps.api.routes.report_routes import (
    CONTRACT_RENEWAL_WATCHLIST_ROW_MODEL,
    CONTRACT_REVIEW_CANDIDATES_ROW_MODEL,
    TRANSACTION_ANOMALIES_ROW_MODEL,
    UPCOMING_FIXED_COSTS_ROW_MODEL,
)
from packages.domains.overview.pipelines.attention_records import (
    AttentionRecordNotFoundError,
    AttentionRecordUnavailableError,
)
from packages.pipelines.reporting_service import ReportingService


def _record_response_model(model_name: str, row_model: Any) -> type[BaseModel]:
    return build_object_response_model(
        model_name,
        {
            "item_id": (str, ...),
            "rows": (list[row_model], ...),
        },
    )


TRANSACTION_ANOMALIES_RECORD_RESPONSE_MODEL = _record_response_model(
    "TransactionAnomaliesRecordResponse", TRANSACTION_ANOMALIES_ROW_MODEL
)
CONTRACT_REVIEW_CANDIDATES_RECORD_RESPONSE_MODEL = _record_response_model(
    "ContractReviewCandidatesRecordResponse", CONTRACT_REVIEW_CANDIDATES_ROW_MODEL
)
CONTRACT_RENEWAL_WATCHLIST_RECORD_RESPONSE_MODEL = _record_response_model(
    "ContractRenewalWatchlistRecordResponse", CONTRACT_RENEWAL_WATCHLIST_ROW_MODEL
)
UPCOMING_FIXED_COSTS_RECORD_RESPONSE_MODEL = _record_response_model(
    "UpcomingFixedCostsRecordResponse", UPCOMING_FIXED_COSTS_ROW_MODEL
)


def register_attention_record_routes(
    app: FastAPI,
    *,
    resolved_reporting_service: ReportingService | None,
    to_jsonable: Callable[[Any], Any],
) -> None:
    def _record(item_type: str, item_id: str) -> dict[str, Any]:
        if resolved_reporting_service is None:
            raise HTTPException(
                status_code=404, detail="Attention record reads require a reporting service."
            )
        try:
            rows = resolved_reporting_service.get_attention_record(item_type, item_id)
        except AttentionRecordNotFoundError:
            raise HTTPException(status_code=404, detail="Attention record not found.") from None
        except AttentionRecordUnavailableError:
            raise HTTPException(
                status_code=503, detail="Attention record source is unavailable."
            ) from None
        return {"item_id": item_id, "rows": to_jsonable(rows)}

    @app.get(
        "/reports/transaction-anomalies/records/{item_id:path}",
        response_model=TRANSACTION_ANOMALIES_RECORD_RESPONSE_MODEL,
    )
    async def get_transaction_anomaly_record(item_id: str) -> dict[str, Any]:
        return _record("anomaly", item_id)

    @app.get(
        "/reports/contract-review-candidates/records/{item_id:path}",
        response_model=CONTRACT_REVIEW_CANDIDATES_RECORD_RESPONSE_MODEL,
    )
    async def get_contract_review_candidate_record(item_id: str) -> dict[str, Any]:
        return _record("contract_review", item_id)

    @app.get(
        "/reports/contract-renewal-watchlist/records/{item_id:path}",
        response_model=CONTRACT_RENEWAL_WATCHLIST_RECORD_RESPONSE_MODEL,
    )
    async def get_contract_renewal_watchlist_record(item_id: str) -> dict[str, Any]:
        return _record("contract_renewal", item_id)

    @app.get(
        "/reports/upcoming-fixed-costs/records/{item_id:path}",
        response_model=UPCOMING_FIXED_COSTS_RECORD_RESPONSE_MODEL,
    )
    async def get_upcoming_fixed_cost_record(item_id: str) -> dict[str, Any]:
        return _record("upcoming_cost", item_id)
