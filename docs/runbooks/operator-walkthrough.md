# Operator Walkthrough — Product Loop from Upload to Operating Picture

**Purpose:** Prove the product loop end-to-end using demo data.  
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
Upload source file
  → Wizard detects format + shows publication preview
    → Dry-run validates row count, date range, issues
      → Ingest lands data
        → Promotion runs transformation
          → Operating Picture updates
```

---

## Walkthrough Steps

### Step 1 — Personal account transactions

1. Go to **Upload** (`/upload`).
2. Drop `sources/personal account/op_personal_account_2025.csv` from the demo bundle.
3. The detection wizard identifies the source as **OP personal account** with high confidence.
4. Review the publication preview: it shows **Monthly Cashflow** and **Household Overview** as direct publications.
5. Confirm ingest.

**What you see after ingest:**
- Post-ingest summary: 144 rows, Jan–Dec 2025, 0 issues.
- Reports page: Monthly Cashflow now shows 12 months of income and spending.
- Salary visible: Employer Corp, EUR 3 200/month.
- Regular transfers out to shared account and Revolut.

---

### Step 2 — Common household account

1. Go to **Upload** → drop `sources/common account/op_common_account_2025.csv`.
2. Detection: **OP common account**.
3. Confirm ingest.

**What you see:**
- Household overview enriched — shared spending now visible.
- Grocery spend: Supermarket Plus, ~EUR 250–320/month.
- Utility payments via direct debit: City Power (~EUR 38–63/month).
- Transport: Metro Transport (~EUR 54–68/month).

---

### Step 3 — Revolut card account

1. Go to **Upload** → drop `sources/revolut/revolut_2025.csv`.
2. Detection: **Revolut personal** format.
3. Confirm ingest.

**What you see:**
- Entertainment spend appears: Netflix EUR 15.99/month.
- Health spend: Pharmacy Central.
- Revolut top-up amounts reconcile with OP personal account outflows — proof of account closure.

At this point the **Money** domain card on the Operating Picture is fully populated.

---

### Step 4 — Utility bills

1. Go to **Upload** → drop `canonical/utility_bills.csv`.
2. Upload via the **utility bills** upload form (`/upload` → select Utility Bills, or use the
   direct ingest endpoint `/ingest/utility-bills`). Note: utility bills use their own ingest
   endpoint and are not covered by the configured-CSV dry-run wizard.
3. Confirm ingest.

**What you see:**
- Utility Cost Summary: electricity (City Power) and water (City Water) for 12 months.
- Electricity seasonal pattern: Jun trough ~257 kWh, Dec peak ~421 kWh.
- Total annual electricity: ~3 762 kWh.

The **Utilities** domain card now has a headline metric and trend indicator.

---

### Step 5 — Subscriptions

1. Go to **Upload** → drop `canonical/subscriptions.csv` → upload via `/upload/subscriptions`.
2. Confirm ingest.

**What you see:**
- Subscription Summary table populated.
- Upcoming renewals appear in the Operating Picture **Upcoming Actions** strip.

---

### Step 6 — Contract prices, budgets, loan repayments

Upload the remaining canonical files in any order:

| File | Upload path |
|------|------------|
| `canonical/contract_prices.csv` | `/upload/contract-prices` |
| `canonical/budgets.csv` | `/upload/budgets` |
| `canonical/loan_repayments.csv` | `/upload/loan-repayments` |

After all three:
- Budget Variance table populated — compare planned vs actual by category.
- Loan Overview: outstanding balance and monthly payment visible.
- Affordability ratio with debt service included in household overview.

---

## Operating Picture — Expected State After All Uploads

| Domain | Headline | Key Attention |
|--------|----------|---------------|
| Money | Net cashflow (12 months) | Card payment loop each month |
| Utilities | Electricity + water cost YTD | Winter peak visible in trend |
| Operations | Active subscriptions | Renewals in upcoming-actions strip |

---

## Freshness and Remediation

1. Go to **Sources** (`/sources`).
2. All datasets should show green (fresh) status after all uploads.
3. To test remediation: wait for one source to show as stale, or simulate by uploading a bad file.
4. The **Upload in context** section at the bottom of Sources shows quick-upload buttons for each stale dataset — no navigation required.
5. After re-upload, the freshness indicator recovers and the Operating Picture confidence band updates.

---

## Verifying the Product Loop

| Check | Where |
|-------|-------|
| Monthly Cashflow populated | `/reports` → Monthly Cashflow |
| Budget Variance shows overage in groceries | `/reports` → Budget Variance |
| Loan overview shows balance | `/reports` → Loan Overview |
| Operating Picture: all domain cards green | `/` (dashboard) |
| Sources: all fresh | `/sources` |
| Runs: all landed | `/runs` |

---

## Demo Bundle Machine Reference

The demo bundle is generated deterministically from a fixed seed. The `journey.json` file in the bundle root contains the machine-readable journey with 8 individual steps (one per data-source artifact), including artifact IDs, upload paths, what each step unlocks, and attention items. This walkthrough groups steps 6–8 into one section for readability; `journey.json` lists each separately.

```
/tmp/homelab-demo/
  manifest.json          — artifact index
  journey.json           — scripted journey metadata
  canonical/             — canonical CSV artifacts (direct upload)
  sources/               — source-format artifacts (wizard upload)
```

To seed the full dataset programmatically:

```
python -m apps.worker.main seed-demo-data --input-dir /tmp/homelab-demo
```
