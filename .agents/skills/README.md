# Agent Skills

## Maintenance

Canonical shared skills are maintained in
`/projects/dev/agentops/templates/dispatch/skills/` and synchronized into
`.agents/skills/` from the repository dispatch manifest. Repository-specific
constraints belong in `.agents/overlays/`, which the manifest names explicitly.
`AGENTS.md` points here so the same guidance works for every agent.

`.claude/skills/` should only hold symlinks. To add a skill:
1. Add a reusable skill to the canonical agentops template and select it in the
	repository manifest.
2. Add repository-specific behavior to an overlay instead of copying a shared
	skill body.
3. Run `python /projects/dev/agentops/templates/dispatch/scripts/sync_skills.py check --repo . --apply` from a clean managed skill tree.
4. Register the skill here.

Use `docs/runbooks/project-working-practices.md` to choose the right working loop before opening a skill.

- `domain-impact-scan`: map layer impact, contracts, and blockers for a new domain or cross-layer change.
- `dispatch-plan`: delegate read-only planning for new scope or unresolved architecture decisions.
- `dispatch-build`: delegate spec-complete sprint items or approved implementation slices to build workers.
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

## Repository overlays

- `homelab-analytics.dispatch-workflows.md`: Python verification, layer-boundary,
  claim, and review-specialist rules.
- `review-specialists/`: prompts selected by the homelab review overlay.
