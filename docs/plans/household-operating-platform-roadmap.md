# Household Operating Platform Roadmap

## Purpose

This document defines the 11-stage roadmap that takes homelab-analytics from a household analytics platform to a household operating platform. Each stage describes what it delivers, what architectural capability it introduces, and what it makes possible for subsequent stages.

References:

- Direction ADR: `docs/decisions/household-operating-platform-direction.md`
- Platform ADR: `docs/decisions/household-platform-adr-and-refactor-blueprint.md`
- Product scope: `docs/product/core-household-operating-picture.md`
- Capability packs: `docs/product/initial-capability-packs-and-publications.md`
- HA product scope: `docs/product/homeassistant-and-smart-home-hub.md`
- HA integration architecture: `docs/architecture/homeassistant-integration-hub.md`

---

## Stage summary

| Stage | Name | Key outcome | Primary layers affected |
|---|---|---|---|
| 0 | Documentation reset and direction lock | Shared vocabulary, forward-facing framing | Docs only |
| 1 | Canonical household model | Stable cross-domain semantic core | Transformation, dimensions |
| 2 | Operating views | Product-grade answers to recurring household questions | Reporting, publications, UI |
| 3 | Planning and control surfaces | Budget targets, debt planning, affordability ratios | Planning models, reporting |
| 4 | Simulation and scenario engine | Hypothetical future-state reasoning | Scenario storage, compute |
| 5 | Policy, automation, and action engine | Rule-based alerts, integration triggers | Policy model, action dispatch |
| 6 | Integration adapter layer | Generic adapter contracts for external system integration | Adapter manifests, lifecycle model |
| 7 | Multi-renderer and semantic delivery layer | Publication semantics decoupled from frontends | Delivery adapters, content negotiation |
| 8 | Extension and pack ecosystem | Governed pack discovery, validation, lifecycle | Pack manifest, registry |
| 9 | Trust, governance, and operator confidence | Explainability, lineage, audit completeness | Lineage model, quality scoring |
| 10 | Agentic and assistant layer | Agent-accessible household reasoning | Tool definitions, retrieval layer |

---

## Stage 0 — Documentation reset and direction lock

### Capability goal

Create one coherent statement of purpose so the repo stops telling two stories at once.

### Key deliverables

- Direction ADR establishing the 11-stage vocabulary
- This roadmap document
- Architecture doc expanded with forward-looking layer definitions
- Requirements phase table reframed around operating-platform maturity
- README rewritten around product purpose rather than bootstrap status
- Docs index refreshed to include all existing documentation
- `docs/product/homeassistant-and-smart-home-hub.md` — why the platform is not a Home Assistant add-on, what belongs in HA vs what belongs in the platform, HA's five roles as edge runtime and delivery surface, and the five-step build ordering for HA integration
- `docs/architecture/homeassistant-integration-hub.md` — six-layer integration hub architecture: entity normalization bridge, bidirectional event/command fabric, synthetic entity publication model, action safety model, and resilience model
- README update explaining HA as a first-class integration surface and why the platform is separate from, but tightly integrated with, Home Assistant

### Status

Substantially complete. This sprint addresses the remaining documentation gaps.

---

## Stage 1 — Canonical household model

### Capability goal

Move from "several useful domain-specific transforms" to a stable, versioned, cross-domain household semantic core that all downstream surfaces depend on.

### Key deliverables

- Remaining canonical dimensions and facts narrowed to the real carryover: `dim_household_member` and infrastructure follow-up that has not yet received explicit landing/reporting contracts; `fact_balance_snapshot` is now implemented as the Stage 1 point-in-time balance fact
- Home automation state foundation (`dim_entity`, `fact_sensor_reading`, `fact_automation_event`) now exists in the transformation layer and remains separate from the HA bridge tables
- Cross-domain semantic-governance rules ensuring shared dimensions such as `dim_category` and `dim_counterparty` are defined once and promoted deliberately when new platform-level identities emerge
- Semantic typing for publications so renderer consumers can rely on meaning-bearing metadata beyond table names

