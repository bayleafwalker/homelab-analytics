# Manual Reference Inputs Examples

## Allowed

- `loan_policy` facts for a mortgage interest margin or maturity date
- `account_metadata` facts for a household member or portfolio label
- `transaction_override` facts for a single transaction fingerprint
- `household_member` facts for operator-maintained member metadata
- `portfolio` facts for grouping accounts or assets

## Not allowed

- Re-entering a bank CSV row by row
- Entering 12 months of salary payments as manual facts
- Copying PDF statement line items into reference facts
- Shadowing a source contract with manual values when the source contract already gets the data right

## Example records

```text
entity_type: loan_policy
entity_key:  mortgage-001
attribute:   interest_margin
value:       "0.75"
effective_from: 2025-01-01
source:      operator
created_by:  user-admin-001
note:        "Initial manual entry."
```

```text
entity_type: transaction_override
entity_key:  txn-fingerprint-abc123
attribute:   category
value:       "medical"
effective_from: 2026-03-01
source:      operator
created_by:  user-admin-001
note:        "Pharmacy receipt, 50% reimbursed."
```

## Versioning rule

When a later version of the same `entity_type` + `entity_key` + `attribute` is created, the previous active version is closed by setting its `effective_to` to the day before the new `effective_from`.
