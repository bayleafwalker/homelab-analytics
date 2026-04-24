"""
CI drift test: the Demo Bundle Machine Reference section of operator-walkthrough.md
must match what scripts/generate_walkthrough_reference.py produces from the
current bundle.py and manifest.json.

If this test fails, run:
    python scripts/generate_walkthrough_reference.py
"""

from __future__ import annotations

import pytest

from scripts.generate_walkthrough_reference import (
    BEGIN_MARKER,
    END_MARKER,
    WALKTHROUGH_PATH,
    render_section,
)


@pytest.mark.docs
def test_walkthrough_demo_bundle_reference_is_not_stale() -> None:
    text = WALKTHROUGH_PATH.read_text(encoding="utf-8")

    assert BEGIN_MARKER in text, (
        "operator-walkthrough.md is missing the machine reference section. "
        "Run: python scripts/generate_walkthrough_reference.py"
    )
    assert END_MARKER in text, (
        "operator-walkthrough.md is missing the end marker for the machine reference section."
    )

    start = text.index(BEGIN_MARKER)
    end = text.index(END_MARKER) + len(END_MARKER)
    embedded = text[start:end]

    expected = render_section()
    assert embedded == expected, (
        "Demo bundle reference section in operator-walkthrough.md is stale.\n"
        "Run: python scripts/generate_walkthrough_reference.py"
    )
