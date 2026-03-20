# Home Assistant and Smart-Home Hub

## Purpose

This document defines the intended role of Home Assistant as an edge runtime and household operations surface within the household operating platform. It establishes how HA fits alongside homelab-analytics as the semantic and planning core, how consumer ecosystems and legacy hubs relate to that structure, and what product intent the platform should satisfy when implementing HA integration across the roadmap.

## Why this is not just a Home Assistant integration

A Home Assistant add-on or custom integration works within the HA data model, executes in the HA runtime, and produces outputs that HA can visualize or act on. That is a useful and legitimate scope. This platform does something different.

HA does not model financial transactions, loan amortization, contract prices, cross-domain cost attribution, subscription variance, or infrastructure cost. Its entity model describes the current state of devices and sensors, not the historical semantics of a household's financial and operational picture. Its statistics layer retains operational telemetry; it does not hold long-horizon publication-grade marts with explicit lineage, planning targets, scenario assumptions, or trust and confidence metadata.

This platform exists because the questions a household operating platform must answer — "are we on track this month?", "what does this loan cost us over ten years?", "how much does running the homelab contribute to our electricity bill?", "should we refinance given current rates?", "which appliance is most likely to fail this year based on runtime patterns?" — require a cross-domain semantic core, a planning layer, a simulation engine, and a governance model that live outside HA. Once those exist, HA is the right surface to deliver outputs to: as synthetic entities, voice responses, dashboard cards, and automation triggers. The platform decides; HA acts.

## Core stance

Federated, local-first, semantically centralized. HA handles edge control, device integration, local automations, voice and UI surfaces, and real-time household state. homelab-analytics is the canonical household model, long-horizon history, planning and simulation engine, policy engine, and pack ecosystem.

## What Home Assistant should be

### 1. Edge device and event runtime

HA is the primary integration surface for devices, protocols, and vendor cloud adapters. It absorbs raw real-time device state, local events, and room and area context through its native integration ecosystem. Automations, dashboards, energy views, and device organization all belong here. It is the right layer to carry the breadth of protocol and vendor integrations without pushing that surface area into the analytics platform.

### 2. Real-time household state fabric

HA's entity model and long-term statistics are the correct home for operational telemetry and short-horizon history. Occupancy, device states, alarms, energy flows, HVAC state, tariff-active mode, appliance runtime, and derived house-mode state all live here. This data is available to platform ingestion but is authoritative in HA first.

### 3. Operator cockpit

HA is already where household interaction lives: overview dashboards, energy and comfort views, alerts and pending actions, room and device status, maintenance reminders, and approval prompts for automations. The platform should surface outputs through this cockpit rather than requiring operators to maintain a separate control surface for household operations.

### 4. Actuation gateway

homelab-analytics decides; HA acts. The analytics platform determines a recommendation or policy result and dispatches it to HA, which executes the corresponding device or service calls, scripts, scenes, notifications, or approval flows. This separation avoids teaching the analytics platform to speak to every light bulb, thermostat, and inverter directly and keeps actuation logic in the layer that already has device trust.

### 5. Voice and ambient interaction surface

HA is the local voice and ambient presentation layer for household platform queries. Questions such as "What is our current monthly burn?", "Should I run the dishwasher now?", and "Approve battery discharge strategy for peak period?" should be answerable through HA voice pipelines using platform-published state. This keeps conversational household control local, contextual, and accessible without requiring a cloud-dependent assistant service for routine operational queries.

## What the platform adds beyond Home Assistant

### 1. Canonical household digital twin

HA gives you entities; the platform gives you meaning. A raw entity such as `sensor.living_room_temperature` is a location-aware device in the platform model. That device belongs to an asset in the asset register, which has a cost center, a warranty record, a maintenance schedule, and participation in tariff-shifting policies. The HA entity tells you the current temperature. The platform tells you that the sensor is part of an HVAC asset approaching scheduled service, covered by a warranty expiring in three months, and that the room's heating is consuming more than its baseline runtime suggests given the current external temperature and occupancy pattern.

### 2. Long-horizon planning and simulation

HA is strong at current and recent operational state. The platform owns the rest: monthly and annual cost models, debt and loan projections, energy-price what-if scenarios, appliance replacement ROI, self-hosted versus vendor-service cost comparisons, solar and battery and EV optimization simulations, and household resilience scenarios. None of this is achievable from HA's entity model alone; it requires a cross-domain canonical model with historical depth and scenario evaluation capability.

