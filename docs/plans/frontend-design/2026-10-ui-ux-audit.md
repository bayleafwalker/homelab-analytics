# UI/UX audit and wave 2–4 delivery notes — October 2026

**Classification:** SURFACE
**Date:** 2026-10-18
**Branch:** `feat/ui-ux-innovation`
**Method:** API (`local_single_user`, SQLite control plane, DuckDB reporting) and Next.js dev server run locally over the seeded demo dataset (`generate-demo-data` + `seed-demo-data`); every main-shell route screenshotted with Playwright at 1440 px and the key routes at 390 px, signed in as the bootstrap admin. Accessibility checked with axe on the live pages and in Storybook.

Reference shots for the shipped work are in `refs/2026-10-ui-ux/`.

---

## 1. Top friction points found (before this branch)

| # | Finding | Where | Severity |
|---|---|---|---|
| 1 | **Navigation took over the first screen.** 13–14 flat nav pills plus Retro / user / Sign out wrapped into three to five rows. At 390 px the whole first viewport was navigation. No grouping, no keyboard way to jump. | `components/app-shell.js` | High |
| 2 | **Orphaned pages.** `/operating-picture`, `/control/freshness`, `/control/lineage`, `/control/confidence` and `/first-answer` had no nav entry (ADR web-surface-shell-decision §3.3 predicted this). | shell | High |
| 3 | **Raw reporting decimals everywhere.** Money rendered as `2474.9800` with no currency mark or grouping on the dashboard, operating picture and recent-changes lists. | `app/page.js`, `operating-picture-view.js` | High |
| 4 | **Dashboard hero read the wrong fields.** It looked for `overview.net` / `income` / `expense`, but the publication returns `cashflow_net` / `cashflow_income` / `cashflow_expense`, so the hero always showed the filler sentence "Dashboard and control-plane visibility from one API surface." and an empty right card. | `app/page.js` | High |
| 5 | **Any backend failure became a bare 500.** No `error.js`, `loading.js` or `not-found.js` anywhere in the app router. | `app/` | High |
| 6 | **Dashboard failed for non-admin roles.** It always called the admin-only `/control/source-freshness`; in `disabled` identity mode (404) and for reader/operator users (403) the whole dashboard errored. | `app/page.js` | High |
| 7 | **Staleness was invisible.** Demo data ends 2025-12; nothing on the dashboard said the figures were ten months old. The operating picture shows freshness pulses but they read "Never" for datasets that were loaded (freshness configs unconfigured), which is noise rather than a signal. | dashboard, operating picture | Medium |
| 8 | **`/control/lineage` and `/control/confidence` redirect to `/login`** in split-origin topologies (API :8080, web :8081) because they are `'use client'` pages doing relative fetches — the ADR §3.3 defect is still present. | control | Medium (`/control/lineage` fixed here; `/control/confidence` left to its owner) |
| 9 | **Sources table shows the same source for every row** (`demo-revolut` three times, one `latest_run_id` for all assets). Looks like the freshness join picks the global latest run rather than the asset's. | `/sources`, `/control/source-freshness` | Medium (backend; not fixed here) |
| 10 | **Sparkline axis labels collide** — twelve month labels in a 400-unit viewBox overprint each other on the operating picture hero. | `components/sparkline-chart.js` | Low |
| 11 | **Horizontal overflow at phone width** on `/` (425 px), `/reports` (467 px) and `/control` (819 px) at a 390 px viewport. The shell no longer contributes; `/reports` and `/control` tables/forms still overflow. | page bodies | Medium |
| 12 | **No visible focus style, no skip link, top-level `aside` inside `main`** (axe `landmark-complementary-is-top-level`, `region`). | shell, dashboard | Medium |
| 13 | **Copy talks about the system, not the household.** "A minimal Next.js shell over the reporting and run APIs. The web workload no longer computes or reads reporting data directly." as the dashboard lede; "Authenticated Control Plane" as the default eyebrow. | shell, dashboard | Low |

## 2. What this branch ships

