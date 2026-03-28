# Finnish Positive Credit Registry Snapshot

## Purpose

The `fi_positive_credit_registry_snapshot_v1` contract parses the structured text export from the Finnish positive credit registry into a reconciliation snapshot.

Use it when you need to compare external authority data against the platform's internal loan and repayment view.

## Landing contract

Expected source shape:

- structured text export
- a snapshot header with requestor and report metadata
- one or more credit records
- optional income history rows

## Canonical output

The parser emits:

- one snapshot record
- one credit record per reported credit
- one income record per reported income month

All emitted rows share a `snapshot_id` so the snapshot can be joined safely during reconciliation.

## Validation

The contract validates:

- header presence and snapshot metadata
- declared credit count against parsed credit rows
- numeric and date parsing for credit and income rows

## Operator notes

- The registry is a reconciliation source, not operational truth.
- Balance and income data can lag the source of truth; treat it as an external checkpoint.
- Keep the raw export unchanged so the archive hash remains stable for replay and audit.
