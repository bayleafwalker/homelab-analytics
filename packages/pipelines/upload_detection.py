from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, TypedDict

from packages.storage.ingestion_config import (
    ColumnMappingRecord,
    DatasetContractConfigRecord,
    SourceAssetRecord,
)

_HEADER_PREVIEW_BYTES = 128 * 1024
_DELIMITER_CANDIDATES = (",", ";", "\t", "|")
_JSON_PREFIX_BYTES = (b"{", b"[")

class BuiltinCsvTarget(TypedDict):
    target_id: str
    title: str
    upload_path: str
    contract_id: str
    required_columns: tuple[str, ...]
    optional_columns: tuple[str, ...]


_BUILTIN_CSV_TARGETS: tuple[BuiltinCsvTarget, ...] = (
    {
        "target_id": "account_transactions",
        "title": "Account transactions",
        "upload_path": "/upload/account-transactions",
        "contract_id": "account_transactions",
        "required_columns": (
            "booked_at",
            "account_id",
            "counterparty_name",
            "amount",
            "currency",
        ),
        "optional_columns": ("description",),
    },
    {
        "target_id": "subscriptions",
        "title": "Subscriptions",
        "upload_path": "/upload/subscriptions",
        "contract_id": "subscriptions",
        "required_columns": (
            "service_name",
            "provider",
            "billing_cycle",
            "amount",
            "currency",
            "start_date",
        ),
        "optional_columns": ("end_date",),
    },
    {
        "target_id": "contract_prices",
        "title": "Contract prices",
        "upload_path": "/upload/contract-prices",
        "contract_id": "contract_prices",
        "required_columns": (
            "contract_name",
            "provider",
            "contract_type",
            "price_component",
            "billing_cycle",
            "unit_price",
            "currency",
            "valid_from",
        ),
        "optional_columns": ("quantity_unit", "valid_to"),
    },
    {
        "target_id": "budgets",
        "title": "Budgets",
        "upload_path": "/upload/budgets",
        "contract_id": "budgets",
        "required_columns": (
            "budget_name",
            "category",
            "period_type",
            "target_amount",
            "currency",
            "effective_from",
        ),
        "optional_columns": ("effective_to",),
    },
    {
        "target_id": "loan_repayments",
        "title": "Loan repayments",
        "upload_path": "/upload/loan-repayments",
        "contract_id": "loan_repayments",
        "required_columns": (
            "loan_id",
            "repayment_date",
            "payment_amount",
            "currency",
        ),
        "optional_columns": (
            "principal_portion",
            "interest_portion",
            "extra_amount",
        ),
    },
)


def detect_upload_target(
    *,
    file_name: str,
    source_bytes: bytes,
    source_assets: Iterable[SourceAssetRecord],
    column_mappings_by_id: dict[str, ColumnMappingRecord],
    dataset_contracts_by_id: dict[str, DatasetContractConfigRecord],
) -> dict[str, object]:
    detected_format = _detect_format(file_name=file_name, source_bytes=source_bytes)
    if detected_format == "json":
        detection = _detect_json_target(file_name=file_name, source_bytes=source_bytes)
        return {
            "file_name": file_name,
            "format": detected_format,
            "header_columns": [],
            "candidate": detection["candidate"],
            "alternatives": detection["alternatives"],
        }
    if detected_format == "csv":
        header_columns = _extract_csv_header(source_bytes)
        candidates = _rank_csv_candidates(
            header_columns=header_columns,
            source_assets=source_assets,
            column_mappings_by_id=column_mappings_by_id,
            dataset_contracts_by_id=dataset_contracts_by_id,
        )
        primary = candidates[0] if candidates else None
        alternatives = candidates[1:4] if len(candidates) > 1 else []
        return {
            "file_name": file_name,
            "format": detected_format,
            "header_columns": header_columns,
            "candidate": primary,
            "alternatives": alternatives,
        }
    return {
        "file_name": file_name,
        "format": detected_format,
        "header_columns": [],
        "candidate": None,
        "alternatives": [],
    }


def _detect_format(*, file_name: str, source_bytes: bytes) -> str:
    suffix = Path(file_name).suffix.strip().lower()
    if suffix in {".csv", ".tsv", ".txt"}:
        return "csv"
    if suffix in {".json"}:
        return "json"
    if suffix in {".xlsx", ".xls"}:
        return "xlsx"
    stripped = source_bytes.lstrip()
    if stripped.startswith(_JSON_PREFIX_BYTES):
        return "json"
    if b"," in source_bytes[:2048] or b";" in source_bytes[:2048]:
        return "csv"
    return "unknown"


def _decode_source_preview(source_bytes: bytes) -> str:
    preview = source_bytes[:_HEADER_PREVIEW_BYTES]
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return preview.decode(encoding)
        except UnicodeDecodeError:
            continue
    return preview.decode("utf-8", errors="ignore")


def _extract_csv_header(source_bytes: bytes) -> list[str]:
    preview_text = _decode_source_preview(source_bytes)
    first_line = ""
    for line in preview_text.splitlines():
        if line.strip():
            first_line = line
            break
    if not first_line:
        return []
    delimiter = max(_DELIMITER_CANDIDATES, key=first_line.count)
    reader = csv.reader([first_line], delimiter=delimiter)
    parsed = next(reader, [])
    return [column.strip().strip("\"'").lower() for column in parsed if column.strip()]


