from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.api import contract_artifacts


def _artifact_snapshot(
    *,
    openapi: dict,
    publication_contracts: dict,
) -> contract_artifacts.ContractArtifactsSnapshot:
    return contract_artifacts.ContractArtifactsSnapshot(
        openapi=openapi,
        publication_contracts=publication_contracts,
    )


def test_contract_report_marks_new_response_field_as_additive() -> None:
    baseline = _artifact_snapshot(
        openapi={
            "openapi": "3.1.0",
            "paths": {
                "/reports/example": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "required": ["id"],
                                            "properties": {"id": {"type": "string"}},
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
        },
        publication_contracts={"publication_contracts": [], "ui_descriptors": []},
    )
    candidate = _artifact_snapshot(
        openapi={
            "openapi": "3.1.0",
            "paths": {
                "/reports/example": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "required": ["id"],
                                            "properties": {
                                                "id": {"type": "string"},
                                                "total": {"type": "string"},
                                            },
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
        },
        publication_contracts={"publication_contracts": [], "ui_descriptors": []},
    )

    report = contract_artifacts.build_contract_compatibility_report(
        baseline=baseline,
        candidate=candidate,
        baseline_label="base",
        candidate_label="candidate",
    )

    assert report["status"] == "additive"
    assert report["breaking_changes"] == []
    assert report["additive_changes"][0]["identifier"] == "GET /reports/example 200.total"


def test_contract_report_marks_publication_column_removal_as_breaking_with_policy_warning() -> None:
    baseline = _artifact_snapshot(
        openapi={"openapi": "3.1.0", "paths": {}},
        publication_contracts={
            "publication_contracts": [
                {
                    "publication_key": "monthly_cashflow",
                    "schema_version": "1.1.0",
                    "columns": [
                        {"name": "month", "json_type": "string", "nullable": False},
                        {"name": "net", "json_type": "string", "nullable": False},
                    ],
                }
            ],
            "ui_descriptors": [],
        },
    )
    candidate = _artifact_snapshot(
        openapi={"openapi": "3.1.0", "paths": {}},
        publication_contracts={
            "publication_contracts": [
                {
                    "publication_key": "monthly_cashflow",
                    "schema_version": "1.2.0",
                    "columns": [
                        {"name": "month", "json_type": "string", "nullable": False},
                    ],
                }
            ],
            "ui_descriptors": [],
        },
    )

    report = contract_artifacts.build_contract_compatibility_report(
        baseline=baseline,
        candidate=candidate,
        baseline_label="base",
        candidate_label="candidate",
    )

    assert report["status"] == "breaking"
    assert report["breaking_changes"][0]["identifier"] == "monthly_cashflow.net"
    assert "schema_version bump" in report["policy_warnings"][0]


def test_contract_report_marks_request_body_requiredness_tightening_as_breaking() -> None:
    baseline = _artifact_snapshot(
        openapi={
            "openapi": "3.1.0",
            "paths": {
                "/reports/example": {
                    "post": {
                        "requestBody": {
                            "required": False,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "string"}},
                                    }
                                }
                            },
                        },
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {"schema": {"type": "object"}}
                                }
                            }
                        },
                    }
                }
            },
        },
        publication_contracts={"publication_contracts": [], "ui_descriptors": []},
    )
    candidate = _artifact_snapshot(
        openapi={
            "openapi": "3.1.0",
            "paths": {
                "/reports/example": {
                    "post": {
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "string"}},
                                    }
                                }
                            },
                        },
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {"schema": {"type": "object"}}
                                }
                            }
                        },
                    }
                }
            },
        },
        publication_contracts={"publication_contracts": [], "ui_descriptors": []},
    )

    report = contract_artifacts.build_contract_compatibility_report(
        baseline=baseline,
        candidate=candidate,
        baseline_label="base",
        candidate_label="candidate",
    )

    assert report["status"] == "breaking"
    assert report["breaking_changes"] == [
        {
            "severity": "breaking",
            "scope": "route-request",
            "identifier": "POST /reports/example",
            "detail": "request body became required",
        }
    ]


