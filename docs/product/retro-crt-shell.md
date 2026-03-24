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
