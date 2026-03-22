from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from apps.api.export_contracts import DEFAULT_GENERATED_DIR, export_contracts

JSON_ARTIFACT_FILENAMES = ("openapi.json", "publication-contracts.json")
RELEASE_ARTIFACT_FILENAMES = (
    "openapi.json",
    "publication-contracts.json",
    "api.d.ts",
    "publication-contracts.ts",
)
DEFAULT_RELEASE_DIR = Path("dist/contracts")
HTTP_METHODS = {"get", "put", "post", "patch", "delete", "options", "head"}
UNION_MEMBER_REPLACEMENT_COST = 101


@dataclass(frozen=True)
class ContractArtifactsSnapshot:
    openapi: dict[str, Any]
    publication_contracts: dict[str, Any]


@dataclass(frozen=True)
class ContractChange:
    severity: str
    scope: str
    identifier: str
    detail: str


@dataclass(frozen=True)
class UnionSchemaMember:
    identifier: str
    member: dict[str, Any]


def load_contract_artifacts(directory: Path) -> ContractArtifactsSnapshot:
    return ContractArtifactsSnapshot(
        openapi=_read_json(directory / "openapi.json"),
        publication_contracts=_read_json(directory / "publication-contracts.json"),
    )


def load_contract_artifacts_from_git_ref(
    ref: str,
    *,
    generated_dir: Path = DEFAULT_GENERATED_DIR,
) -> ContractArtifactsSnapshot:
    return ContractArtifactsSnapshot(
        openapi=json.loads(_read_git_file(ref, generated_dir / "openapi.json")),
        publication_contracts=json.loads(
            _read_git_file(ref, generated_dir / "publication-contracts.json")
        ),
    )


def check_export_artifacts_in_sync(
    *,
    generated_dir: Path = DEFAULT_GENERATED_DIR,
) -> None:
    with TemporaryDirectory(prefix="homelab-analytics-contract-export-") as temp_dir:
        exported_dir = Path(temp_dir)
        export_contracts(exported_dir)
        stale_files = [
            filename
            for filename in JSON_ARTIFACT_FILENAMES
            if (generated_dir / filename).read_text(encoding="utf-8")
            != (exported_dir / filename).read_text(encoding="utf-8")
        ]
    if stale_files:
        stale_list = ", ".join(stale_files)
        raise ValueError(
            "Backend-owned generated contract artifacts are stale. "
            f"Run `python -m apps.api.export_contracts` and regenerate the frontend types. "
            f"Stale files: {stale_list}."
        )


def build_contract_compatibility_report(
    *,
    baseline: ContractArtifactsSnapshot | None,
    candidate: ContractArtifactsSnapshot,
    baseline_label: str,
    candidate_label: str,
) -> dict[str, Any]:
    if baseline is None:
        return {
            "status": "initial",
            "baseline": baseline_label,
            "candidate": candidate_label,
            "breaking_changes": [],
            "additive_changes": [],
            "policy_warnings": [],
            "summary": "No baseline contract artifacts were available for comparison.",
        }

    changes: list[ContractChange] = []
    policy_warnings: list[str] = []
    _compare_openapi_contracts(baseline.openapi, candidate.openapi, changes)
    _compare_publication_contracts(
        baseline.publication_contracts,
        candidate.publication_contracts,
        changes,
        policy_warnings,
    )

    breaking_changes = [
        _serialize_change(change) for change in changes if change.severity == "breaking"
    ]
    additive_changes = [
        _serialize_change(change) for change in changes if change.severity == "additive"
    ]
    status = "breaking" if breaking_changes else ("additive" if additive_changes else "unchanged")
    return {
        "status": status,
        "baseline": baseline_label,
        "candidate": candidate_label,
        "breaking_changes": breaking_changes,
        "additive_changes": additive_changes,
        "policy_warnings": policy_warnings,
        "summary": _build_summary(status, len(breaking_changes), len(additive_changes)),
    }


def write_contract_compatibility_report(output_dir: Path, report: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "compatibility-summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "compatibility-summary.md").write_text(
        _build_markdown_summary(report),
        encoding="utf-8",
    )


def write_release_artifact_bundle(
    *,
    generated_dir: Path = DEFAULT_GENERATED_DIR,
    output_dir: Path = DEFAULT_RELEASE_DIR,
    compatibility_report: dict[str, Any] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_hashes: dict[str, str] = {}
    for filename in RELEASE_ARTIFACT_FILENAMES:
        source = generated_dir / filename
        target = output_dir / filename
        shutil.copy2(source, target)
        file_hashes[filename] = hashlib.sha256(target.read_bytes()).hexdigest()

    manifest: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "artifacts": file_hashes,
    }
    if compatibility_report is not None:
        manifest["compatibility_status"] = compatibility_report["status"]
        write_contract_compatibility_report(output_dir, compatibility_report)

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_git_file(ref: str, path: Path) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path.as_posix()}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise ValueError(
            f"Could not read contract artifact {path} from git ref {ref!r}: {stderr}"
        )
    return result.stdout


def _serialize_change(change: ContractChange) -> dict[str, str]:
    return {
        "severity": change.severity,
        "scope": change.scope,
        "identifier": change.identifier,
        "detail": change.detail,
    }


def _build_summary(status: str, breaking_count: int, additive_count: int) -> str:
    if status == "unchanged":
        return "No contract changes detected."
    if status == "initial":
        return "No baseline contract artifacts were available for comparison."
    return (
        f"{status.capitalize()} contract changes detected: "
        f"{breaking_count} breaking, {additive_count} additive."
    )


