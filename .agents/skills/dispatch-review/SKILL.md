---
name: dispatch-review
description: Use when implementation is stable and a findings-first code review is required before final handoff or PR prep for a code-bearing scope. Spawns specialist subagents in read-only review mode. Do not use during early implementation, for planning, or when a reviewer summary is not the required output.
---

## Goal

Produce a findings-first review of a completed or stable diff by running seven specialist
subagents in parallel and consolidating their structured findings into a severity-ordered
markdown report.

Run this once per stable reviewable scope, not once per sprint item.

## Inputs

- The diff or set of files under review.
- The relevant requirements, architecture sections, and test coverage.
- The review mode guide at `docs/agents/review.md`.
- The applicable change-class done checklist from `docs/runbooks/project-working-practices.md`.

## Steps

1. Confirm implementation is stable enough to review — the diff is not expected to change
   significantly before the review completes.

2. Read the review mode guide at `docs/agents/review.md`.

3. Assemble context: the diff or file list, the relevant requirements, the change class,
   and the applicable done criteria.

4. Fan-out: spawn all seven specialist subagents in parallel using `run_in_background=true`.
   For each specialist, pass:
   - The specialist prompt from `.agents/skills/dispatch-review/specialists/<name>.md`
     (read the file; do not embed its contents inline)
   - The diff or file list under review
   - Explicit instruction: read and report only — no edits, no bash mutations
   - The JSON output schema from the specialist file
   - Instruction: return a JSON array of findings objects, or `[]` if no findings

   Specialist roster (all run in parallel):
   - `specialists/pack-boundary.md` — model: haiku
   - `specialists/stratum-coherence.md` — model: sonnet
   - `specialists/semantic-ownership.md` — model: sonnet
   - `specialists/god-class-file-size.md` — model: haiku
   - `specialists/repetition-vs-abstraction.md` — model: sonnet
   - `specialists/test-quality.md` — model: haiku
   - `specialists/suppression-drift.md` — model: haiku

5. Collect results. For each specialist:
   - If the specialist returns valid JSON, parse the findings array.
   - If the specialist returns malformed JSON or non-JSON text, log a warning
     (`specialist: <name> — degraded, output not parseable`) and skip that specialist's
     findings rather than failing the review.

6. Consolidate into findings-first markdown:

   a. **Dedup**: key is `(file, line, specialist)`. When the same specialist flags the
      same location twice, keep the higher-severity entry.

   b. **Merge across specialists**: group entries by `(file, line)`. When two specialists
      flag the same location, keep the highest severity entry and note both specialists.

   c. **Sort within tiers**: Blockers first, then Advisories, then Watchlist. Within each
      tier, sort by file path then line number.

   d. **Render** using this structure:

      ```
      ## Triage

      **Blockers:** N  **Advisories:** N  **Watchlist:** N
      Degraded specialists (if any): <name>, <name>

      ---

      ## Blockers

      ### [file:line] finding-title
      **Specialist:** name (+ name if merged)
      **Evidence:** ...
      **Recommendation:** ...

      ---

      ## Advisories

      (same block format as Blockers)

      ---

      ## Watchlist

      | File | Finding | Specialist |
      |---|---|---|
      | path:line | description | name |
      ```

      For file-level findings (`line: null`), render as `file` without a line anchor.

   e. If zero blockers: append "No blockers found. Scope is clear for handoff."

   f. If blockers present: append "Blockers present. Route to dispatch-build for
      remediation before proceeding."

7. Present the consolidated report to the user.

8. If blockers exist, route to `dispatch-build` for fixes before proceeding.

9. Treat this review as complete only when the current stable scope is either cleared or
   any residual risks are explicitly called out in the handoff.

## Output contract

- Findings ordered by severity with file references.
- Open questions or missing coverage noted explicitly.
- No repo edits made during this skill.
- The reviewed scope is ready for handoff or PR prep, or the blockers preventing that
  are explicit.

## Do not

- Do not run the review subagents before implementation is stable.
- Do not suppress findings to produce a clean summary.
- Do not proceed to PR handoff if the review surfaces unresolved blockers.
- Do not treat this as optional for a stable code-bearing scope that is about to be
  handed off or pushed toward PR.
- Do not embed specialist prompt content inline in this file — read the specialist files
  from `.agents/skills/dispatch-review/specialists/` at runtime.
- Do not use Opus for any specialist — Haiku for pattern-matching specialists, Sonnet
  for synthesis specialists.
