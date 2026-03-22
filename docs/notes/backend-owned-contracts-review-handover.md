# Backend-Owned Contracts Review Handover

**Status:** merged to `main`
**Main tip commit:** `41475cd`
**Workstream plan:** `docs/plans/backend-owned-contracts-workstream.md`

## Review intent

This note is the handoff for reviewing the completed backend-owned contracts workstream after merge to `main`.

The last merge to `main` covered the remaining stacked branches:

- `feat/contracts-07-extension-pack-contract-parity` — `9f2ed59`
- `feat/contracts-08-contract-governance-and-release` — `41475cd`

If you want the final merged delta only, review:

- `b8b71d6..41475cd`

If you want the full workstream landmarks, review in this order:

- `21c2c7c` — route/publication codegen foundation, generated frontend artifacts, typed contract endpoints
- `b8b71d6` — secondary renderer proof and web discovery completion
- `9f2ed59` — extension-pack contract parity and activation-time validation
- `41475cd` — contract governance, compatibility reporting, and release artifacts

## What shipped

The completed workstream now provides:

- backend-owned OpenAPI and publication contract exports as the canonical frontend source of truth
- generated TypeScript route and publication contracts in the Next.js app
- typed web transport helpers instead of handwritten transport `any`
- semantic publication schemas and backend-owned renderer discovery
- a second renderer proof using the same contract system
- extension-pack contract parity, including activation-time validation of extension capability packs
- contract governance tooling: stale-export detection, compatibility reports, and release-ready contract bundles

## Primary review surfaces

Review these files first:

- [contract_artifacts.py](/projects/dev/homelab-analytics/apps/api/contract_artifacts.py)
- [verify.yaml](/projects/dev/homelab-analytics/.github/workflows/verify.yaml)
- [Makefile](/projects/dev/homelab-analytics/Makefile)
- [capability_registry.py](/projects/dev/homelab-analytics/packages/platform/capability_registry.py)
- [builder.py](/projects/dev/homelab-analytics/packages/platform/runtime/builder.py)
- [external_registry.py](/projects/dev/homelab-analytics/packages/shared/external_registry.py)
- [publication-contracts.md](/projects/dev/homelab-analytics/docs/architecture/publication-contracts.md)
- [contract-governance.md](/projects/dev/homelab-analytics/docs/architecture/contract-governance.md)

Then review the new regression coverage:

- [test_contract_artifacts.py](/projects/dev/homelab-analytics/tests/test_contract_artifacts.py)
- [test_external_registry_support.py](/projects/dev/homelab-analytics/tests/test_external_registry_support.py)
- [test_api_main.py](/projects/dev/homelab-analytics/tests/test_api_main.py)
- [test_verification_tooling.py](/projects/dev/homelab-analytics/tests/test_verification_tooling.py)

## Review checklist

- Confirm `make contract-export-check` fails only when backend-owned JSON exports drift from the code, not when only derived TS output is stale.
- Confirm the compatibility classifier is conservative on removals, requiredness tightening, nullability changes, and type changes.
- Confirm publication breaking changes produce a policy warning when `schema_version` is not major-bumped.
- Confirm the verify workflow now uploads a deliberate contract bundle instead of leaving contract review implicit.
- Confirm extension capability packs validate through the same publication/UI descriptor pipeline as built-ins.

## Verification run before merge

The merged stack was verified with:

- `make contract-export-check`
- `make contract-release-artifacts CONTRACT_BASE_REF=HEAD`
- `make verify-fast`

The generated release bundle shape under `dist/contracts/` is:

- `openapi.json`
- `publication-contracts.json`
- `api.d.ts`
- `publication-contracts.ts`
- `compatibility-summary.json`
- `compatibility-summary.md`
- `manifest.json`

## Residual follow-ups

These are not blockers for the merged workstream, but they remain visible:

- Next.js still prints the existing lockfile patch warning during `next build`, although the build succeeds.
- OPS-05 tag-driven image/chart publishing is still a separate release-ops follow-up.
