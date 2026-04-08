from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ha_bridge_ingest_architecture_doc_captures_implemented_contract() -> None:
    doc = (ROOT / "docs" / "architecture" / "ha-bridge-ingest-api.md").read_text()

    assert "/api/ingest/ha-bridge/registry" in doc
    assert "/api/ingest/ha-bridge/states" in doc
    assert "/api/ingest/ha-bridge/events" in doc
    assert "/api/ingest/ha-bridge/statistics" in doc
    assert "/api/ingest/ha-bridge/heartbeat" in doc
    assert "ha-bridge:ingest" in doc
    assert 'schema_version = "1.0"' in doc
    assert "canonical_entity_id" in doc
    assert "Retry-After" in doc
