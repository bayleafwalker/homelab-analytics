# OP Gold Credit Card Invoice

Contract: `op_gold_credit_card_invoice_pdf_v1`

Use this contract for OP Gold monthly invoice PDFs. It produces one statement snapshot record plus best-effort line items.

## What it captures

- `statement_date`
- `period_start` and `period_end`
- `due_date`
- `previous_balance`
- `payments_total`
- `purchases_total`
- `interest_amount`
- `service_fee`
- `minimum_due`
- `ending_balance`
- line items with `posted_at`, `merchant`, `amount`, and `confidence`

## Operator workflow

1. Download the monthly invoice PDF from OP.
2. Upload the file or drop it into a watched folder.
3. The parser extracts the statement summary first.
4. Line items are parsed where the layout is clear.
5. Low-confidence line items emit warnings instead of silently being treated as authoritative.

## Notes

- The original PDF is preserved as raw evidence.
- This snapshot is not the source of truth for card payments. Use OP account transactions for the actual payment movement.
- Re-uploading the same PDF is safe because file-level dedupe uses the raw content hash.
