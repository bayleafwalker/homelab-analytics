from __future__ import annotations

import json
from typing import Any

from packages.platform.contract_compat.models import ContractChange, UnionSchemaMember

UNION_MEMBER_REPLACEMENT_COST = 101


def compare_schema(
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
        resolve_schema(baseline_spec, baseline_schema)
    )
    resolved_candidate, candidate_nullable = _normalize_nullable_schema(
        resolve_schema(candidate_spec, candidate_schema)
    )
    resolved_baseline = resolve_schema(baseline_spec, resolved_baseline)
    resolved_candidate = resolve_schema(candidate_spec, resolved_candidate)

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

    baseline_kind = schema_kind(resolved_baseline)
    candidate_kind = schema_kind(resolved_candidate)
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
        compare_schema(
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


def resolve_schema(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in schema:
        ref_name = str(schema["$ref"]).split("/")[-1]
        target = spec.get("components", {}).get("schemas", {}).get(ref_name)
        if isinstance(target, dict):
            return resolve_schema(spec, target)
    if "allOf" in schema and isinstance(schema["allOf"], list):
        merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        for item in schema["allOf"]:
            resolved = resolve_schema(spec, item)
            if schema_kind(resolved) != "object":
                return resolved
            merged["properties"].update(resolved.get("properties", {}))
            merged["required"].extend(resolved.get("required", []))
        merged["required"] = sorted(set(merged["required"]))
        return merged
    return schema


def schema_kind(schema: dict[str, Any]) -> str:
    if "properties" in schema:
        return "object"
    if schema.get("type") is not None:
        return str(schema["type"])
    if "items" in schema:
        return "array"
    return "unknown"


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

        compare_schema(
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
        compare_schema(
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
    resolved = resolve_schema(spec, member)
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
    compare_schema(
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
