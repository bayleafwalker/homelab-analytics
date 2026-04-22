from __future__ import annotations

import logging
import time
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

from apps.api.models import ConfiguredCsvIngestRequest
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.domains.finance.pipelines.cashflow_analytics import MonthlyCashflowSummary
from packages.pipelines.promotion import PromotionResult, promote_run
from packages.pipelines.reporting_service import (
    ReportingService,
    publish_promotion_reporting,
)
from packages.pipelines.run_context import RunControlContext
from packages.pipelines.transformation_service import TransformationService
from packages.platform.auth.role_hierarchy import AuthenticatedPrincipal
from packages.shared.metrics import metrics_registry
from packages.storage.control_plane import IngestionCatalogStore
from packages.storage.ingestion_config import (
    ColumnMappingRecord,
    DatasetContractConfigRecord,
)
from packages.storage.run_metadata import IngestionRunRecord


def build_ingest_response(
    run: IngestionRunRecord,
    service: AccountTransactionService,
    transformation_service: TransformationService | None,
    reporting_service: ReportingService | None,
) -> JSONResponse:
    promotion: PromotionResult | None = None
    if transformation_service is not None and run.passed:
        promotion = promote_run(
            run.run_id,
            account_service=service,
            transformation_service=transformation_service,
        )
        publish_promotion_reporting(reporting_service, promotion)
    return build_run_response(run, promotion=promotion)


def build_run_response(
    run: IngestionRunRecord,
    *,
    promotion: PromotionResult | None = None,
) -> JSONResponse:
    observe_ingest_run(run)
    if any(issue.code == "duplicate_file" for issue in run.issues):
        status_code = 409
    elif run.passed:
        status_code = 201
    else:
        status_code = 400
    body: dict[str, Any] = {"run": serialize_run(run)}
    if promotion is not None:
        body["promotion"] = serialize_promotion(promotion)
    return JSONResponse(status_code=status_code, content=body)


def resolve_configured_ingest_binding(
    payload: ConfiguredCsvIngestRequest,
    *,
    config_repository: IngestionCatalogStore,
):
    source_asset = (
        config_repository.get_source_asset(payload.source_asset_id)
        if payload.source_asset_id
        else None
    )
    if source_asset is not None:
        if getattr(source_asset, "archived", False):
            raise HTTPException(
                status_code=400,
                detail=f"Source asset is archived: {source_asset.source_asset_id}",
            )
        if not source_asset.enabled:
            raise HTTPException(
                status_code=400,
                detail=f"Source asset is disabled: {source_asset.source_asset_id}",
            )
        if (
            payload.source_system_id
            and payload.source_system_id != source_asset.source_system_id
        ):
            raise HTTPException(
                status_code=400,
                detail="source_system_id does not match the selected source asset.",
            )
        if (
            payload.dataset_contract_id
            and payload.dataset_contract_id != source_asset.dataset_contract_id
        ):
            raise HTTPException(
                status_code=400,
                detail="dataset_contract_id does not match the selected source asset.",
            )
        if (
            payload.column_mapping_id
            and payload.column_mapping_id != source_asset.column_mapping_id
        ):
            raise HTTPException(
                status_code=400,
                detail="column_mapping_id does not match the selected source asset.",
            )
        source_system_id = source_asset.source_system_id
        dataset_contract_id = source_asset.dataset_contract_id
        column_mapping_id = source_asset.column_mapping_id
    else:
        missing_fields = [
            field_name
            for field_name, value in (
                ("source_system_id", payload.source_system_id),
                ("dataset_contract_id", payload.dataset_contract_id),
                ("column_mapping_id", payload.column_mapping_id),
            )
            if not value
        ]
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=(
                    "source_asset_id or explicit configured-ingest binding is required; "
                    f"missing {', '.join(missing_fields)}."
                ),
            )
        source_system_id = str(payload.source_system_id)
        dataset_contract_id = str(payload.dataset_contract_id)
        column_mapping_id = str(payload.column_mapping_id)

    source_system = config_repository.get_source_system(source_system_id)
    if not source_system.enabled:
        raise HTTPException(
            status_code=400,
            detail=f"Source system is disabled: {source_system_id}",
        )
    return source_asset, source_system_id, dataset_contract_id, column_mapping_id


