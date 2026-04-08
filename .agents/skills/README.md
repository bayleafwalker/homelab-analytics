# Agent Skills

## Maintenance

`.agents/skills/` is the source of truth for skills. `AGENTS.md` points here so the same guidance works for every agent.

`.claude/skills/` should only hold symlinks. To add a skill:
1. Create `.agents/skills/<name>/SKILL.md`.
2. Add the matching symlink under `.claude/skills/`.
3. Register the skill here.

Use `docs/runbooks/project-working-practices.md` to choose the right working loop before opening a skill.

- `domain-impact-scan`: map layer impact, contracts, and blockers for a new domain or cross-layer change.
- `sprint-packet`: turn accepted scope into a sprint-ready packet and register it in `sprintctl`.
- `sprint-resume`: resume an existing sprint item with claim and handoff checks.
- `code-change-verification`: pick and report the smallest useful verification for the change.
- `dispatch-review`: run the findings-first review pass on a stable code-bearing scope.
- `pr-handoff-summary`: write the compact reviewer or handoff summary.
- `workflow-artifact-capture`: promote reusable workflow examples into `docs/training/` or `kctl`.
- `sprint-snapshot`: render the current sprint state into the committed snapshot.
- `kctl-extract`: extract and review sprint-close knowledge candidates.
- `item-done`: verify, capture lessons, and close a finished sprint item.
- `sprint-close`: run the full sprint close-out sequence.
