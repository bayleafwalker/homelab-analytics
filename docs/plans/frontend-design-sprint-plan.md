# Frontend design — backlog sprint plan

**Source material:** `docs/plans/frontend-design/` (concepts C1–C5, shared groundwork, implementation prompts)  
**Date:** 2026-04-25  
**Classification:** SURFACE

---

## 1. Design review summary

Five concepts are defined in the design canvas. Three are refinements or lightweight new surfaces inside the existing default shell. Two carry significant new backend dependencies.

| # | Concept | Target | Risk posture | Backend lift |
|---|---|---|---|---|
| C1 | Operating Picture v2 | Refactor `operating-picture/page.js` | Low — existing route, no new surface | None; reuses existing data fetches |
| C2 | Ops Console | New route `/console` | Medium — new route using retro tokens; depends on web-surface decision | New endpoint: `getSpendHeatmap(window)` |
| C3 | Morning Briefing | New route `/briefing` + `/briefing.json` | Low — editorial/server-rendered, doubles as worker email source | None beyond server-side lede assembly |
| C4 | Cashflow Map | New route `/cashflow` | Low-medium — new SVG component, new API join | New endpoint: `getCashflowSankey(month)` joins 4 tables |
| C5 | Homelab Wallboard | New route `/wallboard` (TV/kiosk) | High — needs 4 new HA-bridge adapters; MQTT device readings | `getServiceHealth`, `getDeviceReadings`, `getEventFeed`, `getPowerSeries` |

**Shared groundwork:** Design tokens, four shared primitive components, motion rules, and Storybook story baseline. Prerequisite for all five concepts.

---

## 2. Positioning against the existing sprint pipeline

The backlog refinement doc (`docs/plans/2026-04-backlog-refinement.md`) places surface work after semantic-seam and product-loop hardening. That sequencing is right for infrastructure surfaces. These concepts are different: they are well-scoped presentation work against an API layer that already exists, and the design canvas represents a completed design decision pass that the `surface-glass-bridge` sprint was holding space for.

**The `surface-glass-bridge` sprint already includes the web-surface decision gate** (default shell versus `/retro`). These frontend concepts are the implementation work that follows from that decision. They should be registered as a backlog track that begins after `surface-glass-bridge` closes, or in parallel with it if the decision gate resolves early.

**What does not change:** the sequencing rule that semantic seam work (`semantic-seam-forge`, `transform-dispatch-forge`) and product loop work (`pack-loop-harbor`) should not be blocked waiting for surface polish. These frontend sprints are a parallel track, not a gate.

**One firm prerequisite:** The web-surface decision from `surface-glass-bridge` must be documented before any work in the C2 (Ops Console) sprint starts. The console uses retro design tokens and is explicitly positioned as a denser sibling to the retro shell. If the web-surface decision retires `/retro` or changes its token ownership, the console concept needs to be revisited. C1, C3, C4, and the shared groundwork sprint do not carry this dependency.

---

## 3. Guardrails

These constraints must hold across all four sprints:

- All new routes land in `apps/web/frontend/app/` (default Next.js shell), not under `/retro`.
- No new renderer lane. The Ops Console and Wallboard share retro CSS tokens but are not `/retro` routes.
- No new state library. Pages stay server-rendered or use existing SWR patterns for polling (wallboard). Do not introduce Redux, Zustand, or Jotai.
- No shortcut reads past the reporting layer. New data shapes that require joins (Sankey, heatmap) must be computed behind an API endpoint, not assembled in the page component.
- Shared primitives in Wave 1 (`<Pill>`, `<Spark>`, `<NumMono>`, `<Eyebrow>`) replace ad-hoc one-off styled spans across existing pages. Do not create new parallel primitives in later sprints.
- Storybook stories are part of each sprint, not deferred. The delivery playbook (`docs/product/frontend-ui-delivery-playbook.md`) requires a story per new component before review.

---

## 4. Sprint wave 1 — `shell-token-pulse`

**Objective:** Land the shared design groundwork and refine the existing Operating Picture without adding any new routes.

**Rationale:** C1 is the lowest-risk concept (existing page, no new surface). Doing it first with the shared primitives in the same sprint means every subsequent concept inherits working, tested building blocks rather than layering on fresh ones.

