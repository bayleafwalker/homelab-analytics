from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import date, datetime
from io import StringIO
from typing import Any

from packages.domains.finance.pipelines.account_transaction_service import (
    ACCOUNT_TRANSACTION_CONTRACT,
)
from packages.domains.finance.pipelines.budget_service import BUDGET_CONTRACT
from packages.domains.finance.pipelines.contract_price_service import (
    CONTRACT_PRICE_CONTRACT,
)
from packages.domains.finance.pipelines.loan_service import LOAN_REPAYMENT_CONTRACT
from packages.domains.finance.pipelines.subscription_service import (
    SUBSCRIPTION_CONTRACT,
)
from packages.pipelines.configured_csv_ingestion import map_csv_columns
from packages.pipelines.csv_validation import (
    ColumnType,
    DatasetContract,
    ValidationIssue,
    validate_csv_text,
)
from packages.pipelines.file_format import normalize_to_csv_bytes
from packages.pipelines.upload_detection import detect_upload_target
from packages.storage.ingestion_config import (
    ColumnMappingRecord,
    DatasetContractConfigRecord,
    SourceAssetRecord,
    resolve_dataset_contract,
)

_BUILTIN_UPLOAD_TARGETS: dict[str, tuple[str, str, DatasetContract]] = {
    "/upload/account-transactions": (
        "Account transactions",
        "account_transactions",
        ACCOUNT_TRANSACTION_CONTRACT,
    ),
    "/upload/subscriptions": (
        "Subscriptions",
        "subscriptions",
        SUBSCRIPTION_CONTRACT,
    ),
    "/upload/contract-prices": (
        "Contract prices",
        "contract_prices",
        CONTRACT_PRICE_CONTRACT,
    ),
    "/upload/budgets": (
        "Budgets",
        "budgets",
        BUDGET_CONTRACT,
    ),
    "/upload/loan-repayments": (
        "Loan repayments",
        "loan_repayments",
        LOAN_REPAYMENT_CONTRACT,
    ),
}


def preview_upload_dry_run(
    *,
    file_name: str,
    source_bytes: bytes,
    upload_path_override: str | None,
    source_asset_id_override: str | None,
    source_assets: list[SourceAssetRecord],
    column_mappings_by_id: dict[str, ColumnMappingRecord],
    dataset_contracts_by_id: dict[str, DatasetContractConfigRecord],
) -> dict[str, Any]:
    source_assets_by_id = {
        record.source_asset_id: record
        for record in source_assets
    }
    detection = detect_upload_target(
        file_name=file_name,
        source_bytes=source_bytes,
        source_assets=source_assets,
        column_mappings_by_id=column_mappings_by_id,
        dataset_contracts_by_id=dataset_contracts_by_id,
    )
    candidate, resolution_issues = _resolve_candidate(
        detection=detection,
        upload_path_override=upload_path_override,
        source_asset_id_override=source_asset_id_override,
        source_assets_by_id=source_assets_by_id,
        dataset_contracts_by_id=dataset_contracts_by_id,
    )
    issues: list[ValidationIssue] = list(resolution_issues)
    row_count = 0
    date_range: dict[str, str] | None = None

    if candidate is not None and not issues:
        upload_path = str(candidate.get("upload_path") or "")
        if upload_path == "/upload/configured-csv":
            row_count, date_range, preview_issues = _preview_configured_csv(
                file_name=file_name,
                source_bytes=source_bytes,
                candidate=candidate,
                source_assets_by_id=source_assets_by_id,
                column_mappings_by_id=column_mappings_by_id,
                dataset_contracts_by_id=dataset_contracts_by_id,
            )
            issues.extend(preview_issues)
        elif upload_path in _BUILTIN_UPLOAD_TARGETS:
            _, _, contract = _BUILTIN_UPLOAD_TARGETS[upload_path]
            row_count, date_range, preview_issues = _preview_csv_contract(
                file_name=file_name,
                source_bytes=source_bytes,
                contract=contract,
            )
            issues.extend(preview_issues)
        elif upload_path == "/upload/ha-states":
            row_count, date_range, preview_issues = _preview_ha_states(
                source_bytes=source_bytes,
            )
            issues.extend(preview_issues)
        else:
            issues.append(
                ValidationIssue(
                    code="unsupported_upload_target",
                    message=f"Dry-run preview is not supported for '{upload_path}'.",
                    column="upload_path",
                )
            )

    return {
        "target": _target_summary(candidate),
        "row_count": row_count,
        "date_range": date_range,
        "issues": [asdict(issue) for issue in issues[:8]],
        "issue_count": len(issues),
        "ready": len(issues) == 0,
        "detection": {
            "format": str(detection.get("format") or "unknown"),
            "file_name": str(detection.get("file_name") or file_name),
        },
    }


