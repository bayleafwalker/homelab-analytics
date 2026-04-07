# Sprint amber-claim-ledger — Sprint Packet

**Dates:** 2026-04-07 to 2026-04-10
**Goal:** Close the remaining Sprint #23 follow-up work by recording the claim-token persistence lesson as durable sprint knowledge under tracked ownership.

---

## Scope

This packet is intentionally narrow.

Sprint #23 close-out identified four workflow follow-ups. The repo already contains the repo-tracked changes for the first three:

- claim-token persistence guidance is documented in the sprint resume and build skills
- architecture-contract verification is part of implementation guidance and dispatch-build verification
- sprint close guidance now uses the architecture contract fast gate instead of the full test suite as a blocking close step

The only remaining follow-through is operational rather than code-facing: capture the claim-token persistence rule as a durable `decision` event so it can move through the knowledge pipeline without depending on ephemeral session notes.

---

## Deliverable

### Item 1 — Durable claim-token decision event

**Deliverable:** Log the claim-token persistence lesson as a `decision` event during sprint planning or execution, tied to a claimed sprint item.

**Required content:**

- claim tokens must survive session resets
- `.sprintctl/claims/claim-<item_id>.token` is the crash-recovery path
- the orchestrating session still keeps the token in memory for normal execution
- subagents do not receive the claim token directly

**Acceptance:**

- a new sprint item exists for the operational follow-through
- the item is claimed before mutation
- the `decision` event is recorded with summary, detail, tags, and confidence payload fields
- the item can be closed without repo-code changes

---

## Out Of Scope

- re-implementing claim-token persistence guidance already landed in tracked docs and skills
- reopening sprint-close verification rules already updated in the repo
- changing `sprintctl` or `kctl` runtime behavior

---

## Dependencies

- `sprintctl` project DB is loaded from the repo-scoped `.sprintctl/sprintctl.db`
- live sprint state shows no remaining open items in sprint #25, so this work must be registered rather than resumed
- existing runbooks and skills already reflect the repo-tracked workflow changes from Sprint #23 close-out

---

## Verification Path

```bash
source .envrc

# Confirm the new sprint and item are registered
sprintctl sprint list --json
sprintctl item list --sprint-id <new-sprint-id> --json

# Confirm the decision event exists on the claimed item
sprintctl event list --item-id <new-item-id> --json

# Refresh the shared sprint snapshot after state changes
sprintctl render --output docs/sprint-snapshots/sprint-current.txt
```

---

## Execution Order

1. Register the new sprint and item in `sprintctl`
2. Claim the item with explicit session identity
3. Log the durable `decision` event
4. Mark the item done and refresh the sprint snapshot