**Dependencies:** None. Does not require the web-surface decision.

### Items

| # | Item | Stratum | Size | Notes |
|---|---|---|---|---|
| W1-1 | Add `--font-display`, `--line-strong` tokens and document 6-step type scale in `ui-tokens.css` | Surfaces | XS | Fraunces or Iowan; must sit alongside existing sans/mono pair without displacing them |
| W1-2 | `<Pill tone>` primitive — replaces ad-hoc `.statusPill` chains across existing pages | Surfaces | S | Tones: neutral, ok, warn, cool, accent, warm; accepts children and optional style override |
| W1-3 | `<Spark values>` — lightweight wrapper around existing `SparklineChart` | Surfaces | XS | No new chart logic; thin adapter with sensible defaults |
| W1-4 | `<NumMono>` and `<Eyebrow color>` primitives | Surfaces | XS | NumMono: tabular-nums span; Eyebrow: small-caps line with color prop |
| W1-5 | Motion standard — 120ms ease on color/border/transform; `prefers-reduced-motion` guard in globals | Surfaces | XS | One place, one rule; wallboard cursor blink is the only timed animation |
| W1-6 | Operating Picture v2 layout refactor (`operating-picture/page.js`) | Surfaces | M | Hero → single big-number net + sparkline; freshness pulse cards (5 domains); 7-day horizon strip; attention queue as numbered list; ratios + categories to right rail |
| W1-7 | `<FreshnessPulse>` and `<HorizonStrip>` components extracted from v2 page | Surfaces | S | Extracted after the page layout is stable, not speculatively ahead of it |
| W1-8 | Storybook stories: Pill, Spark, NumMono, Eyebrow, FreshnessPulse, HorizonStrip, operating-picture page snapshot | Surfaces | S | Use existing `app-shell.stories.jsx` as template |

**Acceptance criteria:**
- All existing operating-picture data fetches in `Promise.all` remain unchanged.
- No new state library imported.
- Freshness is rendered in exactly one place (pulse cards, not also a table).
- `make verify-fast` passes.
- Storybook builds without errors.

---

## 5. Sprint wave 2 — `brief-flow-mark`

**Objective:** Ship two data-driven surfaces — the Morning Briefing (editorial, email-ready) and the Cashflow Map (Sankey) — as new routes that extend the default shell without changing its navigation model.

**Rationale:** C3 and C4 are the two "pure data + presentation" concepts with no retro-token entanglement and no heavy HA-bridge lift. Doing them together keeps the sprint coherent: both require a new API endpoint and a new page-level component, and both exercise the shared primitives from Wave 1.

**Dependencies:** Wave 1 complete (shared primitives needed). No web-surface decision dependency.

### Items

| # | Item | Stratum | Size | Notes |
|---|---|---|---|---|
| W2-1 | Server-side lede assembly — generate headline and body from cashflow + utility + recurring data | Semantic engine | S | Server component function, not a separate service; three branches: net-positive-streak, net-negative, flat |
| W2-2 | `/briefing` route — Briefing server component (masthead, lede, by-the-numbers rail, chart-of-week SVG, 3-column footer) | Surfaces | M | Two horizontal rules only; serif for display, Inter for body; max 52ch |
| W2-3 | `/briefing.json` alternate response — same content as typed object for worker email digest | Surfaces | S | Structured as a typed response object; worker can consume without HTML parsing |
| W2-4 | `getCashflowSankey(month)` API endpoint — join `account_transactions`, `subscriptions`, `contract_prices`, `loan_repayments` into 3-layer node/link graph | Product packs | M | Returns `{ nodes, links }` per the specified data shape; supports `?m=YYYY-MM`; month picker persists to URL |
| W2-5 | `<CashflowSankey>` SVG component — plain SVG bezier links, node labels, source-color fills at 0.32 opacity | Surfaces | M | No D3; layout computed from node cumulative share; bezier formula from implementation prompts |
| W2-6 | `/cashflow` route — Sankey + month picker + 4 KPI cards (fixed, discretionary, saved, buffer), derived client-side from nodes | Surfaces | S | KPI cards use `<NumMono>` and `<Pill>` from Wave 1 |
| W2-7 | Storybook stories: Briefing page snapshot, CashflowSankey (3 data fixtures), KPI card | Surfaces | S | |