def _rank_csv_candidates(
    *,
    header_columns: list[str],
    source_assets: Iterable[SourceAssetRecord],
    column_mappings_by_id: dict[str, ColumnMappingRecord],
    dataset_contracts_by_id: dict[str, DatasetContractConfigRecord],
) -> list[dict[str, object]]:
    if not header_columns:
        return []
    header_set = {column.lower().strip() for column in header_columns}
    candidates: list[dict[str, object]] = []
    candidates.extend(_build_configured_candidates(
        header_set=header_set,
        source_assets=source_assets,
        column_mappings_by_id=column_mappings_by_id,
        dataset_contracts_by_id=dataset_contracts_by_id,
    ))
    candidates.extend(_build_builtin_candidates(header_set=header_set))
    return sorted(candidates, key=_candidate_sort_key, reverse=True)


def _build_configured_candidates(
    *,
    header_set: set[str],
    source_assets: Iterable[SourceAssetRecord],
    column_mappings_by_id: dict[str, ColumnMappingRecord],
    dataset_contracts_by_id: dict[str, DatasetContractConfigRecord],
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for source_asset in source_assets:
        if source_asset.archived or not source_asset.enabled:
            continue
        mapping = column_mappings_by_id.get(source_asset.column_mapping_id)
        if mapping is None or mapping.archived:
            continue
        expected_columns = sorted(
            {
                str(rule.source_column).strip().lower()
                for rule in mapping.rules
                if rule.source_column
            }
        )
        if not expected_columns:
            continue
        expected_set = set(expected_columns)
        matched_columns = sorted(header_set & expected_set)
        if not matched_columns:
            continue
        missing_columns = sorted(expected_set - header_set)
        score = len(matched_columns) / len(expected_columns)
        confidence_label = _confidence_label(score)
        if confidence_label == "none":
            continue
        dataset_contract = dataset_contracts_by_id.get(source_asset.dataset_contract_id)
        candidates.append(
            {
                "kind": "configured_csv",
                "title": f"Configured asset: {source_asset.source_asset_id}",
                "upload_path": "/upload/configured-csv",
                "contract_id": (
                    dataset_contract.dataset_contract_id
                    if dataset_contract is not None
                    else source_asset.dataset_contract_id
                ),
                "source_asset_id": source_asset.source_asset_id,
                "column_mapping_id": source_asset.column_mapping_id,
                "confidence_label": confidence_label,
                "confidence_score": round(score, 3),
                "matched_columns": matched_columns,
                "missing_columns": missing_columns,
                "expected_columns": expected_columns,
                "matched_count": len(matched_columns),
            }
        )
    return candidates


def _build_builtin_candidates(*, header_set: set[str]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for target in _BUILTIN_CSV_TARGETS:
        required_columns = list(target["required_columns"])
        optional_columns = list(target["optional_columns"])
        required_set = set(required_columns)
        matched_required = sorted(required_set & header_set)
        if not matched_required:
            continue
        missing_required = sorted(required_set - header_set)
        score = len(matched_required) / len(required_columns)
        confidence_label = _confidence_label(score)
        if confidence_label == "none":
            continue
        candidates.append(
            {
                "kind": "builtin",
                "title": str(target["title"]),
                "upload_path": str(target["upload_path"]),
                "contract_id": str(target["contract_id"]),
                "confidence_label": confidence_label,
                "confidence_score": round(score, 3),
                "matched_columns": matched_required,
                "missing_columns": missing_required,
                "expected_columns": required_columns + optional_columns,
                "matched_count": len(matched_required),
            }
        )
    return candidates


def _candidate_sort_key(candidate: dict[str, object]) -> tuple[float, int, str, str]:
    return (
        _as_float(candidate.get("confidence_score")),
        _as_int(candidate.get("matched_count")),
        str(candidate.get("kind", "")),
        str(candidate.get("title", "")),
    )


def _as_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _as_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _detect_json_target(
    *,
    file_name: str,
    source_bytes: bytes,
) -> dict[str, object]:
    try:
        payload = json.loads(_decode_source_preview(source_bytes))
    except json.JSONDecodeError:
        return {"candidate": None, "alternatives": []}

    states_payload: object
    if isinstance(payload, dict) and isinstance(payload.get("states"), list):
        states_payload = payload["states"]
    else:
        states_payload = payload

    if not isinstance(states_payload, list) or not states_payload:
        return {"candidate": None, "alternatives": []}

    dict_rows = [row for row in states_payload if isinstance(row, dict)]
    if not dict_rows:
        return {"candidate": None, "alternatives": []}

    has_entity_id = any("entity_id" in row for row in dict_rows)
    has_state = any("state" in row for row in dict_rows)
    if not has_entity_id:
        return {"candidate": None, "alternatives": []}

    score = 0.97 if has_state else 0.72
    candidate = {
        "kind": "builtin",
        "title": "HA States",
        "upload_path": "/upload/ha-states",
        "contract_id": "home_assistant_states_json_v1",
        "confidence_label": _confidence_label(score),
        "confidence_score": round(score, 3),
        "matched_columns": ["entity_id"] + (["state"] if has_state else []),
        "missing_columns": [] if has_state else ["state"],
        "expected_columns": ["entity_id", "state"],
        "matched_count": 2 if has_state else 1,
        "file_name_hint": file_name,
    }
    return {"candidate": candidate, "alternatives": []}


def _confidence_label(score: float) -> str:
    if score >= 0.9:
        return "high"
    if score >= 0.65:
        return "medium"
    if score >= 0.45:
        return "low"
    return "none"
