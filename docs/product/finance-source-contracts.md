# Finance Source Contracts

## What this is

A source contract defines how the platform ingests, validates, and normalizes data from a specific financial provider or document type. Each contract is a self-contained parser that understands one source format and produces canonical output.

This document describes the contracts available for personal finance ingestion, when to use each one, and how they relate to each other.

**Architecture reference:** `docs/architecture/finance-ingestion-model.md`

The implementation exposes the shared vocabulary in `packages/domains/finance/contracts/base.py` so the parser protocol, the canonical dataset types, and the ingestion lanes stay aligned across new contracts.

---

## Available contracts

### Account transaction contracts

These contracts parse bank account CSV exports into a canonical transaction event stream. Each row becomes one cash movement event.

| Contract | Provider | Format | Key features |
|----------|----------|--------|--------------|
| `op_account_transactions_csv_v1` | OP (Osuuspankki) | Semicolon-delimited CSV, Finnish headers, decimal comma | Archive ID dedupe, repayment message enrichment |
| `revolut_personal_account_statement_v1` | Revolut | Comma-delimited CSV, English headers | Provider state/type preservation, fee tracking, stable source account id |

**When to use:** These are the primary truth for cash movement. Use them to answer "what money moved, when, and between whom."

**Operator workflow:**
1. Export CSV from the bank's web interface or mobile app
2. Upload via the platform's file upload surface or drop into a watched folder
3. The platform detects the format, parses, validates, and lands the data
4. Replaying the same file is safe — deduplication prevents double-counting

### Statement snapshot contracts

These contracts parse statement documents into a point-in-time snapshot of a billing period. The snapshot captures summary fields (balance, payments, fees, interest) and optional line items.

| Contract | Provider | Format | Key features |
|----------|----------|--------|--------------|
| `op_gold_credit_card_invoice_pdf_v1` | OP Gold credit card | PDF | Summary extraction priority, confidence scoring, line items best-effort |

**When to use:** These capture the issuer's view at statement close. Use them for credit card balance tracking, interest/fee monitoring, and minimum-due alerts. Do not use them as the primary record of payments — that comes from the account transaction contracts.

**Operator workflow:**
1. Download the monthly invoice PDF from OP
2. Upload to the platform
3. The parser extracts summary fields with high confidence
4. Line items are extracted where layout permits, with confidence flags
5. Low-confidence extractions produce warnings, not silent bad data

### External reconciliation snapshot contracts

These contracts parse point-in-time exports from external authorities into a snapshot of known debts, credits, or obligations. They are not event streams — they represent "what was known as of this date."

| Contract | Provider | Format | Key features |
|----------|----------|--------|--------------|
| `fi_positive_credit_registry_snapshot_v1` | Finnish positive credit registry (Positiivinen luottotietorekisteri) | Structured text | Multi-credit parsing, income history extraction, installment + revolving variants |

**When to use:** These are reconciliation tools. Use them to cross-check internal loan data against what the credit registry reports. Do not treat registry balances as real-time truth — they may lag by days or weeks.

**Operator workflow:**
1. Request a credit registry extract from the registry service
2. Save the text export
3. Upload to the platform
4. The parser extracts report metadata, per-credit records, and income rows
5. Results are available for reconciliation against internal loan/account data

The parser emits a snapshot record, one record per registered credit, and one record per income row. All records carry the same `snapshot_id` so downstream reconciliation can join them safely.

---

## How contracts relate to each other

Financial data often overlaps across sources. The contracts are designed so each source has a clear role:

| Question | Primary source | Reconciliation source |
|----------|---------------|----------------------|
| What money moved? | Account transaction contracts (OP, Revolut) | — |
| What does my credit card statement say? | Statement snapshot (OP Gold invoice) | Account transactions show the payment |
| What debts do I have? | Internal loan/reference data | Credit registry snapshot |
| What interest/fees am I paying? | Statement snapshot (summary fields) | Account transactions (payment line items) |
| What is my reported income? | Credit registry snapshot (income rows) | — |

### Reconciliation patterns

**Credit card payment:** The OP Gold invoice shows a balance and minimum due. The OP account CSV shows the actual payment as a transaction. These should reconcile — the payment amount in the account CSV should match or exceed the minimum due from the invoice.

