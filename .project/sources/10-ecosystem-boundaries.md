---
render_levels: [full]
---

## Ecosystem ownership and safety boundaries

- `homelab-analytics` owns its own cluster/infra manifests (`infra/`,
  `charts/`), migrations, and operator tooling. Do not treat project scope as
  authority to reconcile, deploy, or mutate this repository's cluster state
  from outside it.
- Members bound at `render: baseline` (currently `aligned-equity`) do not
  receive this fragment: it is scoped to full members that need
  homelab-analytics' own operational surface, not to boundary members that
  only need the shared project-scope basics.
- Inspect this repository's own `AGENTS.md` and `.agents/overlays/` before
  changing anything under `infra/`, `charts/`, or `migrations/` — project
  scope adds read/union convenience, never new mutation authority.
