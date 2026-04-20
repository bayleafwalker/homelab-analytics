WP-12 Assessment: Route-Extension / Composition Hooks

Date: 2026-04-20
Scope: Inspection only - no application code changed.
Question: Are route-extension/composition hooks needed now, after seam cleanup?

---

1. Verdict

Recommendation: Re-defer.

The prerequisite seam cleanup work (WP-1a, WP-2, WP-4) is substantially
incomplete. Adding a pack-based route extension hook now would optimise
for an intermediate architecture that is still in flux. Re-examine when
WP-1a lands and the pipelines split produces a stable packages/domains/
boundary.

---

2. Current route/composition architecture

2a. Route registration (apps/api/app.py)

create_app() at apps/api/app.py:347 accepts 29 positional/keyword
parameters including household-specific objects (lines 348-375):
  service_or_container, subscription_service, contract_price_service,
  ha_bridge, ha_mqtt_publisher, ha_policy_evaluator, ha_action_dispatcher

Inside create_app(), fourteen route modules are registered via explicit
sequential calls (apps/api/app.py:564-737):

  Line 564  register_auth_routes(...)
  Line 581  register_run_routes(...)
  Line 605  register_config_routes(...)
  Line 620  register_contract_routes(...)
  Line 625  register_control_routes(...)
  Line 645  register_control_terminal_routes(...)
  Line 667  register_report_routes(...)
  Line 675  register_assistant_routes(...)
  Line 683  register_homelab_routes(...)
  Line 689  register_category_routes(...)
  Line 694  register_ingest_routes(...)
  Line 719  register_scenario_routes(...)
  Line 725  register_ha_routes(...)
  Line 737  register_adapter_routes(...)

No register_api_routes callback exists on CapabilityPack; no extension
hook exists.

2b. Composition (packages/platform/runtime/)

packages/platform/runtime/builder.py:6-16 imports household-typed services
directly from packages/pipelines/:
  from packages.pipelines.account_transaction_service import AccountTransactionService
  from packages.pipelines.reporting_service import ReportingService
  from packages.pipelines.transformation_service import TransformationService

packages/platform/runtime/container.py similarly imports pipeline types.
The platform runtime is not independent of household domain code.

packages/platform/publication_contracts.py:591 contains a lazy import
from packages.pipelines.publication_confidence_service (Leak 5, unresolved).

---

3. Status of prerequisite seam work (as of 2026-04-20)

WP-4  Clean shared-layer imports of domain manifests
  Status: Partial
  Evidence: packages/platform/ still imports packages.pipelines.* in 15+ places

WP-1a Split finance-domain logic out of packages/pipelines/
  Status: Started, incomplete
  Evidence: packages/domains/ exists (finance, homelab, overview, utilities);
            packages/pipelines/ still has 96 files

WP-2  Remove household-typed fields from platform container
  Status: Not started
  Evidence: builder.py:6 still imports AccountTransactionService;
            create_app() still accepts subscription_service, contract_price_service,
            ha_bridge etc.

WP-7  Add import-boundary enforcement tests
  Status: Not started
  Evidence: No boundary assertions for packages/domains/ exist yet

WP-12 Route-extension / composition hooks
  Scope: Deferred (this item)

WP-1a has begun: commit 3c37f2d moved cashflow_analytics to packages/domains/finance/;
commit 1d5d764 moved cross-domain scenario builders to packages/domains/overview.
the primary split is far from complete with 96 files remaining in packages/pipelines/.

---

4. Is there evidence of repeated pain from hard-coded route registration?

No. The approved plan (docs/plans/substrate-baseline-approved.md:391-393) states:

  "only introduce a pack-based route extension mechanism if hard-coded route
  composition becomes a real pain after the primary seam cleanup"
  Validation: evidence of repeated pain exists before implementation

Neither the git log nor the sprint backlog records any pain ticket, workaround,
or friction attributable to hard-coded route registration. The 14 explicit
register_*_routes() calls are verbose but not a documented source of bugs
or repeated developer cost.

---

5. What the route hook would look like (reference only)

When prerequisites are met, the minimal change is:

Step 1. packages/platform/capability_types.py - add optional field to
    CapabilityPack:
      register_routes: Callable[[FastAPI, AppContainer], None] | None = None

Step 2. apps/api/app.py - replace domain-specific register_*_routes() calls
    for domain packs with a loop:
      for pack in container.capability_packs:
          if pack.register_routes is not None:
              pack.register_routes(app, container)

Step 3. Domain manifests (e.g. packages/domains/finance/manifest.py) -
    implement and wire register_routes.

This is straightforward once the domain boundary is enforced. Doing it
before WP-1a lands would require rewriting the hook again as the domain
package structure stabilises.

---

6. Recommendation

Re-defer WP-12. Re-examine when both of the following are true:

1. WP-1a has landed: packages/pipelines/ is reduced to platform-generic
   files only, with domain logic in packages/domains/finance/,
   packages/domains/homelab/, etc.
2. At least one sprint item documents friction from hard-coded route
   registration (e.g., a new domain pack needed routes and the author
   had to edit app.py to wire them in).

Until those conditions are met, the deferral rationale in
docs/plans/substrate-baseline-approved.md:388-393 remains valid.