def observe_ingest_run(run: IngestionRunRecord) -> None:
    metrics_registry.inc(
        "ingestion_runs_total",
        1,
        help_text="Total ingestion runs observed by the API.",
    )
    if not run.passed:
        metrics_registry.inc(
            "ingestion_failures_total",
            1,
            help_text="Total failed or rejected ingestion runs observed by the API.",
        )


def request_principal_from_user(
    user: Any,
    *,
    csrf_token: str | None = None,
) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        csrf_token=csrf_token,
    )


def log_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    started: float,
) -> None:
    logger.info(
        "request handled",
        extra={
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    )


def build_dataset_contract_diff(
    left: DatasetContractConfigRecord,
    right: DatasetContractConfigRecord,
) -> dict[str, Any]:
    field_changes = []
    for field_name, left_value, right_value in (
        ("dataset_name", left.dataset_name, right.dataset_name),
        ("version", left.version, right.version),
        ("allow_extra_columns", left.allow_extra_columns, right.allow_extra_columns),
        ("archived", left.archived, right.archived),
    ):
        if left_value != right_value:
            field_changes.append(
                {
                    "field": field_name,
                    "left": to_jsonable(left_value),
                    "right": to_jsonable(right_value),
                }
            )
    left_columns = {column.name: column for column in left.columns}
    right_columns = {column.name: column for column in right.columns}
    changed_columns = []
    for column_name in sorted(set(left_columns) & set(right_columns)):
        if left_columns[column_name] == right_columns[column_name]:
            continue
        changed_columns.append(
            {
                "name": column_name,
                "left": to_jsonable(left_columns[column_name]),
                "right": to_jsonable(right_columns[column_name]),
            }
        )
    return {
        "left_id": left.dataset_contract_id,
        "right_id": right.dataset_contract_id,
        "left_version": left.version,
        "right_version": right.version,
        "field_changes": field_changes,
        "column_changes": {
            "added": to_jsonable(
                [right_columns[name] for name in sorted(set(right_columns) - set(left_columns))]
            ),
            "removed": to_jsonable(
                [left_columns[name] for name in sorted(set(left_columns) - set(right_columns))]
            ),
            "changed": changed_columns,
        },
    }


def build_column_mapping_diff(
    left: ColumnMappingRecord,
    right: ColumnMappingRecord,
) -> dict[str, Any]:
    field_changes = []
    for field_name, left_value, right_value in (
        ("source_system_id", left.source_system_id, right.source_system_id),
        ("dataset_contract_id", left.dataset_contract_id, right.dataset_contract_id),
        ("version", left.version, right.version),
        ("archived", left.archived, right.archived),
    ):
        if left_value != right_value:
            field_changes.append(
                {
                    "field": field_name,
                    "left": to_jsonable(left_value),
                    "right": to_jsonable(right_value),
                }
            )
    left_rules = {rule.target_column: rule for rule in left.rules}
    right_rules = {rule.target_column: rule for rule in right.rules}
    changed_rules = []
    for target_column in sorted(set(left_rules) & set(right_rules)):
        if left_rules[target_column] == right_rules[target_column]:
            continue
        changed_rules.append(
            {
                "target_column": target_column,
                "left": to_jsonable(left_rules[target_column]),
                "right": to_jsonable(right_rules[target_column]),
            }
        )
    return {
        "left_id": left.column_mapping_id,
        "right_id": right.column_mapping_id,
        "left_version": left.version,
        "right_version": right.version,
        "field_changes": field_changes,
        "rule_changes": {
            "added": to_jsonable(
                [right_rules[name] for name in sorted(set(right_rules) - set(left_rules))]
            ),
            "removed": to_jsonable(
                [left_rules[name] for name in sorted(set(left_rules) - set(right_rules))]
            ),
            "changed": changed_rules,
        },
    }


def serialize_promotion(promotion: PromotionResult) -> dict[str, Any]:
    return {
        "facts_loaded": promotion.facts_loaded,
        "marts_refreshed": promotion.marts_refreshed,
        "publication_keys": promotion.publication_keys,
        "skipped": promotion.skipped,
        "skip_reason": promotion.skip_reason,
    }


_CONTRACT_ISSUE_CODES = frozenset(
    {
        "missing_required_column",
        "unexpected_column",
        "duplicate_column",
        "type_mismatch",
        "invalid_value",
        "empty_file",
    }
)


def build_run_remediation(
    run: IngestionRunRecord,
    *,
    recovery: dict[str, Any] | None = None,
    has_source_asset_binding: bool = False,
) -> dict[str, str]:
    """Derive the operator remediation action for a completed run.

    Returns a dict with ``action`` (one of: retry, upload_missing_period,
    inspect_binding, fix_contract, none) and ``reason`` (human-readable).
    """
    from packages.storage.run_metadata import IngestionRunStatus

    status = run.status

    # Passed runs: check whether the promotion had a binding to promote to.
    if run.passed:
        if not has_source_asset_binding:
            return {
                "action": "inspect_binding",
                "reason": (
                    "Run landed successfully but no source asset binding was found. "
                    "Check the source system / dataset contract / column mapping configuration."
                ),
            }
        return {"action": "none", "reason": "Run completed and promoted successfully."}

    # Failed or rejected: distinguish contract issues vs retryable failures.
    issue_codes = {i.code for i in run.issues}
    if issue_codes & _CONTRACT_ISSUE_CODES:
        return {
            "action": "fix_contract",
            "reason": (
                "Run failed due to schema or contract violations. "
                "Fix the source file columns or update the dataset contract, then re-upload."
            ),
        }

    if status == IngestionRunStatus.FAILED:
        if recovery is not None and recovery.get("retry_supported"):
            return {
                "action": "retry",
                "reason": "Run failed but the payload is available. Use POST /runs/{run_id}/retry.",
            }
        return {
            "action": "upload_missing_period",
            "reason": (
                "Run failed and cannot be automatically retried. "
                "Correct and re-upload the source file for the affected period."
            ),
        }

    if status == IngestionRunStatus.REJECTED:
        return {
            "action": "upload_missing_period",
            "reason": (
                "Run was rejected. Correct and re-upload the source file for the affected period."
            ),
        }

    # Received / landed or any other status.
    return {"action": "none", "reason": "No operator action required."}


def serialize_run(
    run: IngestionRunRecord,
    *,
    context: RunControlContext | None = None,
    recovery: dict[str, Any] | None = None,
    remediation: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": run.run_id,
        "source_name": run.source_name,
        "dataset_name": run.dataset_name,
        "file_name": run.file_name,
        "raw_path": run.raw_path,
        "manifest_path": run.manifest_path,
        "sha256": run.sha256,
        "row_count": run.row_count,
        "header": list(run.header),
        "status": run.status.value,
        "passed": run.passed,
        "issues": [
            {
                "code": issue.code,
                "message": issue.message,
                "column": issue.column,
                "row_number": issue.row_number,
            }
            for issue in run.issues
        ],
        "created_at": run.created_at.isoformat(),
    }
    if context is not None:
        payload["context"] = context.as_manifest_dict()
    if recovery is not None:
        payload["recovery"] = recovery
    if remediation is not None:
        payload["remediation"] = remediation
    return payload


def serialize_summary(summary: MonthlyCashflowSummary) -> dict[str, Any]:
    return {
        "booking_month": summary.booking_month,
        "income": str(summary.income),
        "expense": str(summary.expense),
        "net": str(summary.net),
        "transaction_count": summary.transaction_count,
    }


_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def require_upload(value: object) -> UploadFile:
    if not isinstance(value, UploadFile):
        raise ValueError("multipart request must include file")
    return value


async def read_upload_limited(upload: UploadFile) -> bytes:
    """Stream upload into memory, raising ValueError if it exceeds _MAX_UPLOAD_BYTES."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_UPLOAD_BYTES:
            raise ValueError(
                f"Upload exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB size limit."
            )
        chunks.append(chunk)
    return b"".join(chunks)


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: to_jsonable(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(inner) for inner in value]
    return value
