---
name: item-done
description: Use when a sprint item's implementation is complete and verified. Captures knowledge events while context is hot, then commits, marks done, and refreshes the snapshot.
---

## Goal

Close a sprint item cleanly: verify the work, capture any durable knowledge before the context cools, commit, and update sprint state — in that order.

## Inputs

- A completed, verified sprint item with an active claim.
- A loaded project DB via `.envrc` or exported `SPRINTCTL_DB`.
- The `claim_id` and `claim_token` for the current claim.

## Steps

### 1. Confirm verification is clean

Run the full test suite and report pass/fail count:

```bash
make test
```

Do not proceed if tests are failing. Use the self-healing loop (diagnose and fix up to 5 cycles) before escalating.

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

### 3. Commit the item

One commit per sprint item:

```bash
git add <files>
git commit -m "<type>(<scope>): <description>"
```

Commit message should reference the item work, not the item ID. Tests must be green before this commit.

### 4. Mark done via claim

```bash
SPRINTCTL_DB=... sprintctl item done-from-claim \
  --item-id <item-id> \
  --claim-id <claim-id> \
  --claim-token <claim-token>
```

This ties the done transition to ownership proof. Do not use `item status done` separately when a claim exists.

### 5. Refresh sprint snapshot

Run the `sprint-snapshot` skill or:

```bash
SPRINTCTL_DB=... sprintctl render > docs/sprint-snapshots/sprint-current.txt
git add docs/sprint-snapshots/sprint-current.txt
git commit -m "chore: update sprint snapshot after <item-title>"
```

## Output contract

- Tests are green.
- Any non-obvious decision or lesson is logged as a structured `sprintctl` event with `summary`, `detail`, `tags`, and `confidence`.
- One commit exists for the item's implementation.
- The item is in `done` state in `sprintctl`, tied to the claim.
- `docs/sprint-snapshots/sprint-current.txt` reflects the updated sprint state.

## Do not

- Do not mark done before tests pass.
- Do not skip step 2 assuming you'll capture it at sprint close — retroactive logging produces thin knowledge candidates.
- Do not manufacture events if nothing non-obvious happened; one honest event beats three thin ones.
- Do not batch this item's commit with another item's changes.
- Do not use `item status done` when a claim exists — use `done-from-claim` to preserve ownership proof.
