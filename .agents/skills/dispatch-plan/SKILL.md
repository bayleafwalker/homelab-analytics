---
name: dispatch-plan
description: Use when a request requires architecture decisions, new scope definition, or a planning pass before any repo edits. Spawns an Opus subagent in read-only planning mode and returns a decision-complete implementation brief. Do not use for direct implementation, resuming an existing sprint item, or narrowly scoped edits that don't require design decisions.
---

## Goal

Produce a decision-complete implementation brief by delegating the planning pass to an Opus subagent, without any repo mutations in this step.

## Inputs

- The user request or accepted scope description.
- Relevant requirements, architecture docs, and sprint context.
- Live sprintctl state when the request is sprint-scoped.

## Steps

1. Confirm the request requires a planning pass — it involves architecture decisions, layer-boundary questions, or multi-file scope that isn't already decided by existing code and docs.
2. If the work is already registered in sprintctl as a pending item, stop and use `dispatch-build` or `sprint-resume` instead.
3. Load `.envrc` and read live sprintctl state to check for existing scope overlap.
4. Read the planning mode guide at `docs/agents/planning.md`.
5. Spawn a subagent: type=Plan, model=opus, with this brief:
   - The user's goal and success criteria
   - The relevant mode guide content from `docs/agents/planning.md`
   - Current sprintctl sprint/item state (summarised, not full JSON)
   - Affected layer boundaries (landing / transformation / reporting)
   - Any requirements or architecture docs that constrain the design
6. Wait for the subagent to return a decision-complete plan.
7. Present the plan to the user for confirmation before any implementation begins.
8. If the plan is accepted and new sprint scope is needed, invoke `sprint-packet` to register it.

## Output contract

- A concise plan with: goal, scope, out-of-scope, layer boundaries, deliverables, acceptance checks, and verification path.
- No repo edits made during this skill.
- The plan is confirmed before implementation starts.

## Do not

- Do not proceed to implementation within this skill.
- Do not invent product decisions not present in requirements or user instruction.
- Do not spawn the Opus subagent if the scope is already fully decided by existing code and the task is routine implementation.
