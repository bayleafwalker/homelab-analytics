from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI, HTTPException

from apps.api.models import ScheduleDispatchRequest
from apps.api.response_models import ScheduleDispatchResponseModel
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.platform.publication_confidence import FreshnessState
from packages.shared.metrics import metrics_registry
from packages.storage.control_plane import ControlPlaneAdminStore


def _worst_case_verdict(verdict1: str, verdict2: str) -> str:
    """Return the worst case verdict between two verdicts.

    Verdict severity order: UNAVAILABLE > UNRELIABLE > DEGRADED > TRUSTWORTHY
    """
    severity = {
        "TRUSTWORTHY": 1,
        "DEGRADED": 2,
        "UNRELIABLE": 3,
        "UNAVAILABLE": 4,
    }
    v1 = verdict1.upper()
    v2 = verdict2.upper()
    return verdict1 if severity.get(v1, 0) >= severity.get(v2, 0) else verdict2


def register_control_routes(
    app: FastAPI,
    *,
    service: AccountTransactionService,
    resolved_config_repository: ControlPlaneAdminStore,
    require_unsafe_admin: Callable[[], None],
    serialize_run_detail: Callable[[Any], dict[str, Any]],
    build_operational_summary: Callable[[], dict[str, Any]],
    to_jsonable: Callable[[Any], Any],
    resolved_reporting_service: Any = None,
) -> None:
    @app.get("/control/source-lineage")
    async def get_source_lineage(
        run_id: str | None = None,
        target_layer: str | None = None,
        target_name: str | None = None,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        return {
            "lineage": to_jsonable(
                resolved_config_repository.list_source_lineage(
                    input_run_id=run_id,
                    target_layer=target_layer,
                    target_name=target_name,
                )
            )
        }

    @app.get("/control/lineage/downstream")
    async def get_lineage_downstream(
        source_asset_id: str,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        lineage_records = resolved_config_repository.list_source_lineage(
            source_asset_id=source_asset_id,
        )
        publications = sorted(set(record.target_name for record in lineage_records))
        return {
            "source_asset_id": source_asset_id,
            "publications": publications,
        }

    @app.get("/control/lineage/upstream")
    async def get_lineage_upstream(
        publication_key: str,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        lineage_records = resolved_config_repository.list_source_lineage(
            target_name=publication_key,
        )
        sources = sorted(
            {
                record.source_system
                for record in lineage_records
                if record.source_system is not None
            }
        )
        return {
            "publication_key": publication_key,
            "contributing_sources": sources,
        }

    @app.get("/control/publication-audit")
    async def get_publication_audit(
        run_id: str | None = None,
        publication_key: str | None = None,
        summary: bool = False,
    ) -> dict[str, Any]:
        require_unsafe_admin()
        records = resolved_config_repository.list_publication_audit(
            run_id=run_id,
            publication_key=publication_key,
        )
        if summary:
            seen: set[str] = set()
            latest: list[Any] = []
            for record in records:
                if record.publication_key not in seen:
                    seen.add(record.publication_key)
                    latest.append(record)
            records = latest
        return {"publication_audit": to_jsonable(records)}

    @app.get("/control/operational-summary")
    async def get_operational_summary() -> dict[str, Any]:
        require_unsafe_admin()
        summary = build_operational_summary()
        publication_backend_active = resolved_reporting_service is not None
        if publication_backend_active:
            reporting_mode = "postgres"
            reporting_mode_label = "Published reporting (Postgres)"
        else:
            reporting_mode = "duckdb"
            reporting_mode_label = "Warehouse-backed (DuckDB)"
        summary["reporting_mode"] = reporting_mode
        summary["reporting_mode_label"] = reporting_mode_label
        summary["publication_backend_active"] = publication_backend_active
        return summary

    @app.get("/control/source-freshness")
    async def get_source_freshness() -> dict[str, Any]:
        require_unsafe_admin()
        from packages.storage.run_metadata import IngestionRunStatus
        recent_runs = service.metadata_repository.list_runs()
        seen: set[str] = set()
        datasets = []
        for run in recent_runs:
            if run.dataset_name in seen:
                continue
            seen.add(run.dataset_name)
            # Derive a simple suggested_action for stale / failed datasets.
            if run.status == IngestionRunStatus.FAILED:
                suggested_action = "retry"
            elif run.status == IngestionRunStatus.REJECTED:
                suggested_action = "upload_missing_period"
            else:
                suggested_action = "none"
            datasets.append(
                {
                    "dataset_name": run.dataset_name,
                    "latest_run_id": run.run_id,
                    "status": run.status,
                    "landed_at": run.created_at.isoformat(),
                    "suggested_action": suggested_action,
                }
            )
        return {"datasets": datasets}

    @app.get("/control/confidence")
    async def get_confidence(stale_only: bool = False) -> dict[str, Any]:
        require_unsafe_admin()
        snapshots = resolved_config_repository.list_publication_confidence_snapshots()
        publication_defs = resolved_config_repository.list_publication_definitions()

        # Filter snapshots if stale_only is True
        if stale_only:
            snapshots = [
                s for s in snapshots
                if s.freshness_state in (FreshnessState.STALE, FreshnessState.UNAVAILABLE)
            ]

        # Build map of publication_key -> domain from publication definitions
        pub_to_domain: dict[str, str] = {}
        for pub_def in publication_defs:
            # Default to "platform" domain (pack_name concept not available in current schema)
            domain = "platform"
            pub_to_domain[pub_def.publication_key] = domain

        # Group snapshots by domain
        domain_summaries: dict[str, dict[str, Any]] = {}
        publications = []

        for snapshot in snapshots:
            # Serialize source_freshness_states if present
            source_freshness_dict = None
            if snapshot.source_freshness_states:
                source_freshness_dict = {
                    asset_id: {
                        "source_asset_id": state.get("source_asset_id"),
                        "freshness_state": state.get("freshness_state"),
                        "last_ingest_at": state.get("last_ingest_at"),
                        "covered_through": state.get("covered_through"),
                    }
                    for asset_id, state in snapshot.source_freshness_states.items()
                }

            pub_data = {
                "publication_key": snapshot.publication_key,
                "freshness_state": snapshot.freshness_state,
                "completeness_pct": snapshot.completeness_pct,
                "confidence_verdict": snapshot.confidence_verdict,
                "assessed_at": snapshot.assessed_at.isoformat(),
                "source_freshness_states": source_freshness_dict,
                "quality_flags": snapshot.quality_flags,
            }
            publications.append(pub_data)

            # Look up domain from publication definition, fall back to "platform"
            domain = pub_to_domain.get(snapshot.publication_key, "platform")

            if domain not in domain_summaries:
                domain_summaries[domain] = {
                    "domain": domain,
                    "verdict": snapshot.confidence_verdict,
                    "count": 0,
                }
            else:
                # Roll up to worst-case verdict
                current_verdict = domain_summaries[domain]["verdict"]
                worst_case = _worst_case_verdict(current_verdict, snapshot.confidence_verdict)
                domain_summaries[domain]["verdict"] = worst_case

            domain_summaries[domain]["count"] += 1

        return {
            "publications": publications,
            "domain_summaries": list(domain_summaries.values()),
        }

    @app.get("/control/confidence/{publication_key}")
    async def get_confidence_detail(publication_key: str) -> dict[str, Any]:
        require_unsafe_admin()
        snapshots = resolved_config_repository.list_publication_confidence_snapshots(
            publication_key=publication_key
        )
        if not snapshots:
            raise HTTPException(status_code=404, detail="No confidence snapshot found for this publication.")
        # Return the most recent (list is ordered DESC by assessed_at from storage)
        snapshot = snapshots[0]
        source_freshness_dict = None
        if snapshot.source_freshness_states:
            source_freshness_dict = {
                asset_id: {
                    "source_asset_id": state.get("source_asset_id"),
                    "freshness_state": state.get("freshness_state"),
                    "last_ingest_at": state.get("last_ingest_at"),
                    "covered_through": state.get("covered_through"),
                }
                for asset_id, state in snapshot.source_freshness_states.items()
            }
        return {
            "publication_key": snapshot.publication_key,
            "snapshot_id": snapshot.snapshot_id,
            "freshness_state": snapshot.freshness_state,
            "completeness_pct": snapshot.completeness_pct,
            "confidence_verdict": snapshot.confidence_verdict,
            "assessed_at": snapshot.assessed_at.isoformat(),
            "source_freshness_states": source_freshness_dict,
            "quality_flags": snapshot.quality_flags,
            "contributing_run_ids": list(snapshot.contributing_run_ids) if snapshot.contributing_run_ids else [],
        }

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
