# ADR: Household Operating Platform Direction

**Status:** Accepted
**Owner:** Juha
**Decision type:** Product direction / identity evolution
**Applies to:** All platform, domain, product, and roadmap documentation

---

## 1. Executive summary

This project evolves from a **household analytics platform** into a **household operating platform**.

The distinction is deliberate. An analytics platform observes and reports. An operating platform additionally supports planning, control, simulation, policy enforcement, and eventually agentic assistance — capabilities that turn a descriptive household picture into a managerial one.

This ADR locks the direction and vocabulary. It does not commit the project to implementing all stages simultaneously.

---

## 2. Context

The platform already has a working foundation:

- three domain capability packs (finance, utilities, cross-domain overview)
- eighteen publications across cash flow, subscriptions, contracts, electricity, and utilities
- a full data pipeline from landing through transformation to reporting
- config-driven source onboarding for CSV, XLSX, JSON, and HTTP sources
- authentication (local, OIDC, scoped service tokens) with role separation
- Docker Compose and Helm/Kubernetes deployment paths
- an accepted platform ADR defining a modular monolith with hard internal contracts
- a product scope document defining the Household Operating Picture

What is missing is a coherent articulation of where the platform goes beyond visibility. The README still frames the project as a bootstrap-era analytics platform. The requirements baseline still uses phase names (Bootstrap, Foundation, Generalization, Household packs, Productization) that undersell the intended trajectory. The architecture document covers landing, transformation, and reporting but stops before the capabilities needed for planning, simulation, automation, or multi-renderer delivery.

This ADR provides the missing forward trajectory.

---

## 3. Relationship to existing decisions

This ADR **extends** the following accepted documents. It does not replace or override them.

### Platform ADR

`docs/decisions/household-platform-adr-and-refactor-blueprint.md` established:

- the modular monolith with hard internal contracts
- the 5-layer architecture (platform core, application, domain capability packs, adapters, apps)
- capability pack registration, boundary enforcement, and import direction rules
- the publication contract model

All of these remain unchanged. The operating-platform direction is a trajectory built on top of that structural foundation.

### Product scope document

`docs/product/core-household-operating-picture.md` established:

- the Household Operating Picture as the first product goal
- four core views (Overview, Money, Utilities, Operations)
- product principles, acceptance criteria, and the litmus test for future work

This document becomes the specification for Stage 2 of the broader roadmap. It is not superseded.

### Product design workflow

`docs/product/README.md` and `docs/product/core-product-design-workflow.md` established:

- the separation between architecture decisions and product decisions
- the requirement that new work must point to a product question

This workflow remains the intake process for new capability slices.

---

## 4. Relationship to Home Assistant

Home Assistant is the intended edge runtime, device integration hub, family-facing operational UI, and primary actuation surface for this platform. It is not a competing system and not a fallback integration target — it is a first-class partner layer that the platform is designed to work alongside.

This project is not a Home Assistant add-on or custom integration. The distinction matters:

**What Home Assistant does well and should continue to own**: device and protocol integration, real-time entity state, local automations, family dashboards, voice pipelines, notification delivery, and in-day energy visualization.

**What this platform provides that a HA add-on cannot**: canonical cross-domain household semantics spanning finance, utilities, assets, contracts, loans, and homelab telemetry; long-horizon history and publication-grade marts with explicit lineage; budget and planning models; scenario simulation; policy evaluation and recommendation logic; trust, lineage, and governance; and multi-surface publishing so the same outputs reach HA, the web UI, API clients, and agent surfaces.

A HA add-on works within the HA data model, executes in the HA runtime, and operates on HA entities. This platform works across domains that HA does not model — financial transactions, loan amortization, contract prices, infrastructure cost, cross-domain cost attribution — and publishes outputs back to HA as synthetic entities for family-facing visualization and actuation.

The evaluation gate in `docs/plans/household-operating-platform-roadmap.md` codifies this boundary for Stages 5–9. The product and architecture documents in `docs/product/homeassistant-and-smart-home-hub.md` and `docs/architecture/homeassistant-integration-hub.md` define how HA integrates as a first-class surface.

---

## 5. The 10-stage model

| Stage | Name | Key outcome |
|---|---|---|
| 0 | Documentation reset and direction lock | Shared vocabulary and forward-facing framing |
| 1 | Canonical household model | Stable cross-domain semantic core for all downstream consumers |
| 2 | Operating views | Product-grade answers to recurring household questions |
| 3 | Planning and control surfaces | Budget targets, variance tracking, debt planning, affordability |
| 4 | Simulation and scenario engine | Hypothetical future-state reasoning as a first-class capability |
| 5 | Policy, automation, and action engine | Rule-based alerts, integration triggers, recommended actions |
| 6 | Multi-renderer and semantic delivery layer | Publication semantics decoupled from any single frontend |
| 7 | Extension and pack ecosystem | Disciplined discovery, validation, and lifecycle for external packs |
| 8 | Trust, governance, and operator confidence | Explainability, lineage, audit, and confidence indicators |
| 9 | Agentic and assistant layer | Agent-accessible household reasoning with auditable action proposals |

---

## 6. What each stage adds architecturally

### Stage 0 — Documentation reset