### Relationship to existing work

The architecture doc already names most of these dimensions and facts in the transformation section. Three domain packs already implement subsets: finance owns `dim_account`, `dim_counterparty`, `fact_transaction`, `fact_subscription`; utilities owns `dim_meter`, `fact_utility_usage`, `fact_bill`, `fact_contract_price`. The additional-data-domains plan (`docs/plans/additional-data-domains.md`) specifies sources, canonical models, and marts for seven domains including loans, infrastructure, and home automation, with the asset foundation now landed.

### Remaining gaps

- `dim_household_member`
- Landing contracts and reporting starters that complete the remaining infrastructure foundations
- Explicit promotion rules for future shared dimensions instead of treating repeated provider-style fields as a registry by default

### Planned documentation

- `docs/architecture/domain-model.md` — canonical household ontology
- `docs/architecture/semantic-contracts.md` — rules for extending the shared semantic layer without creating duplicate platform identities

### Status

Mostly complete. Sprint I finance ingestion is complete, and the worktree now includes internal-platform ingestion, utilities automation foundations, loan and budget planning models, infrastructure metrics dimensions/facts, home-automation state foundations, and the completed asset inventory foundation. Remaining Stage 1 work is the true carryover: semantic-governance cleanup, explicit infrastructure contracts, and `dim_household_member`.

---

## Stage 2 — Operating views

### Capability goal

Deliver product-grade answers to recurring household questions through stable publication-backed views.

### Specification

This stage is defined by `docs/product/core-household-operating-picture.md`, which establishes the four core views (Overview, Money, Utilities, Operations), product principles, and acceptance criteria. The publication set is defined in `docs/product/initial-capability-packs-and-publications.md`.

### Active execution

The 4-sprint product loop (`docs/sprints/household-operator-product-loop.md`) is actively delivering this stage. Sprint 1 (Weekly Money View) has shipped. Sprints 2–4 cover budget variance, debt and cost truth, and the household control panel.

### Remaining gaps

- Homelab capability pack (service health, backup freshness, storage risk, workload cost)
- Overview composition from all four domain packs once homelab is available
- Full insight type coverage across finance, utilities, and homelab

### Status

Complete. Delivered as v0.1.0 (2026-03-20) through the 4-sprint product loop. All four sprints merged as a single delivery on `feat/combined-dashboard`.

---

## Stage 3 — Planning and control surfaces

### Capability goal

Turn the platform from descriptive to managerial. Move beyond "what happened" to "what should happen" and "how far off are we."

### Key capabilities

- Budget definitions and variance tracking (ANA-03)
- Loan repayment projections and amortization (ANA-02)
- Household cost model aggregating all cost streams (ANA-04)
- Affordability and exposure ratios (ANA-06)
- Category-based cost envelopes with drift visibility
- Structured state indicators: good / warning / needs action

### Relationship to existing work

Requirements ANA-02, ANA-03, ANA-04, and ANA-06 are already defined in `requirements/analytics-and-reporting.md` with acceptance criteria and dependency chains. The 4-sprint product loop covers budget variance (Sprint 2), debt and cost truth (Sprint 3), and the household control panel (Sprint 4).

### Architectural additions

- Planning model persistence layer — budget targets, goal definitions, and obligation records — separate from operational reporting state
- Variance computation engine comparing planned vs. actual across time windows
- Recurring commitment management with renewal and expiry tracking

### Planned documentation

- `docs/product/planning-and-control.md` — concepts of budget, obligation, target, threshold, variance, and intervention

### Status

Partially complete. Budget definitions, variance tracking, category-based cost envelopes with drift visibility, affordability ratios, household cost model, recurring cost baseline, and structured state indicators are shipped.

---

## Stage 4 — Simulation and scenario engine

### Capability goal

Make future-state reasoning a first-class system capability rather than isolated calculators.

### Key capabilities

