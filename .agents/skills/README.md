# Agent Skills

Use `docs/runbooks/project-working-practices.md` to decide which working loop applies before choosing a skill.

- `domain-impact-scan`: use before implementing a new domain, ingestion family, or cross-layer capability. It identifies layer impact, required docs, and blockers.
- `sprint-packet`: use when accepted scope needs to become a sprint-ready implementation packet with deliverables, acceptance, and verification. Use it to register new scope in sprintctl, not to resume an existing item.
- `code-change-verification`: use after repo-tracked changes to standardize what local checks to run and how to report them.
- `pr-handoff-summary`: use when preparing the final reviewer or handoff summary for stable work.
- `sprint-snapshot`: use to render and commit the current sprintctl sprint state as a reviewable plaintext snapshot after live state changes, with the project DB loaded explicitly first.
- `kctl-extract`: use at sprint close to extract decisions, patterns, and lessons from sprintctl events into the kctl knowledge review pipeline, with JSON review/status output available for agent-driven follow-up, then publish and render to `docs/knowledge/knowledge-base.md` when that is in scope.
