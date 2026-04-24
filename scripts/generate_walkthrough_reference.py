"""
Generate the 'Demo Bundle Machine Reference' section of operator-walkthrough.md.

Sources:
- packages/demo/bundle.py  (build_journey, DEMO_SEED)
- infra/examples/demo-data/manifest.json  (artifact paths, ingest_support)

Run from the repo root after any bundle change:
    python scripts/generate_walkthrough_reference.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MANIFEST_PATH = REPO_ROOT / "infra" / "examples" / "demo-data" / "manifest.json"
WALKTHROUGH_PATH = REPO_ROOT / "docs" / "runbooks" / "operator-walkthrough.md"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BEGIN_MARKER = "<!-- BEGIN DEMO BUNDLE MACHINE REFERENCE -->"
END_MARKER = "<!-- END DEMO BUNDLE MACHINE REFERENCE -->"


def render_section() -> str:
    from packages.demo.bundle import DEMO_SEED, build_journey  # noqa: PLC0415

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    journey = build_journey()

    artifacts_by_id = {a["artifact_id"]: a for a in manifest["artifacts"]}
    journey_artifact_ids = {aid for step in journey["steps"] for aid in step["artifact_ids"]}

    lines: list[str] = [
        BEGIN_MARKER,
        "",
        "## Demo Bundle Machine Reference",
        "",
        "Generated from `packages/demo/bundle.py` and `infra/examples/demo-data/manifest.json`.",
        "Run `python scripts/generate_walkthrough_reference.py` to regenerate after bundle changes.",
        "",
        "**Bundle layout after `make demo-generate`:**",
        "",
        "```",
        "/tmp/homelab-demo/",
        f"  manifest.json          — artifact index ({len(manifest['artifacts'])} artifacts, seed {DEMO_SEED})",
        f"  journey.json           — scripted journey metadata ({len(journey['steps'])} steps)",
        "  canonical/             — canonical CSV artifacts",
        "  sources/               — source-format artifacts",
        "```",
        "",
        "**Upload sequence (operator journey):**",
        "",
        "| Step | Artifact ID | File | Upload path | Routability |",
        "|------|-------------|------|-------------|-------------|",
    ]

    for step in journey["steps"]:
        for aid in step["artifact_ids"]:
            artifact = artifacts_by_id[aid]
            lines.append(
                f"| {step['step']} "
                f"| `{aid}` "
                f"| `{artifact['relative_path']}` "
                f"| `{step['upload_path']}` "
                f"| `{artifact['ingest_support']}` |"
            )

    template_only = [
        a for a in manifest["artifacts"] if a["artifact_id"] not in journey_artifact_ids
    ]
    if template_only:
        lines += [
            "",
            "**Template-only artifacts (reference; not yet routable for direct upload):**",
            "",
            "| Artifact ID | File | Format |",
            "|-------------|------|--------|",
        ]
        for a in template_only:
            lines.append(f"| `{a['artifact_id']}` | `{a['relative_path']}` | `{a['format']}` |")

    lines += ["", END_MARKER]
    return "\n".join(lines)


def inject_section(walkthrough_path: Path, section: str) -> None:
    text = walkthrough_path.read_text(encoding="utf-8")
    if BEGIN_MARKER in text and END_MARKER in text:
        start = text.index(BEGIN_MARKER)
        end = text.index(END_MARKER) + len(END_MARKER)
        updated = text[:start] + section + text[end:]
    else:
        sep = "\n\n---\n\n" if not text.endswith("\n\n") else ""
        updated = text.rstrip("\n") + "\n\n---\n\n" + section + "\n"
    walkthrough_path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    section = render_section()
    inject_section(WALKTHROUGH_PATH, section)
    print(f"Updated: {WALKTHROUGH_PATH.relative_to(REPO_ROOT)}")
