---
render_levels: [baseline, full]
---

# Homelab-analytics project scope

This repository participates in the `homelab-analytics` multi-repository
project. The project is a read and instruction projection; each member
repository remains the authority for its own runtime behavior and Git
history.

- Canonical binding and shared sources live in the `homelab-analytics` home
  repository, at its root (in-place topology — no project folder, no
  worktrees).
- Cross-cutting project work is tracked in the homelab-analytics sprintctl
  backlog.
- Use `sprintctl usage --context --project --json` and
  `sprintctl next-work --project --json --explain` from any member repository
  checkout. Every union row must retain its `origin_repo`.
- Direct repository sessions remain supported. Omitting `--project` must keep
  the repository-local sprintctl behavior unchanged.
- Project instructions are baseline guidance followed by member-owned
  overrides. The member's authored `AGENTS.md` remains authoritative for local
  workflow and safety constraints.

Treat a dirty, divergent, or unexpectedly branched member worktree as a stop
condition; resolve it through the owning repository rather than resetting it
from project tooling.