def _resolve_candidate(
    *,
    detection: dict[str, object],
    upload_path_override: str | None,
    source_asset_id_override: str | None,
    source_assets_by_id: dict[str, SourceAssetRecord],
    dataset_contracts_by_id: dict[str, DatasetContractConfigRecord],
) -> tuple[dict[str, object] | None, list[ValidationIssue]]:
    candidates = _list_detection_candidates(detection)
    normalized_upload_path = _normalize_optional_string(upload_path_override)
    normalized_source_asset_id = _normalize_optional_string(source_asset_id_override)

    if normalized_upload_path == "/upload/configured-csv":
        return _resolve_configured_candidate(
            candidates=candidates,
            source_asset_id_override=normalized_source_asset_id,
            source_assets_by_id=source_assets_by_id,
            dataset_contracts_by_id=dataset_contracts_by_id,
        )

    if normalized_upload_path:
        for candidate in candidates:
            if str(candidate.get("upload_path") or "") == normalized_upload_path:
                return candidate, []
        if normalized_upload_path in _BUILTIN_UPLOAD_TARGETS:
            title, contract_id, _ = _BUILTIN_UPLOAD_TARGETS[normalized_upload_path]
            return (
                {
                    "kind": "builtin",
                    "title": title,
                    "upload_path": normalized_upload_path,
                    "contract_id": contract_id,
                },
                [],
            )
        if normalized_upload_path == "/upload/ha-states":
            return (
                {
                    "kind": "builtin",
                    "title": "HA States",
                    "upload_path": normalized_upload_path,
                    "contract_id": "home_assistant_states_json_v1",
                },
                [],
            )
        return (
            None,
            [
                ValidationIssue(
                    code="unsupported_upload_target",
                    message=f"Unknown upload target '{normalized_upload_path}'.",
                    column="upload_path",
                )
            ],
        )

    if normalized_source_asset_id:
        return _resolve_configured_candidate(
            candidates=candidates,
            source_asset_id_override=normalized_source_asset_id,
            source_assets_by_id=source_assets_by_id,
            dataset_contracts_by_id=dataset_contracts_by_id,
        )

    primary = detection.get("candidate")
    if isinstance(primary, dict):
        return primary, []
    return (
        None,
        [
            ValidationIssue(
                code="no_target_detected",
                message=(
                    "Could not determine a compatible upload target. "
                    "Review file format and selected upload path."
                ),
            )
        ],
    )


def _resolve_configured_candidate(
    *,
    candidates: list[dict[str, object]],
    source_asset_id_override: str | None,
    source_assets_by_id: dict[str, SourceAssetRecord],
    dataset_contracts_by_id: dict[str, DatasetContractConfigRecord],
) -> tuple[dict[str, object] | None, list[ValidationIssue]]:
    source_asset_id = source_asset_id_override
    if not source_asset_id:
        for candidate in candidates:
            if str(candidate.get("upload_path") or "") != "/upload/configured-csv":
                continue
            detected_asset_id = _normalize_optional_string(candidate.get("source_asset_id"))
            if detected_asset_id:
                source_asset_id = detected_asset_id
                break

    if not source_asset_id:
        return (
            None,
            [
                ValidationIssue(
                    code="source_asset_required",
                    message="Configured upload dry-run requires source_asset_id.",
                    column="source_asset_id",
                )
            ],
        )

    source_asset = source_assets_by_id.get(source_asset_id)
    if source_asset is None:
        return (
            None,
            [
                ValidationIssue(
                    code="unknown_source_asset",
                    message=f"Unknown source asset '{source_asset_id}'.",
                    column="source_asset_id",
                )
            ],
        )

    issues: list[ValidationIssue] = []
    if not source_asset.enabled:
        issues.append(
            ValidationIssue(
                code="source_asset_disabled",
                message=f"Source asset '{source_asset_id}' is disabled.",
                column="source_asset_id",
            )
        )

    for candidate in candidates:
        if str(candidate.get("upload_path") or "") != "/upload/configured-csv":
            continue
        if str(candidate.get("source_asset_id") or "") == source_asset_id:
            return candidate, issues

    dataset_contract = dataset_contracts_by_id.get(source_asset.dataset_contract_id)
    contract_id = (
        dataset_contract.dataset_contract_id
        if dataset_contract is not None
        else source_asset.dataset_contract_id
    )
    return (
        {
            "kind": "configured_csv",
            "title": f"Configured asset: {source_asset_id}",
            "upload_path": "/upload/configured-csv",
            "contract_id": contract_id,
            "source_asset_id": source_asset_id,
            "column_mapping_id": source_asset.column_mapping_id,
            "confidence_label": "manual",
            "confidence_score": 0.0,
        },
        issues,
    )