def _build_markdown_summary(report: dict[str, Any]) -> str:
    lines = [
        "# Contract Compatibility Summary",
        "",
        f"- Status: `{report['status']}`",
        f"- Baseline: `{report['baseline']}`",
        f"- Candidate: `{report['candidate']}`",
        f"- Summary: {report['summary']}",
        "",
        "## Breaking Changes",
    ]
    breaking_changes = report.get("breaking_changes", [])
    if breaking_changes:
        lines.extend(
            f"- `{change['scope']}` `{change['identifier']}`: {change['detail']}"
            for change in breaking_changes
        )
    else:
        lines.append("- None")

    lines.extend(["", "## Additive Changes"])
    additive_changes = report.get("additive_changes", [])
    if additive_changes:
        lines.extend(
            f"- `{change['scope']}` `{change['identifier']}`: {change['detail']}"
            for change in additive_changes
        )
    else:
        lines.append("- None")

    lines.extend(["", "## Policy Warnings"])
    policy_warnings = report.get("policy_warnings", [])
    if policy_warnings:
        lines.extend(f"- {warning}" for warning in policy_warnings)
    else:
        lines.append("- None")

    lines.append("")
    return "\n".join(lines)


def _compare_openapi_contracts(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    changes: list[ContractChange],
) -> None:
    base_operations = _collect_operations(baseline)
    candidate_operations = _collect_operations(candidate)

    for operation_key in sorted(base_operations):
        if operation_key not in candidate_operations:
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope="route",
                    identifier=operation_key,
                    detail="route operation was removed",
                )
            )
            continue
        _compare_operation(
            baseline,
            candidate,
            operation_key,
            base_operations[operation_key],
            candidate_operations[operation_key],
            changes,
        )

    for operation_key in sorted(candidate_operations):
        if operation_key not in base_operations:
            changes.append(
                ContractChange(
                    severity="additive",
                    scope="route",
                    identifier=operation_key,
                    detail="new route operation was added",
                )
            )


def _collect_operations(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    operations: dict[str, dict[str, Any]] = {}
    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operations[f"{method.upper()} {path}"] = operation
    return operations


def _compare_operation(
    baseline_spec: dict[str, Any],
    candidate_spec: dict[str, Any],
    identifier: str,
    baseline_operation: dict[str, Any],
    candidate_operation: dict[str, Any],
    changes: list[ContractChange],
) -> None:
    _compare_parameters(
        baseline_spec,
        candidate_spec,
        identifier,
        baseline_operation.get("parameters", []),
        candidate_operation.get("parameters", []),
        changes,
    )
    _compare_request_bodies(
        baseline_spec,
        candidate_spec,
        identifier,
        baseline_operation.get("requestBody"),
        candidate_operation.get("requestBody"),
        changes,
    )
    _compare_responses(
        baseline_spec,
        candidate_spec,
        identifier,
        baseline_operation.get("responses", {}),
        candidate_operation.get("responses", {}),
        changes,
    )


def _compare_parameters(
    baseline_spec: dict[str, Any],
    candidate_spec: dict[str, Any],
    operation_identifier: str,
    baseline_parameters: list[dict[str, Any]],
    candidate_parameters: list[dict[str, Any]],
    changes: list[ContractChange],
) -> None:
    base_map = {
        (_resolve_parameter(baseline_spec, parameter)["name"], _resolve_parameter(baseline_spec, parameter)["in"]):
        _resolve_parameter(baseline_spec, parameter)
        for parameter in baseline_parameters
    }
    candidate_map = {
        (_resolve_parameter(candidate_spec, parameter)["name"], _resolve_parameter(candidate_spec, parameter)["in"]):
        _resolve_parameter(candidate_spec, parameter)
        for parameter in candidate_parameters
    }

    for key, baseline_parameter in base_map.items():
        if key not in candidate_map:
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope="route-parameter",
                    identifier=f"{operation_identifier} parameter {key[1]}:{key[0]}",
                    detail="parameter was removed",
                )
            )
            continue
        candidate_parameter = candidate_map[key]
        if baseline_parameter.get("required") is False and candidate_parameter.get("required") is True:
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope="route-parameter",
                    identifier=f"{operation_identifier} parameter {key[1]}:{key[0]}",
                    detail="parameter became required",
                )
            )
        _compare_schema(
            baseline_spec,
            baseline_parameter.get("schema"),
            candidate_spec,
            candidate_parameter.get("schema"),
            scope="route-parameter",
            identifier=f"{operation_identifier} parameter {key[1]}:{key[0]}",
            direction="request",
            changes=changes,
        )

    for key, candidate_parameter in candidate_map.items():
        if key in base_map:
            continue
        severity = "breaking" if candidate_parameter.get("required") else "additive"
        detail = (
            "new required parameter was added"
            if candidate_parameter.get("required")
            else "new optional parameter was added"
        )
        changes.append(
            ContractChange(
                severity=severity,
                scope="route-parameter",
                identifier=f"{operation_identifier} parameter {key[1]}:{key[0]}",
                detail=detail,
            )
        )


def _compare_request_bodies(
    baseline_spec: dict[str, Any],
    candidate_spec: dict[str, Any],
    operation_identifier: str,
    baseline_request_body: dict[str, Any] | None,
    candidate_request_body: dict[str, Any] | None,
    changes: list[ContractChange],
) -> None:
    baseline_body = _resolve_request_body(baseline_spec, baseline_request_body)
    candidate_body = _resolve_request_body(candidate_spec, candidate_request_body)
    if baseline_body is None and candidate_body is None:
        return
    if baseline_body is None and candidate_body is not None:
        severity = "breaking" if candidate_body.get("required") else "additive"
        changes.append(
            ContractChange(
                severity=severity,
                scope="route-request",
                identifier=operation_identifier,
                detail="request body was added",
            )
        )
        return
    if baseline_body is not None and candidate_body is None:
        changes.append(
            ContractChange(
                severity="breaking",
                scope="route-request",
                identifier=operation_identifier,
                detail="request body was removed",
            )
        )
        return
    assert baseline_body is not None
    assert candidate_body is not None
    baseline_required = bool(baseline_body.get("required"))
    candidate_required = bool(candidate_body.get("required"))
    if not baseline_required and candidate_required:
        changes.append(
            ContractChange(
                severity="breaking",
                scope="route-request",
                identifier=operation_identifier,
                detail="request body became required",
            )
        )
    elif baseline_required and not candidate_required:
        changes.append(
            ContractChange(
                severity="additive",
                scope="route-request",
                identifier=operation_identifier,
                detail="request body became optional",
            )
        )
    _compare_schema(
        baseline_spec,
        _select_json_schema(baseline_body),
        candidate_spec,
        _select_json_schema(candidate_body),
        scope="route-request",
        identifier=operation_identifier,
        direction="request",
        changes=changes,
    )


