# ADR: Web Surface Decision — Default Shell Primary, Retro Shell Scoped Secondary

**Classification:** CROSS-CUTTING
**Status:** Accepted
**Owner:** Sprint 357 (`choose-web-surface`)
**Decision type:** Product surface direction / frontend navigation architecture
**Applies to:** `apps/web/frontend/app/` (default shell), `apps/web/frontend/app/retro/` (retro shell), `apps/web/frontend/lib/renderer-discovery.ts`, `apps/web/frontend/components/app-shell.js`, `apps/web/frontend/components/retro-shell.js`

---

## 1. Executive summary

Two parallel Next.js shells have existed side by side since the retro slice shipped: the **default shell** (`app/`) and the **retro shell** (`app/retro/`). `docs/product/retro-crt-shell.md` named this decision gate up front and asked for one of three outcomes: retro becomes primary, retro stays experimental, or retro is harvested for components and retired.

**Decision:**

- **The default shell remains the primary, canonical operator surface.** It is not being retired, and no new product workflow may launch retro-only.
- **The retro shell continues as an explicitly-scoped, secondary "operator cockpit" renderer.** It is not promoted to primary, and it is not slated for harvest-and-delete. It keeps its `/retro` route tree, its own visual language, and its narrower module scope (Overview, Money, Utilities, Operations, Control, Terminal).
- **Retro carries no parity promise.** New publication-backed pages and new operator workflows land in the default shell first. Porting a feature into retro is optional, deliberate, follow-up work — never a blocking requirement of shipping the feature.
- **A single canonical navigation/data model is defined below (Section 4)** so that publication-backed pages stop diverging between shells, satisfying item #717.

This is the first of the three named outcomes in `docs/product/retro-crt-shell.md` ("keep `/retro` as an explicitly experimental operator renderer with no parity promise"), chosen over that document's own stated default recommendation (harvest-then-retire) because hands-on inspection did not support retiring it. See Section 3.

---

## 2. Context

`docs/product/retro-crt-shell.md` shipped the retro shell as a route-scoped parallel renderer over the same reporting/control-plane APIs, explicitly gated: *"The retro shell is not a second permanent product surface by default... The next web-surface decision pass should choose one of three outcomes."* Downstream backlog sprint **#362 (`console-grid-rise`)** is explicitly blocked on this decision being documented.

This ADR closes sprint **#357 (`choose-web-surface`)**, items **#716** (name the outcome) and **#717** (define the canonical navigation model).

The decision below is grounded in running both shells locally against the same seeded demo dataset (`make demo-generate` / `make demo-seed` equivalent, `local_single_user` identity mode, admin session) and visually inspecting every top-level route in both shells, rather than inferring from source alone.

---

## 3. What was actually observed

### 3.1 Route coverage

| Capability | Default shell (`app/`) | Retro shell (`app/retro/`) |
|---|---|---|
| Dashboard / overview | `/` | `/retro` |
| Finance reporting | `/reports`, `/budgets`, `/loans`, `/costs`, `/scenarios` (5 routes) | `/retro/money` (1 route, consolidated) |
| Utilities | `/utilities` | `/retro/utilities` |
| Homelab / HA operations | `/homelab` | `/retro/operations` |
| First-run / onboarding | `/onboarding` | — none |
| Source freshness & remediation | `/sources` | — none |
| File upload | `/upload` | — none |
| Run inspection | `/runs` | — none |
| Ingestion review | `/review` | — none |
| Interactive what-if scenarios | `IncomeScenarioPanel`, `ExpenseShockPanel` (`/reports`), `LoanWhatIfPanel` (`/loans`), `TariffShockPanel` (`/costs`), `HomelabCostBenefitPanel` (`/homelab`), `ArchiveScenarioButton` (`/scenarios`) | — none |
| Admin control plane | `/control`, `/control/catalog(+7 subpaths)`, `/control/execution(+4 subpaths)`, `/control/confidence`, `/control/freshness`, `/control/lineage`, `/control/users`, `/control/service-tokens` | `/retro/control`, `/retro/control/catalog`, `/retro/control/execution(+2 subpaths)` |
| Audited terminal command entry | documented read-only reference table only (`/control`) | interactive `/retro/terminal` |
| Storybook coverage | 4 of 5 top-level component stories | 1 of 5 (`retro-shell.stories.jsx`) |

The retro shell has **zero** equivalent for the entire first-contact/remediation lifecycle (onboarding → upload → sources → runs → review) and **zero** equivalent for any interactive what-if scenario tooling. Both are core, currently-shipping operator workflows (see `docs/runbooks/operator-walkthrough.md`, `docs/product/scenarios-and-what-if.md`) that exist only in the default shell.

### 3.2 Quality of what retro does cover

