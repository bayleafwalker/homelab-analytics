from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.platform.contract_compat.report import write_contract_compatibility_report

DEFAULT_GENERATED_DIR = Path("apps/web/frontend/generated")
RELEASE_ARTIFACT_FILENAMES = (
    "openapi.json",
    "publication-contracts.json",
    "api.d.ts",
    "publication-contracts.ts",
)
DEFAULT_RELEASE_DIR = Path("dist/contracts")


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
