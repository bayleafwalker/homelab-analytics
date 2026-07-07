from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from packages.platform.contract_compat.models import (
    ContractArtifactsSnapshot,
    ContractChange,
)
from packages.platform.contract_compat.openapi_compare import compare_openapi_contracts
from packages.platform.contract_compat.publication_compare import (
    compare_publication_contracts,
)

JSON_ARTIFACT_FILENAMES = ("openapi.json", "publication-contracts.json")
DEFAULT_GENERATED_DIR = Path("apps/web/frontend/generated")


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
    export_contracts_func: Callable[[Path], None] | None = None,
) -> None:
    from tempfile import TemporaryDirectory

    if export_contracts_func is None:
        from apps.api.export_contracts import export_contracts as export_contracts_func

    with TemporaryDirectory(prefix="homelab-analytics-contract-export-") as temp_dir:
        exported_dir = Path(temp_dir)
        export_contracts_func(exported_dir)
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
    compare_openapi_contracts(baseline.openapi, candidate.openapi, changes)
    compare_publication_contracts(
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
        build_markdown_summary(report),
        encoding="utf-8",
    )


def build_markdown_summary(report: dict[str, Any]) -> str:
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
