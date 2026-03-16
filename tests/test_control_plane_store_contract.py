from __future__ import annotations

from packages.storage.control_plane import ControlPlaneStore
from tests.control_plane_test_support import (
    assert_auth_audit_behaviour,
    assert_control_plane_protocol_conformance,
    assert_control_plane_store_round_trip,
    assert_control_plane_store_update_behaviour,
    assert_schedule_dispatch_behaviour,
    assert_schedule_dispatch_claim_is_exclusive,
    assert_schedule_dispatch_resilience_behaviour,
    assert_service_token_behaviour,
)

pytest_plugins = ("tests.control_plane_backend_fixtures",)


def test_control_plane_store_implements_aggregate_protocols(
    control_plane_store: ControlPlaneStore,
) -> None:
    assert_control_plane_protocol_conformance(control_plane_store)


def test_control_plane_store_round_trips_config_and_control_plane_entities(
    control_plane_store: ControlPlaneStore,
) -> None:
    assert_control_plane_store_round_trip(control_plane_store)


def test_control_plane_store_enqueues_due_schedules_and_respects_concurrency(
    control_plane_store: ControlPlaneStore,
) -> None:
    assert_schedule_dispatch_behaviour(control_plane_store)


def test_control_plane_store_renews_and_recovers_stale_dispatches(
    control_plane_store: ControlPlaneStore,
) -> None:
    assert_schedule_dispatch_resilience_behaviour(control_plane_store)


def test_control_plane_store_claims_dispatches_exclusively(
    control_plane_store: ControlPlaneStore,
) -> None:
    assert_schedule_dispatch_claim_is_exclusive(control_plane_store)


def test_control_plane_store_updates_entities_and_supports_manual_dispatch(
    control_plane_store: ControlPlaneStore,
) -> None:
    assert_control_plane_store_update_behaviour(control_plane_store)


def test_control_plane_store_records_and_filters_auth_audit_events(
    control_plane_store: ControlPlaneStore,
) -> None:
    assert_auth_audit_behaviour(control_plane_store)


def test_control_plane_store_manages_service_tokens(
    control_plane_store: ControlPlaneStore,
) -> None:
    assert_service_token_behaviour(control_plane_store)
