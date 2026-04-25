from __future__ import annotations

import logging
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any

_log = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from apps.api.models import ConfiguredCsvIngestRequest
from apps.api.response_models import ConfiguredIngestionProcessResponseModel
from apps.api.support import read_upload_limited
from packages.application.use_cases.ingest_promotion import (
    promote_and_publish_configured_csv,
    promote_and_publish_configured_csv_batch,
    promote_and_publish_contract_prices,
    promote_and_publish_subscription,
)
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.domains.finance.pipelines.contract_price_service import ContractPriceService
from packages.domains.finance.pipelines.subscription_service import SubscriptionService
from packages.domains.homelab.pipelines.ha_bridge_ingestion import (
    HaBridgeEventsPayload,
    HaBridgeHeartbeatPayload,
    HaBridgeLandingService,
    HaBridgeRegistryPayload,
    HaBridgeStatesPayload,
    HaBridgeStatisticsPayload,
)
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionDefinitionService,
)
from packages.pipelines.promotion import (
    PromotionResult,
)
from packages.pipelines.promotion_registry import PromotionHandlerRegistry
from packages.pipelines.publication_preview import attach_publication_preview
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.pipelines.upload_detection import detect_upload_target
from packages.pipelines.upload_dry_run import preview_upload_dry_run
from packages.shared.extensions import ExtensionRegistry
from packages.storage.control_plane import ConfigCatalogStore

HA_BRIDGE_INGEST_RATE_LIMIT_MAX_REQUESTS = 12
HA_BRIDGE_INGEST_RATE_LIMIT_WINDOW_SECONDS = 60.0


@dataclass(frozen=True)
class _HaBridgeIngestRateLimitKey:
    route_path: str
    bridge_instance_id: str
    client_host: str


class HaBridgeIngestRateLimiter:
    def __init__(
        self,
        *,
        max_requests: int = HA_BRIDGE_INGEST_RATE_LIMIT_MAX_REQUESTS,
        window_seconds: float = HA_BRIDGE_INGEST_RATE_LIMIT_WINDOW_SECONDS,
    ) -> None:
        self._lock = Lock()
        self._clock = monotonic
        self.configure(max_requests=max_requests, window_seconds=window_seconds)

    def configure(self, *, max_requests: int, window_seconds: float) -> None:
        if max_requests <= 0:
            raise ValueError("HA bridge ingest rate limit max_requests must be positive.")
        if window_seconds <= 0:
            raise ValueError("HA bridge ingest rate limit window_seconds must be positive.")
        with self._lock:
            self.max_requests = max_requests
            self.window_seconds = window_seconds
            self._request_log: dict[_HaBridgeIngestRateLimitKey, deque[float]] = defaultdict(
                deque
            )

    def check_and_record(
        self,
        *,
        route_path: str,
        bridge_instance_id: str,
        client_host: str,
    ) -> int | None:
        request_key = _HaBridgeIngestRateLimitKey(
            route_path=route_path,
            bridge_instance_id=bridge_instance_id.strip().lower(),
            client_host=client_host.strip().lower() or "unknown",
        )
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            request_times = self._request_log[request_key]
            while request_times and request_times[0] <= cutoff:
                request_times.popleft()
            if len(request_times) >= self.max_requests:
                retry_after = max(1, int(request_times[0] + self.window_seconds - now) + 1)
                return retry_after
            request_times.append(now)
        return None


def _enforce_ha_bridge_rate_limit(
    request: Request,
    *,
    bridge_instance_id: str,
) -> None:
    limiter = request.app.state.ha_bridge_ingest_rate_limiter
    client_host = request.client.host if request.client is not None else "unknown"
    retry_after = limiter.check_and_record(
        route_path=request.url.path,
        bridge_instance_id=bridge_instance_id,
        client_host=client_host,
    )
    if retry_after is None:
        return
    raise HTTPException(
        status_code=429,
        detail="HA bridge ingest rate limit exceeded. Retry again later.",
        headers={"Retry-After": str(retry_after)},
    )


