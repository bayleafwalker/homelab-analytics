---
name: sprint-resume
description: Use when work already exists in sprintctl and the request is to continue, pick up, or resume an existing sprint item. It covers claim identity checks, handoff behavior, live-state updates, and event capture before repo edits.
---

## Goal

Resume an already-registered sprint item from live `sprintctl` state without duplicating work, stealing another agent's claim, or losing knowledge that should flow into `kctl` later.

## Inputs

- A request to continue sprint work, pick up the next existing item, or resume an already-scoped brief.
- A loaded project DB environment via `.envrc` or exported `SPRINTCTL_DB`.
- The relevant sprint item, claim, and recent event state.

## Steps

1. Confirm the work already exists in `sprintctl`. If it does not, stop and use `sprint-packet` instead.
2. Load the project DB first via `.envrc` or exported `SPRINTCTL_DB`.
3. Inspect the live sprint, item, claim, and recent event state before touching repo files. Prefer JSON output where another agent or script may consume the result. Typical checks are `sprintctl sprint show --json`, `sprintctl item list --sprint-id <id> --json`, `sprintctl item show --id <item-id> --json`, `sprintctl claim list --item-id <item-id> --json`, and `sprintctl claim list-sprint --sprint-id <id> --json`. If you are recovering after context loss, use `sprintctl claim resume --instance-id <id>` or `--runtime-session-id <id>` to locate claims that still belong to the current live identity.
4. Check whether an active exclusive claim already exists:
   - If no claim exists, prefer `sprintctl claim start` so claim creation and `pending -> active` happen atomically. If you need to inspect first without activation, use `sprintctl claim create` and move status separately with `sprintctl item status`.
   - Record and preserve strong identity immediately: `claim_id`, `claim_token`, `runtime_session_id`, `instance_id`, actor, and workspace metadata. Treat `claim_token` as a secret.
   - If the current session already holds the active claim's `claim_token` and the live identity plus workspace metadata clearly match, refresh the heartbeat and continue.
   - If the claim token is missing, the identity is ambiguous, or the claim points to another live workspace, do not heartbeat it and do not edit repo files. Resolve a handoff first or choose different work.
5. For Codex, prefer `CODEX_THREAD_ID` as `runtime_session_id` when it is available. Also mint a stable `instance_id` once per live client or process start. Shared labels and workspace metadata alone are not enough to prove ownership. Use `sprintctl agent-protocol --json` if you need the exact create, heartbeat, handoff, or release command shape.
6. Move the item to `active` before implementation when appropriate (already handled if you used `claim start`).
7. Use sprint docs, requirements, and architecture docs only as implementation context for the selected item; they do not override live ownership or status.
8. Record structured `sprintctl` events when decisions, resolved blockers, or reusable lessons happen. Use `decision` or `lesson-learned` for process corrections that should feed `kctl` later, and include payload keys such as `summary`, `detail`, `tags`, and `confidence`. The bar is met when any of these occur:
   - A design choice was made between two viable options
   - A blocker was resolved by a non-obvious fix
   - A pattern emerged that applies to other items or future sprints
   - A migration or schema decision was made
   - An integration failure revealed a wrong assumption
   Log the event immediately — context degrades fast and retroactive logging at sprint close produces thin candidates.
9. If work pauses or changes hands, use `sprintctl claim handoff` to transfer or rotate any active claim, then produce `sprintctl handoff --output <path>` when the next session also needs broader sprint context. Keep handoff artifacts local unless a tracked artifact was explicitly requested.
10. When implementation completes, prefer `sprintctl item done-from-claim` so done + optional claim release stay tied to ownership proof.
11. After material sprint-state changes, refresh the shared snapshot with `sprint-snapshot`.

## Output contract

- Repo edits start only after live ownership is clear.
- Claim identity is strong enough to distinguish one live agent or worktree from another.
- Item status, relevant events, and snapshot state stay aligned with the actual execution state.
- Knowledge-worthy workflow or design lessons are recorded early enough for sprint-close extraction.

## Do not

- Do not pick the next task from docs when the existing item state is available in live `sprintctl`.
- Do not heartbeat or reuse another agent's exclusive claim just because the actor label looks familiar.
- Do not treat matching branch, worktree, commit SHA, or workspace token as sufficient ownership proof.
- Do not start implementation before claim identity or handoff state is clear.
- Do not wait until sprint close to log a reusable lesson that should become a `decision` or `lesson-learned` event now.