This was not a rubber-stamp of the doc's pre-existing lean toward harvesting. Running the retro shell showed a **complete, polished, non-throwaway renderer** for its declared scope:

- `/retro` renders a single dense operating-picture screen (module launcher cards, trend chart, attention queue, run feed, recurring baseline, recent changes) pulling the same real marts as the default dashboard, not mock data.
- `/retro/money` consolidates cashflow, balance trend, affordability ratios, spend-by-category, subscriptions, and recurring baseline into one page, and includes explicit "Classic route" cross-links back into the default shell's discovery views (Anomalies, Large Transactions, Upcoming Costs) for the drill-downs it doesn't reimplement — i.e. it was built to compose with the default shell, not replace it.
- `/retro/control` folds identity management, service tokens, and a recent-auth-events audit feed into one screen, and links out to a "Classic editor."
- Both shells cross-link to each other (`Retro` button in the default header, `Classic` button in the retro header), confirming this was designed as a genuine parallel renderer, not an abandoned spike.

**This is why the decision is not "harvest and retire."** Deleting a shell this complete, after real engineering investment, to reproduce its single-screen density inside the default shell's card-stack layout would be net-negative. It is also why the decision is not "promote to primary": retro has no onboarding, upload, source remediation, run inspection, review, or what-if tooling, and building all of that from scratch inside retro before it could safely become the sole surface is out of proportion to the problem the decision gate was meant to solve.

### 3.3 A live example of the divergence risk item #717 exists to prevent

While exercising every route, `/control/confidence` (shipped by the concurrent confidence-canvas-glow sprint) was found to silently redirect to `/login` when the web origin and API origin are not the same host (the default local/dev topology, and the same topology the `single-user homelab` Compose story uses — API on `:8080`, web on `:8081`, no shared reverse proxy). Root cause: unlike every other page in both shells, `app/control/confidence/page.js` is a `'use client'` component that fetches `/auth/me` and `/api/control/confidence` as same-origin relative browser fetches instead of going through the shared server-side `lib/backend.ts` helper (which every other page — in both shells — uses, and which correctly resolves `HOMELAB_ANALYTICS_API_BASE_URL`). The result: `meResponse.ok` is `false`, and the page's own logic calls `router.push('/login')`.

Additionally, **no navigation in either shell links to `/control/confidence`, `/control/freshness`, or `/control/lineage` at all** — `components/control-nav.js` still only lists `Security / Catalog / Execution`, so these three newer, real, publication-backed pages are only reachable by typing the URL directly, in the default shell that is supposed to be the canonical surface.

This bug is in the scope of the confidence-canvas-glow sprint and is intentionally **not fixed by this ADR or this sprint** — it is flagged here, and should be routed to that sprint's owner, purely as concrete, current evidence for why Section 4 is needed: without one shared navigation/data-fetching contract, new publication-backed pages will keep landing disconnected from the nav and from the API in inconsistent ways, in either shell.