### Shell (all default-shell pages)
- **Grouped navigation rail** (Today / Money / Home / Data / Admin) from 1080 px; below that a **Menu** button opens it as a sheet (Escape closes). `aria-current="page"` on the active entry; prefix-aware so `/control/catalog` lights Control.
- **One nav registry** `lib/nav-model.js` (ADR §4.2 "one registry, two renderings"): role visibility lives there once; the rail and the palette render it. `tests/test_web_auth.py::test_default_shell_nav_registry_covers_every_top_level_route` fails when a new top-level route ships without an entry or an explicit `NAV_UNLISTED_ROUTES` reason. The retro shell is deliberately untouched (no parity promise).
- **Command palette** (`Ctrl K` / `⌘K` / `/`): native `<dialog>`, combobox + listbox semantics, fuzzy match on label and keywords, options are real links. Includes deep links to the orphaned control pages.
- Skip link, global `:focus-visible` ring, rail as a top-level `header` landmark.
- Nav entry for `/briefing` (Morning brief, Today group); the page lands from `feat/morning-brief`.
- `ControlNav` now lists Freshness, Confidence and Lineage, so the newer control pages are reachable.

### `/control/lineage` repaired
- Rewritten as a server component over `getPublicationLineage` / `getPublicationKeys` in `lib/backend.ts` (ADR §4.3). It previously fetched `/auth/me` and `/api/lineage/...` from the browser and bounced to `/login` whenever web and API were on different origins. Adds a publication picker (datalist of publication keys), an explicit "No lineage recorded yet" state and an error state. The Cashflow Map's provenance panel links each publication into it for admins.
- **Note for CI:** the `app-shell-admin-control.png` baseline now changes by design (the story's `main` no longer contains the nav). Refresh it in CI; it was not regenerated locally (NixOS font rendering). The retro baseline is unaffected by this branch and still shows only the known local font diff.

### State primitives
- `components/state-panel.js` — `<StatePanel tone="empty|stale|error|loading">` + `<SkeletonLines>`; error tone is `role="alert"`, the rest `role="status"`.
- `app/error.js` (route error boundary that names the failing endpoint/status and offers Try again), `app/loading.js`, `app/not-found.js`, `app/retro/loading.js`, `app/wallboard/loading.js`.

### Formatting
- `lib/format.js` — `formatMoney` (two decimals, grouping, ISO currency when known), `formatMonth`, `monthsBetween`. Applied to the dashboard, operating picture view and summary.

### Dashboard fixes
- Hero now reads the real `household-overview` fields: "Kept €2,474.98", income/expense sentence, link into the Cashflow Map; empty state points to Upload.
- Right card replaced with **Data through** + a stale StatePanel when the newest month lags.
- Source freshness fetched only for admins.

### `/cashflow` — Cashflow Map (wave 2, W2-4…W2-6)
- New API `GET /reports/cashflow-map?month=YYYY-MM&include_transfers=bool` (`apps/api/routes/report_routes.py`) composed in `packages/domains/finance/pipelines/cashflow_map.py` **only from published marts** (`mart_monthly_cashflow`, `mart_monthly_cashflow_by_counterparty`, `mart_spend_by_category_monthly`). Four columns: income sources → money in → regular / occasional / kept → payees or categories.
- **Honest modelling, disclosed**: same-month equal in/out pairs are treated as own-account transfers and left out by default (toggle in the URL); payees count as regular when paid in ≥3 of the last 4 months; long tails group into "Everything else (n)" with members listed; overspend shows as "Drawn from savings"; reconciliation gaps against the monthly total are flagged.
- Page: sentence-led hero ("Of €3,200.00 that came in, €725.02 went to spending and €2,474.98 was kept."), plain-SVG Sankey with keyboard-reachable payee links, **drill-down** (`?focus=`) with a six-month bar strip and month-on-month change, "Biggest changes since …" list, stale-data banner, month stepper + select (all state in the URL), and an **"Explain these numbers"** panel: transaction count, newest data month, numbered notes, matched transfer list, the publications read with their lineage-graph size (`/api/lineage/publication/{key}`) and, for admins, each publication's confidence verdict.
- Narrow screens get a stacked flow list instead of the SVG.
- Plan deviation: the plan's W2-4 named `subscriptions`, `contract_prices` and `loan_repayments` joins. Those marts don't share a key with account transactions (recurring baseline names ≠ transaction payees), so joining them would invent matches. The map stays on the transaction marts and leaves "fixed vs flexible" to the regularity rule until a payee↔contract mapping exists.

### `/wallboard` (wave 4, reduced to existing adapters)
- Full-bleed retro-token board, mono only, nothing below 18 px (test-enforced): clock, money this month, next payment countdown, decisions pending (grouped by title), homelab services, utilities, data age + home-bridge state, upcoming-payment ticker.
- Refreshes via `router.refresh()` every 60 s; pauses while hidden or hovered and says so. `?compact=1` drops the homelab/utilities tiles and ticker and enlarges figures.
- Optional adapters (`/api/homelab/services`, `/api/ha/bridge/status`, utility trend) degrade per tile instead of failing the board. W4-1/W4-2/W4-4 (device readings, power series) are **not built**; the board shows nothing for them rather than placeholders.

### Not built: `/console` (wave 3)
The ADR unblocks it, but its centre panel (`getSpendHeatmap`, day-of-week × hour) needs transaction timestamps; `account_transactions` carry booking dates only, so the heatmap would be fiction. Recommend a day-of-week × week-of-year variant (`/reports/spend-heatmap?weeks=12`) over `mart_spend_by_category_monthly`'s parent fact, then build the console on the wallboard's retro tokens.

## 3. Proposals not built

1. **"Explain this number" popovers everywhere.** The Cashflow Map's provenance panel is the prototype. Generalise to a `<Explain publication="…" field="…">` primitive: a disclosure button next to any figure that shows the publication, row filter, lineage graph (`/api/lineage/publication/{key}`) and confidence verdict (`/control/confidence/{key}` for admins). Requires recording lineage on the DuckDB path — today every publication returns a single-node graph, so the panel honestly says "no lineage recorded yet".
2. **As-of timeline scrubbing.** A month scrubber in the shell header (`?asof=YYYY-MM`) that every reporting page honours, reusing the Cashflow Map's stepper. Needs `as_of` parameters on the overview/attention endpoints; the monthly marts already support `to_month`.
3. **Payee → contract mapping** so the map can split "fixed" (subscriptions, loans, contracts) from "regular" spending with real joins instead of the regularity heuristic.
4. **Transfer confirmation.** Let an operator confirm or reject a matched transfer pair; persist as a category override so the heuristic becomes a decision.
5. **Phone-width table strategy.** `/reports` and `/control` still overflow at 390 px; adopt stacked "definition list" rows under 600 px via a shared `<ResponsiveTable>`.
6. **Freshness pulse noise.** Show "not configured" instead of "Never" when a dataset has data but no freshness config.
7. **Fix the remaining defects found** (§1 #8, #9) in their owning sprints: migrate `/control/confidence` to server fetches (ADR §4.3) and make `/control/source-freshness` resolve each asset's own latest run.
8. **Retro rail parity (optional).** `retro-shell.js` could consume `lib/nav-model.js` for its module launcher; left alone per the no-parity rule.

## 4. Wave 3 delivery (`feat/ui-wave-3`)

Reference shots: `refs/2026-10-ui-wave-3/` (demo-seeded local API, local identity mode, axe clean on every captured page).

- **§1 #9 fixed (backend).** `build_source_freshness_views` attributes runs to a source asset through the `source_asset_id` in each run's manifest context, so three accounts on one dataset no longer share a run. `/sources` keys rows by asset and joins the asset's own `latest_run_id`. Regression tests: `tests/test_source_freshness_overview.py`, `tests/test_freshness_remediation_flow.py::test_assets_sharing_a_dataset_report_their_own_latest_run`.
- **§1 #8 fixed.** `/control/confidence` is a server component over `getPublicationConfidence({ staleOnly, verdict })`; filters are URL state.
- **Proposal 1, `<Explain>`.** `components/explain.js` (+ `explain-disclosure.js`, `explain-server.js`, `lib/explain.js`). Adopted on dashboard KPIs, the Cashflow Map sentence and publication list, morning-brief lines (presentation only) and the wallboard money tile. Lineage on the DuckDB path is still a single publication node, and the panel says so.
- **Proposal 2, as-of, within its limits.** The reporting layer has no historical snapshots for `household-overview`, `attention-items`, affordability ratios, the recurring baseline or recent changes, and no `as_of` read, so no API parameter was added. `<AsOfScrubber>` offers only the months the monthly marts hold. On the dashboard (`?asof=YYYY-MM`) it rewinds monthly cashflow, top categories, utilities and the trend, and marks the snapshot-only panels "Today". The Cashflow Map uses it for `?m=`. A real as-of view needs dated snapshots of the overview and attention marts.
- **Proposal 5, `<ResponsiveTable>`.** Under 600 px rows become "label .... value" slips while staying a `<table>`. Applied to `/sources`, `/control/confidence` and the dashboard tables. `/reports`, `/budgets`, `/utilities`, `/control/catalog` and `/control/execution` still use scrolling `.tableWrap` tables and are the next candidates.
- Dashboard "Recent changes" read a non-existent `metric_name`; it now shows `description`, period and formatted values.
