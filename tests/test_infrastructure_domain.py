from __future__ import annotations

import unittest

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
