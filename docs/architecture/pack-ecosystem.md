# Pack Ecosystem

**Classification:** PLATFORM

## Overview

A pack is a versioned bundle that extends the platform: sources, domain
models and marts, reporting outputs, or automation. Built-in packs ship with
the platform and are always loaded. Extension packs come from external
registries (local paths or Git repositories) and are governed by an
operator-facing lifecycle: discover, check, preview, install, upgrade, roll
back, disable, enable, pin.

This document covers the manifest standard, the compatibility model, the
lifecycle state machine and the trust boundaries. The operator view is in
`docs/product/pack-model.md`.

## Building blocks

| Piece | Where | Role |
|---|---|---|
| `PackManifest` / `AdapterPack` | `packages/adapters/contracts.py` | Identity, version, trust level, platform constraint, dependencies, publication relations. `AdapterPack.to_pack_manifest()` gives the uniform view. |
| `PackCompatibilityChecker` | `packages/adapters/pack_compatibility.py` | Platform-version constraint, declared dependencies (with version constraints), unknown publication relations (warnings). |
| `PackLifecycle` | `packages/adapters/lifecycle.py` | In-memory lifecycle over the adapter registry (install/activate/upgrade/rollback) used by adapter runtime code. |
| External registry | `packages/shared/external_registry.py` | Sources, sync, validated revisions and activation of extension modules. Manifest `schema_version` 1. |
| Pack catalog discovery | `packages/shared/pack_catalog.py` | Reads the optional `packs` array from validated, cached registry manifests. |
| Pack lifecycle use cases | `packages/application/use_cases/pack_lifecycle.py` | Plans (dry run) and applies operator lifecycle changes. |
| Pack lifecycle store | `packages/storage/pack_lifecycle.py` (+ SQLite/Postgres mixins) | `pack_installations` and the append-only `pack_lifecycle_events`. |
| API | `apps/api/routes/pack_routes.py` | `/control/packs` catalog, history, plan, actions (admin-only). |
| UI | `apps/web/frontend/app/control/packs/` | Catalog, dry-run preview, confirm with reason, history. |

## Manifest standard

The external registry manifest (`homelab-analytics.registry.json`) keeps
`schema_version: 1`. It names the extension and function modules a source
provides and may add an optional `packs` array that advertises the packs those
modules contain:

```json
{
  "schema_version": 1,
  "import_paths": ["."],
  "extension_modules": ["acme_energy_pack"],
  "packs": [
    {
      "pack_key": "acme_energy",
      "display_name": "Acme Energy",
      "version": "1.2.0",
      "pack_kind": "domain",
      "trust_level": "community",
      "description": "Tariff and forecast marts for Acme Energy contracts.",
      "requires_platform_version": ">=0.1.0",
      "dependencies": ["acme_core>=1.0,<2.0"],
      "publications": [
        {"publication_key": "acme_tariffs", "schema_version": "1.0.0"}
      ],
      "requires_publications": ["utility_cost_summary"]
    }
  ]
}
```

The `packs` key is additive. `parse_extension_registry_manifest` ignores it and
the manifest digest the sync records does not cover it, so existing
registries keep validating unchanged.

| Field | Meaning |
|---|---|
| `pack_key`, `version` | Identity. One catalog entry per (`pack_key`, `version`); the newest revision wins on duplicates. |
| `pack_kind` | `adapter`, `domain`, `reporting`, `automation` or `source`. |
| `trust_level` | `community` or `local`. `verified` is reserved for platform-shipped packs; an external entry claiming it is refused. |
| `requires_platform_version` | Constraint checked by `PackCompatibilityChecker` (`>=`, `<=`, `==`, `>`, `<`, comma-separated). |
| `dependencies` | Other packs, optionally with a version constraint (`acme_core>=1.0`). |
| `publications` | Publication contracts the pack provides, each with a schema version. |
| `requires_publications` | Publication keys the pack consumes. |

Each entry gets an `entry_digest` (SHA-256 of its canonical JSON) so the
lifecycle can tell when the cached entry for an installed version changed.

## Compatibility model

`plan_pack_change` assesses the target entry against the running platform and
the enabled packs:

1. **Platform and dependencies** — `PackCompatibilityChecker` with the built-in
   packs and enabled installed packs as the installed set. Issues block;
   unknown publication relations are warnings.
