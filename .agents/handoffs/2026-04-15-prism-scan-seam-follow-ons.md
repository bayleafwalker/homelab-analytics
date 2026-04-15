# 2026-04-15 Handoff — prism-scan-seam follow-on items

## Purpose

Capture the actionable follow-on work surfaced by the dispatch-review dry-run
(sprint #50, `docs/agents/examples/concept-review-dry-run.md`). These are not
defects in the sprint deliverable — the specialist fan-out is complete and committed
at `0b6d235`. These are watchlist findings from the dry-run against
`packages/domains/finance/pipelines/scenario_service.py` that are now candidates
for new sprint items.

## Context the next session needs

- Sprint #50 (`prism-scan-seam`) is closed. All 5 items done.
- The dry-run report is at `docs/agents/examples/concept-review-dry-run.md`. Read
  it for evidence, line numbers, and specialist reasoning before registering items.
- `docs/architecture/stratum-map.md` is the new living reference for stratum assignments.
- No Python files changed in sprint #50 — all deliverables are in `.agents/skills/`
  and `docs/`.
- `make verify-fast` for sprint #50 should be confirmed from the devbox (workstation
  venv shebang is broken; no Python files changed so the risk is low).

---

## Follow-on item groups

### Group A — Scenario placement (root cause, highest leverage)

**One move clears four specialist flags.**

The cross-domain scenario builders — `create_homelab_cost_benefit_scenario` and
`create_tariff_shock_scenario` — live inside `packages/domains/finance/pipelines/scenario_service.py`
but depend on sibling domain packs (homelab, utilities). Moving them to
`packages/domains/overview/` (the designated cross-domain composition pack) or a new
`packages/scenarios/` semantic-engine package resolves:

| Specialist | Finding cleared |
|---|---|
| pack-boundary | Lines 48, 52 — sibling-pack imports for homelab_models / utility_models |
| stratum-coherence | SC-1, SC-3, SC-4 — scenario compute in product pack without ADR |
| semantic-ownership | SO-001 — cross-domain result types (TariffShockResult, HomelabCostBenefitResult) in wrong package |
| repetition | RSA-005 — cross-domain mart table constant imports in finance pack |

**What stays in finance:** `create_loan_what_if_scenario`, loan amortization delegation,
loan-specific freshness checking. The loan scenario is genuinely finance-internal.

**Boundary question to resolve first:** Should the cross-domain scenario builders move to
`packages/domains/overview/` (simplest path, no new package) or to a new
`packages/scenarios/` package in the semantic-engine stratum? The stratum map marks
scenario storage and compute as a semantic-engine responsibility, which argues for a
dedicated package. But the overview pack is already permitted to import siblings, so it's
also a valid landing zone with less ceremony. Resolve this with a short `dispatch-plan`
pass before registering scope — the decision affects whether a new package is created and
how the stratum map gets updated.

**Preconditions before this sprint item can close:**
- `docs/architecture/stratum-map.md` must be updated to assign the destination package.
- If a new `packages/scenarios/` package is created, it must be registered as a
  capability pack or have an explicit stratum annotation.
- The architecture-contract tests that enforce domain-boundary imports must be checked for
  any assertions that would need updating after the move.
- `make verify-fast` must pass.

---

### Group B — scenario_service.py internal cleanup (independent of Group A)

These can be done regardless of where the cross-domain scenario builders end up.
They apply to whatever remains in `scenario_service.py` after Group A.

**B1 — Unit field vocabulary (SO-003, advisory-grade)**

`fact_scenario_assumption.unit` uses `'currency'` (literal string) in most scenario types
but the actual ISO currency code (e.g. `'GBP'`) in loan scenarios. Same column, two
incompatible semantics across rows, no discriminator. Fix: standardize to always store the
currency code for monetary fields, and define an explicit `ALLOWED_UNITS` enum or tuple in
`scenario_models.py` with a docstring explaining `'GBP'` vs `'%'` vs `'months'` etc.
Lines affected: 318, 326, 334, 932, 941, 950, 959, 973, 990, 1004, 1018, 1077, 1289,
1374, 1470, 1477. Needs a migration if scenario data already exists in production stores.

**B2 — SourceFreshnessSummary vs platform type (SO-002)**

`SourceFreshnessSummary` at line 58 partially re-expresses `SourceFreshnessAssessment`
from `packages/platform/source_freshness.py`, using `freshness_state: str` instead of the
platform's `SourceFreshnessState` StrEnum. Either: (a) replace `SourceFreshnessSummary`
with a wrapper struct that composes `SourceFreshnessAssessment`, or (b) formally promote
it to `packages/platform/`. Low blast radius but touches every caller of any
`get_*_comparison` function's return type.

**B3 — Internal helper extractions (RSA-001 through RSA-004, RSA-006)**

Six self-contained refactors, all within `scenario_service.py`:

