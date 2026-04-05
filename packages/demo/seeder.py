from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar, cast

from packages.demo.bundle import (
    COMMON_ACCOUNT_ARTIFACT_ID,
    PERSONAL_ACCOUNT_ARTIFACT_ID,
    REVOLUT_ACCOUNT_ARTIFACT_ID,
    DemoManifestRow,
    load_demo_manifest,
)
from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.finance.pipelines.budget_service import BudgetService
from packages.domains.finance.pipelines.contract_price_service import ContractPriceService
from packages.domains.finance.pipelines.loan_service import LoanService
from packages.domains.finance.pipelines.subscription_service import SubscriptionService
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.domains.utilities.pipelines.utility_bill_service import UtilityBillService
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.csv_validation import ColumnType
from packages.pipelines.household_promotion_handlers import (
    promote_budget_run,
    promote_contract_price_run,
    promote_loan_repayment_run,
    promote_subscription_run,
    promote_utility_bill_run,
)
from packages.pipelines.promotion import promote_source_asset_run
from packages.pipelines.reporting_service import (
    ReportingAccessMode,
    ReportingService,
    publish_promotion_reporting,
)
from packages.pipelines.transformation_service import TransformationService
from packages.platform.runtime.builder import build_container
from packages.platform.runtime.container import AppContainer
from packages.shared.settings import AppSettings
from packages.storage.control_plane import ControlPlaneStore
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRecord,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    DatasetContractConfigRecord,
    IngestionDefinitionCreate,
    SourceAssetCreate,
    SourceSystemCreate,
)
from packages.storage.runtime import build_reporting_store

DEMO_CREATED_AT = datetime(2026, 3, 24, tzinfo=UTC)
DEMO_ACCOUNT_CONTRACT_ID = "demo_account_transactions_v1"
CreateOnlyRecord = DatasetContractConfigRecord | ColumnMappingRecord
CreateOnlyExpected = DatasetContractConfigCreate | ColumnMappingCreate
_RecordT = TypeVar("_RecordT")


class AccountBindingSpec:
    def __init__(
        self,
        *,
        artifact_id: str,
        source_system: SourceSystemCreate,
        column_mapping: ColumnMappingCreate,
        source_asset: SourceAssetCreate,
        ingestion_definition_id: str,
        source_name: str,
    ) -> None:
        self.artifact_id = artifact_id
        self.source_system = source_system
        self.column_mapping = column_mapping
        self.source_asset = source_asset
        self.ingestion_definition_id = ingestion_definition_id
        self.source_name = source_name