def _compare_responses(
    baseline_spec: dict[str, Any],
    candidate_spec: dict[str, Any],
    operation_identifier: str,
    baseline_responses: dict[str, Any],
    candidate_responses: dict[str, Any],
    changes: list[ContractChange],
) -> None:
    baseline_success = {
        code: response
        for code, response in baseline_responses.items()
        if str(code).startswith("2")
    }
    candidate_success = {
        code: response
        for code, response in candidate_responses.items()
        if str(code).startswith("2")
    }

    for code, baseline_response in baseline_success.items():
        if code not in candidate_success:
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope="route-response",
                    identifier=f"{operation_identifier} {code}",
                    detail="success response code was removed",
                )
            )
            continue
        _compare_schema(
            baseline_spec,
            _select_json_schema(_resolve_response(baseline_spec, baseline_response)),
            candidate_spec,
            _select_json_schema(_resolve_response(candidate_spec, candidate_success[code])),
            scope="route-response",
            identifier=f"{operation_identifier} {code}",
            direction="response",
            changes=changes,
        )

    for code in candidate_success:
        if code not in baseline_success:
            changes.append(
                ContractChange(
                    severity="additive",
                    scope="route-response",
                    identifier=f"{operation_identifier} {code}",
                    detail="new success response code was added",
                )
            )


def _compare_publication_contracts(
    baseline_payload: dict[str, Any],
    candidate_payload: dict[str, Any],
    changes: list[ContractChange],
    policy_warnings: list[str],
) -> None:
    base_publications = {
        contract["publication_key"]: contract
        for contract in baseline_payload.get("publication_contracts", [])
    }
    candidate_publications = {
        contract["publication_key"]: contract
        for contract in candidate_payload.get("publication_contracts", [])
    }

    for publication_key, baseline_contract in base_publications.items():
        candidate_contract = candidate_publications.get(publication_key)
        if candidate_contract is None:
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope="publication",
                    identifier=publication_key,
                    detail="publication contract was removed",
                )
            )
            continue
        before_breaking = len([change for change in changes if change.severity == "breaking"])
        _compare_publication_metadata(
            publication_key,
            baseline_contract,
            candidate_contract,
            changes,
        )
        _compare_publication_columns(publication_key, baseline_contract, candidate_contract, changes)
        after_breaking = len([change for change in changes if change.severity == "breaking"])
        if after_breaking > before_breaking and not _schema_version_major_bumped(
            baseline_contract.get("schema_version"),
            candidate_contract.get("schema_version"),
        ):
            policy_warnings.append(
                "Publication "
                f"`{publication_key}` contains breaking contract changes without a major "
                "schema_version bump."
            )

    for publication_key in sorted(candidate_publications):
        if publication_key not in base_publications:
            changes.append(
                ContractChange(
                    severity="additive",
                    scope="publication",
                    identifier=publication_key,
                    detail="new publication contract was added",
                )
            )

    _compare_ui_descriptors(
        baseline_payload.get("ui_descriptors", []),
        candidate_payload.get("ui_descriptors", []),
        changes,
    )


def _compare_publication_metadata(
    publication_key: str,
    baseline_contract: dict[str, Any],
    candidate_contract: dict[str, Any],
    changes: list[ContractChange],
) -> None:
    for field_name in ("relation_name", "schema_name", "visibility", "retention_policy"):
        if baseline_contract.get(field_name) == candidate_contract.get(field_name):
            continue
        changes.append(
            ContractChange(
                severity="breaking",
                scope="publication",
                identifier=publication_key,
                detail=f"{field_name} changed",
            )
        )

    if baseline_contract.get("lineage_required") != candidate_contract.get("lineage_required"):
        severity = (
            "breaking"
            if baseline_contract.get("lineage_required") is False
            and candidate_contract.get("lineage_required") is True
            else "additive"
        )
        detail = (
            "lineage became required"
            if severity == "breaking"
            else "lineage is no longer required"
        )
        changes.append(
            ContractChange(
                severity=severity,
                scope="publication",
                identifier=publication_key,
                detail=detail,
            )
        )

    _compare_additive_text_metadata(
        scope="publication",
        identifier=publication_key,
        field_name="display_name",
        baseline_value=baseline_contract.get("display_name"),
        candidate_value=candidate_contract.get("display_name"),
        changes=changes,
    )
    _compare_additive_text_metadata(
        scope="publication",
        identifier=publication_key,
        field_name="description",
        baseline_value=baseline_contract.get("description"),
        candidate_value=candidate_contract.get("description"),
        changes=changes,
    )
    _compare_set_contract(
        scope="publication",
        identifier=publication_key,
        field_name="supported_renderers",
        baseline_values=baseline_contract.get("supported_renderers", ()),
        candidate_values=candidate_contract.get("supported_renderers", ()),
        changes=changes,
        removal_detail="supported renderer was removed",
        addition_detail="supported renderer was added",
    )
    _compare_mapping_contract(
        scope="publication",
        identifier=publication_key,
        field_name="renderer_hints",
        baseline_mapping=baseline_contract.get("renderer_hints", {}),
        candidate_mapping=candidate_contract.get("renderer_hints", {}),
        changes=changes,
        addition_detail="renderer hint was added",
        removal_detail="renderer hint was removed",
        change_detail="renderer hint changed",
        changed_value_severity="breaking",
        removed_value_severity="breaking",
        added_value_severity="additive",
    )


