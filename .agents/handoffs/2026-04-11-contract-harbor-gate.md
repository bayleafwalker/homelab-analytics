# 2026-04-11 Handoff - contract-harbor-gate

## Current Sprint State

- Sprint: `#48 contract-harbor-gate - Web Client Contract Hardening`
- Goal: replace weak frontend backend-transport seams with generated-operation typed helpers so protected web routes compile against backend-owned contracts.
- Snapshot: `docs/sprint-snapshots/sprint-current.txt` has been regenerated from live `sprintctl` state.
- Open items:
  - `#315` Generated-operation typed backend read helpers for protected web surfaces - `blocked`
  - `#316` Protected frontend contract drift enforcement and Branch 01 verification - `pending`
- Active claims: none. Claim `#164` for item `#315` was released after recording the blocker.

## What Changed

- `apps/web/frontend/lib/backend.ts` has an in-progress change from the dispatched worker for item `#315`.
- The change imports generated `operations` alongside `paths` and maps GET paths to generated operation IDs so response typing comes from generated OpenAPI operations rather than only from `paths[Path]["get"]`.
- No Python files were changed for this scope.
- Existing unrelated dirty file: `.agents/skills/sprint-close/SKILL.md`. It was already modified before this sprint initiation and was not touched for this handoff.

## Verification Status

Verification is blocked by the local frontend dependency tree, not by a confirmed app type error.

Commands attempted:

```bash
npm --prefix apps/web/frontend run typecheck
```

Result:

- Failed before TypeScript checking because `tsc` was missing from `apps/web/frontend/node_modules/.bin`.

```bash
node apps/web/frontend/node_modules/typescript/bin/tsc --noEmit --project apps/web/frontend/tsconfig.json
```

Results:

- First run reached TypeScript but failed inside `apps/web/frontend/node_modules/@types/node/http2.d.ts` with `TS1010: '*/' expected`, indicating a corrupt dependency file.
- After attempted dependency repair, the command failed with `Cannot find module '../lib/tsc.js'`, indicating the local `typescript` package is incomplete.

```bash
npm --prefix apps/web/frontend install
```

Result:

- Failed with `ENOTEMPTY` while renaming `apps/web/frontend/node_modules/aria-query`.

```bash
npm --prefix apps/web/frontend ci
npm --prefix apps/web/frontend ci --ignore-scripts --no-audit --prefer-offline --loglevel=warn
```

Result:

- Both attempts hung silently in package reification and were killed.
- After the failed repair attempts, `apps/web/frontend/node_modules/.bin` is still missing.

## Sprintctl Notes

- Item `#315` has blocker note `#237`: `Web typecheck blocked by broken frontend node_modules`.
- Item `#315` was moved from `active` to `blocked`.
- Item `#316` remains pending and should not be started until item `#315` can be verified or consciously re-scoped.

## Next Steps

1. Repair the frontend dependency tree before continuing implementation verification.
   - Preferred clean path is to remove the broken `apps/web/frontend/node_modules` tree and rerun `npm --prefix apps/web/frontend ci`.
   - This was not done in the prior session because destructive removal should be an explicit operator choice.
2. Rerun:

```bash
npm --prefix apps/web/frontend run typecheck
```

3. Review the `apps/web/frontend/lib/backend.ts` diff after typecheck. The current path-to-operation-ID map is manually enumerated and may need a generated or type-derived replacement before closing Branch 01.
4. If typecheck passes, reclaim item `#315`, move it back to active if needed, complete the item, then start `#316` for protected frontend drift enforcement and Branch 01 verification.
5. Do not mark either item done until focused web verification passes.
