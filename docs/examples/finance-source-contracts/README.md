# Finance Source Contract Examples

This directory collects the disposable examples used to validate the finance onboarding flow before touching real sources.

Use these files as the first-pass demo bundle:

| File | Purpose |
|---|---|
| `op-account-csv.md` | OP account export example and canonical transaction flow |
| `op-gold-invoice.md` | OP Gold statement snapshot example |
| `revolut-personal-account-csv.md` | Alternate account-transaction example |
| `credit-registry-snapshot.md` | External reconciliation snapshot example |

Recommended operator sequence:

1. Start with `op-account-csv.md` to validate the basic file-upload and landing path.
2. Add `op-gold-invoice.md` to verify statement parsing and confidence handling.
3. Use `revolut-personal-account-csv.md` to confirm a second account-transaction provider still lands canonically.
4. Finish with `credit-registry-snapshot.md` to confirm reconciliation-oriented sources remain separate from operational truth.

The example set is meant for local demo/dev and documentation validation. Real operator onboarding should still follow the profile-specific startup stories in `docs/product/source-freshness-workflow.md`.