- Loan what-if modeling (rate changes, extra repayments, refinancing)
- Cost-of-living scenarios (income change, cost inflation, subscription reduction)
- Utility price shock scenarios (tariff increase, usage change, provider switch)
- Housing and affordability scenarios
- Homelab cost/benefit scenarios (scale up/down, migrate services, hardware refresh)
- Scenario comparison and saved scenario sets

### Architectural additions

- Scenario storage with input assumptions, parameters, and version control
- Simulation compute engine producing projected outcomes from current canonical state plus scenario overrides
- Scenario-aware publication model — simulated outputs are clearly distinguishable from observed state
- Explainability metadata linking projections to their assumptions

### Prerequisites

Stage 3 planning models provide the baseline targets and obligation structures that scenarios modify.

### Planned documentation

- `docs/architecture/simulation-engine.md` — scenario inputs, compute model, assumption tracking, explainability
- `docs/product/scenarios-and-what-if.md` — user-facing scenario types and comparison workflows

### Status

Partially complete. Five scenario types shipped (loan what-if, income change, expense shock, utility tariff shock, homelab cost/benefit) with scenario storage, assumption tracking, staleness detection, a scenarios list page, a saved-scenario comparison view, and shared saved compare sets. The homelab value-loop operator panel now surfaces reporting-layer service-health and workload-cost summaries plus a reporting-backed homelab ROI surface, a derived comparison, and a saved scenario summary; richer saved scenario sets remain.

---

## Stage 5 — Policy, automation, and action engine

### Capability goal

Make the platform able to act on observed state, not just report it. Home Assistant is the primary actuation surface for this stage; the platform owns the policy evaluation and recommendation logic.

### Key capabilities

- Rule-based alerts (utility spend deviation, budget breach, backup staleness, subscription anomaly)
- Contract renewal and expiry reminders
- Anomaly notifications across all domains
- Recurring action suggestions (refinancing review, contract switch, subscription audit)
- Home Assistant semantic bridge: mapping HA devices, entities, and areas to canonical household assets, loads, meters, and locations
- Bidirectional HA integration: HA as state source (WebSocket/REST ingest) and HA as action consumer (service calls, scene triggers, notifications)
- Synthetic entity publication: platform outputs materialized as HA sensor, binary_sensor, and helper entities via MQTT discovery
- Energy and tariff policy loop: platform models load, prices, battery/EV/heat-pump behavior; HA executes and visualizes; operator can override
- Approval-aware action dispatch: recommendation → alerting → automated → approval-gated safety model, with approval resolution clearing the HA gate notification, optionally executing a service target, and logging the release event
- Helper-driven approval requests: HA helper entities can surface operator intent that becomes an approval-gated proposal with an HA service target
- Synthetic approval queue sensors: approval proposal counts are published back into HA so operators can monitor pending approvals alongside other platform state
- Approval queue UI controls: homelab and retro operations pages can approve or dismiss pending proposals directly from the web app
- Webhook and job-based integrations for non-HA external systems

### Relationship to existing work

The platform already has the infrastructure substrate: APIs, service tokens, authenticated endpoints, execution schedules, worker dispatch, and Home Assistant metric exposure (ANA-08). This stage makes that substrate product-visible through a policy definition layer and activates the full HA integration hub defined in `docs/architecture/homeassistant-integration-hub.md`.

### Architectural additions

- Policy definition model: thresholds, rules, conditions, trigger actions
- Action dispatch model: notification channels, integration endpoints, report generation, approval-gated policy results, proposal tracking, and approval resolution logging
- HA integration hub (Layer 2–5): normalization bridge, event bus, action/approval layer, synthetic entity publication
- Clear boundary between recommendation (safe), alerting (notify), and automation (act)

### Home Assistant boundary for this stage

HA owns: device control, automation execution, dashboard visualization, notification delivery, local voice responses, energy monitoring UI.

The platform owns: policy definitions, threshold evaluation, recommendation logic, action approval workflows, and publication of policy-state outputs back to HA as synthetic entities.