def _compare_publication_columns(
    publication_key: str,
    baseline_contract: dict[str, Any],
    candidate_contract: dict[str, Any],
    changes: list[ContractChange],
) -> None:
    base_columns = {column["name"]: column for column in baseline_contract.get("columns", [])}
    candidate_columns = {
        column["name"]: column for column in candidate_contract.get("columns", [])
    }

    for column_name, base_column in base_columns.items():
        candidate_column = candidate_columns.get(column_name)
        if candidate_column is None:
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope="publication-column",
                    identifier=f"{publication_key}.{column_name}",
                    detail="column was removed",
                )
            )
            continue
        if base_column.get("storage_type") != candidate_column.get("storage_type"):
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope="publication-column",
                    identifier=f"{publication_key}.{column_name}",
                    detail="storage_type changed",
                )
            )
        if base_column.get("json_type") != candidate_column.get("json_type"):
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope="publication-column",
                    identifier=f"{publication_key}.{column_name}",
                    detail="json_type changed",
                )
            )
        _compare_additive_text_metadata(
            scope="publication-column",
            identifier=f"{publication_key}.{column_name}",
            field_name="description",
            baseline_value=base_column.get("description"),
            candidate_value=candidate_column.get("description"),
            changes=changes,
        )
        if base_column.get("semantic_role") != candidate_column.get("semantic_role"):
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope="publication-column",
                    identifier=f"{publication_key}.{column_name}",
                    detail="semantic_role changed",
                )
            )
        _compare_optional_metadata_field(
            scope="publication-column",
            identifier=f"{publication_key}.{column_name}",
            field_name="unit",
            baseline_value=base_column.get("unit"),
            candidate_value=candidate_column.get("unit"),
            changes=changes,
        )
        _compare_optional_metadata_field(
            scope="publication-column",
            identifier=f"{publication_key}.{column_name}",
            field_name="grain",
            baseline_value=base_column.get("grain"),
            candidate_value=candidate_column.get("grain"),
            changes=changes,
        )
        _compare_optional_metadata_field(
            scope="publication-column",
            identifier=f"{publication_key}.{column_name}",
            field_name="aggregation",
            baseline_value=base_column.get("aggregation"),
            candidate_value=candidate_column.get("aggregation"),
            changes=changes,
        )
        if base_column.get("nullable") is True and candidate_column.get("nullable") is False:
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope="publication-column",
                    identifier=f"{publication_key}.{column_name}",
                    detail="column became non-nullable",
                )
            )
        elif base_column.get("nullable") is False and candidate_column.get("nullable") is True:
            changes.append(
                ContractChange(
                    severity="additive",
                    scope="publication-column",
                    identifier=f"{publication_key}.{column_name}",
                    detail="column became nullable",
                )
            )
        _compare_boolean_capability(
            scope="publication-column",
            identifier=f"{publication_key}.{column_name}",
            field_name="filterable",
            baseline_value=base_column.get("filterable"),
            candidate_value=candidate_column.get("filterable"),
            changes=changes,
        )
        _compare_boolean_capability(
            scope="publication-column",
            identifier=f"{publication_key}.{column_name}",
            field_name="sortable",
            baseline_value=base_column.get("sortable"),
            candidate_value=candidate_column.get("sortable"),
            changes=changes,
        )

    for column_name in sorted(candidate_columns):
        if column_name not in base_columns:
            changes.append(
                ContractChange(
                    severity="additive",
                    scope="publication-column",
                    identifier=f"{publication_key}.{column_name}",
                    detail="new column was added",
                )
            )


def _compare_ui_descriptors(
    baseline_descriptors: list[dict[str, Any]],
    candidate_descriptors: list[dict[str, Any]],
    changes: list[ContractChange],
) -> None:
    base_map = {descriptor["key"]: descriptor for descriptor in baseline_descriptors}
    candidate_map = {descriptor["key"]: descriptor for descriptor in candidate_descriptors}

    for descriptor_key, baseline_descriptor in base_map.items():
        candidate_descriptor = candidate_map.get(descriptor_key)
        if candidate_descriptor is None:
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope="ui-descriptor",
                    identifier=descriptor_key,
                    detail="UI descriptor was removed",
                )
            )
            continue
        removed_publications = sorted(
            set(baseline_descriptor.get("publication_keys", ()))
            - set(candidate_descriptor.get("publication_keys", ()))
        )
        added_publications = sorted(
            set(candidate_descriptor.get("publication_keys", ()))
            - set(baseline_descriptor.get("publication_keys", ()))
        )
        for publication_key in removed_publications:
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope="ui-descriptor",
                    identifier=descriptor_key,
                    detail=f"descriptor no longer references publication `{publication_key}`",
                )
            )
        for publication_key in added_publications:
            changes.append(
                ContractChange(
                    severity="additive",
                    scope="ui-descriptor",
                    identifier=descriptor_key,
                    detail=f"descriptor now references publication `{publication_key}`",
                )
            )
        if baseline_descriptor.get("nav_path") != candidate_descriptor.get("nav_path"):
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope="ui-descriptor",
                    identifier=descriptor_key,
                    detail="nav_path changed",
                )
            )
        if baseline_descriptor.get("kind") != candidate_descriptor.get("kind"):
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope="ui-descriptor",
                    identifier=descriptor_key,
                    detail="kind changed",
                )
            )
        _compare_additive_text_metadata(
            scope="ui-descriptor",
            identifier=descriptor_key,
            field_name="nav_label",
            baseline_value=baseline_descriptor.get("nav_label"),
            candidate_value=candidate_descriptor.get("nav_label"),
            changes=changes,
        )
        _compare_additive_text_metadata(
            scope="ui-descriptor",
            identifier=descriptor_key,
            field_name="icon",
            baseline_value=baseline_descriptor.get("icon"),
            candidate_value=candidate_descriptor.get("icon"),
            changes=changes,
        )
        _compare_set_contract(
            scope="ui-descriptor",
            identifier=descriptor_key,
            field_name="supported_renderers",
            baseline_values=baseline_descriptor.get("supported_renderers", ()),
            candidate_values=candidate_descriptor.get("supported_renderers", ()),
            changes=changes,
            removal_detail="supported renderer was removed",
            addition_detail="supported renderer was added",
        )
        _compare_permission_contract(
            descriptor_key,
            baseline_descriptor.get("required_permissions", ()),
            candidate_descriptor.get("required_permissions", ()),
            changes,
        )
        _compare_mapping_contract(
            scope="ui-descriptor",
            identifier=descriptor_key,
            field_name="renderer_hints",
            baseline_mapping=baseline_descriptor.get("renderer_hints", {}),
            candidate_mapping=candidate_descriptor.get("renderer_hints", {}),
            changes=changes,
            addition_detail="renderer hint was added",
            removal_detail="renderer hint was removed",
            change_detail="renderer hint changed",
            changed_value_severity="breaking",
            removed_value_severity="breaking",
            added_value_severity="additive",
        )
        _compare_mapping_contract(
            scope="ui-descriptor",
            identifier=descriptor_key,
            field_name="default_filters",
            baseline_mapping=baseline_descriptor.get("default_filters", {}),
            candidate_mapping=candidate_descriptor.get("default_filters", {}),
            changes=changes,
            addition_detail="default filter was added",
            removal_detail="default filter was removed",
            change_detail="default filter changed",
            changed_value_severity="additive",
            removed_value_severity="additive",
            added_value_severity="additive",
        )

    for descriptor_key in sorted(candidate_map):
        if descriptor_key not in base_map:
            changes.append(
                ContractChange(
                    severity="additive",
                    scope="ui-descriptor",
                    identifier=descriptor_key,
                    detail="new UI descriptor was added",
                )
            )


