from __future__ import annotations

import os
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
SKILL_DOCS = {
    "domain-impact-scan": ROOT / ".agents" / "skills" / "domain-impact-scan" / "SKILL.md",
    "sprint-packet": ROOT / ".agents" / "skills" / "sprint-packet" / "SKILL.md",
    "code-change-verification": ROOT / ".agents" / "skills" / "code-change-verification" / "SKILL.md",
    "pr-handoff-summary": ROOT / ".agents" / "skills" / "pr-handoff-summary" / "SKILL.md",
    "sprint-snapshot": ROOT / ".agents" / "skills" / "sprint-snapshot" / "SKILL.md",
    "kctl-extract": ROOT / ".agents" / "skills" / "kctl-extract" / "SKILL.md",
}
SKILLS_README = ROOT / ".agents" / "skills" / "README.md"
REQUIRED_SECTIONS = (
    "## Purpose",
    "## Allowed actions",
    "## Required inputs",
    "## Required verification",
    "## Required output shape",
    "## Stop and escalate",
)
REQUIRED_SKILL_SECTIONS = (
    "name:",
    "description:",
    "## Goal",
    "## Inputs",
    "## Steps",
    "## Output contract",
    "## Do not",
)


def test_top_level_agents_doc_references_mode_docs_and_repo_rules() -> None:
    content = (ROOT / "AGENTS.md").read_text()

    for name, path in AGENT_DOCS.items():
        assert str(path.relative_to(ROOT)) in content, f"AGENTS.md missing {name} reference"

    for rule in [
        "When changing or adding requirements",
        "Behavior changes must update or add tests",
        "App-facing reporting paths must use reporting-layer models",
        ".envrc",
        "sprintctl claim",
        "sprintctl handoff",
        "kctl preflight",
        "kctl status --json",
        "docs/knowledge/knowledge-base.md",
    ]:
        assert rule in content

    assert ".agents/skills/" in content


@pytest.mark.parametrize("path", AGENT_DOCS.values(), ids=AGENT_DOCS.keys())
def test_agent_mode_docs_have_required_sections(path: Path) -> None:
    content = path.read_text()

    for heading in REQUIRED_SECTIONS:
        assert heading in content, f"{path.name} missing section {heading}"


@pytest.mark.parametrize("path", SKILL_DOCS.values(), ids=SKILL_DOCS.keys())
def test_skill_docs_have_required_sections(path: Path) -> None:
    content = path.read_text()

    for heading in REQUIRED_SKILL_SECTIONS:
        assert heading in content, f"{path} missing section {heading}"


def test_skills_readme_exists_and_lists_skill_docs() -> None:
    content = SKILLS_README.read_text()

    assert "# Agent Skills" in content
    for name in SKILL_DOCS:
        assert f"`{name}`" in content


def test_docs_index_lists_agent_guides() -> None:
    content = (ROOT / "docs" / "README.md").read_text()

    assert "## Agents" in content
    for path in AGENT_DOCS.values():
        assert str(path.relative_to(ROOT / "docs")) in content


def test_docs_index_lists_agent_skills() -> None:
    content = (ROOT / "docs" / "README.md").read_text()

    assert "## Agent Skills" in content
    assert os.path.relpath(SKILLS_README, ROOT / "docs") in content
    for path in SKILL_DOCS.values():
        assert os.path.relpath(path, ROOT / "docs") in content
