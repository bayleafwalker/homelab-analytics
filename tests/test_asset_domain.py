from __future__ import annotations

import unittest

from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore


class AssetDomainTests(unittest.TestCase):
    def test_asset_register_loads_dimension_and_acquisition_event(self) -> None:
        service = TransformationService(DuckDBStore.memory())

        inserted = service.load_domain_rows(
            "asset_register",
            [
                {
                    "asset_name": "UPS Rack A",
                    "asset_type": "ups",
                    "purchase_date": "2024-01-15",
                    "purchase_price": "1200.00",
                    "currency": "EUR",
                    "location": "rack-a",
                }
            ],
            run_id="asset-run-001",
            source_system="manual-upload",
        )

        self.assertEqual(1, inserted)
        self.assertEqual(1, service.count_asset_event_rows())
        assets = service.get_current_assets()
        self.assertEqual(1, len(assets))
        asset = assets[0]
        self.assertEqual("UPS Rack A", asset["asset_name"])
        self.assertEqual("ups", asset["asset_type"])
        self.assertEqual("rack-a", asset["location"])

    def test_asset_events_append_without_changing_current_dimension(self) -> None:
        service = TransformationService(DuckDBStore.memory())

        service.load_asset_register(
            [
                {
                    "asset_name": "NAS Rack B",
                    "asset_type": "storage",
                    "purchase_date": "2024-03-01",
                    "purchase_price": "2400.00",
                    "currency": "EUR",
                    "location": "rack-b",
                }
            ],
            run_id="asset-run-002",
            source_system="manual-upload",
        )

        asset_id = service.get_current_assets()[0]["asset_id"]
        appended = service.load_asset_events(
            [
                {
                    "asset_id": asset_id,
                    "asset_name": "NAS Rack B",
                    "event_date": "2026-03-28",
                    "event_type": "depreciation",
                    "amount": "150.00",
                    "currency": "EUR",
                    "notes": "Quarterly depreciation",
                }
            ],
            run_id="asset-run-003",
            source_system="asset-register",
        )

        self.assertEqual(1, appended)
        self.assertEqual(2, service.count_asset_event_rows())
        assets = service.get_current_assets()
        self.assertEqual(1, len(assets))
        self.assertEqual("NAS Rack B", assets[0]["asset_name"])
