# Session: Auth Backlog Refinement And Handover — 2026-04-08

**Model:** codex/gpt-5  
**Branch at capture:** main (`84cb4d9`)  
**Captured at:** 2026-04-08T08:59:40Z  

---

## Context

The session started as a read-only assessment of auth components against the documented goal state, with explicit focus on:

- refactoring needs
- future work for kernel separation, maintainability, and security
- repo-wide refactor direction visible in the last 20 commits

That assessment was then converted into live sprint backlog refinement and an implementing-agent handover.

---

## Governing Sources Used

- `docs/decisions/auth-boundary-external-identity-internal-authorization.md`
- `docs/decisions/household-platform-adr-and-refactor-blueprint.md`
- `requirements/security-and-operations.md`
- `docs/runbooks/configuration.md`
- auth runtime, route, storage, and test files under `apps/api/`, `packages/platform/auth/`, `packages/storage/`, and `tests/`
- `git log --oneline -20` plus targeted commit inspection for recent auth and refactor work

---

## Main Assessment Outcome

The repo is functionally aligned with the auth goal state, but structurally incomplete:

- the external-identity / in-app-authorization boundary is documented and implemented
- the auth kernel exists, but key policy and transport concerns are still concentrated in a few hotspot files
- the broader repo trend in recent commits is toward thinner surfaces and extracted use-cases, and auth should continue in that direction

Key findings recorded during the session:

1. Forwarded headers are currently trusted too broadly for security-sensitive decisions.
2. `apps/api/auth_runtime.py` remains the main branch-heavy policy hotspot.
3. Route authorization policy is still encoded as central path-prefix logic.
4. Core auth vocabulary still lives in `packages/storage/auth_store.py`, which weakens kernel separation.
5. `apps/api/routes/auth_session_routes.py` still carries too much orchestration.

---

## Sprintctl Work Completed

Project DB was loaded from `.envrc` and live sprint state was checked before changes.

Confirmed existing state:

- sprint `#41` is the target backlog sprint: `keel-ledger-bond - Kernel Hardening and Runtime Honesty`
- item `#290` is already done: `Auth policy decomposition and thin FastAPI assembly`
- item `#288` is a stale duplicate in archived sprint `#40`

Added new follow-on backlog items under sprint `#41`:

- `#304` `auth-transport` — `Trust forwarded headers only from configured forwarders`
- `#301` `auth-policy` — `Decompose auth middleware into thin FastAPI assembly plus policy components`
- `#302` `auth-contracts` — `Move auth vocabulary out of storage into shared/platform contracts`
- `#300` `auth-routing` — `Replace path-prefix auth policy trees with declarative route policy catalog`
- `#299` `auth-use-cases` — `Extract local login and OIDC session flows into application use-cases`
- `#303` `auth-compat` — `Freeze shared auth shim and legacy auth-mode compatibility follow-up`

Structured brief notes were recorded on all new items with:

- goal
- acceptance
- verification

Dependency graph added:

- `#304 -> #301`
- `#301 -> #299`
- `#301 -> #300`
- `#301 -> #302`

Duplicate handling:

- recorded a decision note on `#288` marking it as superseded by `#299-#304`
- did not force a status transition on `#288` because local `sprintctl` only allowed `pending -> active`

Snapshot refresh:

- ran `sprintctl render --sprint-id 41 --output docs/sprint-snapshots/sprint-current.txt`

---

## Implementing-Agent Handover Produced

The implementing handover explicitly directs the next agent to:

- start with `#304` as the first execution slice
- move next to `#301`
- treat `#299`, `#300`, and `#302` as blocked by `#301`
- treat `#303` as independent follow-up

Hotspot files called out for implementation:

- `apps/api/auth_runtime.py`
- `apps/api/routes/auth_session_routes.py`
- `packages/platform/auth/credential_resolution.py`
- `packages/platform/auth/scope_authorization.py`
- `packages/platform/auth/permission_registry.py`
- `packages/storage/auth_store.py`

Guardrails preserved in the handover:

- no new user-lifecycle features
- keep service-token and machine-JWT parity
- keep `local_single_user` as narrow break-glass only
- follow the recent repo refactor style: extract orchestration into named modules instead of extending hotspot files

---

## Files Mutated During Session

- `docs/sprint-snapshots/sprint-current.txt`
- `.agents/sessions/2026-04-08-auth-backlog-refinement-and-handover.md`

No product code was changed in this session. The repo mutation was sprint-state artifact generation plus this session note.

---

## Commands Of Note

- `git log --oneline -20`
- `sprintctl sprint list`
- `sprintctl item list`
- `sprintctl item show --id 288`
- `sprintctl item show --id 290`
- `sprintctl item add --sprint-id 41 ...`
- `sprintctl item note --id ...`
- `sprintctl item dep add --id ... --blocks-item-id ...`
- `sprintctl render --sprint-id 41 --output docs/sprint-snapshots/sprint-current.txt`

---

## Open Follow-on

- Implement item `#304` first.
- If desired, commit the updated sprint snapshot and this session artifact as a standalone workflow/docs commit.

---

## Post-Handover Outcome Update

This handover was fully executed in the same date window and all planned items were completed:

- `#304` done
- `#301` done
- `#299` done
- `#300` done
- `#302` done
- `#303` done

Follow-up quality gates:

- dedicated findings-first review was dispatched after implementation
- review findings were implemented (including scenario creator auth regression + test coverage gap)
- `make verify-fast` was rerun through multiple iterations and finished green

See the detailed execution artifact:

- `.agents/sessions/2026-04-08-auth-implementation-execution-log.md`
