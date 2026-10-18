"""Transformation service facade over domain-specific warehouse processors.

Domain operations live in per-concern facets under
``packages.pipelines.transformation_facets``; this module owns construction,
schema bootstrap, domain-registry dispatch, and publication confidence wiring.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any

from packages.domains.finance.pipelines.asset_models import (
    CURRENT_DIM_ASSET_VIEW,
    DIM_ASSET,
)
from packages.domains.finance.pipelines.budget_models import (
    CURRENT_DIM_BUDGET_VIEW,
    DIM_BUDGET,
)
from packages.domains.finance.pipelines.category_rules import (
    ensure_category_storage,
)
from packages.domains.finance.pipelines.category_seed import seed_system_categories
from packages.domains.finance.pipelines.loan_models import (
    CURRENT_DIM_LOAN_VIEW,
    DIM_LOAN,
)
from packages.domains.finance.pipelines.subscription_models import (
    CURRENT_DIM_CATEGORY_VIEW,
    CURRENT_DIM_CONTRACT_VIEW,
    DIM_CATEGORY,
    DIM_CONTRACT,
)
from packages.domains.finance.pipelines.transaction_models import (
    CURRENT_DIM_ACCOUNT_VIEW,
    CURRENT_DIM_COUNTERPARTY_VIEW,
    DIM_ACCOUNT,
    DIM_COUNTERPARTY,
    TRANSFORMATION_AUDIT_TABLE,
)
from packages.domains.finance.pipelines.transformation_assets import (
    ensure_asset_storage,
)
from packages.domains.finance.pipelines.transformation_balances import (
    ensure_balance_storage,
)
from packages.domains.finance.pipelines.transformation_budgets import (
    ensure_budget_storage,
)
from packages.domains.finance.pipelines.transformation_contract_prices import (
    ensure_contract_price_storage,
)
from packages.domains.finance.pipelines.transformation_loans import (
    ensure_loan_storage,
)
from packages.domains.finance.pipelines.transformation_subscriptions import (
    ensure_subscription_storage,
)
from packages.domains.finance.pipelines.transformation_transactions import (
    ensure_transaction_storage,
    populate_counterparty_category_ids,
)
from packages.domains.homelab.pipelines.ha_service import (
    ensure_ha_storage,
)
from packages.domains.homelab.pipelines.home_automation_models import (
    CURRENT_DIM_ENTITY_VIEW,
    DIM_ENTITY,
)
from packages.domains.homelab.pipelines.homelab_models import (
    CURRENT_DIM_SERVICE_VIEW,
    CURRENT_DIM_WORKLOAD_VIEW,
    DIM_SERVICE,
    DIM_WORKLOAD,
)
from packages.domains.homelab.pipelines.transformation_home_automation import (
    ensure_home_automation_storage,
)
from packages.domains.homelab.pipelines.transformation_homelab import (
    ensure_homelab_storage,
)
from packages.domains.homelab.pipelines.transformation_infrastructure import (
    ensure_infrastructure_storage,
)
from packages.domains.overview.pipelines.transformation_overview import (
    ensure_overview_storage,
)
from packages.domains.utilities.pipelines.battery_plan_outcome import (
    BatteryPlanProfileResolution,
    ensure_battery_plan_storage,
    load_battery_plan_profile,
)
from packages.domains.utilities.pipelines.transformation_utilities import (
    ensure_utility_storage,
)
from packages.domains.utilities.pipelines.utility_models import (
    CURRENT_DIM_METER_VIEW,
    DIM_METER,
)
from packages.pipelines.publication_confidence_service import (
    compute_and_record_publication_confidence,
)
from packages.pipelines.scenario_registry import (
    ScenarioRegistry,
    get_default_scenario_registry,
)
from packages.pipelines.transformation_domain_registry import (
    TransformationDomainRegistry,
    get_default_transformation_domain_registry,
)
from packages.pipelines.transformation_facets.assets import AssetTransformationMixin
from packages.pipelines.transformation_facets.commitments import CommitmentTransformationMixin
from packages.pipelines.transformation_facets.home_automation import (
    HomeAutomationTransformationMixin,
)
from packages.pipelines.transformation_facets.homelab import HomelabTransformationMixin
from packages.pipelines.transformation_facets.overview import OverviewTransformationMixin
from packages.pipelines.transformation_facets.scenarios import ScenarioTransformationMixin
from packages.pipelines.transformation_facets.transactions import TransactionTransformationMixin
from packages.pipelines.transformation_facets.utilities import UtilityTransformationMixin
from packages.pipelines.transformation_household import (
    ensure_household_member_storage,
    get_household_members,
    seed_default_household_member,
    upsert_household_member,
)
from packages.pipelines.transformation_refresh_registry import (
    PublicationRefreshRegistry,
    get_default_publication_refresh_registry,
)
from packages.platform.publication_keys import PublicationKeyResolver
from packages.storage.control_plane import ControlPlaneStore
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataStore


class TransformationService(
    TransactionTransformationMixin,
    CommitmentTransformationMixin,
    AssetTransformationMixin,
    UtilityTransformationMixin,
    OverviewTransformationMixin,
    HomelabTransformationMixin,
    HomeAutomationTransformationMixin,
    ScenarioTransformationMixin,
):
    """Loads validated landing data into the transformation and reporting layers."""

    def __init__(
        self,
        store: DuckDBStore,
        *,
        control_plane_store: ControlPlaneStore | None = None,
        publication_refresh_registry: PublicationRefreshRegistry | None = None,
        domain_registry: TransformationDomainRegistry | None = None,
        scenario_registry: ScenarioRegistry | None = None,
        run_metadata_store: RunMetadataStore | None = None,
        battery_plan_profile_loader: Callable[[], BatteryPlanProfileResolution]
        | None = None,
        clock: Callable[[], datetime] | None = None,
        publication_key_resolver: PublicationKeyResolver | None = None,
    ) -> None:
        self._store = store
        self._battery_plan_profile_loader = (
            battery_plan_profile_loader or load_battery_plan_profile
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._control_plane_store = control_plane_store
        # Landing validation outcomes feed publication confidence; optional.
        self._run_metadata_store = run_metadata_store
        # Canonicalizes confidence-snapshot keys; identity when not injected.
        self._publication_key_resolver = publication_key_resolver or PublicationKeyResolver()
        self._publication_refresh_registry = (
            publication_refresh_registry or get_default_publication_refresh_registry()
        )
        self._domain_registry = domain_registry or get_default_transformation_domain_registry()
        self._scenario_registry = scenario_registry or get_default_scenario_registry()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._store.ensure_dimension(DIM_ACCOUNT)
        self._store.ensure_dimension(DIM_COUNTERPARTY)
        self._store.ensure_current_dimension_view(DIM_ACCOUNT, CURRENT_DIM_ACCOUNT_VIEW)
        self._store.ensure_current_dimension_view(
            DIM_COUNTERPARTY,
            CURRENT_DIM_COUNTERPARTY_VIEW,
        )
        ensure_transaction_storage(self._store)

        self._store.ensure_dimension(DIM_CATEGORY)
        self._store.ensure_dimension(DIM_CONTRACT)
        self._store.ensure_current_dimension_view(DIM_CATEGORY, CURRENT_DIM_CATEGORY_VIEW)
        self._store.ensure_current_dimension_view(DIM_CONTRACT, CURRENT_DIM_CONTRACT_VIEW)
        seed_system_categories(self._store)
        ensure_subscription_storage(self._store)
        ensure_contract_price_storage(self._store)

        self._store.ensure_dimension(DIM_METER)
        self._store.ensure_current_dimension_view(DIM_METER, CURRENT_DIM_METER_VIEW)
        ensure_utility_storage(self._store)
        ensure_battery_plan_storage(self._store)

        self._store.ensure_dimension(DIM_ASSET)
        self._store.ensure_current_dimension_view(DIM_ASSET, CURRENT_DIM_ASSET_VIEW)
        ensure_asset_storage(self._store)

        self._store.ensure_dimension(DIM_ENTITY)
        self._store.ensure_current_dimension_view(DIM_ENTITY, CURRENT_DIM_ENTITY_VIEW)
        ensure_home_automation_storage(self._store)

        self._store.ensure_dimension(DIM_BUDGET)
        self._store.ensure_current_dimension_view(DIM_BUDGET, CURRENT_DIM_BUDGET_VIEW)
        ensure_budget_storage(self._store)

        self._store.ensure_dimension(DIM_LOAN)
        self._store.ensure_current_dimension_view(DIM_LOAN, CURRENT_DIM_LOAN_VIEW)
        ensure_loan_storage(self._store)
        ensure_balance_storage(self._store)

        ensure_overview_storage(self._store)
        ensure_category_storage(self._store)

        self._store.ensure_dimension(DIM_SERVICE)
        self._store.ensure_current_dimension_view(DIM_SERVICE, CURRENT_DIM_SERVICE_VIEW)
        self._store.ensure_dimension(DIM_WORKLOAD)
        self._store.ensure_current_dimension_view(DIM_WORKLOAD, CURRENT_DIM_WORKLOAD_VIEW)
        ensure_homelab_storage(self._store)
        ensure_infrastructure_storage(self._store)
        ensure_ha_storage(self._store)

        ensure_household_member_storage(self._store)
        seed_default_household_member(self._store)
        populate_counterparty_category_ids(self._store)

    def load_domain_rows(
        self,
        domain_key: str,
        rows: list[dict[str, Any]],
        *,
        run_id: str | None = None,
        effective_date: date | None = None,
        source_system: str | None = None,
    ) -> int:
        return self._domain_registry.load(
            self,
            domain_key,
            rows,
            run_id=run_id,
            effective_date=effective_date,
            source_system=source_system,
        )

    def refresh_publications(
        self,
        publication_keys: list[str] | tuple[str, ...],
    ) -> list[str]:
        """Refresh publications and compute confidence snapshots.

        Refreshes the specified publications and records their confidence
        snapshots in the control plane for upstream consumption by dashboards,
        APIs, and other confidence-aware features.
        """
        refreshed = self._publication_refresh_registry.refresh(self, publication_keys)
        self.record_publication_confidence(refreshed)
        return refreshed

    def record_publication_confidence(
        self,
        publication_keys: list[str] | tuple[str, ...],
    ) -> None:
        """Record confidence snapshots, e.g. again after lineage is recorded."""
        if self._control_plane_store is not None:
            as_of = datetime.now(timezone.utc)
            for publication_key in publication_keys:
                try:
                    compute_and_record_publication_confidence(
                        publication_key,
                        self._control_plane_store,
                        self._store,
                        as_of=as_of,
                        run_metadata_store=self._run_metadata_store,
                        key_resolver=self._publication_key_resolver,
                    )
                except Exception:
                    # Silently skip on error; confidence snapshot is optional
                    # and should not block publication refresh
                    pass

    def count_domain_rows(self, domain_key: str, *, run_id: str | None = None) -> int:
        return self._domain_registry.count(self, domain_key, run_id=run_id)

    def get_transformation_audit(
        self,
        input_run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if input_run_id is not None:
            return self._store.fetchall_dicts(
                f"SELECT * FROM {TRANSFORMATION_AUDIT_TABLE}"
                " WHERE input_run_id = ?"
                " ORDER BY started_at DESC",
                [input_run_id],
            )
        return self._store.fetchall_dicts(
            f"SELECT * FROM {TRANSFORMATION_AUDIT_TABLE} ORDER BY started_at DESC"
        )

    def get_current_dimension_rows(self, dimension_name: str) -> list[dict[str, Any]]:
        if dimension_name == "dim_account":
            return self.get_current_accounts()
        if dimension_name == "dim_counterparty":
            return self.get_current_counterparties()
        if dimension_name == "dim_contract":
            return self.get_current_contracts()
        if dimension_name == "dim_category":
            return self.get_current_categories()
        if dimension_name == "dim_meter":
            return self.get_current_meters()
        if dimension_name == "dim_budget":
            return self.get_current_budgets()
        if dimension_name == "dim_loan":
            return self.get_current_loans()
        if dimension_name == "dim_asset":
            return self.get_current_assets()
        if dimension_name == "dim_entity":
            return self.get_current_entities()
        if dimension_name == "dim_node":
            return self.get_current_nodes()
        if dimension_name == "dim_device":
            return self.get_current_devices()
        if dimension_name == "dim_service":
            return self.get_current_services()
        if dimension_name == "dim_workload":
            return self.get_current_workloads()
        raise KeyError(f"Unknown current dimension: {dimension_name}")

    @property
    def store(self) -> DuckDBStore:
        return self._store

    @property
    def clock(self) -> Callable[[], datetime]:
        """Injected clock; refresh handlers stamp assessments with it."""
        return self._clock

    @property
    def battery_plan_profile_loader(self) -> Callable[[], BatteryPlanProfileResolution]:
        """Injected battery-plan profile source for the utilities refresh handler."""
        return self._battery_plan_profile_loader

    def get_household_members(self) -> list[dict[str, Any]]:
        return get_household_members(self._store)

    def upsert_household_member(
        self,
        *,
        member_id: str,
        display_name: str,
        role: str,
        active: bool = True,
    ) -> None:
        upsert_household_member(
            self._store,
            member_id=member_id,
            display_name=display_name,
            role=role,
            active=active,
        )