**Acceptance criteria:**
- `/briefing` renders correctly with zero client-side JS state (server component).
- `/briefing.json` returns a valid typed object the worker can consume; no HTML escaping leaks.
- `getCashflowSankey` joins across all four tables; returns empty links gracefully for months with no data.
- Month picker state lives in the URL (`?m=`), not component state.
- `make verify-fast` passes.

---

## 6. Sprint wave 3 — `console-grid-rise`

**Objective:** Build the Ops Console — a single-screen, no-scroll power-user view using retro tokens — as a new `/console` route in the default shell.

**Dependencies:**
- Wave 1 complete (shared primitives).
- **Web-surface decision documented** (from `surface-glass-bridge`). The console uses retro-family tokens and is positioned as a denser sibling to the retro shell. If that decision retires or restructures the retro token set, this sprint's visual language needs to be confirmed before starting.

**Note:** If the web-surface decision is delayed, Waves 1 and 2 can proceed independently. This sprint should not block on Waves 1/2 being done, only on the decision gate.

### Items

| # | Item | Stratum | Size | Notes |
|---|---|---|---|---|
| W3-1 | `<ConsoleShell>` — CSS Grid layout `3×2`, 10px gap; panel header row; mirrors RetroShell structure but is not a subcomponent of it | Surfaces | M | `grid-template-columns: 1.1fr 1.4fr 1fr`; `grid-template-rows: 1fr 1fr`; no CRT vignette on bar charts |
| W3-2 | `getSpendHeatmap(window)` endpoint — aggregate `account_transactions.amount` by day-of-week × hour for last N days | Product packs | M | Returns 7×24 matrix; `window` defaults to 28; must handle sparse data gracefully |
| W3-3 | `<HeatGrid>` component — 7 rows (DOW) × 24 cols (hour); cell intensity mapped to spend sum | Surfaces | M | Colors: retro ok/warn/accent/muted only; no decorative hues |
| W3-4 | Six panels wired to data: cashflow ticker, spend heatmap, attention list, runs tail, category bars + ratios, command stub | Surfaces | M | Command stub: read-only scrollback of recent `assistant_confidence` calls; bottom-line cursor blink |
| W3-5 | Keyboard map: F1–F5 focus panels via `data-panel-id`; ⌘K focuses command stub; a11y: map documented in panel header | Surfaces | S | |
| W3-6 | Storybook stories: ConsoleShell (layout), HeatGrid (full/sparse), panel compositions | Surfaces | S | |

**Acceptance criteria:**
- Console fits on one screen at 1440×900 without scrolling.
- All colors are from `var(--retro-*)` set; no new font imports.
- Numbers right-aligned, tabular-nums, no thousands separators inside panels.
- Keyboard map rendered inside the command stub panel header, not as a tooltip.
- `make verify-fast` passes.

---

## 7. Sprint wave 4 — `board-watch-wire`

**Objective:** Build the Homelab Wallboard — an always-on kiosk-mode status board reading from the HA bridge — as a new `/wallboard` route.

**Rationale:** This is the most backend-intensive concept. It requires four new adapters through the HA bridge. Doing it last means the shared primitives and retro tokens are stable, and the team has already integrated one retro-adjacent route (console).

**Dependencies:** Wave 1 complete. Wave 3 recommended but not strictly required (token set is stable by then). HA bridge test coverage (`test_ha_bridge*`) must pass before starting adapter work.

### Items

