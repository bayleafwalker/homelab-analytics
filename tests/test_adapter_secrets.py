"""Tests for adapter secret resolution."""

from __future__ import annotations

import pytest

from packages.adapters.contracts import AdapterDirection, AdapterManifest
from packages.platform.adapter_secrets import (
    ChainedSecretResolver,
    ControlPlaneSecretResolver,
    EnvSecretResolver,
    FileSecretResolver,
    MissingSecretError,
    resolve_manifest_credentials,
)


def _manifest(*requirements: str) -> AdapterManifest:
    return AdapterManifest(
        adapter_key="unit_test_adapter",
        display_name="Unit Test Adapter",
        version="1.0",
        supported_directions=(AdapterDirection.INGEST,),
        credential_requirements=requirements,
    )


def test_env_resolver_returns_value_when_set():
    resolver = EnvSecretResolver(env={"HA_TOKEN": "abc"})
    assert resolver.resolve("HA_TOKEN") == "abc"


def test_env_resolver_returns_none_for_missing_or_empty():
    resolver = EnvSecretResolver(env={"HA_TOKEN": ""})
    assert resolver.resolve("HA_TOKEN") is None
    assert resolver.resolve("UNSET_NAME") is None


def test_file_resolver_reads_secret_from_file(tmp_path):
    (tmp_path / "HA_TOKEN").write_text("secret-value\n")
    resolver = FileSecretResolver(root=tmp_path)
    assert resolver.resolve("HA_TOKEN") == "secret-value"


def test_file_resolver_returns_none_for_missing_file(tmp_path):
    resolver = FileSecretResolver(root=tmp_path)
    assert resolver.resolve("HA_TOKEN") is None


def test_file_resolver_returns_none_for_empty_file(tmp_path):
    (tmp_path / "EMPTY").write_text("")
    resolver = FileSecretResolver(root=tmp_path)
    assert resolver.resolve("EMPTY") is None


def test_control_plane_resolver_delegates_to_callable():
    store = {"HA_TOKEN": "cp-value"}
    resolver = ControlPlaneSecretResolver(lookup=lambda name: store.get(name))
    assert resolver.resolve("HA_TOKEN") == "cp-value"
    assert resolver.resolve("UNKNOWN") is None


def test_chained_resolver_prefers_earlier_resolver(tmp_path):
    (tmp_path / "HA_TOKEN").write_text("file-value")
    chain = ChainedSecretResolver(
        [
            EnvSecretResolver(env={"HA_TOKEN": "env-value"}),
            FileSecretResolver(root=tmp_path),
        ]
    )
    assert chain.resolve("HA_TOKEN") == "env-value"


def test_chained_resolver_falls_through_on_none(tmp_path):
    (tmp_path / "HA_TOKEN").write_text("file-value")
    chain = ChainedSecretResolver(
        [
            EnvSecretResolver(env={}),
            FileSecretResolver(root=tmp_path),
        ]
    )
    assert chain.resolve("HA_TOKEN") == "file-value"


def test_chained_resolver_returns_none_when_all_miss():
    chain = ChainedSecretResolver(
        [
            EnvSecretResolver(env={}),
            EnvSecretResolver(env={}),
        ]
    )
    assert chain.resolve("HA_TOKEN") is None


def test_resolve_manifest_credentials_returns_full_mapping():
    manifest = _manifest("HA_TOKEN", "MQTT_PASSWORD")
    resolver = EnvSecretResolver(env={"HA_TOKEN": "a", "MQTT_PASSWORD": "b"})
    assert resolve_manifest_credentials(manifest, resolver) == {
        "HA_TOKEN": "a",
        "MQTT_PASSWORD": "b",
    }


def test_resolve_manifest_credentials_raises_for_missing_required():
    manifest = _manifest("HA_TOKEN", "MQTT_PASSWORD")
    resolver = EnvSecretResolver(env={"HA_TOKEN": "a"})
    with pytest.raises(MissingSecretError) as exc:
        resolve_manifest_credentials(manifest, resolver)
    assert exc.value.missing == ("MQTT_PASSWORD",)


def test_resolve_manifest_credentials_treats_optional_as_absent_without_raising():
    manifest = _manifest("HA_TOKEN", "MQTT_PASSWORD")
    resolver = EnvSecretResolver(env={"HA_TOKEN": "a"})
    result = resolve_manifest_credentials(
        manifest, resolver, optional=("MQTT_PASSWORD",)
    )
    assert result == {"HA_TOKEN": "a"}


def test_resolve_manifest_credentials_accepts_bare_iterable():
    resolver = EnvSecretResolver(env={"HA_TOKEN": "a"})
    assert resolve_manifest_credentials(("HA_TOKEN",), resolver) == {"HA_TOKEN": "a"}
