---
name: sprint-packet
description: Use when accepted scope needs to become an implementation-ready sprint doc or work packet. Do not use for open-ended brainstorming, narrow code edits, or requests that are still missing scope decisions.
---

## Goal

Convert accepted scope into a concise sprint packet with clear deliverables, dependencies, acceptance, and verification.

## Inputs

- The accepted scope or approved request.
- Governing requirements, architecture docs, and relevant plan or sprint references.
- Known constraints, dependencies, and verification expectations.

## Steps

1. Confirm the scope is already decided enough to plan without inventing product direction.
2. Pull the requirements, architecture docs, and prior sprint material that define the work.
3. Draft the packet in this order:
   goal, scope, out-of-scope, dependencies, deliverables, acceptance checks, verification path.
4. Slice work by repo contracts and layers rather than by vague task buckets.
5. Call out any required doc, requirement, fixture, or contract updates needed for the sprint to be complete.
6. After the packet is agreed, register the sprint in sprintctl:
   - Load the project DB first via `.envrc` or exported `SPRINTCTL_DB`.
   - `sprintctl sprint create --name "<Sprint ID> — <name>" --start <YYYY-MM-DD> --end <YYYY-MM-DD> --status active --kind active_sprint`
   - Add each deliverable as a work item: `sprintctl item add --sprint-id <id> --track <stage-N> --title "<title>"`
   - If the packet represents parked scope rather than active delivery, use `--kind backlog` instead of mixing it into the active sprint list.
   - Run `sprintctl render` and confirm output matches the agreed packet before starting implementation.

## Output contract

- A sprint-ready packet with clear deliverables and acceptance.
- Dependencies and blockers separated from in-scope work.
- A concrete verification path that can be used during implementation and handoff.
- A sprintctl sprint registered and items added, ready for status tracking.

## Do not

- Do not turn unresolved product questions into fake implementation tasks.
- Do not hide architecture or contract work inside generic backlog bullets.
- Do not use this skill for direct implementation when no planning artifact is needed.