- Coherent project identity across README, architecture doc, requirements, and docs index
- 10-stage vocabulary usable by all future planning and sprint documents

### Stage 1 — Canonical household model

- Versioned semantic model governing dimensions, facts, and cross-domain composition rules
- Shared dimension governance so domain packs compose without schema drift
- Remaining canonical entities: budgets, loans, assets, household members, meters, obligations

### Stage 2 — Operating views

- Product-grade Money, Utilities, Operations, and Overview views as defined in `docs/product/core-household-operating-picture.md`
- Insight types that surface change, anomaly, and attention across domains
- The 4-sprint product loop (`docs/sprints/household-operator-product-loop.md`) is the active execution plan for this stage

### Stage 3 — Planning and control

- Budget definition and variance computation models
- Loan repayment projections and amortization tracking
- Household cost model and affordability ratios
- Planning model persistence layer (separate from operational reporting state)

### Stage 4 — Simulation and scenario engine

- Scenario storage and versioning
- Simulation compute engine for what-if modeling
- Scenario-aware publication model so simulated outputs are distinguishable from observed state
- Scenario comparison and saved scenario sets

### Stage 5 — Policy, automation, and action engine

- Policy definition model (thresholds, rules, conditions, triggers)
- Action dispatch for notifications, integrations, and workflow triggers
- Home Assistant integration hub: entity normalization bridge, bidirectional event/command fabric, synthetic entity publication, energy/tariff policy loop
- Boundary between recommendation, alerting, and automated execution
- Evaluation gate: HA-native capabilities stay in HA; platform owns policy evaluation and cross-domain semantic action dispatch

### Stage 6 — Multi-renderer delivery

- Semantic publication metadata beyond table names
- Renderer adapter registry and content negotiation
- Multiple equivalent consumers over shared contracts (admin UI, dashboards, Home Assistant, API clients, agents)

### Stage 7 — Extension and pack ecosystem

- Pack manifest standard with compatibility and trust metadata
- Pack discovery, installation, activation, and lifecycle management
- Pack contract testing and capability declaration
- Curated ecosystem layered on top of the core platform

### Stage 8 — Trust, governance, and operator confidence

- End-to-end data lineage visualization
- Publication freshness and quality scoring
- Decision lineage for planning outputs and automation actions
- Confidence, staleness, and completeness indicators
- Recovery-first operational model

### Stage 9 — Agentic and assistant layer

- Retrieval over semantic models for natural-language exploration
- Safe, auditable action proposals
- Explainable recommendations grounded in publication state
- Domain-specific assistants over finance, utilities, and operations

---

## 7. Stage dependencies and ordering

Stages 0 through 2 are linear prerequisites. Each builds directly on the previous.

Stages 3 through 5 are mostly linear: planning models (3) inform simulation inputs (4), and both inform policy definitions (5). However, Stage 5 can begin basic alerting once Stage 2 operating views exist.

Stages 6 through 8 can partially overlap. Multi-renderer delivery (6) and pack ecosystem (7) are structurally independent. Trust and governance (8) benefits from both but does not strictly require their completion.

Stage 9 depends on Stage 5 (policy engine provides the action surface) and Stage 8 (trust model provides the safety guarantees). It is deliberately late in the roadmap. The platform should become operationally trustworthy before assistants get authority.

---

## 8. What this ADR does NOT decide

- Implementation timelines for Stages 3 and beyond
- Technology choices for the simulation engine, policy engine, or agentic layer
- Whether later stages warrant separate repositories or remain in the monolith
- Pack ecosystem governance model or marketplace design
- Specific rendering frameworks for multi-renderer delivery
- Priority ordering between parallel-eligible stages (6, 7, 8)

These decisions belong in future ADRs when the relevant stages begin active work.

---

## 9. Current state mapping

| Existing artifact | Stage alignment |
|---|---|
| Landing, transformation, reporting pipeline | Stages 1–2 foundation |
| Finance, utilities, overview domain packs | Stage 2 foundation |
| 18 publications across 3 domain packs | Stage 2 foundation |
| `core-household-operating-picture.md` | Stage 2 specification |
| `initial-capability-packs-and-publications.md` | Stage 2 specification |
| 4-sprint product loop | Stage 2–3 execution plan |
| Platform ADR (modular monolith, capability packs) | Stage 7 foundation |
| Extension model (paths, modules, registry) | Stage 7 foundation |
| `external-registry-inclusion.md` | Stage 7 plan |
| Auth, service tokens, role separation | Stage 8 foundation |
| Run metadata, validation outcomes, audit hooks | Stage 8 foundation |
| `additional-data-domains.md` | Stage 1 plan |
| `homeassistant-and-smart-home-hub.md` | Stage 0 / Stage 5 product boundary |
| `homeassistant-integration-hub.md` | Stage 0 / Stage 5 architecture |

---

## 10. Decision

Accept the household operating platform direction. Use the 10-stage vocabulary in all forward-looking documentation, sprint planning, and ADR references.

This direction lock does not grant permission to pursue all 10 stages simultaneously. The active execution plan remains the 4-sprint product loop for Stages 1–3. Later stages receive planning attention when earlier stages reach their acceptance criteria.
