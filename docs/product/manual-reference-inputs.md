# Manual Reference Inputs

## What this is

Some important financial data cannot come from file exports. Loan policy terms, account ownership, classification overrides, and reimbursement flags are the operator's knowledge — they live in the operator's head or in a contract document, not in a bank CSV.

Manual reference inputs are the platform's pathway for this kind of sparse factual knowledge. They are versioned, effective-dated, and auditable.

**Architecture reference:** `docs/architecture/finance-ingestion-model.md`

The control plane stores these facts in a `reference_facts` table. Each record is a versioned fact row, not a mutable blob, so the history of each operator decision remains queryable.

---

## The boundary

Manual reference inputs are for **sparse facts**, not bulk data.

The clearest test: if you are typing in more than a handful of values to describe one real-world fact, you are probably doing it wrong. Bulk event data belongs in Lane A (file-based structured import). Statement line items belong in Lane B (document parser).

| Allowed | Not allowed |
|---------|-------------|
| Loan interest margin (one value per loan) | Full transaction history for an account |
| Account → household member mapping | All credit card transactions from a statement |
| Category override for one transaction | 50 manual budget entries |
| Reimbursement flag for one payment | Manually re-entering a bank export row by row |
| Loan maturity date (from contract document) | |
| Portfolio or bucket assignment for a loan | |

---

## Data model

### Reference fact

Each manual fact is an immutable versioned record:

| Field | Type | Description |
|-------|------|-------------|
| `fact_id` | STRING | Generated unique identifier |
| `entity_type` | STRING | What kind of thing this fact is about |
| `entity_key` | STRING | Identifier of the specific entity |
| `attribute` | STRING | Which property is being set |
| `value` | STRING | The value (JSON-encoded for complex types) |
| `effective_from` | DATE | When this fact becomes active |
| `effective_to` | DATE \| NULL | When this fact expires (null = currently active) |
| `source` | STRING | How it was entered (`operator`, `import`) |
| `created_by` | STRING | Principal ID of the creator |
| `created_at` | DATETIME | When this version was created |
| `note` | STRING \| NULL | Optional operator note explaining the fact |

The storage layer also tracks `closed_by` and `closed_at` when an older version is superseded or closed.

### Versioning

When an operator updates a reference fact (e.g., an interest margin changes), a new record is created with a new `effective_from`. The previous version's `effective_to` is set to one day before the new record's `effective_from`. History is preserved.

```
fact_id: f-001
  entity_type: loan_policy
  entity_key:  mortgage-001
  attribute:   interest_margin
  value:       "0.85"
  effective_from: 2022-01-01
  effective_to:   2024-12-31     ← closed when updated

fact_id: f-002
  entity_type: loan_policy
  entity_key:  mortgage-001
  attribute:   interest_margin
  value:       "0.75"
  effective_from: 2025-01-01
  effective_to:   null           ← currently active
```

Querying "what was the interest margin on 2023-06-01?" returns `f-001`. Querying "what is the interest margin now?" returns `f-002`.

### Entity types

| Entity type | Entity key | Example attributes |
|-------------|------------|-------------------|
| `loan_policy` | Loan identifier | `interest_margin`, `maturity_date`, `repayment_type`, `collateral_type` |
| `account_metadata` | Account number or ID | `household_member`, `portfolio`, `purpose`, `label` |
| `transaction_override` | Transaction ID or fingerprint | `category`, `is_reimbursable`, `split_party`, `note` |
| `household_member` | Member identifier | `name`, `role`, `share_percentage` |
| `portfolio` | Portfolio identifier | `name`, `description`, `member_ids` |

---

## Use cases

### Loan policy facts

When a loan contract is signed, the terms live in a document, not in a CSV. The operator enters:
- Interest margin (the spread above the reference rate)
- Reference rate type (e.g., 12-month Euribor)
- Repayment type (annuity or equal principal)
- Maturity date
- Collateral type (e.g., residential property)

These facts feed scenario calculations (loan what-if, affordability) and reconciliation (does the registry snapshot match what we have?).

```
entity_type: loan_policy
entity_key:  mortgage-001
attributes:
  interest_margin: "0.75"
  reference_rate:  "euribor_12m"
  repayment_type:  "annuity"
  maturity_date:   "2052-01-01"
  collateral_type: "residential_property"
```

### Account metadata

Accounts from different sources need to be mapped to household members or portfolios for household-level views.

```
entity_type: account_metadata
entity_key:  FI12-3456-7890-1234
attributes:
  household_member: "partner"
  portfolio:        "household_joint"
  label:            "Joint current account"
```

### Transaction classification override

The platform's category assignment for a transaction may be wrong. The operator can override it:

```
entity_type: transaction_override
entity_key:  txn-fingerprint-abc123
attributes:
  category:        "medical"
  is_reimbursable: "true"
  note:            "Pharmacy receipt — 50% reimbursed by employer health plan"
```

Classification overrides are effective immediately (`effective_from` = transaction date or today). They do not have expiry unless the override itself should be time-limited.

---

## What this is NOT for

### Not for bulk data entry

If you need to enter more than ~10 rows of data, use a file import instead. The platform has a configured CSV pipeline for exactly this purpose.

**Wrong:** Manually entering 12 months of salary payments as reference facts.
**Right:** Exporting your bank CSV and using the OP account transactions contract.

### Not for statement line items

If you have a PDF statement, use the document parser contract. Do not re-enter the line items by hand.

**Wrong:** Entering each credit card charge from a PDF invoice as a transaction override.
**Right:** Uploading the invoice PDF through the OP Gold invoice contract.

### Not for overriding what a source contract got right

If the file-based parser produced correct data, do not create reference facts to shadow it. Reference facts are for data that has no file source.

---

## Audit expectations

All reference fact operations are auditable:

- Creation: `created_by`, `created_at` on every record
- Updates: new version created; prior version closed with `effective_to`
- Deletion: not supported — facts can be closed (set `effective_to` = today) but not deleted
- History: full version history queryable by entity type + entity key

This means an operator can always answer: "What did we believe about mortgage-001's interest margin on a given date, and who entered it?"

---

## Operator UX sketch

The admin surface for manual reference inputs should offer:

1. **Browse by entity type** — list all loan_policy facts, all account_metadata facts, etc.
2. **Browse by entity** — show all attributes for one loan or account, current and historical
3. **Create fact** — form with entity_type, entity_key, attribute, value, effective_from, note
4. **Update fact** — creates a new version with a new effective_from; shows diff from previous
5. **Close fact** — sets effective_to = today; fact is no longer active
6. **Audit trail** — show full version history for any entity

The form should validate that the `entity_key` matches a known entity in the platform (loan, account, transaction) where possible. Unknown entity keys are allowed for forward-declarations but should produce a warning.
