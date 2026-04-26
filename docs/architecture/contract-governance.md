# Contract Governance

**Classification:** PLATFORM

The repo now treats backend-owned contracts as release artifacts, not just build inputs.

There are four committed frontend-facing artifacts under `apps/web/frontend/generated/`:

- `openapi.json` — canonical route contract export from FastAPI
- `publication-contracts.json` — canonical publication and UI descriptor export
- `api.d.ts` — generated TypeScript route contracts
- `publication-contracts.ts` — generated TypeScript publication/UI descriptor contracts

## Verification Modes

Use the contract checks for different failure classes:

- `make contract-export-check`
  Detects stale backend-owned source artifacts by exporting fresh `openapi.json` and `publication-contracts.json` and comparing them to the committed generated directory.
- `make web-codegen-check`
  Detects stale derived TypeScript artifacts relative to the committed JSON exports.
- `make contract-release-artifacts`
  Packages a release bundle under `dist/contracts/` containing the JSON exports, generated TypeScript artifacts, compatibility summary, and file-hash manifest.

`make verify-fast` runs the export-sync check before the frontend codegen/typecheck/build steps. That means CI can distinguish:

- stale generated artifacts
- valid but additive contract changes
- valid but breaking contract changes

The first case fails the blocking gate. The latter two are classified in the compatibility summary that accompanies the release bundle.

## Compatibility Policy

The compatibility report classifies contract changes with two severities:

- `additive`
  Examples: new route, new optional request field, a request body becoming optional, new response field, new union member, new publication, new publication column, added publication/UI metadata, new UI descriptor.
- `breaking`
  Examples: removed route, removed field, request field becoming required, request body becoming required, response field becoming optional, type change, `anyOf`/`oneOf` member removal or incompatible member drift, publication removal, publication column removal, semantic-role or renderer-hint regression, UI descriptor navigation drift, or nullability tightening.

Publication contracts also carry `schema_version`. A breaking publication change is expected to come with a major `schema_version` bump. The compatibility report flags missing major bumps as policy warnings.

Publication and UI compatibility is not limited to column presence anymore. The report now treats these renderer-facing surfaces as contract-bearing:

- publication supported renderers and renderer hints
- publication field semantics such as `semantic_role`, `unit`, `grain`, `aggregation`, `filterable`, and `sortable`
- UI descriptor navigation metadata, required permissions, renderer support, renderer hints, and default filters

Route contracts follow an additive-first policy:

1. add the replacement shape or endpoint
2. migrate callers
3. mark the old contract as deprecated in docs/release notes
4. remove it in a later change with an explicit breaking-change report

Publication contracts follow the same pattern, but the publication `schema_version` is the canonical compatibility marker for renderer consumers.

## CI and Release Bundle

The verify workflow now produces a contract artifact bundle intentionally. On pull requests and `main` pushes it writes:

- `dist/contracts/openapi.json`
- `dist/contracts/publication-contracts.json`
- `dist/contracts/api.d.ts`
- `dist/contracts/publication-contracts.ts`
- `dist/contracts/compatibility-summary.json`
- `dist/contracts/compatibility-summary.md`
- `dist/contracts/manifest.json`

The workflow uploads that directory as a CI artifact so reviewers and operators can inspect exactly what changed without regenerating the contracts locally.

## Contributor Workflow

When changing API or publication contracts:

1. update the backend models/definitions
2. run `python -m apps.api.export_contracts`
3. run `PATH=.tooling/node-v20.20.1-linux-x64/bin:$PATH npm --prefix apps/web/frontend run codegen`
4. run `make verify-fast`
5. if the change is breaking, review `dist/contracts/compatibility-summary.md` from `make contract-release-artifacts CONTRACT_BASE_REF=<baseline>`

That keeps stale-artifact failures separate from real compatibility decisions.

## Extraction Boundary

The current compatibility implementation lives in `apps/api/contract_artifacts.py` because it grew out of API contract export tooling. That file now owns more than API assembly: artifact loading, Git-ref reads, export-sync checks, OpenAPI comparison, publication/UI descriptor comparison, schema diffing, markdown/JSON report writing, and release bundle packaging.

That behavior should move behind a platform package boundary when the next contract-governance refactor is scheduled:

- `packages/platform/contract_compat/artifacts.py` for snapshot loading, Git-ref reads, and export-sync checks
- `packages/platform/contract_compat/openapi_compare.py` for route/request/response compatibility
- `packages/platform/contract_compat/publication_compare.py` for publication and UI descriptor compatibility
- `packages/platform/contract_compat/schema_compare.py` for shared JSON-schema diffing
- `packages/platform/contract_compat/report.py` for JSON and markdown summaries
- `packages/platform/contract_compat/release_bundle.py` for manifest and release artifact packaging

`apps/api/contract_artifacts.py` should remain as the compatibility CLI entrypoint so `python -m apps.api.contract_artifacts`, `make contract-export-check`, `make contract-compat-report`, and `make contract-release-artifacts` keep their public behavior. The extraction is successful only if `tests/test_contract_artifacts.py` still exercises the same compatibility policy through the preserved entrypoint.