If a proposed capability in this stage could be delivered as a HA automation, script, or custom integration with no cross-domain semantic dependency, it belongs in HA. Only capabilities that require canonical household model state, cross-domain joins, planning outputs, or multi-surface publishing belong in the platform layer.

### Prerequisites

Stage 2 operating views provide the observed state that policies evaluate. Stage 5 can begin basic alerting once Stage 2 views are stable, without waiting for Stages 3–4.

### Planned documentation

- `docs/architecture/policy-and-automation.md` — policy model, action dispatch, integration surface, safety boundaries
- `docs/product/actions-and-alerts.md` — what the platform recommends vs. alerts vs. automates
- `docs/plans/ha-addon-and-integration-design.md` — high-level design plan for the HA add-on (outbound bridge) and HA integration (inbound semantic surface); inputs for later implementation decomposition

### Status

Substantially complete in the worktree. HA Phases 1–6 are complete: batch entity ingest, WebSocket live subscription, MQTT synthetic entity publication, policy/automation evaluation engine, outbound action dispatcher, approval-gated device control, approval queue publication/UI controls, and expanded tariff/cost/maintenance synthetic entities. The next step is boundary hardening and adapter extraction rather than another round of HA feature sprawl.

---

## Stage 6 — Integration adapter layer

### Capability goal

Extract the integration contracts proven in Stage 5 (HA-first) into a generic adapter model so that new external systems can integrate without reimplementing the full stack. HA remains the reference implementation and primary integration surface.

### Key capabilities

- Three adapter contracts: ingest (state stream or poll), publish (entity or metric publication), action (command dispatch)
- Adapter registration and lifecycle model: discovery, connection, typed health/status, teardown
- Entity normalization contract per adapter: source entities mapped to canonical platform entities
- Connection and credential management abstraction
- HA implementation positioned as the reference adapter
- Extension points documented for future adapters

### Integration surfaces this stage enables

The adapter model should account for these integration categories without necessarily implementing them in this stage:

**Cluster monitoring** — Prometheus federation or remote-read for infrastructure metrics, service health, and resource utilization. Ingest adapter.

**Cluster infrastructure** — Kubernetes API for ingress state, certificate expiry, workload status, and scaling actions. Ingest and action adapter.

**Network and access** — WireGuard and Tailscale peer status, connection health, handshake freshness as ingest adapter. Peer management and ACL updates as action adapter.

**Generic MQTT** — Arbitrary topic subscription without HA discovery envelope as ingest adapter. Arbitrary topic publication without HA discovery format as publish adapter.

**Notification services** — ntfy, Pushover, email, and messaging platforms as action adapter for alert dispatch, decoupled from HA persistent_notification.

**Direct device protocols** — Devices or services not managed by HA that expose MQTT, REST, or other standard APIs.

### Architectural additions

- `AdapterManifest`: declares adapter identity, supported directions (ingest, publish, action), credential requirements, entity class vocabulary, and health-check contract
- `IngestAdapter` contract: connect, stream or poll, normalize to canonical entity model, disconnect
- `PublishAdapter` contract: connect, format platform state to target entity model, publish, disconnect
- `ActionAdapter` contract: validate action against target capabilities, dispatch, report result
- Adapter health and status reporting generalizing the existing `/api/ha/*/status` pattern through a shared typed runtime snapshot
- Multi-adapter entity correlation strategy for deduplicating or correlating entities that appear through multiple adapters

### Relationship to existing work

The HA integration hub (Phases 1–5) is the first complete implementation of a bidirectional integration adapter. Its six-layer architecture maps to the adapter contracts:

| HA hub layer | Adapter contract |
|---|---|
| Layer 1 — Device ingress | Handled by HA internally, not a platform adapter concern |
| Layer 2 — Entity normalization | `IngestAdapter.normalize()` |
| Layer 3 — Event and history bus | `IngestAdapter.connect()` and `IngestAdapter.stream()` |
| Layer 5 — Action and approval | `ActionAdapter.dispatch()` |
| Layer 6 — Federation publish | `PublishAdapter.publish()` |

