"""Tests for the entity correlation registry."""

from __future__ import annotations

from packages.adapters.contracts import (
    CanonicalEntityId,
    EntityAlias,
    TrustLevel,
)
from packages.adapters.entity_correlation import EntityCorrelationRegistry


def _alias(
    adapter_key: str,
    source_entity_id: str,
    *,
    canonical_key: str,
    entity_class: str = "device",
    trust_level: TrustLevel = TrustLevel.LOCAL,
) -> EntityAlias:
    return EntityAlias(
        adapter_key=adapter_key,
        entity_class=entity_class,
        source_entity_id=source_entity_id,
        canonical_key=canonical_key,
        trust_level=trust_level,
    )


def test_resolve_returns_none_when_no_alias_registered():
    registry = EntityCorrelationRegistry()
    assert (
        registry.resolve(
            adapter_key="ha", entity_class="device", source_entity_id="sensor.hp"
        )
        is None
    )


def test_resolve_returns_canonical_id_for_registered_alias():
    registry = EntityCorrelationRegistry()
    registry.register_alias(
        _alias("ha", "sensor.heat_pump_power", canonical_key="heat_pump")
    )

    canonical = registry.resolve(
        adapter_key="ha",
        entity_class="device",
        source_entity_id="sensor.heat_pump_power",
    )

    assert canonical == CanonicalEntityId(
        entity_class="device", canonical_key="heat_pump"
    )


def test_two_adapters_can_share_a_canonical_entity():
    registry = EntityCorrelationRegistry()
    registry.register_alias(
        _alias("ha", "sensor.heat_pump_power", canonical_key="heat_pump")
    )
    registry.register_alias(
        _alias("prometheus", "hp_power_watts", canonical_key="heat_pump")
    )

    ha_id = registry.resolve(
        adapter_key="ha",
        entity_class="device",
        source_entity_id="sensor.heat_pump_power",
    )
    prom_id = registry.resolve(
        adapter_key="prometheus",
        entity_class="device",
        source_entity_id="hp_power_watts",
    )

    assert ha_id == prom_id
    assert ha_id is not None
    aliases = registry.aliases_for(ha_id)
    assert {alias.adapter_key for alias in aliases} == {"ha", "prometheus"}


def test_higher_trust_alias_replaces_lower_trust_alias_on_conflict():
    registry = EntityCorrelationRegistry()
    registry.register_alias(
        _alias(
            "ha",
            "sensor.hp",
            canonical_key="wrong_guess",
            trust_level=TrustLevel.LOCAL,
        )
    )
    kept = registry.register_alias(
        _alias(
            "ha",
            "sensor.hp",
            canonical_key="heat_pump",
            trust_level=TrustLevel.VERIFIED,
        )
    )

    assert kept.canonical_key == "heat_pump"
    resolved = registry.resolve(
        adapter_key="ha", entity_class="device", source_entity_id="sensor.hp"
    )
    assert resolved is not None
    assert resolved.canonical_key == "heat_pump"


def test_lower_trust_alias_does_not_overwrite_higher_trust_alias():
    registry = EntityCorrelationRegistry()
    registry.register_alias(
        _alias(
            "ha",
            "sensor.hp",
            canonical_key="heat_pump",
            trust_level=TrustLevel.VERIFIED,
        )
    )
    kept = registry.register_alias(
        _alias(
            "ha",
            "sensor.hp",
            canonical_key="local_guess",
            trust_level=TrustLevel.LOCAL,
        )
    )

    assert kept.canonical_key == "heat_pump"


def test_equal_trust_registration_overrides_previous():
    registry = EntityCorrelationRegistry()
    registry.register_alias(
        _alias(
            "ha",
            "sensor.hp",
            canonical_key="old_guess",
            trust_level=TrustLevel.COMMUNITY,
        )
    )
    kept = registry.register_alias(
        _alias(
            "ha",
            "sensor.hp",
            canonical_key="corrected",
            trust_level=TrustLevel.COMMUNITY,
        )
    )

    assert kept.canonical_key == "corrected"


def test_aliases_for_returns_deterministic_ordering():
    registry = EntityCorrelationRegistry()
    registry.register_alias(
        _alias("prometheus", "hp_power_watts", canonical_key="heat_pump")
    )
    registry.register_alias(
        _alias("ha", "sensor.heat_pump_power", canonical_key="heat_pump")
    )

    aliases = registry.aliases_for(
        CanonicalEntityId(entity_class="device", canonical_key="heat_pump")
    )

    assert [alias.adapter_key for alias in aliases] == ["ha", "prometheus"]