| ID | Pattern | Occurrences | Helper name |
|---|---|---|---|
| RSA-001 | `DIM_SCENARIO_TABLE` insert block | ×5 | `_insert_dim_scenario()` |
| RSA-002 | `list_publication_confidence_snapshots()` → `SourceFreshnessSummary` block | ×4 | `_build_assumptions_summary()` |
| RSA-003 | `SELECT baseline_run_id FROM dim_scenario WHERE scenario_id = ?` + None guard | ×4 | `_get_scenario_baseline_run_id()` |
| RSA-004 | Cashflow projection loop (months, net/delta, deficit tracking, PROJ_INCOME_CASHFLOW insert) | ×3 | `_project_cashflow_rows()` |
| RSA-006 | `get_tariff_shock_comparison` ≈ `get_income_scenario_comparison` | ×2 | `_get_income_cashflow_comparison_impl(store, scenario_id, is_stale_fn, ...)` |

RSA-001 through RSA-004 are the highest value (repeated logic, divergence risk). RSA-006
is lower priority — `get_expense_shock_scenario` already delegates to the income version,
so the tariff version is the outlier.

**B4 — Projection tables missing publication contracts (SO-006)**

`proj_loan_schedule`, `proj_income_cashflow`, and `proj_homelab_cost_benefit_summary` are
DuckDB tables consumed by the frontend scenarios pages with no `PublicationContract`
registration and no schema versioning. The `baseline_value`/`scenario_value`/`delta_value`
columns are `DECIMAL` in the DDL but string-inserted at runtime — possible type mismatch
depending on DuckDB coercion behaviour. At minimum: add schema-version metadata to
`scenario_models.py`. Ideally: register under a `PublicationContract` so that column-shape
changes are caught by `tests/test_contract_artifacts.py`. Check `tests/test_publication_contract_exports.py`
to understand what registration is required.

---

### Group C — Stratum map maintenance

**C1 — Resolve packages/analytics/ ambiguity**

`packages/analytics/cashflow.py` imports `CanonicalTransaction` from finance domain
internals. The stratum map marks this package as `ambiguous/scaffold`. Decision needed:

- **Option 1 (finance-internal):** Move `cashflow.py` into `packages/domains/finance/`
  where it already belongs semantically, and delete `packages/analytics/`.
- **Option 2 (cross-cutting):** Promote `analytics/` to the semantic-engine stratum,
  break the finance domain import, and replace it with a shared semantic contract or
  a `CanonicalTransaction` export from `packages/platform/`.

Until this is resolved, the stratum-coherence specialist will flag any new code added to
`packages/analytics/`. Pick the option, update `stratum-map.md`, and the specialist stops
flagging.

**C2 — utility_type canonical governance (SO-005)**

`utility_type` (e.g. `'electricity'`) is stored as free-text in `dim_scenario.subject_id`
for tariff scenarios, also used as a filter key against `MART_UTILITY_COST_TREND_MONTHLY_TABLE`.
No canonical enum or `dim_meter` join guard exists. A typo produces a silent empty result.
Fix: add a `KNOWN_UTILITY_TYPES` constant to `utility_models.py` (or a shared location)
and validate `utility_type` against it at `create_tariff_shock_scenario` entry. Low blast
radius.

---

### Group D — Codebase-wide suppression clusters (background item)

These are not specific to `scenario_service.py`. The suppression-drift specialist flagged
five existing clusters. The specialist will keep flagging any new suppressions added near
these clusters. No urgent remediation needed, but a dedicated cleanup sprint at some point
would reduce the noise:

- `packages/pipelines/` re-export cluster (`# noqa: F403`) — tied to the seam reduction
  work already tracked in `pipeline-ambiguity-classification.md`
- `apps/worker/runtime.py` — three `# type: ignore[return]`; a typed protocol for the
  store registry would resolve this
- `packages/storage/postgres_provenance_control_plane.py` — three `# type: ignore`; schema
  typing friction in row coercions
- `packages/domains/finance/contracts/op_gold_invoice_pdf_v1.py` — unscoped `# type: ignore`
  on `pdfplumber` optional import; replace with `TYPE_CHECKING` guard

---

## Recommended registration order

If prioritising by leverage:

1. **Group A** (scenario placement) — requires a `dispatch-plan` pass to settle the
   destination package question before registering scope. Use `sprint-packet` after the
   plan is confirmed.
2. **Group B3** (RSA-001 through RSA-004, internal helpers) — straightforward; can be
   dispatched to `dispatch-build` directly, no design questions.
3. **Group B1** (unit field vocabulary) — advisory-grade semantic fix; check whether a
   migration is needed before starting.
4. **Group C1** (analytics/ ambiguity) — cheap if Option 1 (delete and move); more work
   if Option 2. Decide first.
5. **Group B2, B4, C2, D** — background or opportunistic.

## Reference files

| File | Purpose |
|---|---|
| `docs/agents/examples/concept-review-dry-run.md` | Full dry-run findings with line numbers and specialist reasoning |
| `docs/architecture/stratum-map.md` | Current stratum assignments and known violations table |
| `packages/domains/finance/pipelines/scenario_service.py` | 1,631 LOC target file |
| `packages/domains/finance/pipelines/scenario_models.py` | Projection table schemas (SO-006 target) |
| `docs/architecture/pipeline-ambiguity-classification.md` | Transitional package classification (Group D context) |