def _compare_schema(
    baseline_spec: dict[str, Any],
    baseline_schema: dict[str, Any] | None,
    candidate_spec: dict[str, Any],
    candidate_schema: dict[str, Any] | None,
    *,
    scope: str,
    identifier: str,
    direction: str,
    changes: list[ContractChange],
) -> None:
    if baseline_schema is None and candidate_schema is None:
        return
    if baseline_schema is None and candidate_schema is not None:
        changes.append(
            ContractChange(
                severity="additive" if direction == "response" else "breaking",
                scope=scope,
                identifier=identifier,
                detail="schema was added",
            )
        )
        return
    if baseline_schema is not None and candidate_schema is None:
        changes.append(
            ContractChange(
                severity="breaking",
                scope=scope,
                identifier=identifier,
                detail="schema was removed",
            )
        )
        return

    assert baseline_schema is not None
    assert candidate_schema is not None

    resolved_baseline, baseline_nullable = _normalize_nullable_schema(
        _resolve_schema(baseline_spec, baseline_schema)
    )
    resolved_candidate, candidate_nullable = _normalize_nullable_schema(
        _resolve_schema(candidate_spec, candidate_schema)
    )
    resolved_baseline = _resolve_schema(baseline_spec, resolved_baseline)
    resolved_candidate = _resolve_schema(candidate_spec, resolved_candidate)

    if baseline_nullable != candidate_nullable:
        if direction == "request":
            severity = "breaking" if baseline_nullable and not candidate_nullable else "additive"
        else:
            severity = "breaking" if not baseline_nullable and candidate_nullable else "additive"
        changes.append(
            ContractChange(
                severity=severity,
                scope=scope,
                identifier=identifier,
                detail="nullability changed",
            )
        )

    baseline_union_kind = _union_kind(resolved_baseline)
    candidate_union_kind = _union_kind(resolved_candidate)
    if baseline_union_kind or candidate_union_kind:
        _compare_union_schema(
            baseline_spec,
            resolved_baseline,
            candidate_spec,
            resolved_candidate,
            scope=scope,
            identifier=identifier,
            direction=direction,
            changes=changes,
            baseline_union_kind=baseline_union_kind,
            candidate_union_kind=candidate_union_kind,
        )
        return

    baseline_kind = _schema_kind(resolved_baseline)
    candidate_kind = _schema_kind(resolved_candidate)
    if baseline_kind != candidate_kind:
        changes.append(
            ContractChange(
                severity="breaking",
                scope=scope,
                identifier=identifier,
                detail=f"schema type changed from {baseline_kind} to {candidate_kind}",
            )
        )
        return

    if baseline_kind == "object":
        _compare_object_schema(
            baseline_spec,
            resolved_baseline,
            candidate_spec,
            resolved_candidate,
            scope=scope,
            identifier=identifier,
            direction=direction,
            changes=changes,
        )
        return
    if baseline_kind == "array":
        _compare_schema(
            baseline_spec,
            resolved_baseline.get("items"),
            candidate_spec,
            resolved_candidate.get("items"),
            scope=scope,
            identifier=f"{identifier}[]",
            direction=direction,
            changes=changes,
        )
        return

    baseline_enum = baseline_schema.get("enum") or resolved_baseline.get("enum")
    candidate_enum = candidate_schema.get("enum") or resolved_candidate.get("enum")
    if baseline_enum != candidate_enum:
        if set(baseline_enum or ()).issubset(set(candidate_enum or ())):
            severity = "additive"
            detail = "enum values expanded"
        else:
            severity = "breaking"
            detail = "enum values changed incompatibly"
        changes.append(
            ContractChange(
                severity=severity,
                scope=scope,
                identifier=identifier,
                detail=detail,
            )
        )

    baseline_format = resolved_baseline.get("format")
    candidate_format = resolved_candidate.get("format")
    if baseline_format != candidate_format:
        changes.append(
            ContractChange(
                severity="breaking",
                scope=scope,
                identifier=identifier,
                detail="schema format changed",
            )
        )


