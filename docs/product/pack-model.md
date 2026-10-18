# Pack Model

## What a pack is

A pack is a named, versioned piece of household capability that plugs into
the platform. Examples: a utility provider's tariff model, a country-specific
tax mart, a new budget view, an automation policy template.

There are two kinds:

- **Built-in packs** ship with the platform (finance, utilities, home
  automation, and so on). They are always loaded and cannot be removed from
  the operator surface.
- **Extension packs** come from an external registry: a local folder or a Git
  repository the operator has added as a registry source. They are installed,
  upgraded, rolled back, disabled and enabled from **Control → Packs**
  (`/control/packs`).

Each pack declares what it **provides** (publications, with a schema version
per publication) and what it **needs** (a platform version range, other packs,
publications it reads). Those declarations are what the platform checks before
letting a change through.

## How operators find packs

1. Add or sync a registry source under the external registry controls. A sync
   validates the source and caches it locally.
2. Open **Control → Packs**. The catalog lists every pack version that a
   validated, cached revision advertises, with a compatibility badge per
   version:
   - **compatible** — nothing blocks installing or upgrading to it;
   - **compatible with warnings** — allowed, but something deserves a look
     (for example, it reads a publication this platform does not publish yet);
   - **incompatible** — the reason is shown inline (platform too old, a
     missing dependency, a publication already provided by another pack, an
     external pack claiming `verified` trust).

The page never downloads anything. New versions appear after a registry sync.

## How operators change packs

Every change starts as a **preview** (a dry run). The preview shows:

- the version change (for example `1.0.0 → 1.1.0`) and enablement;
- each publication the change adds, removes or changes, with its schema
  versions and which installed packs depend on it;
- the contracts affected (`publication@schema`);
- any blocking diagnostics, in which case the change cannot be confirmed.

Confirming needs a **reason**. The platform re-plans the change when it is
confirmed; if anything changed in between (another admin acted, the cache
changed), the change is refused rather than applied on stale information.

| Action | When it is offered | What it does |
|---|---|---|
| Install | Pack not installed | Installs the chosen version (default: newest cached) and enables it. |
| Upgrade | A newer cached version exists | Moves to it; the current version becomes the rollback target. |
| Roll back | A rollback target exists | Returns to the previous version; the current one becomes the rollback target, so a rollback can itself be undone. |
| Disable / Enable | Installed | Stops / resumes the pack providing its publications. Enable re-checks compatibility. |
| Pin / Unpin | Installed | A pinned pack refuses upgrades and rollbacks until unpinned. |

## What the platform refuses

A change is refused, and the refusal is recorded, when:

- the platform version or a declared dependency does not fit;
- the version is not in the validated local registry cache, or its cached
  entry changed since it was installed;
- the pack would provide a publication another pack already provides;
- the change would remove a publication, or change its schema major version,
  while another enabled pack reads it;
- the change would leave another enabled pack's dependency unsatisfied
  (including disabling a pack others depend on);
- the pack is pinned to a different version;
- an external registry entry claims `verified` trust.

## History

Every applied and every refused change appears in the history with time,
pack, action, version change, outcome, actor and reason. Refusals list their
blocking reasons. History is append-only.

## Who can do this

Only admins. Readers and operators do not see the page, and service tokens
need the `admin.write` scope.

## Current limits

- Disabling a pack records the operator decision; the extension module itself
  is still loaded through the external registry activation until runtime
  gating lands.
- Packs are not uninstalled from the surface yet; disable is the supported way
  to stop using one.
- Pack lifecycle state is not part of control-plane snapshot export/import yet.

Architecture detail: `docs/architecture/pack-ecosystem.md`.
