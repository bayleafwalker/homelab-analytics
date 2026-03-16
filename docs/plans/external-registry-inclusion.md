# External Registry Inclusion Plan

## Objective

Allow operators to include external data pipelines and custom functions from UI-configured custom folders or Git-backed repositories without creating a second execution model outside the existing extension registry contracts.

## Scope

This plan covers:

- external landing, transformation, reporting, and application extensions
- external promotion-handler, transformation-domain, and publication-refresh registrations
- external custom functions that can be referenced by configuration after explicit registration
- control-plane configuration, sync, validation, activation, and audit flow for those external assets

This plan does not cover:

- arbitrary code execution from inline text fields
- hot-reloading code in the middle of request handling
- replacing built-in product logic with an empty-core plugin shell

## Current baseline

The repository already supports external modules through:

- `HOMELAB_ANALYTICS_EXTENSION_PATHS`
- `HOMELAB_ANALYTICS_EXTENSION_MODULES`
- `register_extensions(registry)`
- `register_pipeline_registries(...)`

That is a good bootstrap path, but it is process-local and environment-driven. It does not give the control plane a persisted way to:

- declare a GitHub repository or mounted custom folder
- validate a source before activation
- pin and audit the resolved revision
- show discovered exports in the admin UI
- expose custom functions as explicit config targets

## Design principles

- Keep one runtime loading path. External repositories should still end up as local filesystem imports loaded through the existing registries.
- Keep layer boundaries explicit. External code must register into landing, transformation, reporting, or application layers instead of bypassing them.
- Prefer explicit contracts over free-form imports. Config should reference discovered keys, not Python module strings.
- Make activation revisioned and auditable. A moving branch name is not enough for runtime identity.
- Start with small scaffolding. Local-path and Git-backed acquisition should share one source model and one validation path.

## Proposed model

### 1. Registry sources

Add control-plane entities for external code sources:

- `extension_registry_source`
  - identifies the source
  - stores `source_kind` as `path` or `git`
  - stores location, enabled state, desired ref, optional subdirectory, and secret reference for auth
- `extension_registry_revision`
  - stores the immutable synced result
  - records resolved commit SHA or path fingerprint, manifest digest, sync timestamp, status, and local cache path
- `extension_registry_activation`
  - records which revision set is active for runtime loading
  - makes activation explicit instead of coupling it to save or update

GitHub should be supported through the `git` source kind rather than a separate GitHub-only loader. That keeps the design compatible with Forgejo or plain Git remotes later.

### 2. Source acquisition

Use one acquisition flow for both source kinds:

1. Admin creates a source definition.
2. Worker or control-plane sync resolves the source into a local cache directory.
3. Sync reads a manifest from the resolved source root.
4. Validation checks compatibility and discovered exports.
5. Admin activates the validated revision.
6. API and worker load active revisions on startup or explicit reload.

For `path` sources:

- require the path to be mounted into the container or host runtime already
- compute a fingerprint from manifest plus file metadata for audit purposes

For `git` sources:

- clone or fetch into a managed cache directory under the app data path
- resolve the desired ref to a commit SHA before validation
- store auth as secret references, not inline tokens

### 3. Extension manifest

Require each external source root to expose a small manifest file. Suggested fields:

- manifest schema version
- package or import roots
- extension modules
- optional function modules
- minimum supported homelab-analytics version
- source display name and optional homepage

The manifest exists so the control plane can validate and present the source without making users type Python module names into the UI.

### 4. Registry loading

Keep the existing registration hooks and add one more:

- `register_extensions(registry)`
- `register_pipeline_registries(...)`
- `register_functions(function_registry)`

The runtime should continue to:

- load built-ins first
- load active external source revisions second
- reject duplicate keys across built-in and active external exports before activation succeeds

### 5. Custom function contract

Custom functions should be registered objects, not arbitrary callables imported directly from config.

Each function should declare:

- `function_key`
- `layer`
- `kind`
- `description`
- `module`
- input contract
- output contract
- whether the function is deterministic
- whether it performs side effects