2. **Publication ownership** — a pack may not provide a publication key that a
   built-in pack or another enabled pack already provides
   (`publication_conflict`). A loaded extension whose capability pack name is
   the same `pack_key` is not counted against itself.
3. **Publication safety** — the plan diffs provided publication contracts before
   and after the change (`added`, `removed`, `schema_changed`, `unchanged`). A
   removal or a schema-major change is *breaking*; breaking a publication that
   another enabled pack lists in `requires_publications` blocks the change
   (`would_break_publication`). Breaking changes nobody depends on are warnings.
4. **Dependent packs** — upgrading, rolling back or disabling a pack that an
   enabled pack depends on blocks when the new state no longer satisfies the
   dependency (`would_break_dependency`).
5. **Trust and cache integrity** — the target must be in the validated local
   cache (`not_in_registry_cache`); rollback and enable re-verify that the
   cached entry still has the digest recorded at install
   (`cached_entry_changed`); external `verified` claims block
   (`untrusted_verified_claim`).
6. **Operator intent** — a pinned pack refuses version changes (`pinned`);
   illegal transitions block (`illegal_transition`, `no_rollback_target`).

The plan lists `contracts_affected` as `publication_key@schema_version` for
every publication the change adds, removes or changes.

## Lifecycle state machine

```
not_installed --install--> enabled
enabled  --disable--> disabled         disabled --enable--> enabled
enabled | disabled --upgrade-->  newer version, same enablement
                                 (current version parked as rollback target)
enabled | disabled --rollback--> parked version, same enablement
                                 (current version parked, so rollback is reversible)
enabled | disabled --pin / unpin--> pinned_version set / cleared
```

Upgrade requires a version newer than the installed one; going back is a
rollback. A disabled pack provides nothing, so enabling it is planned like
adding its publications and re-runs the compatibility check.

Control-plane state (sqlite `0011_pack_lifecycle`, postgres
`0018_pack_lifecycle`):

- `pack_installations` — one row per installed pack: installed, previous and
  pinned versions, enablement, the registry source/revision and entry digest it
  came from (plus the previous entry digest), the versions the cache offered at
  the last change, and the compatibility snapshot of that change.
- `pack_lifecycle_events` — append-only history of every applied **and
  refused** change: action, outcome, from/to version, reason, actor identity,
  compatibility snapshot and the full evaluated plan.

`apply_pack_lifecycle_change` is a compare-and-set: it writes the new row and
its event in one transaction only when the stored installed version,
enablement and pin still match what the plan was made against (SQLite
`BEGIN IMMEDIATE`, Postgres `SELECT ... FOR UPDATE`; a concurrent first
install loses on the primary key). A stale plan is a 409, not a silent
overwrite.

## Trust boundaries

- **No request-time fetch.** Lifecycle routes never sync a source, clone a
  repository or import pack code. The catalog reads manifests that an earlier
  registry sync validated and cached on local disk. Getting a new version into
  the catalog means syncing its source through the external registry controls.
- **Cache integrity.** Discovery re-computes each cached manifest's core
  digest and skips revisions whose manifest changed since sync. Path sources
  read the live directory, so the per-entry digest catches an entry edited
  after install.
- **Admin-only.** Every `/control/packs` route sits under the `/control/` admin
  policy (`admin.write`, service-token scope `admin.write`). Each change needs a
  reason and records the acting identity.
- **Same process.** Extension pack code runs in the platform process with the
  privileges the extension registry contracts expose. Trust levels are
  declarations, not sandboxes; `community` and `local` packs deserve operator
  review before install.
- **Provenance.** Installation rows and events name the registry source,
  revision and entry digest, so a publication contributed by a pack can be
  traced to the exact cached manifest entry.

## Relationship to runtime loading

The lifecycle state is the governed operator record. Runtime loading of
extension modules still follows the external registry activation path
(`resolve_active_extension_settings` → `build_capability_packs`), so
disabling a pack here does not yet unload its module. Gating capability-pack
registration on `pack_installations.enabled` is the next step and is tracked
as deferred work in the roadmap.

## Extension packs and contracts

Extension packs follow the same contract and export path as built-ins:
publications they register through `register_capability_packs` go through
`CapabilityPack.validate()`, cross-pack publication uniqueness and the
publication contract catalog that `apps/api/contract_artifacts.py` exports.
The pack catalog only adds governance in front of that path.
