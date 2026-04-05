from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.docs]

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_DIR = ROOT / "requirements"
REQUIREMENT_FILES = sorted(
    path for path in REQUIREMENTS_DIR.glob("*.md") if path.name != "README.md"
)
ALLOWED_STATUSES = {"not-started", "in-progress", "implemented", "deferred"}
REQUIRED_FIELDS = (
    "Description",
    "Rationale",
    "Phase",
    "Status",
    "Acceptance criteria",
    "Dependencies",
)
REQUIREMENT_SECTION_RE = re.compile(
    r"^### ([A-Z]+-\d+): .+?(?=^### [A-Z]+-\d+: |\Z)",
    re.MULTILINE | re.DOTALL,
)
TRACEABILITY_ROW_RE = re.compile(r"^\| ([A-Z]+-\d+) \|.*$", re.MULTILINE)


def _parse_sections(content: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for match in REQUIREMENT_SECTION_RE.finditer(content):
        header_match = re.match(r"^### ([A-Z]+-\d+):", match.group(0))
        assert header_match is not None
        sections[header_match.group(1)] = match.group(0)
    return sections


def _parse_traceability(content: str) -> dict[str, str]:
    traceability = content.split("## Traceability", maxsplit=1)[1]
    rows: dict[str, str] = {}
    for row in TRACEABILITY_ROW_RE.finditer(traceability):
        rows[row.group(1)] = row.group(0)
    return rows


@pytest.mark.parametrize("path", REQUIREMENT_FILES, ids=lambda path: path.stem)
def test_requirement_documents_use_expected_template_fields(path: Path) -> None:
    content = path.read_text()
    sections = _parse_sections(content)

    assert sections, f"No requirement sections found in {path}"

    for requirement_id, section in sections.items():
        for field_name in REQUIRED_FIELDS:
            assert (
                f"**{field_name}:**" in section
            ), f"{path.name} {requirement_id} missing field {field_name!r}"


@pytest.mark.parametrize("path", REQUIREMENT_FILES, ids=lambda path: path.stem)
def test_requirement_status_values_are_allowed(path: Path) -> None:
    content = path.read_text()
    sections = _parse_sections(content)

    for requirement_id, section in sections.items():
        match = re.search(r"\*\*Status:\*\* ([a-z-]+)", section)
        assert match is not None, f"{path.name} {requirement_id} missing parsable status"
        assert match.group(1) in ALLOWED_STATUSES


@pytest.mark.parametrize("path", REQUIREMENT_FILES, ids=lambda path: path.stem)
def test_implemented_and_in_progress_requirements_have_existing_traceability(path: Path) -> None:
    content = path.read_text()
    sections = _parse_sections(content)
    rows = _parse_traceability(content)

    for requirement_id, section in sections.items():
        status_match = re.search(r"\*\*Status:\*\* ([a-z-]+)", section)
        assert status_match is not None
        if status_match.group(1) not in {"implemented", "in-progress"}:
            continue

        assert requirement_id in rows, f"{path.name} {requirement_id} missing traceability row"

        row = rows[requirement_id]
        backticked_paths = re.findall(r"`([^`]+)`", row)
        implementation_paths = [
            ROOT / ref
            for ref in backticked_paths
            if "/" in ref and not ref.startswith("tests/")
        ]
        test_paths = [ROOT / ref for ref in backticked_paths if ref.startswith("tests/")]

        assert implementation_paths, f"{path.name} {requirement_id} missing implementation refs"
        assert test_paths, f"{path.name} {requirement_id} missing test refs"
        assert any(target.exists() for target in implementation_paths), (
            f"{path.name} {requirement_id} has no existing implementation path in traceability"
        )
        assert any(target.exists() for target in test_paths), (
            f"{path.name} {requirement_id} has no existing test path in traceability"
        )
