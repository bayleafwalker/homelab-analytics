---
name: kctl-extract
description: Use at sprint close to extract durable knowledge (decisions, patterns, resolved blockers, lessons) from sprintctl events into the kctl review pipeline.
---

## Goal

Recover durable knowledge from sprint events before the sprint goes stale. This is the sprint-close step that feeds the knowledge pipeline.

## Inputs

- A closed or nearly-closed sprint with events logged via `sprintctl event add`.
- Event types that carry extractable knowledge: `decision`, `blocker-resolved`, `pattern-noted`, `risk-accepted`, `lesson-learned`, `claim-handoff`, `claim-ownership-corrected`, `claim-ambiguity-detected`, `coordination-failure`.
- Process, coordination, or workflow corrections that were logged during the sprint when they were discovered, even if extraction itself waits until sprint close.

## Event payload quality

kctl extracts candidates from event payloads. A bare event with no payload fields produces a candidate whose summary is `decision: <item title>` — a reminder that something happened, not a durable record.

**Fields that matter for extraction:**
- `--summary` — one sentence capturing what was decided or learned. This becomes the candidate title. Required for useful output.
- `--detail` — the reasoning, context, or alternatives considered. Omit only for trivial events.
- `--tags` — JSON array of topic tags (e.g. `'["auth","ha-bridge"]'`). Used for filtering and cross-referencing.
- `--confidence` — `high`, `medium`, or `low`. Signals how settled the decision is.

**Good event (produces a useful candidate):**
```
sprintctl event add --sprint-id 2 --type decision --actor claude \
  --summary "Use MQTT retain flag for HA device state to survive broker restart" \
  --detail "Evaluated polling vs. retain; retain avoids re-sync logic at cost of broker state coupling" \
  --tags '["mqtt","ha-bridge"]' --confidence high
```

**Poor event (produces noise):**
```
sprintctl event add --sprint-id 2 --type decision --actor claude
```

Log events at the moment a decision is made or a blocker resolves — not retroactively at sprint close, where context is lost.
This includes coordination corrections such as claim misuse, handoff rules, or other lessons that future agents should not relearn the hard way.

## Steps

1. Load the project DB environment via `.envrc` or exported `SPRINTCTL_DB` and `KCTL_DB`.
2. Run `kctl preflight` or `sprintctl maintain check --sprint-id <id>` first so stale-item or sprint-health warnings are visible before close-out.
3. Confirm the sprint has meaningful events logged. If none, note that extraction will yield no candidates.
4. Run `kctl extract --sprint-id <id>` to scan events and insert candidates.
5. Run `kctl review list` to see the extracted candidates. Use `--json` if the result is being consumed by another agent or script.
6. Use `kctl review show --id <n>` for handoff or coordination candidates when you need the preserved source payload and actor context before deciding whether to keep them.
7. For each candidate:
   - `kctl review approve --id <n> --title "<concise title>" --tags '["<tag1>","<tag2>"]'` for decisions/patterns worth keeping.
   - `kctl review reject --id <n> --reason "<reason>"` for duplicates, noise, or low-signal entries.
8. Run `kctl review list --status approved` to confirm the promoted set.
9. Run `kctl status --sprint-id <id>` to confirm there are no unexpected leftovers in the pipeline. Use `--json` if the result needs to be machine-consumable.
10. If the task explicitly includes promoting approved knowledge into published entries:
   - Use `kctl publish` for the approved entries that should become durable repo knowledge.
   - Render the committed artifact to `docs/knowledge/knowledge-base.md` via `kctl render --output docs/knowledge/knowledge-base.md`.
   - Keep the knowledge-base update separate from unrelated feature work.

## Output contract

- All extractable events from the sprint have been reviewed (approved or rejected).
- No candidates left in `candidate` status at sprint close.
- Any remaining approved-but-unpublished entries are intentional and visible via `kctl status`.
- If publication was in scope, `docs/knowledge/knowledge-base.md` reflects the published state after rendering.

## Do not

- Do not approve candidates without setting a meaningful title — the default summary is often terse.
- Do not run extraction before the sprint has events; add events first via `sprintctl event add`.
- Do not use this skill mid-sprint as a substitute for logging events now; capture the event immediately and leave extraction for sprint close unless immediate review is required.
- Do not render repo knowledge artifacts anywhere other than `docs/knowledge/knowledge-base.md` unless the repo docs are updated first.
