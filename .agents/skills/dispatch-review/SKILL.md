---
name: dispatch-review
description: Use when implementation is stable and a findings-first code review is required before final handoff or PR prep for a code-bearing scope. Spawns a Sonnet subagent in read-only review mode. Do not use during early implementation, for planning, or when a reviewer summary is not the required output.
---

## Goal

Produce a findings-first review of a completed or stable diff by delegating to a read-only Sonnet subagent.
Run this once per stable reviewable scope, not once per sprint item.

## Inputs

- The diff or set of files under review.
- The relevant requirements, architecture sections, and test coverage.
- The review mode guide at `docs/agents/review.md`.
- The applicable change-class done checklist from `docs/runbooks/project-working-practices.md`.

## Steps

1. Confirm implementation is stable enough to review — the diff is not expected to change significantly before the review completes.
2. Read the review mode guide at `docs/agents/review.md`.
3. Spawn a subagent: type=general-purpose, model=sonnet, with:
   - The diff or file list under review
   - The review mode guide content from `docs/agents/review.md`
   - The relevant requirements and architecture sections
   - The change class (docs-only, behavior, architecture) and its done criteria
   - Explicit instruction: no edits, no bash mutations — read and report only
4. Wait for the subagent to return findings.
5. Present findings to the user in findings-first order: issues by severity, then open questions, then summary.
6. If the review surfaces blockers, route to `dispatch-build` for fixes before proceeding.
7. Treat this review as complete only when the current stable scope is either cleared or any residual risks are explicitly called out in the handoff.

## Output contract

- Findings ordered by severity with file:line references.
- Open questions or missing coverage noted explicitly.
- No repo edits made during this skill.
- The reviewed scope is ready for handoff or PR prep, or the blockers preventing that are explicit.

## Do not

- Do not run the review subagent before implementation is stable.
- Do not suppress findings to produce a clean summary.
- Do not proceed to PR handoff if the review surfaces unresolved blockers.
- Do not treat this as optional for a stable code-bearing scope that is about to be handed off or pushed toward PR.
