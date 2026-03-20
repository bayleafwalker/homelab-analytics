# Household Operating Platform Roadmap

## Purpose

This document defines the 10-stage roadmap that takes homelab-analytics from a household analytics platform to a household operating platform. Each stage describes what it delivers, what architectural capability it introduces, and what it makes possible for subsequent stages.

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
| 6 | Multi-renderer and semantic delivery layer | Publication semantics decoupled from frontends | Delivery adapters, content negotiation |
| 7 | Extension and pack ecosystem | Governed pack discovery, validation, lifecycle | Pack manifest, registry |
| 8 | Trust, governance, and operator confidence | Explainability, lineage, audit completeness | Lineage model, quality scoring |
| 9 | Agentic and assistant layer | Agent-accessible household reasoning | Tool definitions, retrieval layer |

---

## Stage 0 — Documentation reset and direction lock

### Capability goal

Create one coherent statement of purpose so the repo stops telling two stories at once.

### Key deliverables

- Direction ADR establishing the 10-stage vocabulary
- This roadmap document
- Architecture doc expanded with forward-looking layer definitions
- Requirements phase table reframed around operating-platform maturity
- README rewritten around product purpose rather than bootstrap status
- Docs index refreshed to include all existing documentation
- `docs/product/homeassistant-and-smart-home-hub.md` — why the platform is not a Home Assistant add-on, what belongs in HA vs what belongs in the platform, HA's five roles as edge runtime and delivery surface, and the five-step build ordering for HA integration
- `docs/architecture/homeassistant-integration-hub.md` — six-layer integration hub architecture: entity normalization bridge, bidirectional event/command fabric, synthetic entity publication model, action safety model, and resilience model
- README update explaining HA as a first-class integration surface and why the platform is separate from, but tightly integrated with, Home Assistant

### Status

In progress. This is Stage 0.

---

## Stage 1 — Canonical household model

### Capability goal

Move from "several useful domain-specific transforms" to a stable, versioned, cross-domain household semantic core that all downstream surfaces depend on.

### Key deliverables

- Remaining canonical dimensions: `dim_budget`, `dim_loan`, `dim_asset`, `dim_household_member`, cross-domain `dim_category` governance
- Remaining canonical facts: `fact_loan_repayment`, `fact_balance_snapshot`, `fact_asset_event`, `fact_sensor_reading`, `fact_power_consumption`, `fact_cluster_metric`
- Cross-domain dimension registry ensuring shared dimensions (category, counterparty, provider, household member) are defined once and referenced by surrogate key from all consuming facts
- Semantic typing for publications — meaning-bearing metadata beyond table names

### Relationship to existing work

The architecture doc already names most of these dimensions and facts in the transformation section. Three domain packs already implement subsets: finance owns `dim_account`, `dim_counterparty`, `fact_transaction`, `fact_subscription`; utilities owns `dim_meter`, `fact_utility_usage`, `fact_bill`, `fact_contract_price`. The additional-data-domains plan (`docs/plans/additional-data-domains.md`) specifies sources, canonical models, and marts for seven domains including loans, assets, infrastructure, and home automation.

### Remaining gaps

- Budget dimension and its binding to transaction categories
- Loan models (dimension, fact, amortization)
- Asset inventory models
- Homelab/infrastructure models (cluster metrics, power consumption, sensor readings)
- Cross-domain dimension governance (ensuring `dim_category` and `dim_counterparty` are shared, not duplicated per domain)

### Planned documentation

- `docs/architecture/domain-model.md` — canonical household ontology
- `docs/architecture/semantic-contracts.md` — rules for extending the model without wrecking compatibility

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
- Approval-aware action dispatch: recommendation → alerting → automated → approval-gated safety model
- Webhook and job-based integrations for non-HA external systems

### Relationship to existing work

The platform already has the infrastructure substrate: APIs, service tokens, authenticated endpoints, execution schedules, worker dispatch, and Home Assistant metric exposure (ANA-08). This stage makes that substrate product-visible through a policy definition layer and activates the full HA integration hub defined in `docs/architecture/homeassistant-integration-hub.md`.

### Architectural additions

- Policy definition model: thresholds, rules, conditions, trigger actions
- Action dispatch model: notification channels, integration endpoints, report generation
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

---

## Stage 6 — Multi-renderer and semantic delivery layer

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

## Stage 7 — Extension and pack ecosystem

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

## Stage 8 — Trust, governance, and operator confidence

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

The platform already has strong foundations: OIDC, service tokens, role separation, secret-backed config, readiness/liveness checks, run metadata with validation outcomes, source lineage, publication audit, and operational runbooks. This stage extends those foundations to cover planning outputs, simulation assumptions, automation actions, and pack execution.

### Architectural additions

- Lineage graph model connecting source runs through transformations to published outputs
- Publication freshness and quality scoring framework
- Operator confidence dashboard surfacing staleness, completeness, and trust signals
- Decision lineage for planning and simulation outputs (which assumptions produced which projections)

### Planned documentation

- `docs/architecture/trust-and-governance.md` — lineage model, quality scoring, confidence framework, audit requirements

---

## Stage 9 — Agentic and assistant layer

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
- Stage 8 (trust model provides the safety guarantees that make agent actions auditable)

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

### Evaluation gate for Stages 5–9

Before adding any capability to the platform in Stages 5 through 9, apply this check:

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

The existing requirements use a 5-phase model (Phases 0–4) with stable requirement IDs. That model remains the authoritative frame for existing requirements. The 10-stage model describes the broader trajectory.

| Phase | Name | Focus | Stage alignment |
|---|---|---|---|
| 0 | Bootstrap | Repo structure, planning docs, first scaffold vertical slice | Stage 0 |
| 1 | Foundation | Production stack, first complete dataset through all three layers | Stages 0–1 |
| 2 | Generalization | Multiple datasets, generic connectors, operating views | Stages 1–2 |
| 3 | Household operating model | Budget, loans, cost model, planning surfaces, homelab operations | Stages 2–3 |
| 4 | Platform maturity | Auth, CI/CD, multi-renderer, policy, ecosystem foundations | Stages 3–5 |

Stages 5–9 extend beyond the original 5-phase model. New requirements for those stages will be added to the requirements baseline as the stages begin active work.

---

## Staging principles

1. **Each stage should be independently valuable.** The platform should be useful at the end of every stage, not only when all 10 are complete.

2. **No stage requires all previous stages to be 100% complete.** Stage boundaries mark maturity thresholds, not hard gates. Some work from adjacent stages will naturally overlap.

3. **Do not pursue later stages as justification for avoiding current-stage product work.** The 4-sprint product loop remains the active execution plan for Stages 1–3. Architectural foreshadowing is fine; premature abstraction is not.

4. **The product docs remain the intake for new capability slices.** Every new domain pack, publication, or user-facing feature should pass the litmus test defined in `docs/product/core-household-operating-picture.md` section 8.

5. **Later stages receive dedicated ADRs when they begin active work.** This roadmap provides enough context for planning and prioritization. Technology choices, detailed designs, and acceptance criteria belong in stage-specific ADRs and requirement additions.

6. **Apply the platform vs Home Assistant boundary before adding any capability in Stages 5–9.** If a proposed capability could be a HA add-on with no cross-domain semantic, planning, policy, or multi-surface publishing dependency, it belongs in Home Assistant. The evaluation gate in the "Platform vs Home Assistant boundary" section above is the intake check for those stages.
