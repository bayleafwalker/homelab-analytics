# Golden Ingestion and Publication Track

The canonical operator path from file upload to published reporting surface.

---

## The track

```
Source file (CSV, PDF, JSON)
  → /upload  (configured-CSV wizard — detection, dry-run, validation)
    → /ingest/configured-csv  (API landing endpoint)
      → promote_source_asset_run  (transformation + mart refresh)
        → PublicationDefinition  (registered in CapabilityPack)
          → /reports, /sources, /control/source-freshness
```

Every step has a corresponding remediation surface:
- Validation failure → `/runs/{run_id}` → retry or re-upload
- Stale source → `/sources` → upload corrected file
- Publication freshness → `/control/source-freshness` → `freshness_state` from `evaluate_source_freshness`

---

## Canonical surfaces on the golden path

| Surface | Role |
|---------|------|
| `/upload` | Configured-CSV wizard: detect, preview, dry-run, confirm |
| `/ingest/configured-csv` | API landing endpoint for the wizard |
| `/ingest/dry-run` | Validation preview before commit |
| `/ingest/detect-source` | Source detection preflight |
| `/runs` / `/runs/{run_id}` | Post-ingest summary, retry, remediation |
| `/sources` | Source freshness, staleness, quick-upload for recovery |
| `/control/source-freshness` | Unified freshness view (per source asset, from `evaluate_source_freshness`) |
| `/reports` | Stable monthly finance read surface |
| `/onboarding` | First-week operator checklist; status pills from freshness DTO |

---

## Worker CLI on the golden path

| Command | Role |
|---------|------|
| `watch-schedule-dispatches` | Production: runs scheduled ingestion and promotion |
| `ingest-configured-csv` | Operator: ingest a single file via configured-CSV pipeline |
| `generate-demo-data` | Setup: writes the committed demo bundle |
| `seed-demo-data` | Setup: lands and promotes the full demo bundle; used by `make first-run` |

---

## Non-golden paths

The following are dev/demo shortcuts, not part of the operator ingestion track.
They bypass the configured-CSV detection wizard and are not exercised by the walkthrough.

### API endpoints

| Endpoint | Note |
|----------|------|
| `POST /ingest` | Legacy direct ingest; superseded by `/ingest/configured-csv` |
| `POST /ingest/account-transactions` | Legacy typed ingest; dev/demo shortcut |
| `POST /ingest/subscriptions` | Domain-specific endpoint; operator path is configured-CSV |
| `POST /ingest/contract-prices` | Domain-specific endpoint; operator path is configured-CSV |

### Worker CLI commands

| Command | Note |
|---------|------|
| `ingest-account-transactions` | Dev/demo shortcut; bypasses the configured-CSV pipeline |

### Domain services

| Service | Note |
|---------|------|
| `UtilityBillService` | Dev/demo shortcut; operator path is configured-CSV |
| `BudgetService` | Dev/demo shortcut; operator path is configured-CSV |
| `LoanService` | Dev/demo shortcut; operator path is configured-CSV |

---

## Publication coverage gaps

Steps 7 (budgets) and 8 (loan repayments) of the demo journey unlock pipeline-internal
mart tables (`mart_budget_variance`, `mart_loan_schedule_projected`) that are not yet
registered as `PublicationDefinition` entries in any `CapabilityPack`. Their `publication_keys`
in `build_journey()` are empty until a pack is extended.

The CI drift test (`tests/test_demo_journey_verification.py::test_journey_steps_with_no_publication_key_coverage_are_documented`)
will fail if this gap is closed without updating `build_journey()`.