| # | Item | Stratum | Size | Notes |
|---|---|---|---|---|
| W4-1 | `getServiceHealth()` adapter — returns name, host, status, uptime, cpu, mem per service | Surfaces | M | Wire to existing HA bridge; `test_ha_bridge*` as integration reference |
| W4-2 | `getDeviceReadings()` adapter — per-room temperature, humidity, instantaneous power via HA MQTT publisher | Surfaces | M | MQTT path; confirm publisher topic shape before implementation |
| W4-3 | `getEventFeed(since)` endpoint — merge ingestion runs + HA action proposals + alerts into a single timeline | Product packs | S | `since` default: 12h; return newest-first |
| W4-4 | `getPowerSeries(window)` endpoint — 24 buckets of kWh for the last N hours | Product packs | S | `window` default: 24h; align bucket boundaries to UTC hours |
| W4-5 | `/wallboard` route + CSS Grid layout: `[services 1.4fr] [event-feed 1fr]` / `[devices 1fr] [power-24h 1fr]` / `[ticker full-width]` | Surfaces | M | Minimum 14px; numbers 18px+; status text 24px+ |
| W4-6 | Auto-refresh (30s interval); pause when `document.hasFocus()` is false; freeze on hover | Surfaces | S | SWR or simple `setInterval`; no streaming |
| W4-7 | `?compact=1` mode — hide event feed, double device tile font sizes, drop ticker hotkey hint | Surfaces | S | URL-only; no local storage |
| W4-8 | Scanlines + vignette pseudo-element on `body`; cursor blink only timed animation; `prefers-reduced-motion` guard | Surfaces | S | Identical approach to `retroRoot::before` |
| W4-9 | Storybook stories: ServiceTile, DevicePanel, EventFeed, PowerChart, Wallboard page snapshot (compact + standard) | Surfaces | S | |

**Acceptance criteria:**
- Wallboard is readable at 1080p from 3 metres (minimum font size enforced, not just specified).
- No serif type anywhere in the wallboard; mono only.
- Auto-refresh pauses when tab is not focused and on hover.
- `?compact=1` drops event feed and ticker, doubles device tile sizes.
- `getDeviceReadings` gracefully returns empty rooms when MQTT data is unavailable.
- `make verify-fast` passes.

---

## 8. Parked from these concepts

### `/briefing` as the primary daily entry point (replacing operating picture)

**Why parked:** The briefing is an editorial surface, not an operator control surface. Promoting it to primary entry would change the navigation model, which requires a separate product decision outside this sprint track.

**Trigger:** Post `surface-glass-bridge` navigation model decision.

### Worker email digest integration (C3)

**Why parked:** The `/briefing.json` endpoint (W2-3) provides the data contract the worker needs. Actually wiring the worker's email dispatch to that endpoint depends on email infrastructure (SMTP config, scheduling, worker task shape) that is not scoped here.

**Trigger:** Once a worker-side email task exists; wire to `/briefing.json` as a one-sprint follow-on.

### Ops Console promoted to a launcher module in the default shell nav

**Why parked:** The console is a new route but is not registered in the default shell navigation model. Adding it to the primary nav requires the web-surface decision to have resolved what the canonical nav model is.

**Trigger:** Post web-surface decision nav model update.

### `getDeviceReadings` via direct MQTT subscription (non-HA path)

**Why parked:** The design calls for HA MQTT publisher as the device data path. A direct MQTT subscription from the API layer would bypass the HA bridge contract and create a second connectors path. If the HA bridge is insufficient, that is an infrastructure decision, not a wallboard sprint decision.

**Trigger:** If HA bridge device coverage proves insufficient after Wave 4 integration testing.

---

## 9. Sprint ordering relative to existing pipeline

| Position | Sprint | Note |
|---|---|---|
| Active | `policy-registry-boundary` (#72) | Ongoing |
| Next | `keel-ledger-bond` | Kernel posture — not affected by this track |
| Following | `semantic-seam-forge` | Semantic seam — not affected by this track |
| Parallel or following | **`shell-token-pulse`** (Wave 1) | Can start once `surface-glass-bridge` design decision is documented; no kernel dependency |
| Following Wave 1 | **`brief-flow-mark`** (Wave 2) | — |
| After web-surface decision | **`console-grid-rise`** (Wave 3) | Gate on `surface-glass-bridge` web-surface decision only |
| After Wave 3 (or Wave 2) | **`board-watch-wire`** (Wave 4) | Most backend lift; do last |

`transform-dispatch-forge`, `pack-loop-harbor`, `contract-compat-extract`, and `surface-glass-bridge` from the existing pipeline are independent of this track and should not be delayed for it.
