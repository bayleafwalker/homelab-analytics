# Agent Guidance Refactor

## What was removed

- Broad narrative context that duplicates architecture and plan docs.
- Stack defaults and bootstrap framing that already exist in repo docs.
- Per-task workflow triggers from `AGENTS.md`; those now live in mode docs or skills.
- Guidance that was too general to change behavior reliably on a per-task basis.

## What became a skill

- `domain-impact-scan`: front-loads layer, contract, and doc impact before editing.
- `sprint-packet`: turns roadmap or requirements material into an execution-ready packet.
- `code-change-verification`: selects, runs, and reports the right local checks.
- `pr-handoff-summary`: produces a compact reviewer or user handoff.

## Why the final structure is better

- `AGENTS.md` now keeps only rules that are short, broadly applicable, and costly to forget.
- Workflow-specific behavior moved into mode docs, runbooks, and skills, so agents only load that guidance when the task needs it.
- Repo steering stays anchored in architecture docs, requirements, and tests instead of duplicated prose in the top-level agent file.
