# Session: Harbor Policy Seam Sprint Packet And Handover — 2026-04-08

**Model:** codex/gpt-5
**Branch at capture:** main (`1ea2504`)
**Captured at:** 2026-04-08T12:53:17Z

---

## Context

The prior auth hardening sprint closed the functional regressions, including trusted-forwarder handling and the scenario creator policy review fix. The remaining gap is architectural:

- concrete app route strings and policy declarations still live in the platform-owned catalog
- architecture tests currently enforce coverage through that placement
- session use-cases still have HTTP-shaped inputs, but that is follow-on work after the stricter kernel/app auth seam is made explicit

This handover converts that residual into a new active sprint packet and an execution order suitable for a build agent.

---

## Governing Sources Used

- `AGENTS.md`
- `docs/agents/planning.md`
- `docs/runbooks/project-working-practices.md`
- `docs/decisions/auth-boundary-external-identity-internal-authorization.md`
- `docs/plans/2026-04-backlog-refinement.md`
- `packages/platform/auth/route_policy_catalog.py`
- `packages/platform/auth/scope_authorization.py`
- `packages/application/use_cases/auth_sessions.py`
- `apps/api/routes/auth_session_routes.py`
- `tests/test_architecture_contract.py`
- `tests/test_auth_permission_registry.py`
- `tests/test_api_auth.py`

---

## Sprintctl Outcome

Created active sprint:

- `#45` `harbor-policy-seam — App-Owned Authorization Declarations`

Goal:

- Finish the auth kernel/app seam by moving concrete route authorization declarations to app-owned composition while keeping the platform responsible only for generic policy primitives and evaluation.

Items created:

- `#305` `policy-engine` — `Extract generic route-policy primitives and lookup from platform-owned catalog`
- `#306` `app-declarations` — `Move route authorization declarations to app-owned registration`
- `#307` `policy-contracts` — `Reframe auth coverage tests around app-owned declarations`
- `#308` `compat-cleanup` — `Trim touched storage-era auth compatibility imports after policy move`

Dependencies registered:

- `#305 -> #306`
- `#306 -> #307`
- `#306 -> #308`

Snapshot refresh:

- rendered `docs/sprint-snapshots/sprint-current.txt` from sprint `#45`

---

## Packet

### Goal

Make authorization declaration ownership match the documented boundary:

- platform owns generic auth primitives, evaluation, and enforcement
- app owns concrete protected-route declarations and policy mapping for its own surfaces

### In scope

- extract generic route-policy contracts and lookup helpers out of the current platform-owned concrete catalog path
- inject or register app-owned declarations from the API layer or app-local policy modules
- update auth runtime wiring to consume app-provided declarations without broadening auth semantics
- rewrite architecture coverage tests so they assert full protected-route coverage from app-owned declarations
- trim touched compatibility imports that keep storage-era auth paths on the new primary route

### Out of scope

- pure command/result refactor for local login and OIDC session flows
- new auth features, roles, permissions, or policy semantics
- unrelated middleware cleanup
- removal of intentionally frozen compatibility shims that are not touched by this move

### Deliverables

1. A platform-generic policy engine surface that contains no homelab/API route literals.
2. App-owned protected-route declarations wired into API composition.
3. Coverage tests that fail when a protected route lacks role, permission, or scope declarations without assuming platform-owned placement.
4. Narrow cleanup of touched compatibility imports on the moved path.

### Acceptance

- `packages/platform/auth` no longer owns concrete app route strings for the primary authorization declaration path.
- The API app provides protected-route declarations explicitly at composition time.
- Request-aware role, permission, and service-token scope behavior remains unchanged.
- Architecture and auth-policy tests still guarantee no protected endpoint is uncovered.
- No new auth-mode, OIDC, service-token, or permission-model behavior is introduced.

### Verification path

- `pytest tests/test_architecture_contract.py tests/test_auth_permission_registry.py tests/test_api_auth.py -x --tb=short`
- `ruff check <changed-python-files>`
- `mypy <changed-python-files>`
- `make verify-fast` before any PR or CI-triggering push

---

## Implementation Order

Start with `#305`.

1. `#305` should define the extraction seam first. The target is not a second registry or a framework rewrite; it is a generic policy-engine boundary that can accept app-owned declarations cleanly.
2. `#306` should move concrete declarations into the app layer, ideally near route registration or in a clearly app-owned module consumed by registration.
3. `#307` should follow immediately after `#306` so coverage enforcement reflects the new ownership model rather than the old platform table.
4. `#308` is cleanup after the path is moved. Keep it narrow and limited to imports or compatibility scaffolding touched by the new primary path.

---

## Likely Hotspots

- `packages/platform/auth/route_policy_catalog.py`
- `packages/platform/auth/scope_authorization.py`
- `apps/api/auth_runtime.py`
- `apps/api/app.py`
- `apps/api/routes/auth_routes.py`
- `apps/api/routes/auth_session_routes.py`
- `apps/api/routes/control_routes.py`
- `apps/api/routes/report_routes.py`
- `apps/api/routes/run_routes.py`
- `tests/test_architecture_contract.py`
- `tests/test_auth_permission_registry.py`
- `tests/test_api_auth.py`

The exact app-owned destination does not need to be one file, but it must remain obviously app-owned and composition-friendly.

---

## Guardrails For Implementing Agent

- Claim the item in `sprintctl` before repo edits. Use `sprint-resume` or direct claim flow against the live DB; do not infer ownership from this handover alone.
- Preserve current auth behavior. This sprint is a seam correction, not a feature sprint.
- Do not reintroduce path-prefix trees or hidden implicit defaults.
- Do not broaden compatibility cleanup into a general auth-contract migration.
- Keep table-driven coverage strong. If the new design weakens route-coverage guarantees, it is the wrong design.
- Update docs only if the final code changes the documented ownership statement or composition shape materially.

---

## Recommended First Execution Slice

Item `#305` should answer these concrete questions before code spreads:

- What is the smallest generic interface the platform needs for request-aware role, permission, and scope lookup?
- Where should the API app define its declarations so route ownership stays obvious?
- How will auth runtime receive the declaration set without making `apps/api/app.py` branch-heavy again?

The expected answer is a narrow injection/composition seam, not a new abstraction layer.

---

## Files Mutated In This Planning Session

- `docs/sprint-snapshots/sprint-current.txt`
- `.agents/sessions/2026-04-08-harbor-policy-seam-sprint-packet-and-handover.md`

No product code was changed in this session.