### Home Assistant boundary

HA remains the primary integration surface. The adapter abstraction does not diminish HA's role. It ensures that HA-specific protocol logic (WebSocket subscription format, MQTT discovery envelope, REST service call schema) is separable from the generic integration lifecycle (connect, normalize, ingest, publish, act, health-check).

New adapters do not replace HA. They serve integration surfaces that HA does not cover (Prometheus, Kubernetes API, direct VPN management) or that benefit from bypassing HA (high-volume MQTT sensor streams where HA entity overhead is unnecessary).

### What this stage does NOT build

This stage defines the adapter contracts, documents the extension points, and positions the HA integration as the reference implementation. It does not build adapters for all listed integration surfaces. Each new adapter is a discrete implementation task — either a standalone sprint or a pack contribution in Stage 8.

### Prerequisites

Stage 5 HA integration (at least Phases 1–5) provides the concrete implementation from which this stage abstracts.

### Planned documentation

- `docs/architecture/integration-adapters.md` — adapter contracts, registration model, lifecycle, extension points, and HA-as-reference-implementation walkthrough

---

## Stage 7 — Multi-renderer and semantic delivery layer

### Capability goal

Decouple product value from any single frontend. Publications become renderer-agnostic semantic outputs that any consuming surface — including Home Assistant — can read without understanding the platform's internal model.

### Key capabilities

- Stable semantic APIs with meaning-bearing metadata
- Report contracts consumable by multiple clients
- Alternate UI renderers (admin dashboard, simplified view, mobile-friendly surface)
- Home Assistant as a first-class renderer: HA dashboard cards, Lovelace UI bindings, and voice surface responses derived from platform publication contracts
- Export and render packages (PDF, CSV, Parquet)
- Agent and tool consumers over the same semantic layer

### Home Assistant boundary for this stage

HA is one renderer among several, not the primary frontend. The platform's publication contracts define the semantic outputs. HA receives them via synthetic entities (Stage 5) and via explicit renderer adapters in this stage.

If a proposed capability in this stage amounts to pushing more data into HA entities and letting HA render it, that is Stage 5 synthetic entity work, not Stage 6 renderer architecture. Stage 6 is about the generic renderer adapter contract that HA, the web UI, export formats, and agents all consume from the same semantic layer.

### Relationship to existing work

The platform ADR sections 12–13 already define UI descriptors and publication contracts. The web app already consumes the API rather than reaching into the warehouse directly. This stage generalizes that pattern into a product principle: the semantic layer is the product spine, and renderers are replaceable.

### Architectural additions

- Semantic publication metadata beyond table names (data type, aggregation semantics, display hints, time grain)
- Renderer adapter registry and content negotiation
- UI descriptor resolution from publication definitions to rendered components
- Export format selection and rendering pipeline

### Planned documentation

- `docs/architecture/rendering-and-delivery.md` — renderer discovery, consumption model, content negotiation

---

## Stage 8 — Extension and pack ecosystem

### Capability goal

Turn the current extension mechanism into a disciplined, governed pack model.

### Key capabilities

- Source packs (provider connectors, format adapters)
- Domain packs (new fact/dimension families, marts, insights)
- Reporting packs (custom visualizations, export formats)
- Automation packs (integration adapters, policy templates)
- Country/provider-specific packs (geography-specific finance, utility, and tax models)
- Pack metadata, compatibility verification, and trust model
- Pack installation, activation, and lifecycle management
- Pack contract testing and capability declaration

### Relationship to existing work

The extension model already supports local paths and Git repositories via `HOMELAB_ANALYTICS_EXTENSION_PATHS` and `HOMELAB_ANALYTICS_EXTENSION_MODULES`. The platform ADR defines the capability pack model with manifest-driven registration. The external-registry-inclusion plan (`docs/plans/external-registry-inclusion.md`) defines the control-plane design for UI-managed external sources with sync, validation, and activation lifecycle.