Initial supported function kinds should stay narrow:

- landing validation or projection helpers
- transformation rowset or enrichment helpers
- reporting publication or post-processing helpers

Config should bind by `function_key`, not by module path.

### 6. Config binding model

Do not invent a parallel pipeline system. Extend existing config entities to reference discovered keys where appropriate:

- `transformation_package.handler_key` already fits external promotion handlers
- `publication_definition.publication_key` already fits external reporting publications
- dataset checks, mapping transforms, and future reporting post-process steps should reference registered `function_key` values

The admin UI should surface discovered exports from active revisions so operators can bind them without guessing internals.

### 7. Runtime and reload behavior

Do not start with transparent hot-reload. Initial behavior should be:

- save source
- sync and validate
- activate revision
- reload registries through an explicit admin action or process restart

That keeps failure modes understandable and avoids mutating import state during active requests.

### 8. Security and trust model

External code is trusted operator code. The platform should still reduce avoidable risk:

- keep source auth in secret references
- record who synced and activated a revision
- store resolved revision identifiers in audit history
- require explicit activation for new revisions
- optionally allow provider or repository allowlists later

This feature should not weaken the existing rule that app-facing reporting reads published reporting relations when configured.

## Implementation outline

### Phase 1: Control-plane scaffold

- add data models and persistence for `extension_registry_source`, `extension_registry_revision`, and activation state
- add read-only API endpoints and worker CLI listing for sources and revisions
- add manifest parser and validation contract

### Phase 2: Local-path inclusion

- support mounted custom-folder sources first
- load active path-based revisions into the existing extension and pipeline registries
- add duplicate-key validation and discovered-export inspection

### Phase 3: Git-backed inclusion

- add sync and cache management for Git sources
- support GitHub repositories through the generic Git source path
- persist resolved commit SHA and sync outcomes

### Phase 4: Custom function binding

- add `function_registry`
- load `register_functions(...)` from active revisions
- extend selected config entities to reference `function_key`
- start with a narrow set of supported binding points rather than generic arbitrary execution

### Phase 5: Admin UI

- add admin views for sources, revisions, validation results, activation state, and discovered exports
- expose explicit sync and activate actions
- surface function keys alongside extension and publication keys in relevant config forms

## Verification path

Implementation should be considered complete only when these paths exist:

- repository and requirements docs describe the new source and function contracts
- storage tests cover create, update, sync-status, and activation persistence
- extension-loading tests cover active local-path and Git-backed sources
- API tests cover source CRUD, sync, validation, activation, and discovered-export listing
- UI tests cover admin status and activation flows
- worker tests cover sync and reload commands

## Current status

Implemented on `codex/external-registry-scaffold`:

- control-plane persistence for external registry sources, immutable revisions, and explicit activations
- path-backed and Git-backed source sync with manifest validation and pinned Git commit storage
- runtime loading of activated revisions through the existing extension, pipeline, and function registries
- discovered-function, transformation-handler, and publication-key listing through API, worker CLI, and admin web flows
- `function_key` binding for configured CSV column mappings
- transformation-package and publication-definition create, update, archive, and restore flows with archived-aware validation

## Remaining steps

- add SSH-based Git auth and any provider-specific credential ergonomics beyond HTTPS secret-backed auth
- add an explicit admin-triggered reload action if process restart remains too blunt operationally
- extend custom-function binding beyond CSV mapping transforms into additional validated extension points
- expose broader edit/archive/delete flows for all discovered config entities only where the control-plane dependency model is clear
- decide whether activated external revisions need richer provenance in auth or operational audit views

## Assumptions

- External repositories are operator-maintained Python code, not a public marketplace.
- Mounted custom folders remain important even after Git-backed sync exists.
- Restart or explicit reload is acceptable for the first implementation.
- GitHub support should be implemented as generic Git transport plus secret-managed credentials, not as a one-off GitHub API-only path.