def test_contract_report_marks_anyof_member_regression_as_breaking() -> None:
    baseline = _artifact_snapshot(
        openapi={
            "openapi": "3.1.0",
            "paths": {
                "/reports/example": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {
                                                "anyOf": [
                                                    {"$ref": "#/components/schemas/AccountRow"},
                                                    {"$ref": "#/components/schemas/BudgetRow"},
                                                ]
                                            },
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "schemas": {
                    "AccountRow": {
                        "type": "object",
                        "required": ["kind", "account_id"],
                        "properties": {
                            "kind": {"type": "string"},
                            "account_id": {"type": "string"},
                        },
                    },
                    "BudgetRow": {
                        "type": "object",
                        "required": ["kind", "budget_id"],
                        "properties": {
                            "kind": {"type": "string"},
                            "budget_id": {"type": "string"},
                        },
                    },
                }
            },
        },
        publication_contracts={"publication_contracts": [], "ui_descriptors": []},
    )
    candidate = _artifact_snapshot(
        openapi={
            "openapi": "3.1.0",
            "paths": {
                "/reports/example": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {
                                                "anyOf": [
                                                    {"$ref": "#/components/schemas/AccountRow"},
                                                    {"$ref": "#/components/schemas/BudgetRow"},
                                                ]
                                            },
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "schemas": {
                    "AccountRow": {
                        "type": "object",
                        "required": ["kind", "account_id"],
                        "properties": {
                            "kind": {"type": "string"},
                            "account_id": {"type": "string"},
                        },
                    },
                    "BudgetRow": {
                        "type": "object",
                        "required": ["kind"],
                        "properties": {
                            "kind": {"type": "string"},
                            "budget_id": {"type": "string"},
                        },
                    },
                }
            },
        },
        publication_contracts={"publication_contracts": [], "ui_descriptors": []},
    )

    report = contract_artifacts.build_contract_compatibility_report(
        baseline=baseline,
        candidate=candidate,
        baseline_label="base",
        candidate_label="candidate",
    )

    assert report["status"] == "breaking"
    assert any(
        change["identifier"] == "GET /reports/example 200[]<ref:BudgetRow>.budget_id"
        and change["detail"] == "response property became optional"
        for change in report["breaking_changes"]
    )


