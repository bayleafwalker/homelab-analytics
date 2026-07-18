# Homelab analytics dispatch workflow overlay

## Planning and domain boundaries

- Read `docs/agents/planning.md` for planning work and preserve the layer split:
  `landing` owns immutable raw payloads and validation, `transformation` owns
  normalized models and SCD handling, and `reporting` owns dashboard and API
  marts.
- Do not add landing-to-dashboard shortcuts. App-facing paths must use
  reporting-layer models.
- For a connector or cross-layer change, check its landing contract, validation
  checks, canonical mapping target, SCD Type 2 implications for dimensions, and
  reporting-layer output paths before implementation.
- Update relevant architecture documentation under `docs/` when a design or
  stack choice changes, and update requirements under `requirements/` when their
  status or phase changes.

## Verification and delivery

- Prefer environment-self-sufficient Make targets: `make lint`, `make
  typecheck`, and `make test-target TEST="tests/test_<area>.py -x --tb=short"`.
  Run targeted tests in the foreground and use their exit code before an item
  done transition.
- Behavior changes require corresponding tests. After API, auth, policy, or
  architecture-boundary changes, include
  `make test-target TEST="tests/test_architecture_contract.py -x --tb=short"`.
- Run `make verify-fast` before a PR or CI-triggering push. `make test` and
  `make verify-all` are broader operator-initiated checks, not routine
  in-session item gates.
- On a failing targeted check, diagnose, repair, and rerun up to five times
  before escalating a design decision or persistent failure.

## Claim and worktree discipline

- Use `sprintctl agent-protocol --json` as the authoritative claim lifecycle.
  Keep claim proof with the orchestrator; local recovery files under
  `.sprintctl/claims/` aid crash recovery but do not transfer identity.
- Use isolated worktrees for concurrent scopes that touch overlapping files.
  Never pass claim tokens to a subagent or treat stale workspace metadata as
  ownership proof.
- Commit at the smallest reviewable scope boundary rather than mechanically per
  item. Do not commit with failing targeted tests.

## Review specialists

- The selected specialist prompts live in `.agents/overlays/review-specialists/`.
  `pack-boundary`, `god-class-file-size`, `test-quality`, and
  `suppression-drift` are narrow pattern scans; `stratum-coherence`,
  `semantic-ownership`, and `repetition-vs-abstraction` require semantic
  synthesis.
- Resolve model choice through the action and manifest routing data, not the
  prompt text. Specialist output is a JSON array with `specialist`, `severity`,
  `file`, `line`, `finding`, `evidence`, `recommendation`, and `blocker`.
- Consolidate duplicate findings by file, line, and root cause. When specialist
  fan-out is unavailable, run the architecture contract check and record a
  manual review against the same layer and ownership rules.