---
name: sprint-close
description: Use at the end of a sprint to run the full close-out sequence: verify clean test suite, snapshot sprint state, extract and review knowledge candidates, publish approved entries, and tag the sprint boundary.
---

## Goal

Encode the full sprint close-out sequence in one skill so the steps are not repeated ad-hoc across sessions. Produces a clean test baseline, a committed snapshot, reviewed knowledge candidates, and an optional tag.

## Inputs

- The sprint ID to close (confirm with `sprintctl sprint list` if uncertain).
- A loaded project DB via `.envrc` or exported `SPRINTCTL_DB` and `KCTL_DB`.
- Confirmation that all sprint items intended for this sprint are in `done` or explicitly deferred.

## Steps

### 1. Verify clean test suite

```bash
make test
```

Report pass/fail count. If tests fail, diagnose and fix before continuing — do not close a sprint on a red suite. Use the self-healing loop (up to 5 cycles) before escalating.

### 2. Confirm sprint item health

```bash
SPRINTCTL_DB=... sprintctl maintain check --sprint-id <id>
```

Review any stale, blocked, or unclaimed items. Decide with the user whether to defer, cancel, or carry forward before proceeding.

### 3. Close the sprint in sprintctl

```bash
SPRINTCTL_DB=... sprintctl sprint close --sprint-id <id>
```

If the sprint requires a final status comment, add it as an event first:

```bash
SPRINTCTL_DB=... sprintctl event add --sprint-id <id> --type decision --actor <actor> \
  --payload '{"summary":"<close rationale>","detail":"<what was deferred and why>"}'
```

### 4. Refresh the sprint snapshot

Run the `sprint-snapshot` skill (or equivalent commands) to commit the final sprint state to `docs/sprint-snapshots/sprint-current.txt`.

Commit as a standalone `chore:` commit:

```bash
git add docs/sprint-snapshots/sprint-current.txt
git commit -m "chore: final sprint snapshot for <sprint-codename>"
```

### 5. Extract knowledge

Run the `kctl-extract` skill. Key steps:

```bash
KCTL_DB=... kctl extract --sprint-id <id>
KCTL_DB=... kctl review list --kind all
```

Review all candidates. Approve with a meaningful title, reject noise. Verify no candidates remain in `candidate` status:

```bash
KCTL_DB=... kctl status --sprint-id <id> --kind all
```

### 6. Publish and render (if in scope)

If approved entries should become durable repo knowledge:

```bash
KCTL_DB=... kctl publish --id <n> --body "<detail>" --category <decision|pattern|lesson|risk|reference>
KCTL_DB=... kctl render --output docs/knowledge/knowledge-base.md
```

Commit the knowledge-base update as its own `docs:` commit:

```bash
git add docs/knowledge/knowledge-base.md
git commit -m "docs: publish sprint <id> knowledge extracts"
```

### 7. Tag the sprint boundary (optional)

If the project uses git tags for sprint boundaries:

```bash
git tag sprint/<sprint-codename>
git push --tags
```

Confirm with the user before pushing tags.

## Output contract

- Test suite is green at close.
- `docs/sprint-snapshots/sprint-current.txt` reflects the closed sprint state.
- All knowledge candidates are approved or rejected — none left in `candidate` status.
- If publication was in scope, `docs/knowledge/knowledge-base.md` is up to date.
- Sprint is marked closed in `sprintctl`.

## Do not

- Do not close a sprint with a failing test suite.
- Do not skip the `maintain check` step — unresolved stale items silently drop work.
- Do not run `kctl extract` if no events were logged; add retrospective events first via `sprintctl event add`.
- Do not merge the snapshot commit, knowledge commit, and tag step into one commit — keep them separate for diffability.
- Do not use the home-directory DB; always verify `SPRINTCTL_DB` and `KCTL_DB` point to the project paths.