def seed_demo_data(
    settings: AppSettings,
    input_dir: Path,
) -> dict[str, Any]:
    manifest = load_demo_manifest(input_dir)
    artifact_rows = manifest["artifacts"]
    artifact_by_id = {
        str(row["artifact_id"]): row for row in artifact_rows if "artifact_id" in row
    }

    container = build_container(
        settings,
        capability_packs=[FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK],
    )
    transformation_service = _build_transformation_service(settings, container)
    reporting_service = ReportingService(
        transformation_service,
        publication_store=build_reporting_store(settings),
        extension_registry=container.extension_registry,
        access_mode=ReportingAccessMode.WAREHOUSE,
        control_plane_store=container.control_plane_store,
    )

    config_summary, account_assets = _ensure_demo_account_bindings(
        container.control_plane_store,
        input_dir=input_dir,
        artifact_by_id=artifact_by_id,
    )

    configured_csv_service = ConfiguredCsvIngestionService(
        landing_root=settings.landing_root,
        metadata_repository=container.run_metadata_store,
        config_repository=container.control_plane_store,
        blob_store=container.blob_store,
        function_registry=container.function_registry,
    )

    runs: list[dict[str, Any]] = []
    published_counts: dict[str, int] = {}

    for artifact_id in (
        PERSONAL_ACCOUNT_ARTIFACT_ID,
        COMMON_ACCOUNT_ARTIFACT_ID,
        REVOLUT_ACCOUNT_ARTIFACT_ID,
    ):
        row = artifact_by_id[artifact_id]
        source_path = input_dir / str(row["relative_path"])
        source_asset_id = account_assets[artifact_id]
        run = configured_csv_service.ingest_file(
            source_path=source_path,
            source_system_id=container.control_plane_store.get_source_asset(
                source_asset_id
            ).source_system_id,
            dataset_contract_id=DEMO_ACCOUNT_CONTRACT_ID,
            column_mapping_id=container.control_plane_store.get_source_asset(
                source_asset_id
            ).column_mapping_id,
            source_asset_id=source_asset_id,
            source_name=str(row.get("source_name") or artifact_id),
        )
        promotion = None
        published = []
        if run.passed:
            promotion = promote_source_asset_run(
                run.run_id,
                source_asset=container.control_plane_store.get_source_asset(source_asset_id),
                config_repository=container.control_plane_store,
                landing_root=settings.landing_root,
                metadata_repository=container.run_metadata_store,
                transformation_service=transformation_service,
                blob_store=container.blob_store,
                extension_registry=container.extension_registry,
                promotion_handler_registry=container.promotion_handler_registry,
            )
            published = publish_promotion_reporting(reporting_service, promotion)
            _increment_counts(published_counts, published)
        runs.append(_serialize_run_summary(run, promotion, artifact_id))

    canonical_inputs = {
        "subscriptions": input_dir / "canonical" / "subscriptions.csv",
        "contract_prices": input_dir / "canonical" / "contract_prices.csv",
        "utility_bills": input_dir / "canonical" / "utility_bills.csv",
        "budgets": input_dir / "canonical" / "budgets.csv",
        "loan_repayments": input_dir / "canonical" / "loan_repayments.csv",
    }

    subscription_service = SubscriptionService(
        landing_root=settings.landing_root,
        metadata_repository=container.run_metadata_store,
        blob_store=container.blob_store,
    )
    contract_price_service = ContractPriceService(
        landing_root=settings.landing_root,
        metadata_repository=container.run_metadata_store,
        blob_store=container.blob_store,
    )
    utility_bill_service = UtilityBillService(
        landing_root=settings.landing_root,
        metadata_repository=container.run_metadata_store,
        blob_store=container.blob_store,
    )
    budget_service = BudgetService(
        landing_root=settings.landing_root,
        metadata_repository=container.run_metadata_store,
        blob_store=container.blob_store,
    )
    loan_service = LoanService(
        landing_root=settings.landing_root,
        metadata_repository=container.run_metadata_store,
        blob_store=container.blob_store,
    )

    runs.extend(
        [
            _ingest_and_publish(
                dataset_name="subscriptions",
                source_path=canonical_inputs["subscriptions"],
                ingest=lambda path: subscription_service.ingest_file(
                    path,
                    source_name="demo-canonical-subscriptions",
                ),
                promote=lambda run_id: promote_subscription_run(
                    run_id,
                    subscription_service=subscription_service,
                    transformation_service=transformation_service,
                ),
                reporting_service=reporting_service,
                published_counts=published_counts,
            ),
            _ingest_and_publish(
                dataset_name="contract_prices",
                source_path=canonical_inputs["contract_prices"],
                ingest=lambda path: contract_price_service.ingest_file(
                    path,
                    source_name="demo-canonical-contract-prices",
                ),
                promote=lambda run_id: promote_contract_price_run(
                    run_id,
                    contract_price_service=contract_price_service,
                    transformation_service=transformation_service,
                ),
                reporting_service=reporting_service,
                published_counts=published_counts,
            ),
            _ingest_and_publish(
                dataset_name="utility_bills",
                source_path=canonical_inputs["utility_bills"],
                ingest=lambda path: utility_bill_service.ingest_file(
                    path,
                    source_name="demo-canonical-utility-bills",
                ),
                promote=lambda run_id: promote_utility_bill_run(
                    run_id,
                    utility_bill_service=utility_bill_service,
                    transformation_service=transformation_service,
                ),
                reporting_service=reporting_service,
                published_counts=published_counts,
            ),
            _ingest_and_publish(
                dataset_name="budgets",
                source_path=canonical_inputs["budgets"],
                ingest=lambda path: budget_service.ingest_file(
                    path,
                    source_name="demo-canonical-budgets",
                ),
                promote=lambda run_id: promote_budget_run(
                    run_id,
                    budget_service=budget_service,
                    transformation_service=transformation_service,
                ),
                reporting_service=reporting_service,
                published_counts=published_counts,
            ),
            _ingest_and_publish(
                dataset_name="loan_repayments",
                source_path=canonical_inputs["loan_repayments"],
                ingest=lambda path: loan_service.ingest_file(
                    path,
                    source_name="demo-canonical-loan-repayments",
                ),
                promote=lambda run_id: promote_loan_repayment_run(
                    run_id,
                    loan_service=loan_service,
                    transformation_service=transformation_service,
                ),
                reporting_service=reporting_service,
                published_counts=published_counts,
            ),
        ]
    )

    reporting_counts = {
        "monthly_cashflow": len(reporting_service.get_monthly_cashflow()),
        "subscription_summary": len(reporting_service.get_subscription_summary()),
        "contract_price_current": len(reporting_service.get_contract_price_current()),
        "utility_cost_summary": len(reporting_service.get_utility_cost_summary()),
        "budget_variance": len(transformation_service.get_budget_variance()),
        "loan_overview": len(transformation_service.get_loan_overview()),
        "household_overview": len(reporting_service.get_household_overview()),
    }

    return {
        "input_dir": str(input_dir),
        "manifest_path": str(input_dir / "manifest.json"),
        "config": config_summary,
        "runs": runs,
        "published_relations": published_counts,
        "reporting_counts": reporting_counts,
    }