def _compare_object_schema(
    baseline_spec: dict[str, Any],
    baseline_schema: dict[str, Any],
    candidate_spec: dict[str, Any],
    candidate_schema: dict[str, Any],
    *,
    scope: str,
    identifier: str,
    direction: str,
    changes: list[ContractChange],
) -> None:
    baseline_properties = baseline_schema.get("properties", {})
    candidate_properties = candidate_schema.get("properties", {})
    baseline_required = set(baseline_schema.get("required", []))
    candidate_required = set(candidate_schema.get("required", []))

    for property_name, property_schema in baseline_properties.items():
        if property_name not in candidate_properties:
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope=scope,
                    identifier=f"{identifier}.{property_name}",
                    detail="property was removed",
                )
            )
            continue
        if direction == "request":
            if property_name not in baseline_required and property_name in candidate_required:
                changes.append(
                    ContractChange(
                        severity="breaking",
                        scope=scope,
                        identifier=f"{identifier}.{property_name}",
                        detail="property became required",
                    )
                )
        elif property_name in baseline_required and property_name not in candidate_required:
            changes.append(
                ContractChange(
                    severity="breaking",
                    scope=scope,
                    identifier=f"{identifier}.{property_name}",
                    detail="response property became optional",
                )
            )

        _compare_schema(
            baseline_spec,
            property_schema,
            candidate_spec,
            candidate_properties[property_name],
            scope=scope,
            identifier=f"{identifier}.{property_name}",
            direction=direction,
            changes=changes,
        )

    for property_name in sorted(candidate_properties):
        if property_name in baseline_properties:
            continue
        severity = "additive"
        detail = "new response property was added"
        if direction == "request":
            severity = "breaking" if property_name in candidate_required else "additive"
            detail = (
                "new required request property was added"
                if property_name in candidate_required
                else "new optional request property was added"
            )
        changes.append(
            ContractChange(
                severity=severity,
                scope=scope,
                identifier=f"{identifier}.{property_name}",
                detail=detail,
            )
        )


def _resolve_parameter(spec: dict[str, Any], parameter: dict[str, Any]) -> dict[str, Any]:
    if "$ref" not in parameter:
        return parameter
    ref_name = str(parameter["$ref"]).split("/")[-1]
    return spec.get("components", {}).get("parameters", {}).get(ref_name, parameter)


