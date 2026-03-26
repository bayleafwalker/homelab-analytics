---
name: kctl-extract
description: Use at sprint close to extract durable knowledge (decisions, patterns, resolved blockers, lessons) from sprintctl events into the kctl review pipeline.
---

## Goal

Recover durable knowledge from sprint events before the sprint goes stale. This is the sprint-close step that feeds the knowledge pipeline.

## Inputs

- A closed or nearly-closed sprint with events logged via `sprintctl event add`.
- Event types that carry extractable knowledge: `decision`, `blocker-resolved`, `pattern-noted`, `risk-accepted`, `lesson-learned`.

## Steps

1. Confirm the sprint has meaningful events logged. If none, note that extraction will yield no candidates.
2. Run `kctl extract --sprint-id <id>` to scan events and insert candidates.
3. Run `kctl review list` to see the extracted candidates.
4. For each candidate:
   - `kctl review approve --id <n> --title "<concise title>" --tags '["<tag1>","<tag2>"]'` for decisions/patterns worth keeping.
   - `kctl review reject --id <n> --reason "<reason>"` for duplicates, noise, or low-signal entries.
5. Run `kctl review list --status approved` to confirm the promoted set.

## Output contract

- All extractable events from the sprint have been reviewed (approved or rejected).
- No candidates left in `candidate` status at sprint close.

## Do not

- Do not approve candidates without setting a meaningful title — the default summary is often terse.
- Do not run extraction before the sprint has events; add events first via `sprintctl event add`.
- Do not use this skill mid-sprint unless capturing an important decision that must not be lost.
