from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI, HTTPException

from apps.api.models import ScheduleDispatchRequest
from apps.api.response_models import ScheduleDispatchResponseModel
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.shared.metrics import metrics_registry
from packages.storage.control_plane import ControlPlaneAdminStore


def register_control_routes(
    app: FastAPI,
    *,
    service: AccountTransactionService,
    resolved_config_repository: ControlPlaneAdminStore,
    require_unsafe_admin: Callable[[], None],
    serialize_run_detail: Callable[[Any], dict[str, Any]],
    build_operational_summary: Callable[[], dict[str, Any]],
    to_jsonable: Callable[[Any], Any],
) -> None:
    @app.get("/control/source-lineage")
    async def get_source_lineage(
        run_id: str | None = None,
        target_layer: str | None = None,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "lineage": to_jsonable(
                resolved_config_repository.list_source_lineage(
                    input_run_id=run_id,
                    target_layer=target_layer,
                )
            )
        }

    @app.get("/control/publication-audit")
    async def get_publication_audit(
        run_id: str | None = None,
        publication_key: str | None = None,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "publication_audit": to_jsonable(
                resolved_config_repository.list_publication_audit(
                    run_id=run_id,
                    publication_key=publication_key,
                )
            )
        }

    @app.get("/control/operational-summary")
    async def get_operational_summary() -> dict[str, Any]:
        require_unsafe_admin()
        return build_operational_summary()

    @app.get("/control/source-freshness")
    async def get_source_freshness() -> dict[str, Any]:
        require_unsafe_admin()
        recent_runs = service.metadata_repository.list_runs()
        seen: set[str] = set()
        datasets = []
        for run in recent_runs:
            if run.dataset_name in seen:
                continue
            seen.add(run.dataset_name)
            datasets.append(
                {
                    "dataset_name": run.dataset_name,
                    "latest_run_id": run.run_id,
                    "status": run.status,
                    "landed_at": run.created_at.isoformat(),
                }
            )
        return {"datasets": datasets}

    @app.get("/control/schedule-dispatches")
    async def list_schedule_dispatches(
        schedule_id: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "dispatches": to_jsonable(
                resolved_config_repository.list_schedule_dispatches(
                    schedule_id=schedule_id,
                    status=status,
                )
            )
        }

    @app.get("/control/schedule-dispatches/{dispatch_id}")
    async def get_schedule_dispatch(dispatch_id: str) -> dict[str, Any]:
        require_unsafe_admin()
        try:
            dispatch = resolved_config_repository.get_schedule_dispatch(dispatch_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail="Unknown schedule dispatch.",
            ) from exc
        schedule = resolved_config_repository.get_execution_schedule(dispatch.schedule_id)
        ingestion_definition = (
            resolved_config_repository.get_ingestion_definition(schedule.target_ref)
            if schedule.target_kind == "ingestion_definition"
            else None
        )
        source_asset = (
            resolved_config_repository.get_source_asset(
                ingestion_definition.source_asset_id
            )
            if ingestion_definition is not None
            else None
        )
        runs = []
        for run_id in dispatch.run_ids:
            try:
                runs.append(
                    serialize_run_detail(service.metadata_repository.get_run(run_id))
                )
            except KeyError:
                continue
        return {
            "dispatch": to_jsonable(dispatch),
            "schedule": to_jsonable(schedule),
            "ingestion_definition": to_jsonable(ingestion_definition),
            "source_asset": to_jsonable(source_asset),
            "runs": runs,
        }

    @app.post(
        "/control/schedule-dispatches/{dispatch_id}/retry",
        status_code=201,
        response_model=ScheduleDispatchResponseModel,
    )
    async def retry_schedule_dispatch(dispatch_id: str) -> dict[str, Any]:
        require_unsafe_admin()
        try:
            dispatch = resolved_config_repository.get_schedule_dispatch(dispatch_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail="Unknown schedule dispatch.",
            ) from exc
        if dispatch.status not in {"completed", "failed"}:
            raise HTTPException(
                status_code=409,
                detail="Only completed or failed schedule dispatches can be retried.",
            )
        try:
            retried_dispatch = resolved_config_repository.create_schedule_dispatch(
                dispatch.schedule_id
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        metrics_registry.set(
            "worker_queue_depth",
            float(
                len(
                    resolved_config_repository.list_schedule_dispatches(
                        status="enqueued"
                    )
                )
            ),
            help_text="Current queued schedule-dispatch count.",
        )
        return {"dispatch": to_jsonable(retried_dispatch)}

    @app.post("/control/schedule-dispatches", status_code=201)
    async def create_schedule_dispatch(
        payload: ScheduleDispatchRequest,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        if payload.schedule_id:
            dispatch = resolved_config_repository.create_schedule_dispatch(
                payload.schedule_id
            )
            metrics_registry.set(
                "worker_queue_depth",
                float(
                    len(
                        resolved_config_repository.list_schedule_dispatches(
                            status="enqueued"
                        )
                    )
                ),
                help_text="Current queued schedule-dispatch count.",
            )
            return {"dispatch": to_jsonable(dispatch)}
        dispatches = resolved_config_repository.enqueue_due_execution_schedules(
            limit=payload.limit
        )
        metrics_registry.set(
            "worker_queue_depth",
            float(
                len(
                    resolved_config_repository.list_schedule_dispatches(
                        status="enqueued"
                    )
                )
            ),
            help_text="Current queued schedule-dispatch count.",
        )
        return {"dispatches": to_jsonable(dispatches)}
