from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore


class InfrastructureDomainTests(unittest.TestCase):
    def test_cluster_metrics_load_dimensions_and_facts(self) -> None:
        service = TransformationService(DuckDBStore.memory())

        inserted = service.load_cluster_metrics(
            [
                {
                    "hostname": "node-01",
                    "node_name": "node-01",
                    "role": "control-plane",
                    "cpu": "Intel Xeon",
                    "ram_gb": "64",
                    "os": "Debian 12",
                    "recorded_at": "2026-03-28T10:00:00",
                    "metric_name": "cpu_usage_pct",
                    "metric_value": "42.5",
                    "metric_unit": "pct",
                },
                {
                    "hostname": "node-01",
                    "node_name": "node-01 v2",
                    "role": "control-plane",
                    "cpu": "Intel Xeon",
                    "ram_gb": "64",
                    "os": "Debian 12",
                    "recorded_at": "2026-03-28T11:00:00",
                    "metric_name": "cpu_usage_pct",
                    "metric_value": "37.25",
                    "metric_unit": "pct",
                },
                {
                    "hostname": "node-02",
                    "node_name": "node-02",
                    "role": "worker",
                    "cpu": "AMD Ryzen",
                    "ram_gb": "32",
                    "os": "Ubuntu 24.04",
                    "recorded_at": "2026-03-28T10:00:00",
                    "metric_name": "memory_usage_gb",
                    "metric_value": "18.75",
                    "metric_unit": "gb",
                },
            ],
            run_id="infra-run-001",
            source_system="prometheus",
        )

        self.assertEqual(3, inserted)
        self.assertEqual(3, service.count_cluster_metric_rows())
        self.assertEqual(2, len(service.get_current_nodes()))
        current = {row["hostname"]: row for row in service.get_current_nodes()}
        self.assertEqual("node-01 v2", current["node-01"]["node_name"])
        self.assertEqual("node-02", current["node-02"]["node_name"])

    def test_power_consumption_loads_device_dimension_and_fact(self) -> None:
        service = TransformationService(DuckDBStore.memory())

        inserted = service.load_power_consumption(
            [
                {
                    "device_id": "ups-01",
                    "device_name": "UPS Rack A",
                    "device_type": "ups",
                    "location": "rack-a",
                    "power_rating_watts": "900",
                    "recorded_at": "2026-03-28T10:00:00",
                    "watts": "412.5",
                },
                {
                    "device_id": "pdu-01",
                    "device_name": "PDU Rack A",
                    "device_type": "pdu",
                    "location": "rack-a",
                    "power_rating_watts": "1500",
                    "recorded_at": "2026-03-28T10:00:00",
                    "watts": "178.25",
                },
                {
                    "device_id": "ups-01",
                    "device_name": "UPS Rack A v2",
                    "device_type": "ups",
                    "location": "rack-a",
                    "power_rating_watts": "900",
                    "recorded_at": "2026-03-28T11:00:00",
                    "watts": "398.0",
                },
            ],
            run_id="infra-run-002",
            source_system="collector",
        )

        self.assertEqual(3, inserted)
        self.assertEqual(3, service.count_power_consumption_rows())
        devices = {row["device_id"]: row for row in service.get_current_devices()}
        self.assertEqual(2, len(devices))
        self.assertEqual("UPS Rack A v2", devices["ups-01"]["device_name"])

    def test_refresh_cluster_utilization_classifies_and_aggregates(self) -> None:
        service = TransformationService(DuckDBStore.memory())
        service.load_cluster_metrics(
            [
                {
                    "hostname": "node-01",
                    "recorded_at": "2026-03-28T10:00:00",
                    "metric_name": "cpu_usage_pct",
                    "metric_value": "42.5",
                    "metric_unit": "pct",
                },
                {
                    "hostname": "node-01",
                    "recorded_at": "2026-03-28T11:00:00",
                    "metric_name": "cpu_usage_pct",
                    "metric_value": "37.5",
                    "metric_unit": "pct",
                },
                {
                    "hostname": "node-01",
                    "recorded_at": "2026-03-28T10:00:00",
                    "metric_name": "node_filesystem_used_pct",
                    "metric_value": "63.0",
                    "metric_unit": "pct",
                },
                {
                    "hostname": "node-02",
                    "recorded_at": "2026-03-28T10:00:00",
                    "metric_name": "memory_usage_gb",
                    "metric_value": "18.75",
                    "metric_unit": "gb",
                },
                # availability metric belongs to mart_uptime_summary, not here
                {
                    "hostname": "node-02",
                    "recorded_at": "2026-03-28T10:00:00",
                    "metric_name": "up",
                    "metric_value": "1",
                },
            ],
            run_id="infra-run-003",
            source_system="prometheus",
        )

        count = service.refresh_cluster_utilization()

        self.assertEqual(3, count)
        rows = service.get_cluster_utilization()
        by_key = {(row["hostname"], row["resource_type"]): row for row in rows}
        self.assertEqual(
            {("node-01", "cpu"), ("node-01", "storage"), ("node-02", "memory")},
            set(by_key),
        )

        cpu_row = by_key[("node-01", "cpu")]
        self.assertEqual(date(2026, 3, 28), cpu_row["period_day"])
        self.assertEqual(Decimal("40.0000"), Decimal(cpu_row["avg_value"]))
        self.assertEqual(Decimal("42.5000"), Decimal(cpu_row["max_value"]))
        self.assertEqual(2, cpu_row["sample_count"])

        filtered = service.get_cluster_utilization(
            hostname="node-01", resource_type="storage"
        )
        self.assertEqual(1, len(filtered))
        self.assertEqual(Decimal("63.0000"), Decimal(filtered[0]["avg_value"]))

    def test_refresh_uptime_summary_covers_nodes_and_services(self) -> None:
        service = TransformationService(DuckDBStore.memory())
        service.load_cluster_metrics(
            [
                {
                    "hostname": "node-01",
                    "recorded_at": f"2026-03-01T{hour:02d}:00:00",
                    "metric_name": "up",
                    "metric_value": value,
                }
                for hour, value in ((0, "1"), (1, "1"), (2, "0"), (3, "1"))
            ],
            run_id="infra-run-004",
            source_system="prometheus",
        )
        service.load_service_health(
            [
                {
                    "service_id": "svc-grafana",
                    "service_name": "Grafana",
                    "recorded_at": "2026-03-01T00:00:00",
                    "state": "running",
                },
                {
                    "service_id": "svc-grafana",
                    "service_name": "Grafana",
                    "recorded_at": "2026-03-01T01:00:00",
                    "state": "stopped",
                },
            ],
            run_id="homelab-run-001",
        )

        count = service.refresh_uptime_summary()

        self.assertEqual(2, count)
        node_rows = service.get_uptime_summary(subject_type="node")
        self.assertEqual(1, len(node_rows))
        node_row = node_rows[0]
        self.assertEqual("2026-03", node_row["period_month"])
        self.assertEqual("node-01", node_row["subject_id"])
        self.assertEqual(Decimal("75.000"), Decimal(node_row["availability_pct"]))
        self.assertEqual(3, node_row["up_samples"])
        self.assertEqual(4, node_row["total_samples"])

        service_rows = service.get_uptime_summary(subject_type="service")
        self.assertEqual(1, len(service_rows))
        service_row = service_rows[0]
        self.assertEqual("svc-grafana", service_row["subject_id"])
        self.assertEqual("Grafana", service_row["subject_name"])
        self.assertEqual(Decimal("50.000"), Decimal(service_row["availability_pct"]))

    def test_refresh_infra_cost_estimates_power_and_amortisation(self) -> None:
        service = TransformationService(DuckDBStore.memory())
        # Two March samples averaging 400 W → 400 W * 24 h * 31 d / 1000 = 297.6 kWh.
        service.load_power_consumption(
            [
                {
                    "device_id": "ups-01",
                    "device_name": "UPS Rack A",
                    "recorded_at": "2026-03-10T10:00:00",
                    "watts": "412.5",
                },
                {
                    "device_id": "ups-01",
                    "device_name": "UPS Rack A",
                    "recorded_at": "2026-03-20T10:00:00",
                    "watts": "387.5",
                },
            ],
            run_id="infra-run-005",
        )
        service.load_contract_prices(
            [
                {
                    "contract_id": "c-electricity",
                    "contract_name": "Helen Spot",
                    "provider": "Helen",
                    "contract_type": "electricity",
                    "price_component": "energy",
                    "billing_cycle": "per_kwh",
                    "unit_price": "0.10",
                    "currency": "EUR",
                    "quantity_unit": "kWh",
                    "valid_from": "2026-01-01",
                    "valid_to": None,
                }
            ],
            run_id="price-run-001",
        )
        service.refresh_contract_price_current()
        # Acquisition in the current month keeps the amortisation window
        # time-robust: exactly one month has elapsed, so exactly one row.
        current_month_start = date.today().replace(day=1)
        service.load_asset_register(
            [
                {
                    "asset_name": "Homelab Server",
                    "asset_type": "server",
                    "purchase_date": current_month_start.isoformat(),
                    "purchase_price": "1080",
                    "currency": "EUR",
                    "location": "rack-a",
                },
                {
                    "asset_name": "Espresso Machine",
                    "asset_type": "appliance",
                    "purchase_date": current_month_start.isoformat(),
                    "purchase_price": "900",
                    "currency": "EUR",
                    "location": "kitchen",
                },
            ],
            run_id="asset-run-001",
        )

        count = service.refresh_infra_cost()

        self.assertEqual(2, count)
        electricity_rows = service.get_infra_cost(cost_type="electricity")
        self.assertEqual(1, len(electricity_rows))
        electricity_row = electricity_rows[0]
        self.assertEqual("2026-03", electricity_row["billing_month"])
        self.assertEqual("ups-01", electricity_row["subject_id"])
        self.assertEqual(Decimal("297.6000"), Decimal(electricity_row["est_kwh"]))
        self.assertEqual(Decimal("29.7600"), Decimal(electricity_row["est_cost"]))
        self.assertEqual("metered_power_x_tariff", electricity_row["cost_basis"])
        self.assertEqual("EUR", electricity_row["currency"])

        # Only infrastructure-typed assets amortise; the appliance is excluded.
        amortisation_rows = service.get_infra_cost(cost_type="hardware_amortisation")
        self.assertEqual(1, len(amortisation_rows))
        amortisation_row = amortisation_rows[0]
        self.assertEqual("Homelab Server", amortisation_row["subject_name"])
        self.assertEqual(
            current_month_start.strftime("%Y-%m"), amortisation_row["billing_month"]
        )
        self.assertEqual(Decimal("30.0000"), Decimal(amortisation_row["est_cost"]))
        self.assertEqual("straight_line_36m", amortisation_row["cost_basis"])
        self.assertIsNone(amortisation_row["est_kwh"])

    def test_refresh_infra_cost_without_tariff_leaves_cost_null(self) -> None:
        service = TransformationService(DuckDBStore.memory())
        service.load_power_consumption(
            [
                {
                    "device_id": "ups-01",
                    "device_name": "UPS Rack A",
                    "recorded_at": "2026-03-10T10:00:00",
                    "watts": "400",
                }
            ],
            run_id="infra-run-006",
        )

        count = service.refresh_infra_cost()

        self.assertEqual(1, count)
        row = service.get_infra_cost()[0]
        self.assertEqual(Decimal("297.6000"), Decimal(row["est_kwh"]))
        self.assertIsNone(row["est_cost"])
        self.assertEqual("metered_power_no_tariff", row["cost_basis"])
