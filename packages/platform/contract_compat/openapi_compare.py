from __future__ import annotations

from typing import Any

from packages.platform.contract_compat.models import ContractChange
from packages.platform.contract_compat.schema_compare import compare_schema

HTTP_METHODS = {"get", "put", "post", "patch", "delete", "options", "head"}


def compare_openapi_contracts(
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
        compare_schema(
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
    compare_schema(
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
        compare_schema(
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