### Home Assistant boundary for this stage

Automation packs that produce HA automations, scripts, or dashboard cards without any platform-side semantic or policy dependency should be HA integrations or custom components, not platform packs. Platform packs justify their place in the ecosystem by extending the semantic layer, canonical model, planning logic, policy definitions, or multi-surface publication contracts — not by wrapping HA behavior that HA already handles.

### Architectural additions

- Pack manifest standard with compatibility metadata, declared capabilities, and trust declarations
- Pack distribution and discovery model (beyond local paths and Git clones)
- Version compatibility verification between pack manifest and platform version
- Pack lifecycle: discovery, validation, installation, activation, upgrade, deactivation

### Planned documentation

- `docs/architecture/pack-ecosystem.md` — manifest standard, compatibility model, trust boundaries
- `docs/product/pack-model.md` — what a pack is, how operators discover and manage them

---

## Stage 9 — Trust, governance, and operator confidence

### Capability goal

Make the platform explainable, auditable, and safe to rely on for consequential household decisions.

### Key capabilities

- End-to-end data lineage visualization (source → landing → transformation → publication)
- Scenario assumption tracking and decision lineage
- Audit trails for user actions, automation actions, and pack execution
- Confidence, staleness, and completeness indicators on every publication
- Source and pack trust boundaries
- Backup, restore, and portability guarantees
- Privacy and least-privilege defaults
- Recovery-first operational model

### Relationship to existing work

The platform already has strong foundations: OIDC, service tokens, role/scope authorization, secret-backed config, readiness/liveness checks, run metadata with validation outcomes, source lineage, publication audit, and operational runbooks. This stage extends those foundations toward full permission-level governance, planning outputs, simulation assumptions, automation actions, and pack execution.

### Architectural additions

- Lineage graph model connecting source runs through transformations to published outputs
- Publication freshness and quality scoring framework
- Operator confidence dashboard surfacing staleness, completeness, and trust signals
- Decision lineage for planning and simulation outputs (which assumptions produced which projections)

### Planned documentation

- `docs/architecture/trust-and-governance.md` — lineage model, quality scoring, confidence framework, audit requirements

---

## Stage 10 — Agentic and assistant layer

### Capability goal

Make the platform explorable and operable through agent interfaces without making the agent the source of truth.

### Key capabilities

- Natural-language retrieval over semantic models and publications
- Safe action proposals grounded in observed state and policy definitions
- Explainable recommendations with lineage back to source data
- Controlled task execution through approved, auditable automation paths
- Report drafting and scenario narration
- Domain-specific assistants over finance, utilities, and operations

### Prerequisites

- Stage 5 (policy engine provides the action surface that agents can propose against)
- Stage 9 (trust model provides the safety guarantees that make agent actions auditable)

This stage is deliberately late in the roadmap. The platform should become operationally trustworthy before assistants get authority. Otherwise you build an eloquent intern with root access.

### Architectural additions

- Semantic publication index optimized for LLM consumption (descriptions, schemas, sample data)
- Tool definitions for agent frameworks (MCP, function calling)
- Conversation state management
- Action proposal model with approval workflow

### Planned documentation

- `docs/architecture/agent-surfaces.md` — retrieval model, tool definitions, action boundaries, safety guarantees

---

## Platform vs Home Assistant boundary

Home Assistant is a first-class integration target and a primary delivery surface. It is not the platform's canonical system of record, not the place where cross-domain semantics originate, and not the right layer for planning, simulation, or policy evaluation logic.

### What belongs in Home Assistant

- Device and protocol integration (Zigbee, Z-Wave, Matter, Thread, Wi-Fi, and vendor cloud adapters)
- Real-time entity state, presence, occupancy, and house-mode modeling
- Local automations, scripts, and scenes
- Family-facing dashboards and operational UI
- Voice assistant pipelines and ambient interaction surfaces
- Energy monitoring and in-day visualization
- Notification delivery to household members
- Actuation: executing device commands, script triggers, and service calls

