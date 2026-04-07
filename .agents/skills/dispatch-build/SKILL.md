---
name: dispatch-build
description: Use when an approved plan or well-scoped sprint item is ready for implementation. Spawns one or more Haiku subagents to execute discrete items, optionally in parallel with worktree isolation. Do not use for planning, review, or items that require design decisions not already settled.
---

## Goal

Execute approved, spec-complete implementation work by delegating to Haiku subagents, keeping frontier token spend on decisions rather than on mechanical code production.

## Inputs

- An approved plan or active sprint item with clear deliverables.
- Live sprintctl item and claim state.
- The implementation mode guide at `docs/agents/implementation.md`.
- Relevant contracts, fixtures, and extension points for the target layer.

## Steps

1. Confirm the work is implementation-ready: scope is decided, layer boundaries are clear, and a plan or sprint item exists.
2. Load `.envrc` and inspect live sprint/item/claim state before touching repo files.
3. For each implementation item:
   a. Claim or verify ownership using `sprintctl claim start` before dispatching.
   b. Spawn a subagent: type=general-purpose, model=haiku, with:
      - The specific deliverable and acceptance criteria
      - The implementation mode guide from `docs/agents/implementation.md`
      - The claim ID and item context (but not the claim token — keep that in the orchestrating session)
      - The local verification command: `pytest <specific-test-files> -x --tb=short` — foreground, blocking, targeting only files changed by this item. Do not run the full suite; do not background pytest.
   c. For independent items: use `run_in_background=true` and dispatch in parallel.
   d. For items touching overlapping files: use `isolation=worktree` to prevent conflicts.
4. Collect subagent results. If a subagent reports test failures, run up to 5 fix cycles before escalating.
5. After each item completes verification, use `item-done` to commit and mark done.

## Output contract

- Each item implemented with passing tests before close-out.
- One commit per item, not batched.
- Sprint state updated after each item.

## Do not

- Do not dispatch to Haiku if the item still has unresolved design decisions — use `dispatch-plan` first.
- Do not pass the claim token to the subagent.
- Do not batch multiple items into a single commit.
- Do not skip the local verification step before marking an item done.
