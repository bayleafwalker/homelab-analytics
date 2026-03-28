# Non-Finance Domain Backlog And Sprint Realignment

## Purpose

Realign the non-finance backlog against the actual worktree and live sprint state. Sprint I is effectively complete, while the local worktree already contains domain-foundation code that the older backlog write-up still described as future work.

## Assessment Of The Public-Branch Guidance

The external verdict is directionally correct but stale against the local worktree.

- The warning about surface-area inflation still holds, especially around runtime/config/auth posture and HA wiring density.
- The recommended sequence needs to account for work already landed locally: utility tariff shock, approval-gated HA control, synthetic entity expansion, internal-platform ingestion, utilities automation foundation, infrastructure metrics foundation, and the first asset-inventory spine are no longer hypothetical.
- The main planning problem is now sprint shape, not roadmap direction. Live `sprintctl` still shows an active finance sprint that is complete and a catch-all backlog sprint that mixes delivered work, genuine carryover, and future-stage planning.

## Stop/Go Summary

| Domain | Decision | Worktree status | Main blocker |
|---|---|---|---|
| Utilities automation | Go, mostly landed | Generic HTTP/API pull + freshness posture is already in the worktree; the remaining work is profile-safe provider onboarding and operator UX. | Provider-specific auth posture and golden-path onboarding. |
| Homelab value loop | Go now, but narrow | The homelab pack already owns sources, marts, API routes, web surfaces, and HA publication. The missing piece is value-vs-cost decision support. | Keep it tied to Stage 3/4 decision surfaces, not another foundation rewrite. |
| Overview | Do not add a new domain item now | Overview is still a reporting-only composition pack. Existing Stage 3 items already cover the next cross-domain composition work. | Finance, utilities, and homelab decision signals must mature first. |
| Infrastructure metrics | Go foundation-complete, then stop | `dim_node`, `dim_device`, `fact_cluster_metric`, and `fact_power_consumption` now exist in the worktree. | Add landing/reporting contracts only when the next sprint takes them explicitly. |
| Home automation state | Go foundation-next | Internal HA state landing exists, but there is still no separate canonical home-automation model and reporting starter. | Keep the semantic boundary from homelab operations explicit. |
| Asset inventory | Go foundation-next | The transformation-layer `dim_asset` and `fact_asset_event` spine now exists in the worktree. | Finish the manual register landing contract and choose the first reporting surface. |

## Layer Impact

### Landing

- Utilities automation needs provider/API or download contracts plus Home Assistant energy-sensor contracts while keeping raw payloads immutable.
- Infrastructure metrics need explicit landing contracts for Prometheus and/or Kubernetes metrics plus a clear power-sample source whenever the reporting layer is ready to consume them.
- Home automation state needs explicit HA state/history landing contracts rather than reusing the homelab operational feeds.
- Asset inventory needs a manual register contract that can support CSV upload first and web entry later.

### Transformation

- Utilities can reuse the existing `fact_utility_usage`, `fact_bill`, and `dim_meter` spine; the missing work is source onboarding and normalization breadth.
- Infrastructure metrics already have `dim_node`, `dim_device`, `fact_cluster_metric`, and `fact_power_consumption`; the remaining work is how far the next sprint pushes them toward reporting.
- Home automation state still needs the canonical `dim_entity`, `fact_sensor_reading`, and `fact_automation_event` slice to stand on its own boundary.
- Asset inventory has `dim_asset` plus `fact_asset_event`; the next slice still needs to decide whether depreciation stays in scope or is deferred.

### Reporting And App Surface

- Utilities should continue to publish through reporting marts only; no direct landing-to-dashboard shortcuts.
- Overview should remain a composition layer over reporting outputs from finance, utilities, and homelab.
- Homelab value work should land as reporting marts and then flow into web/HA surfaces through the existing reporting and publication contracts.
- New infrastructure, home-automation, and asset slices should not add app-facing reads until at least one reporting mart exists for each.

## Docs, Requirements, And Tests That Must Move With Later Implementation

- Update `requirements/data-ingestion.md` for any new source connector, landing contract, validation rule, or freshness policy.
- Update `requirements/data-platform.md` for new canonical facts, dimensions, SCD handling, current snapshots, and reporting marts.
- Update `requirements/analytics-and-reporting.md` for new analytical outputs or decision-support views.
- Update `requirements/application-services.md` if new API, web, or HA-facing endpoints ship.
- Keep `docs/plans/additional-data-domains.md` and `docs/plans/household-operating-platform-roadmap.md` aligned if backlog priority or domain ordering changes materially.
- Add or extend tests in the same change: landing-contract validation, transformation-domain coverage, reporting/API coverage, and HA publication tests where applicable.

## Sprint Mapping

The old catch-all backlog should be split into focused sprint packets:

1. `Sprint J — Non-Finance Canonical Foundations`
   Carries the genuine Stage 1 follow-up: remaining canonical dimensions/facts, home automation state foundation, and completion of the asset foundation around a real landing contract and reporting starter.
2. `Sprint K — Household Decision Surfaces`
   Carries the Stage 3 and Stage 4 value work already queued in backlog: cost envelopes, structured state indicators, homelab cost/benefit, scenario comparison, and the homelab value loop.
3. `Sprint L — Runtime Profiles And Operator Onboarding`
   Converts the support matrix into three blessed deployment profiles and makes import/freshness/remediation flows coherent for real operators.
4. `Sprint M — Integration Boundary Hardening`
   Finishes the composition-root and HA wiring cleanup and turns the Stage 6 adapter layer from roadmap text into an implementation-ready boundary.
5. `Sprint H — Auth Migration Completion + Machine Federation`
   Stays as a dedicated Stage 9 backlog sprint rather than being buried in a generic cross-stage bucket.

Do not register a separate overview-domain sprint in this pass because the existing Stage 3 backlog already covers the next cross-domain composition work.
