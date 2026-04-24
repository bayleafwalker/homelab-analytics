# Operator Walkthrough — Canonical Finance Loop from Upload to /reports

**Purpose:** Prove the canonical finance operator journey end-to-end using demo data.
**Time:** ~10 minutes with the demo bundle pre-generated.  
**Audience:** Operators and developers validating the first-week onboarding experience.

---

## Prerequisites

1. A running instance of the platform (API + web, `make dev`).
2. The demo bundle generated in a local directory:

```
docker exec -it worker python -m apps.worker.main generate-demo-data --output-dir /tmp/homelab-demo
```

Or from the project root:

```
python -m apps.worker.main generate-demo-data --output-dir /tmp/homelab-demo
```

The demo bundle contains 12 months of realistic household data (2025) across three account sources, utility bills, subscriptions, contract prices, budgets, and loan repayments.

---

## The Product Loop

```
Upload or refresh source file
  → Source freshness and remediation in /sources and /runs
    → /reports monthly operating view
      → Expense-shock action
```

---

## Walkthrough Steps

### Step 1 — Personal account transactions

1. Go to **Upload** (`/upload`).
2. Drop `sources/personal account/tapahtumat20250101-20251231.csv` from the demo bundle.
3. The detection wizard identifies the source as **OP personal account** with high confidence.
4. Review the publication preview: it shows **Monthly Cashflow** and **Household Overview** as direct publications.
5. Confirm ingest.

**What you see after ingest:**
- Post-ingest summary: 144 rows, Jan–Dec 2025, 0 issues.
- `/reports`: Monthly Cashflow now shows 12 months of income and spending.
- Salary visible: Employer Corp, EUR 3 200/month.
- Regular transfers out to shared account and Revolut.

---

### Step 2 — Common household account

1. Go to **Upload** → drop `sources/common account/tapahtumat20250101-20251231.csv`.
2. Detection: **OP common account**.
3. Confirm ingest.

**What you see:**
- Household overview enriched - shared spending now visible.
- Grocery spend: Supermarket Plus, ~EUR 250-320/month.
- Utility payments via direct debit: City Power (~EUR 38-63/month).
- Transport: Metro Transport (~EUR 54-68/month).

---

### Step 3 — Revolut card account

1. Go to **Upload** → drop `sources/revolut/account-statement_2025-01-01_2025-12-31_en-us_demo.csv`.
2. Detection: **Revolut personal** format.
3. Confirm ingest.

**What you see:**
- Entertainment spend appears: Netflix EUR 15.99/month.
- Health spend: Pharmacy Central.
- Revolut top-up amounts reconcile with OP personal account outflows - proof of account closure.

At this point `/reports` has the monthly finance inputs needed for the canonical operating view.

---

### Step 4 — Utility bills

1. Go to **Upload** (`/upload`) → drop `canonical/utility_bills.csv`.
2. The wizard detects the utility bill format. Confirm ingest.

**What you see:**
- Utility Cost Summary: electricity (City Power) and water (City Water) for 12 months.
- Electricity seasonal pattern: Jun trough ~257 kWh, Dec peak ~421 kWh.
- Total annual electricity: ~3 762 kWh.

The **Utilities** domain card now has a headline metric and trend indicator.
The monthly finance view in `/reports` now includes utility context alongside cashflow.

---

### Step 5 — Subscriptions

1. Go to **Upload** (`/upload`) → drop `canonical/subscriptions.csv`.
2. Confirm ingest.

**What you see:**
- Subscription Summary table populated.
- Upcoming renewals appear in the Operating Picture **Upcoming Actions** strip.

---

### Step 6 — Contract prices, budgets, loan repayments

Upload the remaining canonical files in any order:

| File | Upload path |
|------|------------|
| `canonical/contract_prices.csv` | `/upload` |
| `canonical/budgets.csv` | `/upload` |
| `canonical/loan_repayments.csv` | `/upload` |

After all three:
- Budget Variance table populated - compare planned vs actual by category.
- Loan Overview: outstanding balance and monthly payment visible.
- Affordability ratio with debt service included in household overview.

With those uploads complete, `/reports` is the stable monthly finance read surface.

### Step 7 — Expense shock

1. Open `/reports`.
2. Launch the expense-shock action from the monthly finance view.
3. Confirm the baseline, projected value, and delta are visible before you proceed.

---

## Operating Picture - Expected State After All Uploads

| Domain | Headline | Key Attention |
|--------|----------|---------------|
| Money | Net cashflow (12 months) | Card payment loop each month |
| Utilities | Electricity + water cost YTD | Winter peak visible in trend |
| Operations | Active subscriptions | Renewals in upcoming-actions strip |

---

## Control Terminal

The control terminal (`/control/terminal`) is a deliberate operator aid, not an undocumented escape hatch. Commands are grouped by task:

- **diagnostics** - inspect live state: `status`, `runs`, `dispatches`, `heartbeats`, `freshness`
- **remediation** - trace and validate: `publication-audit`, `lineage`, `verify-config`
- **configuration** - review registered entities: `source-systems`, `source-assets`, `ingestion-definitions`, `publication-definitions`, `schedules`
- **admin** - users, tokens, audit trail, and queue operations: `users`, `tokens`, `audit`, `enqueue-due`

