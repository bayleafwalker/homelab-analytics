from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from packages.pipelines.publication_preview import attach_publication_preview
from packages.storage.ingestion_config import IngestionConfigRepository
from tests.control_plane_test_support import seed_source_asset_graph


def test_attach_publication_preview_for_builtin_candidate() -> None:
    detection = {
        "candidate": {
            "kind": "builtin",
            "contract_id": "account_transactions",
            "title": "Account transactions",
        },
        "alternatives": [],
    }

    enriched = attach_publication_preview(
        detection,
        source_assets_by_id={},
        dataset_contracts_by_id={},
    )
    candidate = enriched["candidate"]
    assert isinstance(candidate, dict)
    preview = candidate["publication_preview"]
    assert preview["transformation_package_id"] == "builtin_account_transactions"
    direct_keys = {
        entry["publication_key"]
        for entry in preview["direct"]
    }
    assert "mart_monthly_cashflow" in direct_keys
    derived_keys = {
        entry["publication_key"]
        for entry in preview["derived"]
    }
    assert "mart_household_overview" in derived_keys


def test_attach_publication_preview_for_configured_candidate_uses_source_asset_package() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        seed_source_asset_graph(repository)

        source_assets = repository.list_source_assets(include_archived=False)
        dataset_contracts = repository.list_dataset_contracts(include_archived=False)

        detection = {
            "candidate": {
                "kind": "configured_csv",
                "contract_id": "household_account_transactions_v1",
                "source_asset_id": "bank_partner_transactions",
            },
            "alternatives": [],
        }

        enriched = attach_publication_preview(
            detection,
            source_assets_by_id={
                record.source_asset_id: record
                for record in source_assets
            },
            dataset_contracts_by_id={
                record.dataset_contract_id: record
                for record in dataset_contracts
            },
        )
        candidate = enriched["candidate"]
        assert isinstance(candidate, dict)
        preview = candidate["publication_preview"]
        assert preview["transformation_package_id"] == "builtin_account_transactions"
        direct_keys = {
            entry["publication_key"]
            for entry in preview["direct"]
        }
        assert "mart_spend_by_category_monthly" in direct_keys
        assert "mart_monthly_cashflow_by_counterparty" in direct_keys


def test_attach_publication_preview_for_unknown_candidate_is_empty() -> None:
    detection = {
        "candidate": {
            "kind": "builtin",
            "contract_id": "mystery_contract",
            "title": "Mystery",
        },
        "alternatives": [],
    }

    enriched = attach_publication_preview(
        detection,
        source_assets_by_id={},
        dataset_contracts_by_id={},
    )
    candidate = enriched["candidate"]
    assert isinstance(candidate, dict)
    preview = candidate["publication_preview"]
    assert preview["transformation_package_id"] is None
    assert preview["direct"] == []
    assert preview["derived"] == []
