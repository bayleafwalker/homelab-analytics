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