(Separately, and unrelated to shell scope: `apps/web/frontend/app/sources/page.js` had a pre-existing JSX syntax error — a ternary at line 248 missing its `: null` branch — that broke `next build`/`next dev` compilation for `/sources` and cascaded into 500s on every route after it in the dev server. That was a trivial, pre-existing defect blocking the ability to run either shell at all, unrelated to sprint #395's scope, and was fixed as a one-line correction in this same change; see the commit for this ADR.)

---

## 4. Canonical operator navigation model (item #717)

### 4.1 Current state (why it diverges)

Today there are **three uncoordinated navigation mechanisms**:

1. `components/app-shell.js` — a hand-written `navItemsForUser(user)` array for the default shell's top nav.
2. `components/retro-shell.js` — a separate, independently hand-written `navItemsForUser(user)` array for the retro shell's top nav.
3. `lib/renderer-discovery.ts` — a backend-driven discovery layer (`getWebRendererDiscovery()`) that both shells already call for **secondary**, in-page discovery links, grouped by `renderer_hints.web_nav_group` and keyed to a hardcoded `WEB_RENDERER_SURFACES` map that only recognizes three buckets: `overview` (`/`), `reports` (`/reports`), `homelab` (`/homelab`). Every other top-level route (`/budgets`, `/loans`, `/costs`, `/scenarios`, `/utilities`, `/control`, `/sources`, `/upload`, `/onboarding`, `/runs`, `/review`, and all of `/retro/*`) is invisible to this layer.

Mechanisms 1 and 2 must be hand-edited in lockstep for every new top-level route or every role-visibility change; mechanism 3 is the only one actually backend-driven, but covers a fifth of the surface. This is the direct cause of the orphaned-route problem in Section 3.3.

### 4.2 The rule going forward

**One registry, two renderings.** There is exactly one canonical navigation model per operator, expressed as a single ordered list of nav entries. Each shell's shell component renders that same list; it does not maintain its own.

An entry is one of two kinds:

- **Publication-backed entry** — derived automatically from backend-owned `renderer_hints` (`web_surface`, `web_nav_group`, `web_anchor`, `web_render_mode`) on published `UiDescriptor`/`PublicationDefinition` records, exactly as `lib/renderer-discovery.ts` already does for its three buckets today. Extending this requires widening `WEB_RENDERER_SURFACES` (or replacing it with a surface registry driven off `renderer_hints.web_surface` values already present in the backend, rather than a hardcoded three-item map) to cover every top-level route that is backed by a publication.
- **Shell-owned entry** — explicitly declared (not discovered) for admin/operational surfaces that are not publication-backed: Control, Terminal, Onboarding, Upload, Sources, Runs, Review. These are first-class registry entries flagged `shellOwned: true` so they render in nav without pretending to be publication-discovered, matching the existing distinction `docs/product/retro-crt-shell.md` already draws for `Control`/`Terminal`.

Role visibility (`reader` / `operator` / `admin`) is a property of the registry entry, evaluated once, not duplicated per shell.

Each shell may still choose **how** to lay out or group these entries (default: flat top nav; retro: module-card launcher grouped by `web_nav_group`) — presentation is allowed to diverge, the **set of what exists and where it points is not**.

### 4.3 The rule for data fetching

Every publication-backed page, in either shell, fetches through the existing shared `lib/backend.ts` server-side helper set (`getCurrentUser()`, `get<Publication>()`, etc.), which resolves the real API base URL. A page must not issue same-origin relative `fetch()` calls from a `'use client'` component for data that a server component could fetch instead. If a page genuinely needs client-side interactivity (polling, filters without full navigation), it fetches through a thin client wrapper around the same resolved API base URL — never a bare relative path. `/control/confidence` (Section 3.3) is the counter-example this rule exists to prevent from recurring.

### 4.4 Enforcement going forward (recommended, not implemented in this change)

This ADR defines the model; it does not implement the `app-shell.js`/`retro-shell.js` refactor onto a shared registry, and does not fix `/control/confidence`. Both are real, scoped follow-up work that should land as their own sprint items (natural candidates: a `web-nav-registry` item consuming this ADR, filed against whichever sprint owns frontend platform work next, and a fix for `/control/confidence` filed against confidence-canvas-glow or its successor). Recommended acceptance for that follow-up work:

- a single `lib/nav-model.ts` (or equivalent) is the only place `navItemsForUser`-shaped logic exists; `app-shell.js` and `retro-shell.js` import from it instead of defining their own arrays
- `WEB_RENDERER_SURFACES` (or its replacement) covers every top-level route, not three
- an architecture-contract-style test asserts every route directory under `app/` and `app/retro/` (excluding a small, explicit legacy allowlist) has a corresponding nav-registry entry, so a new page without a nav entry fails CI instead of shipping orphaned
- `/control/confidence` is migrated to the server-fetch convention in Section 4.3

---

## 5. Consequences

- Sprint **#362 (`console-grid-rise`)** is unblocked: it may proceed building `/console` using retro design tokens, understanding that `/console` is additive to the retro-scoped surface set, not a promotion of retro to primary, and that it should register itself in the nav model per Section 4.2 once that registry exists (or, in the interim, be added explicitly to both shells' current hand-written arrays with a follow-up TODO referencing this ADR).
- No existing route in either shell is removed or frozen by this decision.
- Future publication-backed admin pages (the pattern `/control/confidence`, `/control/freshness`, `/control/lineage` just followed) must not ship without a nav entry and without using the shared server-fetch convention; reviewers should check both against Section 4 before approving.
- Retro remains free to keep or drop its own routes without needing default-shell sign-off, and the default shell remains free to ship new workflows without needing a retro equivalent.

---

## 6. Alternatives considered

- **Promote retro to primary, retire default-shell paths.** Rejected: retro has no onboarding/upload/sources/runs/review lifecycle and no what-if scenario tooling; rebuilding those inside retro before cutover would be a multi-sprint effort disproportionate to the problem, and would regress the first-week operator experience that `docs/runbooks/operator-walkthrough.md` depends on today.
- **Harvest useful retro patterns into the default shell, then freeze/remove `/retro`.** This was the doc's own stated default recommendation. Rejected on hands-on inspection: retro is a complete, cross-linked, real-data renderer for its declared scope, not a prototype whose only value is a few extractable components; deleting it would discard working product surface for no operator-facing benefit, and its dense single-screen module-card layout is a genuinely different (not strictly worse) answer to "operator cockpit" than the default shell's stacked-card layout.
- **Do nothing / leave the decision open.** Rejected: sprint #362 is explicitly blocked on this decision being documented, and the orphaned-route problem in Section 3.3 is actively recurring.
