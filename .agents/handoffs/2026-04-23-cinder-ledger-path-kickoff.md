# 2026-04-23 Handoff — cinder-ledger-path kickoff on dirty worktree

## Authoritative kickoff doc

- `docs/plans/cinder-ledger-path-flagship-finance-operator-loop.md`

## Dirty-worktree separation

Dirty files before sprint `#64` implementation starts:

- `.gitignore`
- `AGENTS.md`
- `CLAUDE.md`
- `apps/web/node_modules` (deleted broken symlink)
- `docs/agents/implementation.md`
- `docs/sprint-snapshots/sprint-current.txt`
- `tests/test_repository_contract.py`

Treat that hygiene diff as a separate reviewable scope. Do not mix it into kickoff-doc work or later finance-loop implementation unless a file overlap forces an explicit handoff.

## Dispatch sequencing

1. Resolve overlapping hygiene scope first if a `#64` change needs one of the already-dirty files.
2. Execute `#414` first to lock the exact existing finance reporting destination and post-ingest path, or keep the story route-neutral until it is locked.
3. Execute `#416` next so source freshness/remediation and publication trust vocabulary stay distinct before broader surface wiring expands.
4. Dispatch `#418`, `#417`, and `#415` only after the journey and trust vocabulary are stable enough to avoid churn.

## Scope-boundary notes

- This kickoff scope owns only the authoritative packet and handoff cleanup.
- It does not choose a new route family, renderer lane, or finance-only quasi-surface.
- It does not implement the broader finance loop.
- App/web/API changes for later sprint items must stay thin and route through `packages/application` plus reporting contracts, as recorded in the authoritative kickoff packet.