def _build_transformation_service(
    settings: AppSettings,
    container: AppContainer,
) -> TransformationService:
    analytics_path = settings.resolved_analytics_database_path
    analytics_path.parent.mkdir(parents=True, exist_ok=True)
    return TransformationService(
        DuckDBStore.open(str(analytics_path)),
        control_plane_store=container.control_plane_store,
        publication_refresh_registry=container.publication_refresh_registry,
        domain_registry=container.transformation_domain_registry,
    )


def _ensure_demo_account_bindings(
    store: ControlPlaneStore,
    *,
    input_dir: Path,
    artifact_by_id: dict[str, DemoManifestRow],
) -> tuple[dict[str, list[dict[str, object]]], dict[str, str]]:
    summary: dict[str, list[dict[str, object]]] = {
        "source_systems": [],
        "dataset_contracts": [],
        "column_mappings": [],
        "source_assets": [],
        "ingestion_definitions": [],
    }
    asset_ids: dict[str, str] = {}

    contract_create = DatasetContractConfigCreate(
        dataset_contract_id=DEMO_ACCOUNT_CONTRACT_ID,
        dataset_name="account_transactions",
        version=1,
        allow_extra_columns=False,
        columns=(
            DatasetColumnConfig("booked_at", ColumnType.DATE),
            DatasetColumnConfig("account_id", ColumnType.STRING),
            DatasetColumnConfig("counterparty_name", ColumnType.STRING),
            DatasetColumnConfig("amount", ColumnType.DECIMAL),
            DatasetColumnConfig("currency", ColumnType.STRING),
            DatasetColumnConfig("description", ColumnType.STRING, required=False),
        ),
        created_at=DEMO_CREATED_AT,
    )
    summary["dataset_contracts"].append(
        _ensure_create_only(
            store,
            "dataset_contract",
            contract_create.dataset_contract_id,
            lambda: store.get_dataset_contract(contract_create.dataset_contract_id),
            lambda: store.create_dataset_contract(contract_create),
            expected=contract_create,
        )
    )

    binding_specs = (
        AccountBindingSpec(
            artifact_id=PERSONAL_ACCOUNT_ARTIFACT_ID,
            source_system=SourceSystemCreate(
                source_system_id="demo_op_personal_export",
                name="Demo OP Personal Account Export",
                source_type="file-drop",
                transport="filesystem",
                schedule_mode="manual",
                description="Synthetic OP-style personal account CSV export.",
                created_at=DEMO_CREATED_AT,
            ),
            column_mapping=ColumnMappingCreate(
                column_mapping_id="demo_op_personal_mapping_v1",
                source_system_id="demo_op_personal_export",
                dataset_contract_id=DEMO_ACCOUNT_CONTRACT_ID,
                version=1,
                rules=(
                    ColumnMappingRule("booked_at", source_column="Kirjauspäivä"),
                    ColumnMappingRule("account_id", default_value="PERS-001"),
                    ColumnMappingRule("counterparty_name", source_column="Saaja/Maksaja"),
                    ColumnMappingRule(
                        "amount",
                        source_column="Määrä EUROA",
                        function_key="transform_flexible_decimal",
                    ),
                    ColumnMappingRule("currency", default_value="EUR"),
                    ColumnMappingRule("description", source_column="Selitys"),
                ),
                created_at=DEMO_CREATED_AT,
            ),
            source_asset=SourceAssetCreate(
                source_asset_id="demo_op_personal_transactions",
                source_system_id="demo_op_personal_export",
                dataset_contract_id=DEMO_ACCOUNT_CONTRACT_ID,
                column_mapping_id="demo_op_personal_mapping_v1",
                transformation_package_id="builtin_account_transactions",
                name="Demo OP Personal Transactions",
                asset_type="dataset",
                description="Synthetic OP personal-account transaction export.",
                created_at=DEMO_CREATED_AT,
            ),
            ingestion_definition_id="demo_op_personal_transactions_file",
            source_name="demo-op-personal",
        ),
        AccountBindingSpec(
            artifact_id=COMMON_ACCOUNT_ARTIFACT_ID,
            source_system=SourceSystemCreate(
                source_system_id="demo_op_common_export",
                name="Demo OP Common Account Export",
                source_type="file-drop",
                transport="filesystem",
                schedule_mode="manual",
                description="Synthetic OP-style common account CSV export.",
                created_at=DEMO_CREATED_AT,
            ),
            column_mapping=ColumnMappingCreate(
                column_mapping_id="demo_op_common_mapping_v1",
                source_system_id="demo_op_common_export",
                dataset_contract_id=DEMO_ACCOUNT_CONTRACT_ID,
                version=1,
                rules=(
                    ColumnMappingRule("booked_at", source_column="Kirjauspäivä"),
                    ColumnMappingRule("account_id", default_value="COMM-001"),
                    ColumnMappingRule("counterparty_name", source_column="Saaja/Maksaja"),
                    ColumnMappingRule(
                        "amount",
                        source_column="Määrä EUROA",
                        function_key="transform_flexible_decimal",
                    ),
                    ColumnMappingRule("currency", default_value="EUR"),
                    ColumnMappingRule("description", source_column="Selitys"),
                ),
                created_at=DEMO_CREATED_AT,
            ),
            source_asset=SourceAssetCreate(
                source_asset_id="demo_op_common_transactions",
                source_system_id="demo_op_common_export",
                dataset_contract_id=DEMO_ACCOUNT_CONTRACT_ID,
                column_mapping_id="demo_op_common_mapping_v1",
                transformation_package_id="builtin_account_transactions",
                name="Demo OP Common Transactions",
                asset_type="dataset",
                description="Synthetic OP common-account transaction export.",
                created_at=DEMO_CREATED_AT,
            ),
            ingestion_definition_id="demo_op_common_transactions_file",
            source_name="demo-op-common",
        ),
        AccountBindingSpec(
            artifact_id=REVOLUT_ACCOUNT_ARTIFACT_ID,
            source_system=SourceSystemCreate(
                source_system_id="demo_revolut_export",
                name="Demo Revolut Export",
                source_type="file-drop",
                transport="filesystem",
                schedule_mode="manual",
                description="Synthetic Revolut-style account statement CSV export.",
                created_at=DEMO_CREATED_AT,
            ),
            column_mapping=ColumnMappingCreate(
                column_mapping_id="demo_revolut_mapping_v1",
                source_system_id="demo_revolut_export",
                dataset_contract_id=DEMO_ACCOUNT_CONTRACT_ID,
                version=1,
                rules=(
                    ColumnMappingRule(
                        "booked_at",
                        source_column="Started Date",
                        function_key="transform_iso_datetime_to_date",
                    ),
                    ColumnMappingRule("account_id", default_value="REV-001"),
                    ColumnMappingRule("counterparty_name", source_column="Description"),
                    ColumnMappingRule("amount", source_column="Amount"),
                    ColumnMappingRule("currency", source_column="Currency"),
                    ColumnMappingRule("description", source_column="Type"),
                ),
                created_at=DEMO_CREATED_AT,
            ),
            source_asset=SourceAssetCreate(
                source_asset_id="demo_revolut_transactions",
                source_system_id="demo_revolut_export",
                dataset_contract_id=DEMO_ACCOUNT_CONTRACT_ID,
                column_mapping_id="demo_revolut_mapping_v1",
                transformation_package_id="builtin_account_transactions",
                name="Demo Revolut Transactions",
                asset_type="dataset",
                description="Synthetic Revolut transaction export.",
                created_at=DEMO_CREATED_AT,
            ),
            ingestion_definition_id="demo_revolut_transactions_file",
            source_name="demo-revolut",
        ),
    )

    for spec in binding_specs:
        source_system = spec.source_system
        column_mapping = spec.column_mapping
        source_asset = spec.source_asset
        artifact_row = artifact_by_id[spec.artifact_id]
        source_path = input_dir / str(artifact_row["relative_path"])

        summary["source_systems"].append(
            _ensure_updatable(
                store,
                "source_system",
                source_system.source_system_id,
                lambda: store.get_source_system(source_system.source_system_id),
                lambda: store.create_source_system(source_system),
                lambda: store.update_source_system(source_system),
                comparable=lambda record: {
                    "name": record.name,
                    "source_type": record.source_type,
                    "transport": record.transport,
                    "schedule_mode": record.schedule_mode,
                    "description": record.description,
                    "enabled": record.enabled,
                },
                expected={
                    "name": source_system.name,
                    "source_type": source_system.source_type,
                    "transport": source_system.transport,
                    "schedule_mode": source_system.schedule_mode,
                    "description": source_system.description,
                    "enabled": source_system.enabled,
                },
            )
        )
        summary["column_mappings"].append(
            _ensure_create_only(
                store,
                "column_mapping",
                column_mapping.column_mapping_id,
                lambda: store.get_column_mapping(column_mapping.column_mapping_id),
                lambda: store.create_column_mapping(column_mapping),
                expected=column_mapping,
            )
        )
        summary["source_assets"].append(
            _ensure_updatable(
                store,
                "source_asset",
                source_asset.source_asset_id,
                lambda: store.get_source_asset(source_asset.source_asset_id),
                lambda: store.create_source_asset(source_asset),
                lambda: store.update_source_asset(source_asset),
                comparable=lambda record: {
                    "source_system_id": record.source_system_id,
                    "dataset_contract_id": record.dataset_contract_id,
                    "column_mapping_id": record.column_mapping_id,
                    "transformation_package_id": record.transformation_package_id,
                    "name": record.name,
                    "asset_type": record.asset_type,
                    "description": record.description,
                    "enabled": record.enabled,
                    "archived": record.archived,
                },
                expected={
                    "source_system_id": source_asset.source_system_id,
                    "dataset_contract_id": source_asset.dataset_contract_id,
                    "column_mapping_id": source_asset.column_mapping_id,
                    "transformation_package_id": source_asset.transformation_package_id,
                    "name": source_asset.name,
                    "asset_type": source_asset.asset_type,
                    "description": source_asset.description,
                    "enabled": source_asset.enabled,
                    "archived": source_asset.archived,
                },
            )
        )
        ingestion_definition = IngestionDefinitionCreate(
            ingestion_definition_id=spec.ingestion_definition_id,
            source_asset_id=source_asset.source_asset_id,
            transport="filesystem",
            schedule_mode="manual",
            source_path=str(source_path),
            source_name=spec.source_name,
            created_at=DEMO_CREATED_AT,
        )
        summary["ingestion_definitions"].append(
            _ensure_updatable(
                store,
                "ingestion_definition",
                ingestion_definition.ingestion_definition_id,
                lambda: store.get_ingestion_definition(
                    ingestion_definition.ingestion_definition_id
                ),
                lambda: store.create_ingestion_definition(ingestion_definition),
                lambda: store.update_ingestion_definition(ingestion_definition),
                comparable=lambda record: {
                    "source_asset_id": record.source_asset_id,
                    "transport": record.transport,
                    "schedule_mode": record.schedule_mode,
                    "source_path": record.source_path,
                    "source_name": record.source_name,
                    "enabled": record.enabled,
                    "archived": record.archived,
                },
                expected={
                    "source_asset_id": ingestion_definition.source_asset_id,
                    "transport": ingestion_definition.transport,
                    "schedule_mode": ingestion_definition.schedule_mode,
                    "source_path": ingestion_definition.source_path,
                    "source_name": ingestion_definition.source_name,
                    "enabled": ingestion_definition.enabled,
                    "archived": ingestion_definition.archived,
                },
            )
        )
        asset_ids[spec.artifact_id] = source_asset.source_asset_id

    return summary, asset_ids


