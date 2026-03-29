# Agent Surfaces

## Goal

Stage 10 adds agent-facing retrieval and proposal surfaces without making agents the source of truth. The semantic layer remains publication contracts, policy state, and approved execution paths.

## Retrieval model

Agents should read through a semantic publication index, not by probing landing or transformation tables directly.

The retrieval surface is built from:

- publication contracts
- UI descriptor contracts
- renderer metadata attached to publication definitions
- lineage-aware publication metadata already exposed by the existing contract layer

The index is intentionally read-only. It exists so agents can answer questions like:

- which publication covers monthly cash flow?
- what renderer surfaces exist for a given publication?
- which fields and semantic roles are available?

The index should not duplicate business logic or invent a second publication registry. It should normalize the already-published contract model into a search-friendly form.

## Action proposals

Agent-generated actions must remain proposals until they pass the existing approval-gated execution path.

Required properties:

- proposals reference publication state or policy outputs
- proposals are auditable and traceable
- proposals do not bypass approval, policy, or authentication checks
- execution remains owned by the platform's existing action engine
- proposal drafts capture their source kind, source key, and creator before approval
- the approval and dismissal paths remain the only state transitions that release a proposal

The assistant layer may suggest, summarize, or draft proposals. It may not directly mutate canonical state or dispatch external actions without the approval path.

## Assistant scope

The initial assistant surfaces should stay narrow:

- finance questions over publication outputs
- utilities questions over publication outputs
- operations questions over publication outputs

The assistant should return explainable responses with pointers back to publication metadata and, where relevant, policy or lineage context. It should not reach into landing or transformation internals as a shortcut.

The first implemented entrypoint is a single read-only `GET /api/assistant/answer` surface that routes finance, utilities, and operations questions through the semantic publication index and reporting layer. Each answer should name the publication-backed sources it used and point back to the corresponding publication-index and report paths.

## Boundary rules

- Read from publication contracts, not raw tables.
- Propose actions, do not execute them.
- Prefer existing policy and approval rails.
- Keep the semantic layer reusable by dashboards, APIs, and future agents.