def _preview_configured_csv(
    *,
    file_name: str,
    source_bytes: bytes,
    candidate: dict[str, object],
    source_assets_by_id: dict[str, SourceAssetRecord],
    column_mappings_by_id: dict[str, ColumnMappingRecord],
    dataset_contracts_by_id: dict[str, DatasetContractConfigRecord],
) -> tuple[int, dict[str, str] | None, list[ValidationIssue]]:
    source_asset_id = _normalize_optional_string(candidate.get("source_asset_id"))
    if not source_asset_id:
        return (
            0,
            None,
            [
                ValidationIssue(
                    code="source_asset_required",
                    message="Configured upload dry-run requires source_asset_id.",
                    column="source_asset_id",
                )
            ],
        )
    source_asset = source_assets_by_id.get(source_asset_id)
    if source_asset is None:
        return (
            0,
            None,
            [
                ValidationIssue(
                    code="unknown_source_asset",
                    message=f"Unknown source asset '{source_asset_id}'.",
                    column="source_asset_id",
                )
            ],
        )
    dataset_contract = dataset_contracts_by_id.get(source_asset.dataset_contract_id)
    if dataset_contract is None:
        return (
            0,
            None,
            [
                ValidationIssue(
                    code="missing_dataset_contract",
                    message=(
                        "Configured source asset references a missing dataset contract."
                    ),
                    column="dataset_contract_id",
                )
            ],
        )
    column_mapping = column_mappings_by_id.get(source_asset.column_mapping_id)
    if column_mapping is None:
        return (
            0,
            None,
            [
                ValidationIssue(
                    code="missing_column_mapping",
                    message=(
                        "Configured source asset references a missing column mapping."
                    ),
                    column="column_mapping_id",
                )
            ],
        )

    try:
        normalized_bytes = normalize_to_csv_bytes(source_bytes, file_name)
    except ValueError as exc:
        return (
            0,
            None,
            [ValidationIssue(code="invalid_format", message=str(exc))],
        )

    try:
        mapped_bytes = map_csv_columns(
            source_bytes=normalized_bytes,
            dataset_contract=dataset_contract,
            column_mapping=column_mapping,
        )
    except ValueError as exc:
        return (
            0,
            None,
            [ValidationIssue(code="mapping_error", message=str(exc))],
        )

    contract = resolve_dataset_contract(dataset_contract)
    validation = validate_csv_text(mapped_bytes.decode("utf-8"), contract)
    date_range = _extract_date_range_from_csv(
        csv_text=mapped_bytes.decode("utf-8"),
        date_columns=_contract_date_columns(contract),
    )
    return validation.row_count, date_range, list(validation.issues)


def _preview_csv_contract(
    *,
    file_name: str,
    source_bytes: bytes,
    contract: DatasetContract,
) -> tuple[int, dict[str, str] | None, list[ValidationIssue]]:
    try:
        csv_bytes = normalize_to_csv_bytes(source_bytes, file_name)
    except ValueError as exc:
        return (
            0,
            None,
            [ValidationIssue(code="invalid_format", message=str(exc))],
        )

    csv_text = csv_bytes.decode("utf-8")
    validation = validate_csv_text(csv_text, contract)
    date_range = _extract_date_range_from_csv(
        csv_text=csv_text,
        date_columns=_contract_date_columns(contract),
    )
    return validation.row_count, date_range, list(validation.issues)


