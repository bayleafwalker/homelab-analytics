"""scripts/capture_finance_loop_screenshots.py: upload fixtures and wiring."""

from __future__ import annotations

import csv
import importlib.util
import io
from pathlib import Path

import pytest

pytestmark = [pytest.mark.docs]

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "capture_finance_loop_screenshots.py"
CAPTURE_JS = ROOT / "scripts" / "capture_finance_loop_screenshots.mjs"
WALKTHROUGH = ROOT / "docs" / "runbooks" / "operator-walkthrough.md"


def _load_script():
    spec = importlib.util.spec_from_file_location("capture_finance_loop_screenshots", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")), delimiter=";"))


def test_upload_files_are_a_new_period_and_an_empty_amount(tmp_path: Path) -> None:
    script = _load_script()
    good, bad = script.write_upload_files(tmp_path)

    landed = _rows(good)
    assert [row["Kirjauspäivä"] for row in landed] == ["2026-01-03", "2026-01-04"]
    assert [row["Määrä EUROA"] for row in landed] == ["3200,00", "-959,24"]
    assert all(row["Arkistointitunnus"].startswith("202601") for row in landed)

    rejected = _rows(bad)
    assert bad.name == "op-personal-broken.csv"
    assert len(rejected) == 1
    # The column stays (dropping it is refused before a run exists); the
    # value is empty, which the contract records as missing_required_value.
    assert rejected[0]["Määrä EUROA"] == ""
    assert list(rejected[0]) == list(landed[0])


def test_capture_writes_the_eight_walkthrough_images() -> None:
    capture = CAPTURE_JS.read_text()
    walkthrough = WALKTHROUGH.read_text()
    images = sorted(
        path.name for path in (ROOT / "docs" / "product" / "screenshots" / "finance-loop").glob("*.png")
    )
    assert len(images) == 8
    for name in images:
        assert f'shot("{name}")' in capture
        assert f"finance-loop/{name}" in walkthrough
    assert "python scripts/capture_finance_loop_screenshots.py" in walkthrough
    # Never touches visual-test baselines.
    assert "-snapshots" not in capture
