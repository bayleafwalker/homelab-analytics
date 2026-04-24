"""
Demo journey verification: artifact IDs, file paths, supported_now routability,
and PublicationDefinition coverage.

These checks ensure the journey metadata in build_journey() stays consistent
with the committed manifest and the registered CapabilityPacks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.demo.bundle import (
    MANIFEST_NAME,
    build_journey,
    write_demo_bundle,
)
from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK

REPO_ROOT = Path(__file__).parent.parent
COMMITTED_MANIFEST_PATH = REPO_ROOT / "infra" / "examples" / "demo-data" / MANIFEST_NAME

_DEMO_PACKS = [FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK]
_ALL_PACK_PUBLICATION_KEYS = frozenset(
    p.key for pack in _DEMO_PACKS for p in pack.publications
)

_KNOWN_UPLOAD_PATHS = {
    "/upload",
    "/upload/utility-bills",
    "/upload/subscriptions",
    "/upload/contract-prices",
    "/upload/budgets",
    "/upload/loan-repayments",
}


@pytest.fixture(scope="module")
def journey() -> dict:
    return build_journey()


@pytest.fixture(scope="module")
def committed_manifest() -> dict:
    import json
    return json.loads(COMMITTED_MANIFEST_PATH.read_text(encoding="utf-8"))


def test_journey_artifact_ids_exist_in_committed_manifest(journey, committed_manifest):
    manifest_ids = {a["artifact_id"] for a in committed_manifest["artifacts"]}
    for step in journey["steps"]:
        for aid in step["artifact_ids"]:
            assert aid in manifest_ids, (
                f"Journey step {step['step']} references artifact_id '{aid}' "
                f"that is not present in {COMMITTED_MANIFEST_PATH.name}."
            )


def test_journey_supported_now_artifacts_are_routable(journey, committed_manifest):
    manifest_by_id = {a["artifact_id"]: a for a in committed_manifest["artifacts"]}
    journey_artifact_ids_by_step = {
        aid: step
        for step in journey["steps"]
        for aid in step["artifact_ids"]
    }
    for aid, step in journey_artifact_ids_by_step.items():
        artifact = manifest_by_id[aid]
        if artifact["ingest_support"] == "supported_now":
            assert step.get("upload_path"), (
                f"Artifact '{aid}' is supported_now but step {step['step']} "
                f"has no upload_path."
            )
            assert step["upload_path"] in _KNOWN_UPLOAD_PATHS, (
                f"Artifact '{aid}' step {step['step']} upload_path "
                f"'{step['upload_path']}' is not in the known upload paths. "
                f"Add it to _KNOWN_UPLOAD_PATHS or update the journey."
            )


def test_journey_file_paths_match_committed_manifest(journey, committed_manifest):
    manifest_paths = {a["artifact_id"]: a["relative_path"] for a in committed_manifest["artifacts"]}
    for step in journey["steps"]:
        for aid in step["artifact_ids"]:
            path = manifest_paths[aid]
            assert not path.startswith("/"), (
                f"Artifact '{aid}' relative_path must not be absolute: {path!r}"
            )
            assert ".." not in Path(path).parts, (
                f"Artifact '{aid}' relative_path must not traverse parent dirs: {path!r}"
            )


def test_journey_publication_keys_exist_in_capability_packs(journey):
    for step in journey["steps"]:
        for pk in step.get("publication_keys", []):
            assert pk in _ALL_PACK_PUBLICATION_KEYS, (
                f"Journey step {step['step']} references publication_key '{pk}' "
                f"that is not registered in any CapabilityPack. "
                f"Known keys: {sorted(_ALL_PACK_PUBLICATION_KEYS)}"
            )


def test_journey_steps_with_no_publication_key_coverage_are_documented(journey):
    uncovered = [
        step["step"]
        for step in journey["steps"]
        if not step.get("publication_keys")
    ]
    assert uncovered == [7, 8], (
        f"Expected steps 7 and 8 to have no CapabilityPack publication coverage "
        f"(budget_variance and loan_overview are pipeline-internal, not yet in a pack). "
        f"Got uncovered steps: {uncovered}. "
        f"If new publications were added to a pack, update publication_keys in build_journey()."
    )


def test_journey_all_supported_now_artifacts_in_committed_bundle(tmp_path: Path):
    import json
    write_demo_bundle(tmp_path)
    generated = json.loads((tmp_path / MANIFEST_NAME).read_text())
    generated_by_id = {a["artifact_id"]: a for a in generated["artifacts"]}
    committed = json.loads(COMMITTED_MANIFEST_PATH.read_text(encoding="utf-8"))
    committed_supported_now = {
        a["artifact_id"] for a in committed["artifacts"] if a["ingest_support"] == "supported_now"
    }
    for aid in committed_supported_now:
        assert aid in generated_by_id, (
            f"Committed manifest artifact '{aid}' with supported_now is missing from generated bundle."
        )
        assert (tmp_path / generated_by_id[aid]["relative_path"]).exists(), (
            f"Generated bundle is missing file for supported_now artifact '{aid}'."
        )
