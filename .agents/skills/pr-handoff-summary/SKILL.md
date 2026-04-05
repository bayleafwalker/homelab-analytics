---
name: pr-handoff-summary
description: Use when preparing a final implementation handoff or reviewer-facing summary for completed or stable work. Do not use during early exploration or when a findings-first code review is required instead.
---

## Goal

Produce a consistent final handoff that tells a reviewer or next engineer what changed, what was verified, and what still needs attention.

## Inputs

- The final diff or stable set of changes.
- Verification results already run.
- Any residual risk, follow-up, or known limitation.

## Steps

1. Summarize the change by outcome or architectural consequence, not by file inventory.
2. Identify the highest-signal files, docs, or contracts worth reviewer attention.
3. Include the verification already run and any remaining risk or follow-up.
4. Keep the handoff compact enough to scan quickly.

## Output contract

- A short summary of the implemented outcome.
- A verification section with the commands already run.
- A residual-risk or follow-up note when applicable.

## Do not

- Do not dump a file-by-file changelog.
- Do not omit verification status.
- Do not use this skill as a substitute for a findings-first review.