def register_ingest_routes(
    app: FastAPI,
    *,
    service: AccountTransactionService,
    registry: ExtensionRegistry,
    configured_ingestion_service: ConfiguredCsvIngestionService,
    configured_definition_service: ConfiguredIngestionDefinitionService,
    resolved_config_repository: ConfigCatalogStore,
    transformation_service: TransformationService | None,
    resolved_reporting_service: ReportingService | None,
    subscription_service: SubscriptionService | None,
    contract_price_service: ContractPriceService | None,
    require_unsafe_admin: Callable[[], None],
    promotion_handler_registry: PromotionHandlerRegistry | None,
    publish_reporting: Callable[[PromotionResult | None], None],
    resolve_configured_ingest_binding: Callable[
        [ConfiguredCsvIngestRequest], tuple[Any, str, str, str]
    ],
    build_run_response: Callable[..., JSONResponse],
    build_ingest_response: Callable[..., JSONResponse],
    require_upload: Callable[[object], UploadFile],
    serialize_run: Callable[..., dict[str, Any]],
    serialize_promotion: Callable[[PromotionResult], dict[str, Any]],
    to_jsonable: Callable[[Any], Any],
) -> None:
    ha_bridge_landing_service = HaBridgeLandingService(
        service.landing_root,
        service.metadata_repository,
        blob_store=service.blob_store,
    )
    app.state.ha_bridge_ingest_rate_limiter = HaBridgeIngestRateLimiter()

    @app.post("/landing/{extension_key}", status_code=201)
    async def run_landing_extension(
        extension_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        require_unsafe_admin()
        result = registry.execute(
            "landing",
            extension_key,
            service=service,
            **payload,
        )
        return {"result": to_jsonable(result)}

    @app.post("/ingest", status_code=201)
    async def ingest_account_transactions(request: Request) -> JSONResponse:
        # Dev/demo shortcut. Operator path is /upload → /ingest/configured-csv.
        return await _handle_account_transaction_ingest(
            request,
            service=service,
            transformation_service=transformation_service,
            reporting_service=resolved_reporting_service,
            build_ingest_response=build_ingest_response,
            require_upload=require_upload,
        )

    @app.post("/api/ingest/ha-bridge/registry", status_code=201)
    async def ingest_ha_bridge_registry(
        request: Request,
        payload: HaBridgeRegistryPayload,
    ) -> JSONResponse:
        _enforce_ha_bridge_rate_limit(
            request,
            bridge_instance_id=payload.bridge_instance_id,
        )
        result = ha_bridge_landing_service.ingest_registry_payload(
            raw_bytes=await request.body(),
            payload=payload,
        )
        return build_run_response(service.get_run(result.run.run_id))

    @app.post("/api/ingest/ha-bridge/states", status_code=201)
    async def ingest_ha_bridge_states(
        request: Request,
        payload: HaBridgeStatesPayload,
    ) -> JSONResponse:
        _enforce_ha_bridge_rate_limit(
            request,
            bridge_instance_id=payload.bridge_instance_id,
        )
        result = ha_bridge_landing_service.ingest_states_payload(
            raw_bytes=await request.body(),
            payload=payload,
        )
        return build_run_response(service.get_run(result.run.run_id))

    @app.post("/api/ingest/ha-bridge/events", status_code=201)
    async def ingest_ha_bridge_events(
        request: Request,
        payload: HaBridgeEventsPayload,
    ) -> JSONResponse:
        _enforce_ha_bridge_rate_limit(
            request,
            bridge_instance_id=payload.bridge_instance_id,
        )
        result = ha_bridge_landing_service.ingest_events_payload(
            raw_bytes=await request.body(),
            payload=payload,
        )
        return build_run_response(service.get_run(result.run.run_id))

    @app.post("/api/ingest/ha-bridge/statistics", status_code=201)
    async def ingest_ha_bridge_statistics(
        request: Request,
        payload: HaBridgeStatisticsPayload,
    ) -> JSONResponse:
        _enforce_ha_bridge_rate_limit(
            request,
            bridge_instance_id=payload.bridge_instance_id,
        )
        result = ha_bridge_landing_service.ingest_statistics_payload(
            raw_bytes=await request.body(),
            payload=payload,
        )
        return build_run_response(service.get_run(result.run.run_id))

    @app.post("/api/ingest/ha-bridge/heartbeat", status_code=201)
    async def ingest_ha_bridge_heartbeat(
        request: Request,
        payload: HaBridgeHeartbeatPayload,
    ) -> JSONResponse:
        _enforce_ha_bridge_rate_limit(
            request,
            bridge_instance_id=payload.bridge_instance_id,
        )
        result = ha_bridge_landing_service.ingest_heartbeat_payload(
            raw_bytes=await request.body(),
            payload=payload,
        )
        return build_run_response(service.get_run(result.run.run_id))

    @app.post("/ingest/account-transactions", status_code=201)
    async def ingest_account_transactions_alias(request: Request) -> JSONResponse:
        # Dev/demo shortcut. Operator path is /upload → /ingest/configured-csv.
        return await _handle_account_transaction_ingest(
            request,
            service=service,
            transformation_service=transformation_service,
            reporting_service=resolved_reporting_service,
            build_ingest_response=build_ingest_response,
            require_upload=require_upload,
        )

    @app.post("/ingest/configured-csv", status_code=201)
    async def ingest_configured_csv(request: Request) -> JSONResponse:
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            upload = require_upload(form.get("file"))
            payload = ConfiguredCsvIngestRequest(
                source_path="",
                source_asset_id=str(form.get("source_asset_id") or "") or None,
                source_system_id=str(form.get("source_system_id") or "") or None,
                dataset_contract_id=str(form.get("dataset_contract_id") or "") or None,
                column_mapping_id=str(form.get("column_mapping_id") or "") or None,
                source_name=str(form.get("source_name") or "configured-upload"),
            )
            source_asset, source_system_id, dataset_contract_id, column_mapping_id = (
                resolve_configured_ingest_binding(payload)
            )
            source_bytes = await read_upload_limited(upload)
            await upload.close()
            run = configured_ingestion_service.ingest_bytes(
                source_bytes=source_bytes,
                file_name=getattr(upload, "filename", None) or "configured-upload.csv",
                source_system_id=source_system_id,
                dataset_contract_id=dataset_contract_id,
                column_mapping_id=column_mapping_id,
                source_asset_id=source_asset.source_asset_id if source_asset else None,
                source_name=payload.source_name,
            )
        else:
            try:
                payload = ConfiguredCsvIngestRequest(**(await request.json()))
            except ValidationError as exc:
                raise HTTPException(status_code=422, detail=exc.errors()) from exc
            source_asset, source_system_id, dataset_contract_id, column_mapping_id = (
                resolve_configured_ingest_binding(payload)
            )
            run = configured_ingestion_service.ingest_file(
                source_path=Path(payload.source_path),
                source_system_id=source_system_id,
                dataset_contract_id=dataset_contract_id,
                column_mapping_id=column_mapping_id,
                source_asset_id=source_asset.source_asset_id if source_asset else None,
                source_name=payload.source_name,
            )
        promotion: PromotionResult | None = None
        if run.passed:
            promotion = promote_and_publish_configured_csv(
                run.run_id,
                source_asset=source_asset,
                config_repository=resolved_config_repository,
                service=configured_ingestion_service,
                transformation_service=transformation_service,
                registry=registry,
                promotion_handler_registry=promotion_handler_registry,
                publish_reporting=publish_reporting,
                source_system_id=source_system_id,
                dataset_contract_id=dataset_contract_id,
                column_mapping_id=column_mapping_id,
            )
        return build_run_response(run, promotion=promotion)

    @app.post("/ingest/detect-source")
    async def detect_source_upload_target(request: Request) -> dict[str, Any]:
        form = await request.form()
        upload = require_upload(form.get("file"))
        source_bytes = await read_upload_limited(upload)
        file_name = getattr(upload, "filename", None) or "upload"
        await upload.close()

        source_assets = resolved_config_repository.list_source_assets(include_archived=False)
        column_mappings = resolved_config_repository.list_column_mappings(include_archived=False)
        dataset_contracts = resolved_config_repository.list_dataset_contracts(
            include_archived=False
        )

        detection = detect_upload_target(
            file_name=file_name,
            source_bytes=source_bytes,
            source_assets=source_assets,
            column_mappings_by_id={
                record.column_mapping_id: record for record in column_mappings
            },
            dataset_contracts_by_id={
                record.dataset_contract_id: record for record in dataset_contracts
            },
        )
        detection = attach_publication_preview(
            detection,
            source_assets_by_id={
                record.source_asset_id: record for record in source_assets
            },
            dataset_contracts_by_id={
                record.dataset_contract_id: record for record in dataset_contracts
            },
        )
        return {"detection": to_jsonable(detection)}

    @app.post("/ingest/dry-run")
    async def dry_run_source_upload(request: Request) -> dict[str, Any]:
        form = await request.form()
        upload = require_upload(form.get("file"))
        source_bytes = await read_upload_limited(upload)
        file_name = getattr(upload, "filename", None) or "upload"
        await upload.close()

        source_assets = resolved_config_repository.list_source_assets(include_archived=False)
        column_mappings = resolved_config_repository.list_column_mappings(include_archived=False)
        dataset_contracts = resolved_config_repository.list_dataset_contracts(
            include_archived=False
        )

        preview = preview_upload_dry_run(
            file_name=file_name,
            source_bytes=source_bytes,
            upload_path_override=str(form.get("upload_path") or "") or None,
            source_asset_id_override=str(form.get("source_asset_id") or "") or None,
            source_assets=source_assets,
            column_mappings_by_id={
                record.column_mapping_id: record for record in column_mappings
            },
            dataset_contracts_by_id={
                record.dataset_contract_id: record for record in dataset_contracts
            },
        )
        return {"preview": to_jsonable(preview)}

    _DEPRECATION_HEADERS = {
        "Deprecation": "true",
        "Sunset": "Sat, 01 Aug 2026 00:00:00 GMT",
        "Link": '</upload>; rel="successor-version"',
    }

    @app.post("/ingest/subscriptions", status_code=201)
    async def ingest_subscriptions(request: Request) -> JSONResponse:
        # Deprecated dev/demo shortcut. Operator path is /upload → /ingest/configured-csv.
        _log.warning(
            "Deprecated endpoint /ingest/subscriptions called. "
            "Use /upload (configured-CSV path) instead. "
            "This endpoint will be removed; see Sunset header."
        )
        if subscription_service is None:
            raise KeyError("subscription ingestion is not configured")
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            upload = require_upload(form.get("file"))
            source_name = str(form.get("source_name") or "manual-upload")
            source_bytes = await read_upload_limited(upload)
            await upload.close()
            run = subscription_service.ingest_bytes(
                source_bytes=source_bytes,
                file_name=getattr(upload, "filename", None) or "subscriptions.csv",
                source_name=source_name,
            )
        else:
            payload = await request.json()
            run = subscription_service.ingest_file(
                Path(payload["source_path"]),
                source_name=payload.get("source_name", "manual-upload"),
            )
        promotion: PromotionResult | None = None
        if run.passed:
            promotion = promote_and_publish_subscription(
                run.run_id,
                subscription_service=subscription_service,
                transformation_service=transformation_service,
                publish_reporting=publish_reporting,
            )
        body: dict[str, Any] = {"run": serialize_run(run)}
        if promotion is not None:
            body["promotion"] = serialize_promotion(promotion)
        status_code = (
            409
            if any(i.code == "duplicate_file" for i in run.issues)
            else (201 if run.passed else 400)
        )
        return JSONResponse(status_code=status_code, content=body, headers=_DEPRECATION_HEADERS)

    @app.post("/ingest/contract-prices", status_code=201)
    async def ingest_contract_prices(request: Request) -> JSONResponse:
        # Deprecated dev/demo shortcut. Operator path is /upload → /ingest/configured-csv.
        _log.warning(
            "Deprecated endpoint /ingest/contract-prices called. "
            "Use /upload (configured-CSV path) instead. "
            "This endpoint will be removed; see Sunset header."
        )
        if contract_price_service is None:
            raise KeyError("contract-price ingestion is not configured")
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            upload = require_upload(form.get("file"))
            source_name = str(form.get("source_name") or "manual-upload")
            source_bytes = await read_upload_limited(upload)
            await upload.close()
            run = contract_price_service.ingest_bytes(
                source_bytes=source_bytes,
                file_name=getattr(upload, "filename", None) or "contract-prices.csv",
                source_name=source_name,
            )
        else:
            payload = await request.json()
            run = contract_price_service.ingest_file(
                Path(payload["source_path"]),
                source_name=payload.get("source_name", "manual-upload"),
            )
        promotion: PromotionResult | None = None
        if run.passed:
            promotion = promote_and_publish_contract_prices(
                run.run_id,
                contract_price_service=contract_price_service,
                transformation_service=transformation_service,
                publish_reporting=publish_reporting,
            )
        body: dict[str, Any] = {"run": serialize_run(run)}
        if promotion is not None:
            body["promotion"] = serialize_promotion(promotion)
        status_code = (
            409
            if any(i.code == "duplicate_file" for i in run.issues)
            else (201 if run.passed else 400)
        )
        return JSONResponse(status_code=status_code, content=body, headers=_DEPRECATION_HEADERS)

    @app.post(
        "/ingest/ingestion-definitions/{ingestion_definition_id}/process",
        status_code=201,
        response_model=ConfiguredIngestionProcessResponseModel,
    )
    async def process_ingestion_definition(
        ingestion_definition_id: str,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        result = configured_definition_service.process_ingestion_definition(ingestion_definition_id)
        body: dict[str, Any] = {"result": to_jsonable(result)}
        if transformation_service is not None:
            ingestion_definition = resolved_config_repository.get_ingestion_definition(
                ingestion_definition_id
            )
            source_asset = resolved_config_repository.get_source_asset(
                ingestion_definition.source_asset_id
            )
            promotions = promote_and_publish_configured_csv_batch(
                result.run_ids,
                source_asset=source_asset,
                config_repository=resolved_config_repository,
                service=configured_ingestion_service,
                transformation_service=transformation_service,
                registry=registry,
                promotion_handler_registry=promotion_handler_registry,
                publish_reporting=publish_reporting,
            )
            body["promotions"] = to_jsonable(promotions)
        return body

    @app.get("/transformations/{extension_key}")
    async def run_transformation_extension(
        extension_key: str,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        if not run_id:
            raise HTTPException(status_code=400, detail="run_id is required")
        result = registry.execute(
            "transformation",
            extension_key,
            service=service,
            run_id=run_id,
        )
        return {"result": to_jsonable(result)}


async def _handle_account_transaction_ingest(
    request: Request,
    *,
    service: AccountTransactionService,
    transformation_service: TransformationService | None,
    reporting_service: ReportingService | None,
    build_ingest_response: Callable[..., JSONResponse],
    require_upload: Callable[[object], UploadFile],
) -> JSONResponse:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = require_upload(form.get("file"))
        source_name = str(form.get("source_name") or "manual-upload")
        source_bytes = await read_upload_limited(upload)
        await upload.close()
        run = service.ingest_bytes(
            source_bytes=source_bytes,
            file_name=upload.filename or "upload.csv",
            source_name=source_name,
        )
        return build_ingest_response(
            run,
            service,
            transformation_service,
            reporting_service,
        )

    payload = await request.json()
    run = service.ingest_file(
        Path(payload["source_path"]),
        source_name=payload.get("source_name", "manual-upload"),
    )
    return build_ingest_response(
        run,
        service,
        transformation_service,
        reporting_service,
    )
