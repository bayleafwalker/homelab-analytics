# Concept Review Dry Run — scenario_service.py

**Date:** 2026-04-14
**Scope:** Full-file review of `packages/domains/finance/pipelines/scenario_service.py` (1,631 LOC)
**Diff:** None — full-file review used as smoke test for the specialist fan-out. All findings
are pre-existing; severity ceiling is **watchlist** throughout.
**Specialists run:** 7 (all parallel)

---

## Triage

**Blockers:** 0  **Advisories:** 0  **Watchlist:** 22 (across 6 specialists)
**Degraded specialists:** none — all 7 returned valid JSON

No blockers found. Scope is clear for handoff. (Dry-run produces findings, not fixes —
acting on watchlist items is a separate sprint item.)

---

## Acceptance gate (smoke test)

| Requirement | Met? | Evidence |
|---|---|---|
| God-class finding from specialist 4 | ✅ | scenario_service.py at 1,631 LOC — watchlist |
| Cross-pack coupling with specific import lines from specialist 1 | ✅ | line 48 (homelab_models), line 52 (utility_models) |
| Findings from ≥ 2 additional specialists | ✅ | stratum-coherence (4), semantic-ownership (6), repetition (6), test-quality (4), suppression-drift (3) |
| All 7 specialists returned output | ✅ | No degraded specialists |

---

## Watchlist

### Pack boundary (specialist 1)

| File | Line | Finding | Evidence |
|---|---|---|---|
| `packages/domains/finance/pipelines/scenario_service.py` | 48 | Finance pack imports homelab domain internals | `from packages.domains.homelab.pipelines.homelab_models import MART_SERVICE_HEALTH_CURRENT_TABLE, MART_WORKLOAD_COST_7D_TABLE` |
| `packages/domains/finance/pipelines/scenario_service.py` | 52 | Finance pack imports utilities domain internals | `from packages.domains.utilities.pipelines.utility_models import MART_UTILITY_COST_TREND_MONTHLY_TABLE` |
| `packages/domains/utilities/pipelines/transformation_utilities.py` | 8 | Utilities pack imports finance domain internals | `from packages.domains.finance.pipelines.contract_price_models import FACT_CONTRACT_PRICE_TABLE, DIM_CONTRACT_TABLE` |

**Recommendation:** Route cross-domain scenario inputs through `packages/domains/overview/` (the
designated composition pack) or through a shared reporting contract. Finance pack should not
import homelab or utilities model internals directly.

---

### Stratum coherence (specialist 2)

The file lives in `packages/domains/finance/` (product pack stratum), but `scenario storage
and compute` is explicitly a **semantic engine** responsibility per the architecture doc and
stratum map.

| ID | Lines | Finding |
|---|---|---|
| SC-1 | 1–1631 | Scenario storage and compute engine living in a product pack with no ADR justifying the placement |
| SC-2 | 48–54 | Cross-pack sibling imports (merged with pack-boundary above — both specialists flagged lines 48–54) |
| SC-3 | 748–1151, 1418–1517 | Cross-domain scenario builders (`create_homelab_cost_benefit_scenario`, `create_tariff_shock_scenario`) owned by finance pack instead of overview or a semantic-engine package |
| SC-4 | 1–7 | No ADR or classification note documenting the decision to place scenario storage and compute in the finance product pack |

**Recommendation (SC-1, SC-3):** A `packages/scenarios/` package in the semantic-engine
stratum, or promotion of generic scenario storage/compute into `packages/platform/`, would
correctly locate the engine. Finance-specific loan amortization may remain a pack-local plugin;
cross-domain scenario builders (homelab, tariff shock) should move to `packages/domains/overview/`.

---

### Semantic ownership (specialist 3)