def test_contract_report_matches_inline_anyof_member_drift_before_reporting_changes() -> None:
    baseline = _artifact_snapshot(
        openapi={
            "openapi": "3.1.0",
            "paths": {
                "/reports/example": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "anyOf": [
                                                {
                                                    "type": "object",
                                                    "required": ["id"],
                                                    "properties": {"id": {"type": "string"}},
                                                }
                                            ]
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
        },
        publication_contracts={"publication_contracts": [], "ui_descriptors": []},
    )
    candidate = _artifact_snapshot(
        openapi={
            "openapi": "3.1.0",
            "paths": {
                "/reports/example": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "anyOf": [
                                                {
                                                    "type": "object",
                                                    "required": ["id"],
                                                    "properties": {
                                                        "id": {"type": "string"},
                                                        "extra": {"type": "string"},
                                                    },
                                                }
                                            ]
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
        },
        publication_contracts={"publication_contracts": [], "ui_descriptors": []},
    )

    report = contract_artifacts.build_contract_compatibility_report(
        baseline=baseline,
        candidate=candidate,
        baseline_label="base",
        candidate_label="candidate",
    )

    assert report["status"] == "additive"
    assert report["breaking_changes"] == []
    assert any(
        change["identifier"].endswith(".extra")
        and change["detail"] == "new response property was added"
        for change in report["additive_changes"]
    )
    assert not any(
        "member was removed" in change["detail"] or "member was added" in change["detail"]
        for change in report["additive_changes"]
    )


def test_contract_report_marks_publication_semantic_contract_regression_as_breaking() -> None:
    baseline = _artifact_snapshot(
        openapi={"openapi": "3.1.0", "paths": {}},
        publication_contracts={
            "publication_contracts": [
                {
                    "publication_key": "monthly_cashflow",
                    "schema_version": "1.1.0",
                    "supported_renderers": ["ha", "web"],
                    "renderer_hints": {"ha_state_aggregation": "sum"},
                    "columns": [
                        {
                            "name": "net",
                            "storage_type": "DECIMAL(18,4) NOT NULL",
                            "json_type": "string",
                            "nullable": False,
                            "description": "Net cashflow for the month.",
                            "semantic_role": "measure",
                            "unit": "currency",
                            "aggregation": "sum",
                            "filterable": False,
                            "sortable": True,
                        }
                    ],
                }
            ],
            "ui_descriptors": [],
        },
    )
    candidate = _artifact_snapshot(
        openapi={"openapi": "3.1.0", "paths": {}},
        publication_contracts={
            "publication_contracts": [
                {
                    "publication_key": "monthly_cashflow",
                    "schema_version": "1.1.0",
                    "supported_renderers": ["web"],
                    "renderer_hints": {},
                    "columns": [
                        {
                            "name": "net",
                            "storage_type": "DECIMAL(18,4) NOT NULL",
                            "json_type": "string",
                            "nullable": False,
                            "description": "Net cashflow for the month.",
                            "semantic_role": "dimension",
                            "unit": None,
                            "aggregation": None,
                            "filterable": True,
                            "sortable": True,
                        }
                    ],
                }
            ],
            "ui_descriptors": [],
        },
    )

    report = contract_artifacts.build_contract_compatibility_report(
        baseline=baseline,
        candidate=candidate,
        baseline_label="base",
        candidate_label="candidate",
    )

    assert report["status"] == "breaking"
    assert any(
        change["identifier"] == "monthly_cashflow"
        and change["detail"] == "supported_renderers `ha` supported renderer was removed"
        for change in report["breaking_changes"]
    )
    assert any(
        change["identifier"] == "monthly_cashflow"
        and change["detail"] == "renderer_hints `ha_state_aggregation` renderer hint was removed"
        for change in report["breaking_changes"]
    )
    assert any(
        change["identifier"] == "monthly_cashflow.net"
        and change["detail"] == "semantic_role changed"
        for change in report["breaking_changes"]
    )
    assert "schema_version bump" in report["policy_warnings"][0]


def test_contract_report_marks_ui_descriptor_navigation_and_renderer_regression_as_breaking() -> None:
    baseline = _artifact_snapshot(
        openapi={"openapi": "3.1.0", "paths": {}},
        publication_contracts={
            "publication_contracts": [],
            "ui_descriptors": [
                {
                    "key": "overview",
                    "nav_label": "Overview",
                    "nav_path": "/reports",
                    "kind": "dashboard",
                    "publication_keys": ["monthly_cashflow"],
                    "icon": "chart",
                    "required_permissions": ["report:view"],
                    "supported_renderers": ["ha", "web"],
                    "renderer_hints": {"web_anchor": "overview"},
                    "default_filters": {"period": "current"},
                }
            ],
        },
    )
    candidate = _artifact_snapshot(
        openapi={"openapi": "3.1.0", "paths": {}},
        publication_contracts={
            "publication_contracts": [],
            "ui_descriptors": [
                {
                    "key": "overview",
                    "nav_label": "Overview",
                    "nav_path": "/new-reports",
                    "kind": "dashboard",
                    "publication_keys": ["monthly_cashflow"],
                    "icon": "chart",
                    "required_permissions": ["admin:write", "report:view"],
                    "supported_renderers": ["web"],
                    "renderer_hints": {},
                    "default_filters": {"period": "trailing_12_months"},
                }
            ],
        },
    )

    report = contract_artifacts.build_contract_compatibility_report(
        baseline=baseline,
        candidate=candidate,
        baseline_label="base",
        candidate_label="candidate",
    )

    assert report["status"] == "breaking"
    assert any(
        change["identifier"] == "overview" and change["detail"] == "nav_path changed"
        for change in report["breaking_changes"]
    )
    assert any(
        change["identifier"] == "overview"
        and change["detail"] == "supported_renderers `ha` supported renderer was removed"
        for change in report["breaking_changes"]
    )
    assert any(
        change["identifier"] == "overview"
        and change["detail"] == "required permission `admin:write` was added"
        for change in report["breaking_changes"]
    )
    assert any(
        change["identifier"] == "overview"
        and change["detail"] == "renderer_hints `web_anchor` renderer hint was removed"
        for change in report["breaking_changes"]
    )
    assert any(
        change["identifier"] == "overview"
        and change["detail"] == "default_filters `period` default filter changed"
        for change in report["additive_changes"]
    )


def test_check_export_artifacts_in_sync_fails_when_exported_sources_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    (generated_dir / "openapi.json").write_text('{"version": "committed"}\n', encoding="utf-8")
    (generated_dir / "publication-contracts.json").write_text(
        '{"version": "committed"}\n',
        encoding="utf-8",
    )

    def fake_export_contracts(output_dir: Path) -> None:
        (output_dir / "openapi.json").write_text('{"version": "fresh"}\n', encoding="utf-8")
        (output_dir / "publication-contracts.json").write_text(
            '{"version": "fresh"}\n',
            encoding="utf-8",
        )

    monkeypatch.setattr(contract_artifacts, "export_contracts", fake_export_contracts)

    with pytest.raises(ValueError, match="openapi.json, publication-contracts.json"):
        contract_artifacts.check_export_artifacts_in_sync(generated_dir=generated_dir)


def test_write_release_artifact_bundle_writes_manifest_and_summary(tmp_path: Path) -> None:
    generated_dir = tmp_path / "generated"
    output_dir = tmp_path / "dist"
    generated_dir.mkdir()
    for filename in contract_artifacts.RELEASE_ARTIFACT_FILENAMES:
        (generated_dir / filename).write_text(f"{filename}\n", encoding="utf-8")

    report = {
        "status": "additive",
        "baseline": "origin/main",
        "candidate": "apps/web/frontend/generated",
        "breaking_changes": [],
        "additive_changes": [],
        "policy_warnings": [],
        "summary": "Additive contract changes detected: 0 breaking, 0 additive.",
    }

    contract_artifacts.write_release_artifact_bundle(
        generated_dir=generated_dir,
        output_dir=output_dir,
        compatibility_report=report,
    )

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["compatibility_status"] == "additive"
    assert sorted(manifest["artifacts"]) == sorted(contract_artifacts.RELEASE_ARTIFACT_FILENAMES)
    assert (output_dir / "compatibility-summary.json").is_file()
    assert (output_dir / "compatibility-summary.md").is_file()
