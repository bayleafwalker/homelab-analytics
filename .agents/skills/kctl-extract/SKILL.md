---
name: kctl-extract
description: Use at sprint close to extract durable knowledge (decisions, patterns, resolved blockers, lessons) from sprintctl events into the kctl review pipeline.
---

## Goal

Recover durable knowledge from sprint events before the sprint goes stale. This is the sprint-close step that feeds the knowledge pipeline.

## Inputs

- A closed or nearly-closed sprint with events logged via `sprintctl event add`.
- Event types that carry extractable knowledge: `decision`, `blocker-resolved`, `pattern-noted`, `risk-accepted`, `lesson-learned`.

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
