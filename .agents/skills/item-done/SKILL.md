---
name: item-done
description: Use when a sprint item's implementation is complete and verified. Captures knowledge events while context is hot, then marks done and refreshes the snapshot only when the workflow needs a shared state artifact; commit immediately only when the item closes the current reviewable scope.
---

## Goal

Close a sprint item cleanly: verify the work, capture any durable knowledge before the context cools, update sprint state, and commit at the right scope boundary instead of mechanically per item.

## Inputs

- A completed, verified sprint item with an active claim.
- A loaded project DB via `.envrc` or exported `SPRINTCTL_DB`.
- The `claim_id` and `claim_token` for the current claim.

## Steps

### 1. Confirm verification is clean

Run targeted tests for the files changed in this item — blocking, foreground, fast-fail:

```bash
pytest tests/test_foo.py tests/test_bar.py -x --tb=short
```

Do not run the full suite (`make test`) in-session — that is a CI gate. Do not background pytest. Do not proceed if targeted tests are failing; use the self-healing loop (diagnose and fix up to 5 cycles) before escalating.

Gate the rest of this skill on exit code zero:

```bash
pytest <changed-test-files> -x --tb=short && echo "verified"
```

### 2. Reflect — log knowledge events while context is hot

Before marking done, ask: did any of the following happen during this item?

- A design choice was made between two viable options
- A blocker was resolved by a non-obvious fix
- A pattern emerged that applies to other items or future sprints
- A migration or schema decision was made
- An integration failure revealed a wrong assumption

If yes, log it now — not at sprint close, where context is lost:

```bash
SPRINTCTL_DB=... sprintctl event add \
  --sprint-id <sprint-id> \
  --item-id <item-id> \
  --type <decision|lesson-learned> \
  --actor <actor> \
  --payload '{
    "summary": "<one sentence: what was decided or learned>",
    "detail": "<reasoning, alternatives considered, or why this matters>",
    "tags": ["<tag1>", "<tag2>"],
    "confidence": "<high|medium|low>"
  }'
```

A bare event with no payload produces a thin candidate at `kctl-extract` time. Include `summary` and `detail` at minimum.

If nothing non-obvious happened, skip this step — don't manufacture events.

### 3. Commit now only if this item closes the current scope

Use one commit per reviewable scope. If this item is the last item in a tight, related scope that should be reviewed together, commit now:

```bash
git add <files>
git commit -m "<type>(<scope>): <description>"
```

Commit message should reference the scope work, not the item ID. Tests must be green before this commit.

If the current scope still includes additional tightly related in-flight items, defer the commit until that scope stabilizes. Do not use deferral to batch unrelated work or to postpone commits until the end of a session without an explicit handoff note.

### 4. Mark done via claim

```bash
SPRINTCTL_DB=... sprintctl item done-from-claim \
  --item-id <item-id> \
  --claim-id <claim-id> \
  --claim-token <claim-token>
```

This ties the done transition to ownership proof. Do not use `item status done` separately when a claim exists.

### 5. Refresh sprint snapshot only when it is needed now

If the updated sprint state needs to be shared immediately — for example at handoff, end-of-batch, review handoff, or sprint close — run the `sprint-snapshot` skill or:

```bash
SPRINTCTL_DB=... sprintctl render > docs/sprint-snapshots/sprint-current.txt
git add docs/sprint-snapshots/sprint-current.txt
git commit -m "chore: update sprint snapshot after <item-title>"
```

If no immediate shared artifact is needed, stop after `done-from-claim` and batch the snapshot refresh at the next natural milestone instead of creating a mechanical per-item snapshot commit.

## Output contract

- Tests are green.
- Any non-obvious decision or lesson is logged as a structured `sprintctl` event with `summary`, `detail`, `tags`, and `confidence`.
- The item's implementation is either committed now or intentionally held in the active scope diff pending a scope-level commit.
- The item is in `done` state in `sprintctl`, tied to the claim.
- `docs/sprint-snapshots/sprint-current.txt` is refreshed when the workflow needs a new shared sprint artifact, not reflexively after every item.

## Do not

- Do not mark done before targeted tests pass.
- Do not run `make test` (full suite) in-session — push to CI and let it run there.
- Do not background `pytest` — run it foreground and wait for the exit code.
- Do not use `sprintctl item status --status done` before the pytest exit code is 0.
- Do not skip step 2 assuming you'll capture it at sprint close — retroactive logging produces thin knowledge candidates.
- Do not manufacture events if nothing non-obvious happened; one honest event beats three thin ones.
- Do not batch this item's changes with unrelated work under the guise of a scope-level commit.
- Do not use `item status done` when a claim exists — use `done-from-claim` to preserve ownership proof.
- Do not create a snapshot-only commit after every item unless the workflow explicitly needs that shared state artifact immediately.
