"""Demo household fixture generator."""
from __future__ import annotations

from packages.demo import canonical_demo_files


def generate_all() -> dict[str, bytes]:
    return canonical_demo_files()
