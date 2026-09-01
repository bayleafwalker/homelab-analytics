#!/usr/bin/env python3
"""Render a sprint snapshot from live sprintctl state.

`sprintctl render` is not available through the Vuoro served catalog, and the
repo marker forbids `SPRINTCTL_BACKEND=local`, so the sanctioned
`make snapshot-refresh` path cannot run here. This renderer rebuilds the same
document from the served-available JSON commands, so the committed snapshot
stays provably derived from sprintctl state rather than hand-authored.

Every line comes from one of:
  sprintctl sprint show --id <id> --detail --json
  sprintctl item list --sprint-id <id> --json
  sprintctl item ref list --id <item> --json

Fields absent from sprintctl are omitted, never invented. Retire this in favour
of `sprintctl render` once the served catalog exposes it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUS_ORDER = ("done", "active", "pending", "blocked")


def sprintctl(*args: str) -> Any:
    """Run a sprintctl subcommand and parse its JSON output."""
    result = subprocess.run(
        ["sprintctl", *args, "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.exit(f"sprintctl {' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def counts_line(counts: dict[str, int], total: int, blocked_ratio: float) -> str:
    done = counts.get("done", 0)
    done_pct = round(100 * done / total) if total else 0
    noun = "item" if total == 1 else "items"
    return (
        f"  health: {total} {noun} — {done} done ({done_pct}%), "
        f"{counts.get('active', 0)} active, {counts.get('pending', 0)} pending, "
        f"{counts.get('blocked', 0)} blocked ({round(100 * blocked_ratio)}%)"
    )


def render(sprint_id: int) -> str:
    sprint = sprintctl("sprint", "show", "--id", str(sprint_id), "--detail")
    items = sprintctl("item", "list", "--sprint-id", str(sprint_id))
    track_health = sprint.get("detail", {}).get("track_health", {})

    tally = {status: sum(1 for i in items if i["status"] == status) for status in STATUS_ORDER}
    lines = [
        f"SPRINT: {sprint['name']}  [{sprint['status']}]",
    ]
    # Only sprintctl-backed fields; `goal` is frequently empty and there is no
    # `sprint edit` command to populate it, so an empty goal prints nothing.
    if sprint.get("goal"):
        lines.append(f"Goal:   {sprint['goal']}")
    lines += [
        f"Dates:  {sprint['start_date']} to {sprint['end_date']}",
        f"ID:     {sprint['id']}",
        "Items:  {} total — {}".format(
            len(items),
            ", ".join(f"{tally[status]} {status}" for status in STATUS_ORDER),
        ),
    ]

    # Track order follows first appearance in item order, which is stable.
    tracks: list[str] = []
    for item in items:
        if item["track_name"] not in tracks:
            tracks.append(item["track_name"])

    for track in tracks:
        health = track_health.get(track, {})
        lines += ["", f"--- Track: {track} ---"]
        if health:
            lines.append(
                counts_line(
                    health.get("counts", {}),
                    health.get("total", 0),
                    health.get("blocked_ratio", 0.0),
                )
            )
        for item in (i for i in items if i["track_name"] == track):
            assignee = item.get("assignee") or "-"
            lines.append(
                f"  [{item['status']:<8}] #{item['id']} {item['title']}  (assignee: {assignee})"
            )
            for ref in sprintctl("item", "ref", "list", "--id", str(item["id"])):
                lines.append(f"    ref [{ref['ref_type']}] {ref['label']}: {ref['url']}")

    rendered_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines += ["", f"Rendered: {rendered_at} (source: sprintctl JSON commands)"]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sprint-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(render(args.sprint_id), encoding="utf-8")
    print(f"Rendered sprint #{args.sprint_id} to {args.output}")


if __name__ == "__main__":
    main()
