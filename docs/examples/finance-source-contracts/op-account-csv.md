# OP Account CSV Contract

## Purpose

The `op_account_transactions_csv_v1` contract parses OP account export CSV files into the canonical transaction event stream.

Use it when the source file:

- is semicolon-delimited
- uses Finnish OP headers
- stores amounts with decimal commas
- may include archive identifiers and repayment text in the message field

## Landing contract

Expected source columns:

- `Kirjauspäivä`
- `Arvopäivä`
- `Tilinumero`
- `Saaja/Maksaja`
- `Summa`
- `Valuutta`
- `Viesti`
- `Arkistotunnus`
- `Tapahtuman tila`
- `Tapahtumalaji`

## Canonical output

Each parsed row maps to the finance transaction event stream with these key fields:

- `booked_at`
- `value_date`
- `account_id`
- `counterparty_name`
- `amount`
- `currency`
- `description`
- `direction`
- `source_row_fingerprint`

The parser also preserves:

- `archive_id`
- `provider_state`
- `provider_type`
- repayment enrichment fields when structured loan-payment text is present

## Validation

The contract validates:

- file format and expected header shape
- required OP columns
- date and decimal parsing
- canonical row generation without losing source lineage

## Operator notes

- Re-uploading the same file should be safe because the raw SHA-256 and row fingerprint remain stable.
- Payment rows with repayment breakdown text are enriched in the parser output so downstream loan-repayment logic can reuse the extracted values.