def _ensure_create_only(
    store: ControlPlaneStore,
    entity_kind: str,
    entity_id: str,
    get_existing: Callable[[], CreateOnlyRecord],
    create_new: Callable[[], CreateOnlyRecord],
    *,
    expected: CreateOnlyExpected,
) -> dict[str, object]:
    try:
        record = get_existing()
    except KeyError:
        record = create_new()
        return {"entity_kind": entity_kind, "entity_id": entity_id, "status": "created"}

    if entity_kind == "dataset_contract":
        dataset_record = cast(DatasetContractConfigRecord, record)
        dataset_expected = cast(DatasetContractConfigCreate, expected)
        comparable = {
            "dataset_name": dataset_record.dataset_name,
            "version": dataset_record.version,
            "allow_extra_columns": dataset_record.allow_extra_columns,
            "columns": tuple(asdict(column) for column in dataset_record.columns),
            "archived": dataset_record.archived,
        }
        wanted = {
            "dataset_name": dataset_expected.dataset_name,
            "version": dataset_expected.version,
            "allow_extra_columns": dataset_expected.allow_extra_columns,
            "columns": tuple(asdict(column) for column in dataset_expected.columns),
            "archived": dataset_expected.archived,
        }
    else:
        mapping_record = cast(ColumnMappingRecord, record)
        mapping_expected = cast(ColumnMappingCreate, expected)
        comparable = {
            "source_system_id": mapping_record.source_system_id,
            "dataset_contract_id": mapping_record.dataset_contract_id,
            "version": mapping_record.version,
            "rules": tuple(asdict(rule) for rule in mapping_record.rules),
            "archived": mapping_record.archived,
        }
        wanted = {
            "source_system_id": mapping_expected.source_system_id,
            "dataset_contract_id": mapping_expected.dataset_contract_id,
            "version": mapping_expected.version,
            "rules": tuple(asdict(rule) for rule in mapping_expected.rules),
            "archived": mapping_expected.archived,
        }

    if comparable != wanted:
        raise ValueError(
            f"Existing {entity_kind} does not match demo seed contract: {entity_id}"
        )
    return {"entity_kind": entity_kind, "entity_id": entity_id, "status": "reused"}


