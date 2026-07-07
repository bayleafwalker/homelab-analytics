from __future__ import annotations

import argparse
from pathlib import Path

from packages.platform.contract_compat import (
    DEFAULT_RELEASE_DIR,
    JSON_ARTIFACT_FILENAMES,
    RELEASE_ARTIFACT_FILENAMES,
    ContractArtifactsSnapshot,
    ContractChange,
    UnionSchemaMember,
    build_contract_compatibility_report,
    build_markdown_summary,
    load_contract_artifacts,
    load_contract_artifacts_from_git_ref,
    write_contract_compatibility_report,
    write_release_artifact_bundle,
)
from packages.platform.contract_compat import (
    check_export_artifacts_in_sync as _platform_check_export_artifacts_in_sync,
)

DEFAULT_GENERATED_DIR = Path("apps/web/frontend/generated")

__all__ = [
    "DEFAULT_RELEASE_DIR",
    "JSON_ARTIFACT_FILENAMES",
    "RELEASE_ARTIFACT_FILENAMES",
    "ContractArtifactsSnapshot",
    "ContractChange",
    "UnionSchemaMember",
    "build_contract_compatibility_report",
    "build_parser",
    "check_export_artifacts_in_sync",
    "load_contract_artifacts",
    "load_contract_artifacts_from_git_ref",
    "main",
    "write_contract_compatibility_report",
    "write_release_artifact_bundle",
]


def export_contracts(output_dir: Path = DEFAULT_GENERATED_DIR) -> None:
    from apps.api.export_contracts import export_contracts as _export_contracts

    _export_contracts(output_dir)


def check_export_artifacts_in_sync(
    *,
    generated_dir: Path = DEFAULT_GENERATED_DIR,
) -> None:
    _platform_check_export_artifacts_in_sync(
        generated_dir=generated_dir,
        export_contracts_func=export_contracts,
    )


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
        print(build_markdown_summary(report), end="")
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
