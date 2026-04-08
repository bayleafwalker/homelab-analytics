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
      - Immediately persist the returned `claim_token` to `.sprintctl/claims/claim-<item_id>.token` in the orchestrating session. Keep the token in session memory for normal execution; treat the file as crash recovery and do not pass the token to the subagent.
      - If the orchestrating session keeps the item open for more than 15 minutes, or the item crosses a long review/remediation boundary before close-out, run `sprintctl claim heartbeat` from the orchestrator to refresh ownership before continuing.
   b. Spawn a subagent: type=general-purpose, model=haiku, with:
      - The specific deliverable and acceptance criteria
      - The implementation mode guide from `docs/agents/implementation.md`
      - The claim ID and item context (but not the claim token — keep that in the orchestrating session and in the local recovery file only)
      - The local verification commands for the changed surface:
        - `ruff check <changed-python-files>`
        - `mypy <changed-python-files>`
        - `pytest <specific-test-files> -x --tb=short`
      - Run those checks foreground and blocking, scoped to files changed by this item. Do not run the full suite; do not background pytest.
   c. For independent items: use `run_in_background=true` and dispatch in parallel.
   d. For items touching overlapping files: use `isolation=worktree` to prevent conflicts.
4. Collect subagent results. If a subagent reports test failures, run up to 5 fix cycles before escalating.
   - Heartbeat the claim again before entering a long remediation loop or resuming after review if the item is still owned by the current live claim identity.
   - After adding or modifying any API route, auth policy, scenario policy mapping, or architecture doc, run `pytest tests/test_architecture_contract.py -x --tb=short` before closing the item.
5. After each item completes verification, use `item-done` to capture knowledge and mark done. Commit at the enclosing reviewable scope boundary: one commit per scope, where a scope may be one item or a tight group of related items. Once that scope diff is stable, run `dispatch-review` before final handoff or PR preparation.

## Output contract

- Each item implemented with passing tests before close-out.
- Incremental lint and type failures are caught at the item level instead of batching into `make verify-fast`.
- One commit per reviewable scope, not per unrelated batch.
- Stable code-bearing scopes are reviewed before handoff.
- Sprint state updated after each item.

## Do not

- Do not dispatch to Haiku if the item still has unresolved design decisions — use `dispatch-plan` first.
- Do not pass the claim token to the subagent; keep it only in the orchestrating session and the local `.sprintctl/claims/claim-<item_id>.token` recovery file.
- Do not batch unrelated items or scopes into a single commit.
- Do not skip the local verification step before marking an item done.
- Do not skip `dispatch-review` once a code-bearing scope is stable enough for handoff or PR prep.
- Do not heartbeat or reuse a claim whose live identity no longer clearly belongs to the current session.
