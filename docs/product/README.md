# Product documentation

**Classification:** APP

This directory supplements the ADR workflow with a product-design workflow.

The architecture decisions in `docs/decisions/` answer questions such as:

- what structural direction the platform should take
- where boundaries should exist
- how execution, publication, auth, and extension loading should be organized
- what refactors are justified to keep the codebase maintainable

The product documents in `docs/product/` answer different questions:

- what household problems the platform must solve first
- what questions each domain must answer for a real user
- which outputs are first-class product surfaces rather than incidental internal artifacts
- what functionality is core, supporting, or explicitly deferred
- how new work should be evaluated before it becomes architecture for architecture's sake

## Relationship to the ADR workflow

Use both tracks together.

### ADR track
Use an ADR when you are deciding:

- architecture direction
- package and runtime structure
- boundary ownership
- storage and publication contracts
- execution and extension mechanisms
- auth, policy, and deployment patterns

### Product track
Use a product design document when you are deciding:

- what user problem is worth solving next
- which household questions the platform should answer
- what counts as a product-grade output
- which capability pack should be strengthened or introduced next
- what the acceptance criteria are for a slice beyond "the code is cleaner now"

## Current core product set

The current product direction is defined by these documents:

- `core-household-operating-picture.md`
- `initial-capability-packs-and-publications.md`
- `core-product-design-workflow.md`
- `frontend-ui-delivery-playbook.md`
- `product-slice-template.md`
- `finance-source-contracts.md`
- `source-freshness-workflow.md`
- `manual-reference-inputs.md`
- `retro-crt-shell.md`

For UI-heavy work, pair the product workflow with `frontend-ui-delivery-playbook.md` and the example artifact bundle in `docs/examples/ui-contracts/`.

## Rules of use

1. Do not create an ADR when the real unresolved question is product value.
2. Do not create a product document that quietly smuggles in architecture decisions without naming them.
3. New platform work should point to a product question it improves.
4. New product work should point to the architecture constraints it must respect.
5. If a proposed feature mainly preserves optionality, it is support work, not core product work.

## Decision precedence

When there is tension between documents:

- security, correctness, and data lineage constraints are not optional
- accepted ADRs define the architectural guardrails
- product documents define what should be made valuable inside those guardrails
- implementation plans should derive from both, not from either in isolation
