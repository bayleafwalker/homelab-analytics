# Revolut Personal Account CSV Contract

Contract: `revolut_personal_account_statement_v1`

Use this contract for Revolut personal statement CSV exports. It parses the statement into the canonical transaction event stream and preserves provider status and type fields.

## What it captures

- `booked_at` from `Started Date`
- `value_date` from `Completed Date`
- `counterparty_name` from `Description`
- `amount`
- `currency`
- `direction`
- `provider_type` from `Type`
- `provider_state` from `State`
- `fee`
- `balance`

## Operator workflow

1. Export the personal account statement from Revolut as CSV.
2. Upload the file or drop it into the watched inbox.
3. The parser reads the comma-delimited English headers directly.
4. The canonical row output keeps a stable source account id for the personal account feed.

## Notes

- The raw CSV is preserved as landing evidence.
- Re-uploading the same file is safe because raw file deduplication uses the content hash.
- `Fee` and `Balance` are preserved when present so downstream reconciliation can inspect them without re-parsing the source.
