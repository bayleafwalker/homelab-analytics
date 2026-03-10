from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.docs]

ROOT = Path(__file__).resolve().parents[1]
AGENT_DOCS = {
    "planning": ROOT / "docs" / "agents" / "planning.md",
    "implementation": ROOT / "docs" / "agents" / "implementation.md",
    "review": ROOT / "docs" / "agents" / "review.md",
    "release-ops": ROOT / "docs" / "agents" / "release-ops.md",
}
REQUIRED_SECTIONS = (
    "## Purpose",
    "## Allowed actions",
    "## Required inputs",
    "## Required verification",
    "## Required output shape",
    "## Stop and escalate",
)


def test_top_level_agents_doc_references_mode_docs_and_repo_rules() -> None:
    content = (ROOT / "AGENTS.md").read_text()

    for name, path in AGENT_DOCS.items():
        assert str(path.relative_to(ROOT)) in content, f"AGENTS.md missing {name} reference"

    for rule in [
        "When changing or adding requirements",
        "Behavior changes must update or add tests",
        "App-facing reporting paths must use reporting-layer models",
    ]:
        assert rule in content


@pytest.mark.parametrize("path", AGENT_DOCS.values(), ids=AGENT_DOCS.keys())
def test_agent_mode_docs_have_required_sections(path: Path) -> None:
    content = path.read_text()

    for heading in REQUIRED_SECTIONS:
        assert heading in content, f"{path.name} missing section {heading}"


def test_docs_index_lists_agent_guides() -> None:
    content = (ROOT / "docs" / "README.md").read_text()

    assert "## Agents" in content
    for path in AGENT_DOCS.values():
        assert str(path.relative_to(ROOT / "docs")) in content
