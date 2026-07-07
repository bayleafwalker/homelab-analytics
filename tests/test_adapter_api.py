"""API tests for adapter ecosystem routes — contract exposure and metadata."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository


def _build_client(temp_dir: str) -> TestClient:
    from packages.domains.finance.pipelines.account_transaction_service import (
        AccountTransactionService,
    )

    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    ts = TransformationService(DuckDBStore.memory())
    app = create_app(
        service,
        transformation_service=ts,
        enable_unsafe_admin=True,
    )
    return TestClient(app)


class AdapterPacksAPITests(unittest.TestCase):
    def test_list_packs_includes_prometheus_core(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/adapters/packs")
            self.assertEqual(200, resp.status_code)
            packs = resp.json()["packs"]
            self.assertEqual(3, len(packs))
            pack_keys = {pack["pack_key"] for pack in packs}
            self.assertIn("ha_core", pack_keys)
            self.assertIn("export_core", pack_keys)
            self.assertIn("prometheus_core", pack_keys)

    def test_list_packs_returns_both_ha_and_export(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/adapters/packs")
            self.assertEqual(200, resp.status_code)
            packs = resp.json()["packs"]
            self.assertEqual(3, len(packs))
            pack_keys = {pack["pack_key"] for pack in packs}
            self.assertIn("ha_core", pack_keys)
            self.assertIn("export_core", pack_keys)

    def test_list_packs_includes_required_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/adapters/packs")
            self.assertEqual(200, resp.status_code)
            packs = resp.json()["packs"]
            ha_pack = next(p for p in packs if p["pack_key"] == "ha_core")
            self.assertIn("display_name", ha_pack)
            self.assertIn("version", ha_pack)
            self.assertIn("trust_level", ha_pack)
            self.assertIn("active", ha_pack)
            self.assertIn("adapter_count", ha_pack)
            self.assertIn("renderer_count", ha_pack)
            self.assertIn("description", ha_pack)
            self.assertEqual("verified", ha_pack["trust_level"])
            self.assertTrue(ha_pack["active"])

    def test_get_pack_detail_ha_core_returns_adapters(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/adapters/packs/ha_core")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual("ha_core", data["pack_key"])
            self.assertEqual("Home Assistant Core", data["display_name"])
            self.assertEqual(3, len(data["adapters"]))
            adapter_keys = {a["adapter_key"] for a in data["adapters"]}
            self.assertIn("ha_ingest", adapter_keys)
            self.assertIn("ha_mqtt_publish", adapter_keys)
            self.assertIn("ha_action", adapter_keys)

    def test_get_pack_detail_ha_adapter_has_manifest_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/adapters/packs/ha_core")
            self.assertEqual(200, resp.status_code)
            adapters = resp.json()["adapters"]
            ingest = next(a for a in adapters if a["adapter_key"] == "ha_ingest")
            self.assertIn("display_name", ingest)
            self.assertIn("version", ingest)
            self.assertIn("supported_directions", ingest)
            self.assertIn("ingest", ingest["supported_directions"])
            self.assertIn("supported_entity_classes", ingest)
            self.assertIn("credential_requirements", ingest)
            self.assertIn("health_check_contract", ingest)
            self.assertIn("target_capabilities", ingest)

    def test_get_pack_nonexistent_returns_404(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/adapters/packs/nonexistent")
            self.assertEqual(404, resp.status_code)
            self.assertIn("not found", resp.json()["detail"].lower())

    def test_get_pack_detail_export_core_returns_renderer(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/adapters/packs/export_core")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual("export_core", data["pack_key"])
            self.assertEqual("Export Core", data["display_name"])
            self.assertEqual(0, len(data["adapters"]))
            self.assertEqual(1, len(data["renderers"]))
            renderer = data["renderers"][0]
            self.assertEqual("export_csv_json", renderer["renderer_key"])
            self.assertEqual("Export Renderer — CSV / JSON", renderer["display_name"])
            self.assertIn("csv", renderer["supported_formats"])
            self.assertIn("json", renderer["supported_formats"])


class AdapterRenderersAPITests(unittest.TestCase):
    def test_list_renderers_returns_export_renderer(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/adapters/renderers")
            self.assertEqual(200, resp.status_code)
            renderers = resp.json()["renderers"]
            self.assertEqual(2, len(renderers))
            renderer_keys = {r["renderer_key"] for r in renderers}
            self.assertIn("export_csv_json", renderer_keys)
            self.assertIn("prometheus_metrics", renderer_keys)
            export_renderer = next(r for r in renderers if r["renderer_key"] == "export_csv_json")
            self.assertEqual("Export Renderer — CSV / JSON", export_renderer["display_name"])
            self.assertEqual("1.0", export_renderer["version"])

    def test_renderer_has_required_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/adapters/renderers")
            self.assertEqual(200, resp.status_code)
            renderers = resp.json()["renderers"]
            for renderer in renderers:
                self.assertIn("renderer_key", renderer)
                self.assertIn("display_name", renderer)
                self.assertIn("version", renderer)
                self.assertIn("supported_formats", renderer)
                self.assertIn("supported_publication_keys", renderer)


class AdapterContractsAPITests(unittest.TestCase):
    def test_contracts_returns_directions(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/adapters/contracts")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertIn("directions", data)
            directions = data["directions"]
            self.assertIn("ingest", directions)
            self.assertIn("publish", directions)
            self.assertIn("action", directions)
            self.assertIn("observe", directions)

    def test_contracts_returns_trust_levels(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/adapters/contracts")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertIn("trust_levels", data)
            trust_levels = data["trust_levels"]
            self.assertIn("verified", trust_levels)
            self.assertIn("community", trust_levels)
            self.assertIn("local", trust_levels)


class AdapterOperatorAPITests(unittest.TestCase):
    def test_enable_pack(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            # First, disable the pack (ha_core starts active)
            client.post("/adapters/packs/ha_core/disable")
            # Then enable it
            resp = client.post("/adapters/packs/ha_core/enable")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual("ha_core", data["pack_key"])
            self.assertTrue(data["active"])

    def test_disable_pack(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.post("/adapters/packs/ha_core/disable")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual("ha_core", data["pack_key"])
            self.assertFalse(data["active"])

    def test_enable_nonexistent_pack(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.post("/adapters/packs/nonexistent/enable")
            self.assertEqual(404, resp.status_code)

    def test_disable_nonexistent_pack(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.post("/adapters/packs/nonexistent/disable")
            self.assertEqual(404, resp.status_code)

    def test_get_pack_health(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/adapters/packs/ha_core/health")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual("ha_core", data["pack_key"])
            self.assertIn("active", data)
            self.assertIn("compatibility", data)
            compat = data["compatibility"]
            self.assertIn("is_compatible", compat)
            self.assertIn("issues", compat)
            self.assertIn("warnings", compat)

    def test_get_pack_health_nonexistent(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/adapters/packs/nonexistent/health")
            self.assertEqual(404, resp.status_code)

    def test_get_pack_config(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/adapters/packs/ha_core/config")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual("ha_core", data["pack_key"])
            self.assertIn("credential_requirements", data)
            self.assertIn("adapter_count", data)
            self.assertIn("renderer_count", data)
            # ha_core has adapters with credential_requirements
            self.assertGreater(len(data["credential_requirements"]), 0)
            # Verify credential_requirements is a sorted list
            creds = data["credential_requirements"]
            self.assertEqual(creds, sorted(creds))


class AdapterInstanceStatusAPITests(unittest.TestCase):
    """Live-status endpoints backed by AdapterInstanceRegistry."""

    def _client_with_prom_worker(self, tmp: str) -> TestClient:
        """Build a client with a fake Prometheus federation worker attached."""
        from unittest.mock import MagicMock

        from packages.domains.finance.pipelines.account_transaction_service import (
            AccountTransactionService,
        )

        service = AccountTransactionService(
            landing_root=Path(tmp) / "landing",
            metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
        )
        ts = TransformationService(DuckDBStore.memory())
        prom_worker = MagicMock()
        prom_worker.get_status.return_value = {
            "connected": True,
            "last_sync_at": "2026-06-01T12:00:00+00:00",
            "sync_count": 4,
            "last_sample_count": 42,
            "last_row_count": 42,
            "error_count": 0,
            "last_error": None,
        }
        app = create_app(
            service,
            transformation_service=ts,
            enable_unsafe_admin=True,
            prom_federation_worker=prom_worker,
        )
        return TestClient(app)

    def test_get_prom_ingest_status_returns_typed_shape(self) -> None:
        with TemporaryDirectory() as tmp:
            client = self._client_with_prom_worker(tmp)
            resp = client.get("/api/adapters/prom_ingest/status")
            self.assertEqual(200, resp.status_code)
            data = resp.json()
            self.assertEqual("prom_ingest", data["adapter_key"])
            self.assertTrue(data["enabled"])
            self.assertTrue(data["connected"])
            self.assertEqual("2026-06-01T12:00:00+00:00", data["last_activity_at"])
            self.assertEqual(0, data["error_count"])
            self.assertEqual(4, data["sync_count"])
            self.assertEqual(42, data["last_row_count"])

    def test_list_adapter_statuses_includes_prom_ingest(self) -> None:
        with TemporaryDirectory() as tmp:
            client = self._client_with_prom_worker(tmp)
            resp = client.get("/api/adapters/status")
            self.assertEqual(200, resp.status_code)
            adapters = resp.json()["adapters"]
            keys = {a["adapter_key"] for a in adapters}
            self.assertIn("prom_ingest", keys)

    def test_get_unknown_adapter_returns_404(self) -> None:
        with TemporaryDirectory() as tmp:
            client = self._client_with_prom_worker(tmp)
            resp = client.get("/api/adapters/not_a_real_adapter/status")
            self.assertEqual(404, resp.status_code)

    def test_status_endpoints_omitted_when_no_worker_wired(self) -> None:
        with TemporaryDirectory() as tmp:
            client = _build_client(tmp)
            resp = client.get("/api/adapters/status")
            self.assertEqual(200, resp.status_code)
            # No live workers wired in the default test app, so no adapters.
            self.assertEqual([], resp.json()["adapters"])
            resp404 = client.get("/api/adapters/prom_ingest/status")
            self.assertEqual(404, resp404.status_code)


if __name__ == "__main__":
    unittest.main()
