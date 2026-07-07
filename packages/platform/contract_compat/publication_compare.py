from __future__ import annotations

from typing import Any

from packages.platform.contract_compat.models import ContractChange


def compare_publication_contracts(
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