def _ensure_updatable(
    store: ControlPlaneStore,
    entity_kind: str,
    entity_id: str,
    get_existing: Callable[[], _RecordT],
    create_new: Callable[[], _RecordT],
    update_existing: Callable[[], _RecordT],
    *,
    comparable: Callable[[_RecordT], dict[str, object]],
    expected: dict[str, object],
) -> dict[str, object]:
    try:
        record = get_existing()
    except KeyError:
        create_new()
        return {"entity_kind": entity_kind, "entity_id": entity_id, "status": "created"}

    if comparable(record) == expected:
        return {"entity_kind": entity_kind, "entity_id": entity_id, "status": "reused"}

    update_existing()
    return {"entity_kind": entity_kind, "entity_id": entity_id, "status": "updated"}


def _ingest_and_publish(
    *,
    dataset_name: str,
    source_path: Path,
    ingest,
    promote,
    reporting_service: ReportingService,
    published_counts: dict[str, int],
) -> dict[str, Any]:
    run = ingest(source_path)
    promotion = None
    published = []
    if run.passed:
        promotion = promote(run.run_id)
        published = publish_promotion_reporting(reporting_service, promotion)
        _increment_counts(published_counts, published)
    return _serialize_run_summary(run, promotion, dataset_name)


def _serialize_run_summary(run, promotion, artifact_id: str) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "run_id": run.run_id,
        "dataset_name": run.dataset_name,
        "source_name": run.source_name,
        "status": run.status.value,
        "passed": run.passed,
        "duplicate": any(issue.code == "duplicate_file" for issue in run.issues),
        "issues": [asdict(issue) for issue in run.issues],
        "promotion": (
            {
                "run_id": promotion.run_id,
                "facts_loaded": promotion.facts_loaded,
                "marts_refreshed": list(promotion.marts_refreshed),
                "publication_keys": list(promotion.publication_keys),
                "skipped": promotion.skipped,
                "skip_reason": promotion.skip_reason,
            }
            if promotion is not None
            else None
        ),
    }


def _increment_counts(counts: dict[str, int], relation_names: list[str]) -> None:
    for relation_name in relation_names:
        counts[relation_name] = counts.get(relation_name, 0) + 1