def _resolve_request_body(
    spec: dict[str, Any],
    request_body: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if request_body is None or "$ref" not in request_body:
        return request_body
    ref_name = str(request_body["$ref"]).split("/")[-1]
    return spec.get("components", {}).get("requestBodies", {}).get(ref_name, request_body)


def _resolve_response(spec: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    if "$ref" not in response:
        return response
    ref_name = str(response["$ref"]).split("/")[-1]
    return spec.get("components", {}).get("responses", {}).get(ref_name, response)


def _select_json_schema(response_or_body: dict[str, Any] | None) -> dict[str, Any] | None:
    if response_or_body is None:
        return None
    content = response_or_body.get("content", {})
    for media_type in ("application/json", "application/problem+json", "*/*"):
        media_content = content.get(media_type)
        if isinstance(media_content, dict):
            schema = media_content.get("schema")
            if isinstance(schema, dict):
                return schema
    return None


def _resolve_schema(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in schema:
        ref_name = str(schema["$ref"]).split("/")[-1]
        target = spec.get("components", {}).get("schemas", {}).get(ref_name)
        if isinstance(target, dict):
            return _resolve_schema(spec, target)
    if "allOf" in schema and isinstance(schema["allOf"], list):
        merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        for item in schema["allOf"]:
            resolved = _resolve_schema(spec, item)
            if _schema_kind(resolved) != "object":
                return resolved
            merged["properties"].update(resolved.get("properties", {}))
            merged["required"].extend(resolved.get("required", []))
        merged["required"] = sorted(set(merged["required"]))
        return merged
    return schema


def _union_kind(schema: dict[str, Any]) -> str | None:
    for union_key in ("anyOf", "oneOf"):
        if isinstance(schema.get(union_key), list):
            return union_key
    return None


def _compare_union_schema(
    baseline_spec: dict[str, Any],
    baseline_schema: dict[str, Any],
    candidate_spec: dict[str, Any],
    candidate_schema: dict[str, Any],
    *,
    scope: str,
    identifier: str,
    direction: str,
    changes: list[ContractChange],
    baseline_union_kind: str | None,
    candidate_union_kind: str | None,
) -> None:
    if baseline_union_kind != candidate_union_kind:
        changes.append(
            ContractChange(
                severity="breaking",
                scope=scope,
                identifier=identifier,
                detail=(
                    "union schema kind changed "
                    f"from {baseline_union_kind or 'non-union'} "
                    f"to {candidate_union_kind or 'non-union'}"
                ),
            )
        )
        return

    assert baseline_union_kind is not None
    baseline_members = _collect_union_members(baseline_spec, baseline_schema, baseline_union_kind)
    candidate_members = _collect_union_members(
        candidate_spec,
        candidate_schema,
        baseline_union_kind,
    )
    matched_baseline_indices: set[int] = set()
    matched_candidate_indices: set[int] = set()
    candidate_indices_by_identifier: dict[str, list[int]] = {}
    for candidate_index, candidate_member in enumerate(candidate_members):
        candidate_indices_by_identifier.setdefault(candidate_member.identifier, []).append(
            candidate_index
        )

    matched_pairs: list[tuple[int, int, str]] = []
    for baseline_index, baseline_member in enumerate(baseline_members):
        for candidate_index in candidate_indices_by_identifier.get(
            baseline_member.identifier,
            [],
        ):
            if candidate_index in matched_candidate_indices:
                continue
            matched_baseline_indices.add(baseline_index)
            matched_candidate_indices.add(candidate_index)
            matched_pairs.append(
                (baseline_index, candidate_index, baseline_member.identifier)
            )
            break

    candidate_matches: list[tuple[int, int, int]] = []
    for baseline_index, baseline_member in enumerate(baseline_members):
        if baseline_index in matched_baseline_indices:
            continue
        for candidate_index, candidate_member in enumerate(candidate_members):
            if candidate_index in matched_candidate_indices:
                continue
            comparison_cost = _schema_comparison_cost(
                baseline_spec,
                baseline_member.member,
                candidate_spec,
                candidate_member.member,
                direction=direction,
            )
            if comparison_cost >= UNION_MEMBER_REPLACEMENT_COST:
                continue
            candidate_matches.append((comparison_cost, baseline_index, candidate_index))

    for _, baseline_index, candidate_index in sorted(candidate_matches):
        if baseline_index in matched_baseline_indices or candidate_index in matched_candidate_indices:
            continue
        matched_baseline_indices.add(baseline_index)
        matched_candidate_indices.add(candidate_index)
        matched_pairs.append(
            (
                baseline_index,
                candidate_index,
                _union_member_match_identifier(
                    baseline_members[baseline_index],
                    candidate_members[candidate_index],
                ),
            )
        )

    for baseline_index, candidate_index, member_identifier in matched_pairs:
        _compare_schema(
            baseline_spec,
            baseline_members[baseline_index].member,
            candidate_spec,
            candidate_members[candidate_index].member,
            scope=scope,
            identifier=f"{identifier}<{member_identifier}>",
            direction=direction,
            changes=changes,
        )

    for baseline_index, baseline_member in enumerate(baseline_members):
        if baseline_index in matched_baseline_indices:
            continue
        changes.append(
            ContractChange(
                severity="breaking",
                scope=scope,
                identifier=f"{identifier}<{baseline_member.identifier}>",
                detail=f"{baseline_union_kind} member was removed",
            )
        )

    for candidate_index, candidate_member in enumerate(candidate_members):
        if candidate_index in matched_candidate_indices:
            continue
        changes.append(
            ContractChange(
                severity="additive",
                scope=scope,
                identifier=f"{identifier}<{candidate_member.identifier}>",
                detail=f"new {baseline_union_kind} member was added",
            )
        )


def _collect_union_members(
    spec: dict[str, Any],
    schema: dict[str, Any],
    union_kind: str,
) -> list[UnionSchemaMember]:
    members = schema.get(union_kind, [])
    collected: list[UnionSchemaMember] = []
    for member in members:
        if not isinstance(member, dict):
            continue
        collected.append(
            UnionSchemaMember(
                identifier=_union_member_identifier(spec, member),
                member=member,
            )
        )
    return collected


def _union_member_identifier(spec: dict[str, Any], member: dict[str, Any]) -> str:
    ref = member.get("$ref")
    if isinstance(ref, str):
        return f"ref:{ref.split('/')[-1]}"
    resolved = _resolve_schema(spec, member)
    return "inline:" + json.dumps(resolved, sort_keys=True, separators=(",", ":"))


def _union_member_match_identifier(
    baseline_member: UnionSchemaMember,
    candidate_member: UnionSchemaMember,
) -> str:
    if baseline_member.identifier == candidate_member.identifier:
        return baseline_member.identifier
    if baseline_member.identifier.startswith("ref:"):
        return baseline_member.identifier
    if candidate_member.identifier.startswith("ref:"):
        return candidate_member.identifier
    return baseline_member.identifier


def _schema_comparison_cost(
    baseline_spec: dict[str, Any],
    baseline_schema: dict[str, Any],
    candidate_spec: dict[str, Any],
    candidate_schema: dict[str, Any],
    *,
    direction: str,
) -> int:
    comparison_changes: list[ContractChange] = []
    _compare_schema(
        baseline_spec,
        baseline_schema,
        candidate_spec,
        candidate_schema,
        scope="union-member",
        identifier="<member>",
        direction=direction,
        changes=comparison_changes,
    )
    return sum(100 if change.severity == "breaking" else 1 for change in comparison_changes)


def _normalize_nullable_schema(schema: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if schema.get("nullable") is True:
        normalized = dict(schema)
        normalized.pop("nullable", None)
        return normalized, True
    type_value = schema.get("type")
    if isinstance(type_value, list) and "null" in type_value:
        normalized = dict(schema)
        normalized["type"] = next(
            (entry for entry in type_value if entry != "null"),
            "string",
        )
        return normalized, True
    for union_key in ("anyOf", "oneOf"):
        members = schema.get(union_key)
        if not isinstance(members, list):
            continue
        non_null_members = [
            member
            for member in members
            if not (isinstance(member, dict) and member.get("type") == "null")
        ]
        if len(non_null_members) == 1 and len(non_null_members) != len(members):
            return non_null_members[0], True
    return schema, False


def _compare_additive_text_metadata(
    *,
    scope: str,
    identifier: str,
    field_name: str,
    baseline_value: Any,
    candidate_value: Any,
    changes: list[ContractChange],
) -> None:
    if baseline_value == candidate_value:
        return
    changes.append(
        ContractChange(
            severity="additive",
            scope=scope,
            identifier=identifier,
            detail=f"{field_name} changed",
        )
    )


def _compare_optional_metadata_field(
    *,
    scope: str,
    identifier: str,
    field_name: str,
    baseline_value: Any,
    candidate_value: Any,
    changes: list[ContractChange],
) -> None:
    if baseline_value == candidate_value:
        return
    if baseline_value is None and candidate_value is not None:
        severity = "additive"
        detail = f"{field_name} was added"
    else:
        severity = "breaking"
        detail = (
            f"{field_name} changed"
            if candidate_value is not None
            else f"{field_name} was removed"
        )
    changes.append(
        ContractChange(
            severity=severity,
            scope=scope,
            identifier=identifier,
            detail=detail,
        )
    )


def _compare_boolean_capability(
    *,
    scope: str,
    identifier: str,
    field_name: str,
    baseline_value: Any,
    candidate_value: Any,
    changes: list[ContractChange],
) -> None:
    if baseline_value == candidate_value:
        return
    changes.append(
        ContractChange(
            severity="breaking" if baseline_value and not candidate_value else "additive",
            scope=scope,
            identifier=identifier,
            detail=(
                f"{field_name} was removed"
                if baseline_value and not candidate_value
                else f"{field_name} was added"
            ),
        )
    )


def _compare_set_contract(
    *,
    scope: str,
    identifier: str,
    field_name: str,
    baseline_values: Any,
    candidate_values: Any,
    changes: list[ContractChange],
    removal_detail: str,
    addition_detail: str,
) -> None:
    baseline_set = set(baseline_values or ())
    candidate_set = set(candidate_values or ())
    for value in sorted(baseline_set - candidate_set):
        changes.append(
            ContractChange(
                severity="breaking",
                scope=scope,
                identifier=identifier,
                detail=f"{field_name} `{value}` {removal_detail}",
            )
        )
    for value in sorted(candidate_set - baseline_set):
        changes.append(
            ContractChange(
                severity="additive",
                scope=scope,
                identifier=identifier,
                detail=f"{field_name} `{value}` {addition_detail}",
            )
        )


def _compare_permission_contract(
    descriptor_key: str,
    baseline_permissions: Any,
    candidate_permissions: Any,
    changes: list[ContractChange],
) -> None:
    baseline_set = set(baseline_permissions or ())
    candidate_set = set(candidate_permissions or ())
    for permission in sorted(baseline_set - candidate_set):
        changes.append(
            ContractChange(
                severity="additive",
                scope="ui-descriptor",
                identifier=descriptor_key,
                detail=f"required permission `{permission}` was removed",
            )
        )
    for permission in sorted(candidate_set - baseline_set):
        changes.append(
            ContractChange(
                severity="breaking",
                scope="ui-descriptor",
                identifier=descriptor_key,
                detail=f"required permission `{permission}` was added",
            )
        )


def _compare_mapping_contract(
    *,
    scope: str,
    identifier: str,
    field_name: str,
    baseline_mapping: Any,
    candidate_mapping: Any,
    changes: list[ContractChange],
    addition_detail: str,
    removal_detail: str,
    change_detail: str,
    changed_value_severity: str,
    removed_value_severity: str,
    added_value_severity: str,
) -> None:
    baseline_dict = dict(baseline_mapping or {})
    candidate_dict = dict(candidate_mapping or {})
    for key, baseline_value in baseline_dict.items():
        if key not in candidate_dict:
            changes.append(
                ContractChange(
                    severity=removed_value_severity,
                    scope=scope,
                    identifier=identifier,
                    detail=f"{field_name} `{key}` {removal_detail}",
                )
            )
            continue
        if candidate_dict[key] != baseline_value:
            changes.append(
                ContractChange(
                    severity=changed_value_severity,
                    scope=scope,
                    identifier=identifier,
                    detail=f"{field_name} `{key}` {change_detail}",
                )
            )
    for key in sorted(candidate_dict):
        if key in baseline_dict:
            continue
        changes.append(
            ContractChange(
                severity=added_value_severity,
                scope=scope,
                identifier=identifier,
                detail=f"{field_name} `{key}` {addition_detail}",
            )
        )


def _schema_kind(schema: dict[str, Any]) -> str:
    if "properties" in schema:
        return "object"
    if schema.get("type") is not None:
        return str(schema["type"])
    if "items" in schema:
        return "array"
    return "unknown"


def _schema_version_major_bumped(
    baseline_version: str | None,
    candidate_version: str | None,
) -> bool:
    baseline_major = _parse_major_version(baseline_version)
    candidate_major = _parse_major_version(candidate_version)
    if baseline_major is None or candidate_major is None:
        return False
    return candidate_major > baseline_major


def _parse_major_version(version: str | None) -> int | None:
    if not version:
        return None
    try:
        return int(str(version).split(".", 1)[0])
    except ValueError:
        return None


def _load_baseline_snapshot(
    *,
    base_ref: str | None,
    base_dir: Path | None,
    generated_dir: Path,
) -> tuple[ContractArtifactsSnapshot | None, str]:
    if base_ref:
        return load_contract_artifacts_from_git_ref(base_ref, generated_dir=generated_dir), base_ref
    if base_dir:
        return load_contract_artifacts(base_dir), str(base_dir)
    return None, "none"


def _command_export_check(args: argparse.Namespace) -> int:
    check_export_artifacts_in_sync(generated_dir=args.generated_dir)
    print("Backend-owned contract exports are in sync.")
    return 0


def _command_report(args: argparse.Namespace) -> int:
    baseline, baseline_label = _load_baseline_snapshot(
        base_ref=args.base_ref,
        base_dir=args.base_dir,
        generated_dir=args.generated_dir,
    )
    report = build_contract_compatibility_report(
        baseline=baseline,
        candidate=load_contract_artifacts(args.generated_dir),
        baseline_label=baseline_label,
        candidate_label=str(args.generated_dir),
    )
    if args.output_dir is not None:
        write_contract_compatibility_report(args.output_dir, report)
    else:
        print(_build_markdown_summary(report), end="")
    if report["status"] == "breaking":
        print("Breaking contract changes detected.")
    return 0


def _command_bundle(args: argparse.Namespace) -> int:
    check_export_artifacts_in_sync(generated_dir=args.generated_dir)
    baseline, baseline_label = _load_baseline_snapshot(
        base_ref=args.base_ref,
        base_dir=args.base_dir,
        generated_dir=args.generated_dir,
    )
    compatibility_report = build_contract_compatibility_report(
        baseline=baseline,
        candidate=load_contract_artifacts(args.generated_dir),
        baseline_label=baseline_label,
        candidate_label=str(args.generated_dir),
    )
    write_release_artifact_bundle(
        generated_dir=args.generated_dir,
        output_dir=args.output_dir,
        compatibility_report=compatibility_report,
    )
    print(f"Wrote contract artifact bundle to {args.output_dir}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate, compare, and package backend-owned contract artifacts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_check = subparsers.add_parser(
        "export-check",
        help="Fail if backend-exported contract JSON differs from the committed generated artifacts.",
    )
    export_check.add_argument(
        "--generated-dir",
        type=Path,
        default=DEFAULT_GENERATED_DIR,
    )
    export_check.set_defaults(func=_command_export_check)

    report = subparsers.add_parser(
        "report",
        help="Write or print a compatibility report for the current generated artifacts.",
    )
    report.add_argument("--generated-dir", type=Path, default=DEFAULT_GENERATED_DIR)
    report.add_argument("--base-ref")
    report.add_argument("--base-dir", type=Path)
    report.add_argument("--output-dir", type=Path)
    report.set_defaults(func=_command_report)

    bundle = subparsers.add_parser(
        "bundle",
        help="Write a release-ready contract artifact bundle with compatibility summary.",
    )
    bundle.add_argument("--generated-dir", type=Path, default=DEFAULT_GENERATED_DIR)
    bundle.add_argument("--base-ref")
    bundle.add_argument("--base-dir", type=Path)
    bundle.add_argument("--output-dir", type=Path, default=DEFAULT_RELEASE_DIR)
    bundle.set_defaults(func=_command_bundle)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