| ID | Lines | Finding |
|---|---|---|
| SO-001 | 58–174 | Four cross-domain result dataclasses (`TariffShockResult`, `HomelabCostBenefitResult`, etc.) defined inside the finance domain — any consumer in overview/API must take a finance import dependency |
| SO-002 | 58–66 | `SourceFreshnessSummary` partially re-expresses `SourceFreshnessAssessment` from `packages/platform/source_freshness.py`, with `freshness_state: str` instead of the platform's `SourceFreshnessState` StrEnum — semantic drift without a bridge callout |
| SO-003 | 318, 326, 932, 941 (+ 12 others) | `fact_scenario_assumption.unit` uses heterogeneous vocabulary: ISO currency code (e.g. `'GBP'`) in loan scenarios, literal string `'currency'` in other scenarios, plus `'%'`, `'months'`, `'ratio'` — same column, incompatible semantics across rows, no schema-level discriminator |
| SO-004 | 756–761, 1176–1207 | Cross-domain mart reads use raw table-name constants from sibling domain packs rather than reporting-layer contracts; `est_monthly_cost` in homelab marts is documented as a heuristic — trust source not versioned |
| SO-005 | 1174–1517 | `utility_type` (e.g. `'electricity'`) stored as free-text in `dim_scenario.subject_id` with no canonical enum or `dim_meter` join guard; typo produces silent empty result |
| SO-006 | scenario_models.py:65–134 | Projection tables (`proj_loan_schedule`, `proj_income_cashflow`, `proj_homelab_cost_benefit_summary`) are app-facing but have no `PublicationContract` and no schema versioning; `baseline_value`/`scenario_value` are `DECIMAL` in DDL but string-inserted at runtime |

**Highest-value finding (SO-003):** The `unit` column has mixed semantics across scenario
types — a semantic regression that crossed scenario types without a contract version bump.
Standardise to an explicit enum in `scenario_models.py`.

---

### God class and file size (specialist 4)

| File | LOC | Finding |
|---|---|---|
| `packages/domains/finance/pipelines/scenario_service.py` | 1,631 | 2.7× the 600 LOC threshold; 40 module-level functions across 5 scenario domains; no individual function exceeds 80 lines (largest: 22 lines), but 5 unrelated scenario types in one namespace create high cyclomatic complexity |

**Production watchlist (calibration anchors — unchanged, present every run):**

| File | LOC |
|---|---|
| `packages/pipelines/transformation_service.py` | 1,484 |
| `packages/demo/bundle.py` | 1,384 |
| `packages/storage/sqlite_execution_control_plane.py` | 1,154 |
| `packages/storage/postgres_execution_control_plane.py` | 989 |
| `packages/storage/sqlite_source_contract_catalog.py` | 939 |
| `packages/domains/overview/pipelines/transformation_overview.py` | 880 |
| `packages/storage/control_plane.py` | 838 |
| `packages/shared/external_registry.py` | 775 |
| `packages/storage/sqlite_asset_definition_catalog.py` | 734 |
| `packages/demo/seeder.py` | 732 |
| `packages/storage/postgres_source_contract_catalog.py` | 741 |
| `packages/domains/utilities/pipelines/transformation_utilities.py` | 685 |
| `packages/storage/postgres_asset_definition_catalog.py` | 671 |
| `packages/domains/homelab/pipelines/ha_bridge_ingestion.py` | 658 |
| `packages/domains/finance/pipelines/transformation_transactions.py` | 650 |
| `packages/platform/publication_contracts.py` | 617 |

---

### Repetition vs abstraction (specialist 5)

Six internal repetition patterns found in `scenario_service.py`:

| ID | Occurrences | Pattern | Extraction target |
|---|---|---|---|
| RSA-001 | ×5 (lines 300–308, 1053–1066, 1273–1281, 1358–1367, 1453–1461) | `DIM_SCENARIO_TABLE` insert block — same 6 keys, only `scenario_type` / `subject_id` vary | `_insert_dim_scenario()` private helper |
| RSA-002 | ×4 (lines 490–504, 1124–1138, 1559–1573, 1608–1622) | 12-line `list_publication_confidence_snapshots()` → `list[SourceFreshnessSummary]` block | `_build_assumptions_summary()` helper |
| RSA-003 | ×4 (lines 208–214, 226–232, 869–875, 1212–1218) | `SELECT baseline_run_id FROM dim_scenario WHERE scenario_id = ?` opener + None guard | `_get_scenario_baseline_run_id()` helper |
| RSA-004 | ×3 (lines 1296–1316, 1382–1402, 1484–1504) | Cashflow projection loop — iterate months, compute net/delta, track deficit month, accumulate `PROJ_INCOME_CASHFLOW` rows | `_project_cashflow_rows()` helper |
| RSA-005 | lines 47–53 | Finance scenario service imports mart table name constants from homelab and utilities packs directly | Shared constants module in `packages/shared/` or `packages/platform/` |
| RSA-006 | lines 1536–1582, 1585–1631 | `get_tariff_shock_comparison` and `get_income_scenario_comparison` near-identical except for staleness-check call | `_get_income_cashflow_comparison_impl(store, scenario_id, is_stale_fn, ...)` |

RSA-001 through RSA-004 are self-contained refactors within `scenario_service.py`. RSA-005
overlaps with the pack-boundary and stratum-coherence findings (same cross-pack imports, different
angle). RSA-006 is a structural cleanup opportunity within finance.

---

### Test quality (specialist 6)

| Finding | Detail |
|---|---|
| No integrated test file | Tests split across 4 files: `test_scenario_service.py` (467 LOC), `test_income_scenario_service.py` (215 LOC), `test_scenario_api.py` (489 LOC), `test_income_scenario_api.py` (171 LOC). No single source-of-truth test module for a 1,631 LOC service. |
| 18 scattered private helpers | `_is_stale`, `_is_tariff_scenario_stale`, `_is_homelab_cost_benefit_stale`, `_is_income_scenario_stale`, and 14 others are module-level — no class encapsulation makes unit isolation for individual scenario types difficult |
| 4 divergent staleness functions | Each uses a different freshness-signature approach; mutation testing would require updates in all 4 test files |
| 9 result dataclasses with overlapping fields | `is_stale` and `assumptions_summary` repeated across all result types; no shared base or protocol |

**Test calibration anchor watchlist:**

| File | LOC |
|---|---|
| `tests/test_api_app.py` | 2,758 |
| `tests/test_worker_cli.py` | 1,703 |
| `tests/test_adapter_contracts.py` | 1,502 |
| `tests/test_api_main.py` | 1,280 |
| `tests/test_architecture_contract.py` | 1,276 |
| `tests/control_plane_test_support.py` | 1,260 |

---

### Suppression drift (specialist 7)

`packages/domains/finance/pipelines/scenario_service.py` contains **zero** suppression
annotations — no `# type: ignore`, `# noqa`, or `# pragma: no cover`. No findings for
this file.

**Known hot-spot clusters (codebase watchlist):**

| Location | Suppressions |
|---|---|
| `packages/pipelines/` (legacy re-export cluster) | `# noqa: F403` throughout — extends facade surface |
| `apps/worker/runtime.py` | `# type: ignore[return]` around runtime repository accessors |
| `packages/storage/postgres_provenance_control_plane.py` | `# type: ignore` around row dict coercions |
| `packages/pipelines/publication_confidence_service.py` | `# type: ignore` on freshness/confidence coercions |
| `packages/domains/finance/contracts/op_gold_invoice_pdf_v1.py` | Unscoped `# type: ignore` on `pdfplumber` import |

---

## Cross-specialist observations

Two findings converge from different angles on the same root cause:

**Root cause: scenario computation for cross-domain inputs (homelab, utilities) lives inside
the finance product pack.** This single placement decision is the source of:
- Pack-boundary violations (lines 48, 52) — specialist 1
- Stratum coherence finding SC-1/SC-3 — specialist 2
- Semantic ownership finding SO-001 (cross-domain result types in wrong package) — specialist 3
- Repetition finding RSA-005 (cross-domain constant imports) — specialist 5

The fix for all four is the same structural move: relocate cross-domain scenario builders to
`packages/domains/overview/` or a future `packages/scenarios/` semantic-engine package.
Finance pack retains only loan-specific scenario logic.
