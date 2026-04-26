# Retro CRT Shell

## Why this slice exists

The default web shell remains the primary product surface. The retro shell is a parallel `/retro` renderer that answers a narrower product question: can the same reporting and control-plane APIs support a denser, more operator-oriented experience without creating a second stack or bypassing the reporting layer?

## User questions

The first retro slice is designed to answer these questions quickly:

- What is the current household and homelab operating picture?
- Which launcher module should I enter next?
- Are queue, freshness, workers, and recent runs healthy?
- If I am an admin, can I reach core control views and a minimal command surface without leaving the themed shell?

## Launcher modules

The retro shell groups renderer-published views and shell-owned admin surfaces into these modules:

- `Overview`
- `Money`
- `Utilities`
- `Operations`
- `Control`
- `Terminal`

`Control` and `Terminal` are shell-owned modules. They are not publication-backed views and therefore are not discovered from publication descriptors.

The current route layout is:

- `/retro` for the operating-picture overview
- `/retro/money` for finance-report detail
- `/retro/utilities` for utility-report detail
- `/retro/operations` for homelab and HA operational detail
- `/retro/control/*` for admin control surfaces
- `/retro/terminal` for the audited command entry

Renderer-discovered launcher links for `Money`, `Utilities`, and `Operations` deep-link into anchored sections on those retro detail routes instead of bouncing back to the classic shell.

## Terminal scope and non-goals

The retro terminal is intentionally minimal:

- synchronous request/response execution only
- allowlisted commands only
- read-only diagnostics now include run, dispatch, schedule, heartbeat, freshness, token, auth-audit, publication-audit, user, lineage, source-system, source-asset, ingestion-definition, and publication-definition inspection
- one audited mutating command remains in scope: `enqueue-due [limit]`
- no subprocess shell access
- no arbitrary worker CLI arguments
- no file-path arguments
- no import/export commands
- no streaming or persistent session model

## Rollout choice

The feature ships as a route-scoped parallel shell under `/retro`.

This keeps rollout risk low:

- existing `/`, `/reports`, `/control`, and related routes remain unchanged
- the retro shell can iterate on visual language and information density without destabilizing the default UI
- renderer grouping remains backend-owned through `renderer_hints.web_nav_group`

## Decision gate

The retro shell is not a second permanent product surface by default. It remains an experimental alternate renderer until the first-source and first-broken-run operator loops are stable in the default shell.

The next web-surface decision pass should choose one of three outcomes:

- keep `/retro` as an explicitly experimental operator renderer with no parity promise
- promote the retro shell to the primary operator surface and retire duplicate default-shell paths
- harvest useful dense components and interaction patterns into the default shell, then freeze or remove the parallel route set

The default recommendation is to harvest useful retro patterns into the canonical shell unless a deliberate product decision makes "operator cockpit" the primary identity. Maintaining both shells as full peers is out of scope.

Decision inputs:

- publication-backed Money, Utilities, and Operations pages render the same semantic outputs in both shells
- control and terminal routes do not introduce a second privileged admin path
- first-source onboarding and run remediation are coherent in the default shell
- accessibility and test coverage cost is understood for every route kept as product-supported

Until this decision is made, new retro work should be limited to bug fixes, contract parity, and small evidence-gathering changes. New product workflows should land in the default shell first.