**Loan balance:** Internal loan reference data (manual entry or derived from OP CSV repayment enrichment) tracks the balance the operator knows about. The credit registry snapshot reports what the registry knows. Discrepancies suggest data entry errors or timing lag.

**OP CSV repayment enrichment:** When an OP account transaction's message field contains structured repayment text (principal, interest, fees, remaining balance), the parser extracts these into enrichment fields. This provides a transaction-level view of loan repayment composition without requiring a separate data source.

---

## Source acquisition

The platform does not log into banks or pull data automatically. Source acquisition is the operator's responsibility:

1. **OP account CSV:** Export from OP's web banking. Select the date range. Download as CSV.
2. **Revolut CSV:** Export from Revolut app or web. Select "Statement" → date range → CSV format.
3. **OP Gold credit card invoice:** Download from OP's document archive. Monthly PDF.
4. **Credit registry snapshot:** Request from the positive credit registry service. Save the text output.

The platform tracks expected acquisition schedules through the source freshness system (see `docs/product/source-freshness-workflow.md`). When a manual source is overdue, the operator sees a reminder.

## Operator onboarding

The onboarding path should be demo-first and progressively more realistic. A first-time operator should validate the contract flow in a disposable bundle before moving to live sources.

1. Local demo/dev: seed the demo bundle, then use the example CSV and PDF files under `docs/examples/finance-source-contracts/` to verify parsing, landing, and publication end to end.
2. Single-user homelab: onboard one real source at a time through the file upload surface or watched folder, then confirm the first successful ingest before adding the next source.
3. Shared OIDC deployment: follow the same import and freshness path, but enter the upload and admin surfaces through the shared identity path.
4. If validation fails, keep the raw file available for inspection and point the operator to one clear next action: fix the source file and re-upload, open the failed run, or repair the source binding if the contract itself was wrong.

The freshness system remains the reminder surface for scheduled manual exports. When a source is overdue, the operator should be prompted to fetch the missing export rather than infer whether the parser or the source changed.

---

## Validation and error handling

### What validation catches

- **Missing required columns** — parser rejects the file with a clear error naming the missing column
- **Unparseable dates or amounts** — parser reports which rows failed and why
- **Duplicate file upload** — SHA-256 hash match against prior runs; flagged as a warning, not a hard failure
- **Unexpected format** — if the file doesn't match the expected parser, detection fails and the file can be retried with a different contract or the generic CSV pipeline

### What validation does not catch

- **Incorrect date range** — the parser cannot know if you uploaded January's export when you meant February's
- **Missing transactions** — if the bank export is incomplete, the parser has no way to detect gaps
- **Stale data** — the parser processes what it receives; freshness tracking is handled separately

### Error recovery

- Failed validation leaves the raw file in blob storage for inspection
- The operator can fix the source file and re-upload
- Re-upload of a corrected file creates a new run — the original failed run remains in history for audit

---

## Canonical output fields

### Transaction event stream (OP, Revolut)

| Field | Type | Description |
|-------|------|-------------|
| `booked_at` | DATE | Booking date |
| `value_date` | DATE | Value/settlement date (OP only) |
| `amount` | DECIMAL | Signed transaction amount |
| `currency` | STRING | ISO currency code |
| `counterparty_name` | STRING | Payee or payer |
| `description` | STRING | Raw provider description |
| `direction` | STRING | `inflow` or `outflow` |
| `account_id` | STRING | Source account identifier |
| `source_row_fingerprint` | STRING | Stable hash for row-level dedup |
| `provider_type` | STRING | Provider-specific transaction type |
| `provider_state` | STRING | Provider-specific status |

Plus provider-specific fields retained in metadata columns (archive ID, BIC, reference, fee, balance-after-transaction, etc.).

For Revolut personal account exports, the parser derives a stable source account identifier for the personal statement feed so the canonical transaction stream still carries `account_id` even though the raw export does not.

### Statement snapshot (OP Gold invoice)

Header fields as described in the architecture doc. Line items carry a `confidence` field indicating extraction reliability.

### External reconciliation snapshot (credit registry)

Header, credit rows, and income rows as described in the architecture doc. All carry the `snapshot_id` for linkage.
