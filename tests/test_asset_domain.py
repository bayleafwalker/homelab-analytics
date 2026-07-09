from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

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

    def test_refresh_asset_value_applies_valuation_precedence(self) -> None:
        service = TransformationService(DuckDBStore.memory())
        current_month_start = date.today().replace(day=1)
        service.load_asset_register(
            [
                # purchased this month → zero straight-line depreciation yet
                {
                    "asset_name": "Homelab Server",
                    "asset_type": "server",
                    "purchase_date": current_month_start.isoformat(),
                    "purchase_price": "1200.00",
                    "currency": "EUR",
                    "location": "rack-a",
                },
                {
                    "asset_name": "NAS Rack B",
                    "asset_type": "storage",
                    "purchase_date": "2024-03-01",
                    "purchase_price": "2400.00",
                    "currency": "EUR",
                    "location": "rack-b",
                },
                {
                    "asset_name": "Old Laptop",
                    "asset_type": "computer",
                    "purchase_date": "2020-01-01",
                    "purchase_price": "900.00",
                    "currency": "EUR",
                    "location": "office",
                },
            ],
            run_id="asset-run-010",
        )
        assets = {row["asset_name"]: row["asset_id"] for row in service.get_current_assets()}
        service.load_asset_events(
            [
                # NAS switches to recorded-events valuation
                {
                    "asset_id": assets["NAS Rack B"],
                    "asset_name": "NAS Rack B",
                    "event_date": "2026-03-28",
                    "event_type": "depreciation",
                    "amount": "600.00",
                    "currency": "EUR",
                },
                # laptop was disposed → value zero
                {
                    "asset_id": assets["Old Laptop"],
                    "asset_name": "Old Laptop",
                    "event_date": "2026-01-10",
                    "event_type": "disposal",
                    "amount": "0.00",
                    "currency": "EUR",
                },
            ],
            run_id="asset-run-011",
        )

        count = service.refresh_asset_value()

        self.assertEqual(3, count)
        rows = {row["asset_name"]: row for row in service.get_asset_value()}

        server = rows["Homelab Server"]
        self.assertEqual("straight_line_60m", server["valuation_basis"])
        self.assertEqual(Decimal("0.0000"), Decimal(server["accumulated_depreciation"]))
        self.assertEqual(Decimal("1200.0000"), Decimal(server["estimated_value"]))
        self.assertFalse(server["is_disposed"])

        nas = rows["NAS Rack B"]
        self.assertEqual("recorded_events", nas["valuation_basis"])
        self.assertEqual(Decimal("600.0000"), Decimal(nas["accumulated_depreciation"]))
        self.assertEqual(Decimal("1800.0000"), Decimal(nas["estimated_value"]))

        laptop = rows["Old Laptop"]
        self.assertEqual("disposed", laptop["valuation_basis"])
        self.assertTrue(laptop["is_disposed"])
        self.assertEqual(Decimal("0.0000"), Decimal(laptop["estimated_value"]))

        typed = service.get_asset_value(asset_type="server")
        self.assertEqual(1, len(typed))

    def test_refresh_depreciation_schedule_projects_annual_amounts(self) -> None:
        service = TransformationService(DuckDBStore.memory())
        service.load_asset_register(
            [
                # 1200 over 60 months from Jan 2024 → 20/month;
                # exactly five full years 2024-2028 at 240/year
                {
                    "asset_name": "Homelab Server",
                    "asset_type": "server",
                    "purchase_date": "2024-01-01",
                    "purchase_price": "1200.00",
                    "currency": "EUR",
                    "location": "rack-a",
                }
            ],
            run_id="asset-run-020",
        )
        asset_id = service.get_current_assets()[0]["asset_id"]
        service.load_asset_events(
            [
                # a second asset with explicit depreciation only contributes
                # its recorded events
                {
                    "asset_id": "manual-asset",
                    "asset_name": "Camera Rig",
                    "event_date": "2026-05-01",
                    "event_type": "depreciation",
                    "amount": "150.00",
                    "currency": "EUR",
                }
            ],
            run_id="asset-run-021",
        )
        self.assertNotEqual("manual-asset", asset_id)

        count = service.refresh_depreciation_schedule()

        rows = service.get_depreciation_schedule()
        self.assertEqual(count, len(rows))
        by_year_type = {
            (row["depreciation_year"], row["asset_type"]): row for row in rows
        }

        self.assertEqual(
            Decimal("240.0000"),
            Decimal(by_year_type[(2024, "server")]["annual_depreciation"]),
        )
        self.assertEqual(
            Decimal("240.0000"),
            Decimal(by_year_type[(2028, "server")]["annual_depreciation"]),
        )
        # straight-line asset appears in exactly the five years 2024-2028
        server_years = {
            year for (year, asset_type) in by_year_type if asset_type == "server"
        }
        self.assertEqual({2024, 2025, 2026, 2027, 2028}, server_years)

        recorded = by_year_type[(2026, "unknown")]
        self.assertEqual(Decimal("150.0000"), Decimal(recorded["annual_depreciation"]))
        self.assertEqual(1, recorded["asset_count"])

        filtered = service.get_depreciation_schedule(
            asset_type="server", depreciation_year=2024
        )
        self.assertEqual(1, len(filtered))
        self.assertEqual(1, filtered[0]["asset_count"])