### 3. Policy engine

The platform expresses policies and HA executes them. Policies include rules such as: do not run discretionary loads during expensive tariff periods unless a comfort threshold is violated; prefer battery discharge when grid prices are above a threshold band; notify the operator when device behavior implies fault or waste; flag devices with runtime patterns suggesting maintenance is due. The platform evaluates these policies against its canonical model and publishes recommended or authorized actions. HA receives them and executes the corresponding automations, scripts, or notifications.

### 4. Asset, maintenance, and lifecycle management

Smart-home telemetry becomes part of a wider household asset system. The platform tracks appliances, batteries, inverters, heat pumps, routers, access points, UPS units, storage devices, filters, detectors, and consumables — including warranties, firmware and update posture, and replacement planning. HA runtime hours and state telemetry feed asset lifecycle models rather than being viewed only as current operational state.

### 5. Procurement and compatibility intelligence

The platform helps decide what to buy. Matter and Thread capability, proprietary hub requirements, local control availability, ecosystem compatibility, integration quality, data ownership and cloud dependency, and replacement suggestions all belong in the platform's knowledge model. Standards-first procurement — preferring Matter and Thread devices — is the correct ideal-state strategy for reducing per-vendor integration surface area and maximizing long-term local control.

## Integration principle

Protocol-first, ecosystem-second, cloud-last. In practice:

- Prefer Matter and Thread devices and infrastructure for new procurement
- Use HA as the primary local integration and orchestration hub for all device protocols and vendor adapters
- Expose selected capabilities outward to other ecosystems through standards rather than building separate connectors per ecosystem
- Use vendor clouds only when there is no viable local path or when cloud adds meaningful and specific value not achievable locally

Consumer ecosystems — Apple Home, Google Home, Amazon Alexa, Samsung SmartThings — should be treated as secondary mobile UI surfaces, voice endpoints, presence sources, and multi-admin peers, not systems of record. They are useful access surfaces for household members who prefer their native mobile or voice environments, but platform state lives in HA and homelab-analytics, not in these ecosystems.

When multiple hubs and ecosystems can each trigger automations or issue commands, explicit authority rules are necessary. Without them, the platform degrades into the failure mode where three hubs and a toaster have all decided that bedtime mode is a democracy. HA is the primary automation authority. Consumer ecosystem actions are treated as operator inputs that HA arbitrates, not as independent automation origins with equal standing.

## Relationship to other platforms and hubs

| Platform type | Recommended role | Authority |
|---|---|---|
| Home Assistant | Edge runtime, actuation, operator UI, voice surface | Primary |
| Matter/Thread devices | Standards-first local networking, multi-ecosystem control | Device layer |
| Consumer ecosystems (Apple, Google, Amazon) | Secondary mobile/voice UI, multi-admin peers | Presentation only |
| Vendor cloud integrations | Fallback where no local path exists | Sandboxed adapter |
| Legacy hubs or proprietary platforms | State ingestion, compatibility bridge | Read-mostly |

## Roadmap alignment

This document provides the product intent for two specific stages of the 10-stage household operating platform roadmap defined in `docs/decisions/household-operating-platform-direction.md`. Stage 5, policy, automation, and action engine, is where the integration surface between the platform and HA is implemented: the semantic bridge, bidirectional event fabric, action dispatch, and approval flows. Stage 6, multi-renderer delivery, is where HA entities and cards become first-class renderers of platform publications, allowing platform outputs to appear natively in HA dashboards, automations, and voice surfaces. This document defines what those stages should satisfy from a product standpoint.

Build-first ordering for the HA integration:

1. HA semantic bridge — map HA devices, entities, and areas to canonical household assets, loads, meters, and locations
2. Bidirectional event and command fabric — WebSocket state ingest, REST and service-call dispatch for actions, MQTT for synthetic entity publication
3. Synthetic entity publication — publish platform outputs back into HA as forecast sensors, budget and price state sensors, maintenance entities, policy-state helpers, and recommended-action entities
4. Energy and tariff policy loop — first real closed loop: platform models prices and load, HA executes and visualizes, operator can override
5. Multi-ecosystem federation — selective Matter multi-admin exposure, family voice and mobile surfaces, compatibility adapters for legacy products