### What belongs in the platform

- Canonical cross-domain household model spanning finance, utilities, assets, contracts, loans, and homelab telemetry
- Long-horizon history and publication-grade marts with explicit lineage
- Budget definitions, variance computation, and planning state
- Scenario simulation and what-if modeling
- Policy evaluation, recommendation logic, and approval workflows
- Trust, lineage, governance, and confidence indicators
- Multi-surface publishing so the same semantic outputs reach HA, the web UI, API clients, and agent surfaces
- Pack and ecosystem capabilities that extend the semantic and product layer

### Evaluation gate for Stages 5–10

Before adding any capability to the platform in Stages 5 through 10, apply this check:

1. Could this be delivered as a Home Assistant add-on, custom integration, or automation with no cross-domain semantic dependency?
2. If yes, it belongs in Home Assistant.
3. If no, identify which of the following justifies platform-side implementation: canonical household semantics, long-horizon history, planning or simulation state, policy evaluation, trust or lineage, or multi-surface publishing.
4. If none of those apply, the capability does not belong in the platform layer.

This gate is not a bureaucratic filter. It is a guard against the platform slowly becoming a more complicated way to do what HA already does well.

### Integration model

HA integrates with the platform bidirectionally:

- **HA as source**: device state, sensor readings, energy telemetry, and occupancy data flow from HA into the platform via the WebSocket event stream and REST history API, normalized by the entity bridge layer.
- **HA as consumer**: platform outputs flow back to HA as synthetic entities (forecast sensors, budget state indicators, maintenance flags, policy-state helpers, recommended-action entities), service call dispatch, and notification payloads.

The full integration hub architecture is defined in `docs/architecture/homeassistant-integration-hub.md`. The product boundary and build ordering are defined in `docs/product/homeassistant-and-smart-home-hub.md`.

---

## Phase-to-stage mapping

The existing requirements use a 5-phase model (Phases 0–4) with stable requirement IDs. That model remains the authoritative frame for existing requirements. The 11-stage model describes the broader trajectory.

| Phase | Name | Focus | Stage alignment |
|---|---|---|---|
| 0 | Bootstrap | Repo structure, planning docs, first scaffold vertical slice | Stage 0 |
| 1 | Foundation | Production stack, first complete dataset through all three layers | Stages 0–1 |
| 2 | Generalization | Multiple datasets, generic connectors, operating views | Stages 1–2 |
| 3 | Household operating model | Budget, loans, cost model, planning surfaces, homelab operations | Stages 2–3 |
| 4 | Platform maturity | Auth, CI/CD, multi-renderer, policy, ecosystem foundations | Stages 3–5 |

Stages 5–10 extend beyond the original 5-phase model. New requirements for those stages will be added to the requirements baseline as the stages begin active work.

---

## Staging principles

1. **Each stage should be independently valuable.** The platform should be useful at the end of every stage, not only when all 11 are complete.

2. **No stage requires all previous stages to be 100% complete.** Stage boundaries mark maturity thresholds, not hard gates. Some work from adjacent stages will naturally overlap.

3. **Do not pursue later stages as justification for avoiding current-stage product work.** The 4-sprint product loop remains the active execution plan for Stages 1–3. Architectural foreshadowing is fine; premature abstraction is not.

4. **The product docs remain the intake for new capability slices.** Every new domain pack, publication, or user-facing feature should pass the litmus test defined in `docs/product/core-household-operating-picture.md` section 8.

5. **Later stages receive dedicated ADRs when they begin active work.** This roadmap provides enough context for planning and prioritization. Technology choices, detailed designs, and acceptance criteria belong in stage-specific ADRs and requirement additions.

6. **Apply the platform vs Home Assistant boundary before adding any capability in Stages 5–10.** If a proposed capability could be a HA add-on with no cross-domain semantic, planning, policy, or multi-surface publishing dependency, it belongs in Home Assistant. The evaluation gate in the "Platform vs Home Assistant boundary" section above is the intake check for those stages.
