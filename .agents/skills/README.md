# Agent Skills

## Maintenance

Skills are authored and maintained here in `.agents/skills/` — this is the source of truth and works for all agents via `AGENTS.md`.

`.claude/skills/` holds only symlinks — never content. To add a skill:
1. Create the directory and `SKILL.md` here under `.agents/skills/<name>/`.
2. Add a symlink: `ln -s ../../.agents/skills/<name> .claude/skills/<name>`
3. Register it in this README.

Never copy skill content into `.claude/skills/` — symlinks only.

---

Use `docs/runbooks/project-working-practices.md` to decide which working loop applies before choosing a skill.

- `domain-impact-scan`: use before implementing a new domain, ingestion family, or cross-layer capability. It identifies layer impact, required docs, and blockers.
- `sprint-packet`: use when accepted scope needs to become a sprint-ready implementation packet with deliverables, acceptance, and verification. Use it to register new scope in sprintctl, not to resume an existing item.
- `sprint-resume`: use when the work already exists in sprintctl and you need to pick up or continue an item safely. It covers claim identity checks, handoff behavior, event logging, and snapshot expectations.
- `code-change-verification`: use after repo-tracked changes to standardize what local checks to run and how to report them.
- `pr-handoff-summary`: use when preparing the final reviewer or handoff summary for stable work.
- `sprint-snapshot`: use to render and commit the current sprintctl sprint state as a reviewable plaintext snapshot after live state changes, with the project DB loaded explicitly first.
- `kctl-extract`: use at sprint close to extract decisions, patterns, and lessons from sprintctl events into the kctl knowledge review pipeline, review durable and coordination streams (`--kind all`) with optional JSON output for agent-driven follow-up, then publish and render to `docs/knowledge/knowledge-base.md` when that is in scope.
- `item-done`: use when a sprint item's implementation is complete and verified. Prompts knowledge event capture while context is hot, then commits (one commit per item), runs `done-from-claim`, and refreshes the sprint snapshot.
- `sprint-close`: use at end-of-sprint to run the full close-out sequence in order: verify green test suite → confirm item health → close sprint in sprintctl → commit final snapshot → extract and review knowledge candidates → publish approved entries → optional tag. Encodes the complete sequence so it is not reconstructed ad hoc each time.