Use `help` to list all commands. The `/control/terminal/commands` endpoint returns each command with its `group`, `usage`, and `mutating` flag.

---

## Freshness and Remediation

1. Use **Sources** (`/sources`) to inspect freshness and source-level remediation.
2. Use **Runs** (`/runs`) to inspect run-level remediation such as retry or re-upload guidance.
3. All datasets should show green (fresh) status after all uploads.
4. To test remediation: wait for one source to show as stale, or simulate by uploading a bad file.
5. The **Upload in context** section at the bottom of Sources shows quick-upload buttons for each stale dataset.
6. After re-upload, the freshness indicator recovers and the monthly finance view in `/reports` reflects the refreshed input.

### Remediation actions

When a run fails or a source goes stale, the platform surfaces a specific action. There are four possible actions:

| Action | When it appears | What to do |
|---|---|---|
| `retry` | Run failed but payload is intact | POST `/runs/{run_id}/retry` - no re-upload needed |
| `upload_missing_period` | Run failed, payload unavailable or rejected | Correct and re-upload the source file for the affected period |
| `inspect_binding` | Run passed but promotion was skipped | Check source system / dataset contract / column mapping in Sources config |
| `fix_contract` | Run rejected due to schema or column violations | Fix the source file or update the dataset contract, then re-upload |

The run detail endpoint (`GET /runs/{run_id}`) returns `remediation.action` and `remediation.reason` in its response.
The source freshness endpoint (`GET /control/source-freshness`) returns `suggested_action` per dataset.
Both use the same four-action vocabulary, so the Sources page and the run detail tell the same story.

The active reporting backend (DuckDB warehouse or Postgres published-reporting) is disclosed at `GET /control/operational-summary` under the `reporting_mode`, `reporting_mode_label`, and `publication_backend_active` fields.

---

## Verifying the Product Loop

| Check | Where |
|-------|-------|
| Monthly Cashflow populated | `/reports` |
| Budget Variance shows overage in groceries | `/reports` |
| Loan overview shows balance | `/reports` |
| Expense-shock action is reachable | `/reports` |
| Sources: all fresh | `/sources` |
| Runs: all landed | `/runs` |

---

<!-- BEGIN DEMO BUNDLE MACHINE REFERENCE -->

## Demo Bundle Machine Reference

Generated from `packages/demo/bundle.py` and `infra/examples/demo-data/manifest.json`.
Run `python scripts/generate_walkthrough_reference.py` to regenerate after bundle changes.

**Bundle layout after `make demo-generate`:**

```
/tmp/homelab-demo/
  manifest.json          — artifact index (17 artifacts, seed 20260324)
  journey.json           — scripted journey metadata (8 steps)
  canonical/             — canonical CSV artifacts
  sources/               — source-format artifacts
```

**Upload sequence (operator journey):**

| Step | Artifact ID | File | Upload path | Routability |
|------|-------------|------|-------------|-------------|
| 1 | `op_personal_account_csv` | `sources/personal account/tapahtumat20250101-20251231.csv` | `/upload` | `supported_now` |
| 2 | `op_common_account_csv` | `sources/common account/tapahtumat20250101-20251231.csv` | `/upload` | `supported_now` |
| 3 | `revolut_account_csv` | `sources/revolut/account-statement_2025-01-01_2025-12-31_en-us_demo.csv` | `/upload` | `supported_now` |
| 4 | `utility_bills_canonical_csv` | `canonical/utility_bills.csv` | `/upload` | `supported_now` |
| 5 | `subscriptions_canonical_csv` | `canonical/subscriptions.csv` | `/upload` | `supported_now` |
| 6 | `contract_prices_canonical_csv` | `canonical/contract_prices.csv` | `/upload` | `supported_now` |
| 7 | `budgets_canonical_csv` | `canonical/budgets.csv` | `/upload` | `supported_now` |
| 8 | `loan_repayments_canonical_csv` | `canonical/loan_repayments.csv` | `/upload` | `supported_now` |

**Template-only artifacts (reference; not yet routable for direct upload):**

| Artifact ID | File | Format |
|-------------|------|--------|
| `account_transactions_canonical_csv` | `canonical/account_transactions.csv` | `csv` |
| `credit_card_statement_2026_01` | `sources/credit card/Lasku_01012026.pdf` | `pdf` |
| `credit_card_statement_2026_01_summary` | `sources/credit card/Lasku_01012026.summary.json` | `json` |
| `credit_card_statement_2026_02` | `sources/credit card/Lasku_01022026.pdf` | `pdf` |
| `credit_card_statement_2026_02_summary` | `sources/credit card/Lasku_01022026.summary.json` | `json` |
| `credit_card_statement_2026_03` | `sources/credit card/Lasku_01032026.pdf` | `pdf` |
| `credit_card_statement_2026_03_summary` | `sources/credit card/Lasku_01032026.summary.json` | `json` |
| `loan_registry_html` | `sources/loans/Luottotietorekisteriote - Positiivinen luottotietorekisteri.html` | `html` |
| `loan_registry_text` | `sources/loans/luottorekisteriote.txt` | `txt` |

<!-- END DEMO BUNDLE MACHINE REFERENCE -->