def _preview_ha_states(
    *,
    source_bytes: bytes,
) -> tuple[int, dict[str, str] | None, list[ValidationIssue]]:
    try:
        payload = json.loads(source_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return (
            0,
            None,
            [ValidationIssue(code="invalid_json", message=f"Could not parse JSON: {exc}")],
        )

    if isinstance(payload, dict) and isinstance(payload.get("states"), list):
        states_payload = payload.get("states")
    else:
        states_payload = payload

    if not isinstance(states_payload, list):
        return (
            0,
            None,
            [
                ValidationIssue(
                    code="invalid_payload",
                    message="HA states upload expects an array of state objects.",
                )
            ],
        )

    rows = [entry for entry in states_payload if isinstance(entry, dict)]
    if not rows:
        return (
            0,
            None,
            [
                ValidationIssue(
                    code="empty_file",
                    message="No state rows were found in the uploaded payload.",
                )
            ],
        )

    issues: list[ValidationIssue] = []
    if not any(str(row.get("entity_id") or "").strip() for row in rows):
        issues.append(
            ValidationIssue(
                code="missing_required_column",
                message="Required field 'entity_id' is missing from all rows.",
                column="entity_id",
            )
        )
    if not any(str(row.get("state") or "").strip() for row in rows):
        issues.append(
            ValidationIssue(
                code="missing_required_column",
                message="Required field 'state' is missing from all rows.",
                column="state",
            )
        )
    date_range = _extract_date_range_from_json(
        rows=rows,
        date_fields=("last_changed", "last_updated"),
    )
    return len(rows), date_range, issues


def _contract_date_columns(contract: DatasetContract) -> list[str]:
    return [
        column.name
        for column in contract.columns
        if column.type in {ColumnType.DATE, ColumnType.DATETIME}
    ]


def _extract_date_range_from_csv(
    *,
    csv_text: str,
    date_columns: list[str],
) -> dict[str, str] | None:
    if not date_columns:
        return None
    ranges: dict[str, tuple[date, date]] = {}
    reader = csv.DictReader(StringIO(csv_text))
    for row in reader:
        if not any((value or "").strip() for value in row.values()):
            continue
        for column in date_columns:
            parsed = _parse_date_value(str(row.get(column) or ""))
            if parsed is None:
                continue
            if column not in ranges:
                ranges[column] = (parsed, parsed)
                continue
            current_start, current_end = ranges[column]
            ranges[column] = (
                parsed if parsed < current_start else current_start,
                parsed if parsed > current_end else current_end,
            )
    for column in date_columns:
        if column not in ranges:
            continue
        start, end = ranges[column]
        return {
            "column": column,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
    return None


def _extract_date_range_from_json(
    *,
    rows: list[dict[str, object]],
    date_fields: tuple[str, ...],
) -> dict[str, str] | None:
    ranges: dict[str, tuple[date, date]] = {}
    for row in rows:
        for field in date_fields:
            parsed = _parse_date_value(str(row.get(field) or ""))
            if parsed is None:
                continue
            if field not in ranges:
                ranges[field] = (parsed, parsed)
                continue
            current_start, current_end = ranges[field]
            ranges[field] = (
                parsed if parsed < current_start else current_start,
                parsed if parsed > current_end else current_end,
            )
    for field in date_fields:
        if field not in ranges:
            continue
        start, end = ranges[field]
        return {
            "column": field,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
    return None


def _parse_date_value(value: str) -> date | None:
    stripped = value.strip()
    if not stripped:
        return None

    try:
        return date.fromisoformat(stripped)
    except ValueError:
        pass

    datetime_candidate = stripped
    if datetime_candidate.endswith("Z"):
        datetime_candidate = f"{datetime_candidate[:-1]}+00:00"
    try:
        return datetime.fromisoformat(datetime_candidate).date()
    except ValueError:
        return None


def _target_summary(candidate: dict[str, object] | None) -> dict[str, object] | None:
    if candidate is None:
        return None
    return {
        "kind": str(candidate.get("kind") or ""),
        "title": str(candidate.get("title") or ""),
        "upload_path": str(candidate.get("upload_path") or ""),
        "contract_id": str(candidate.get("contract_id") or ""),
        "source_asset_id": _normalize_optional_string(candidate.get("source_asset_id")),
        "confidence_label": _normalize_optional_string(candidate.get("confidence_label")),
        "confidence_score": candidate.get("confidence_score"),
    }


def _list_detection_candidates(detection: dict[str, object]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    primary = detection.get("candidate")
    if isinstance(primary, dict):
        candidates.append(primary)
    alternatives = detection.get("alternatives")
    if isinstance(alternatives, list):
        for entry in alternatives:
            if isinstance(entry, dict):
                candidates.append(entry)
    return candidates


def _normalize_optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
