"""SQLite parity for the dialect-shared control-plane contract assertions.

The authoritative contract runs against Postgres (``test_control_plane_store_contract``,
slow/integration). The execution control plane and source-contract catalog share one
dialect-neutral implementation (as does the action-proposal queue), so the same assertions run here against SQLite to
prove both dialect hooks behave identically.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from packages.storage.control_plane import ControlPlaneStore
from packages.storage.ingestion_config import IngestionConfigRepository
from tests.control_plane_test_support import (
    assert_action_proposal_changes_feed,
    assert_action_proposal_resolution_is_exclusive,
    assert_action_proposal_store_behaviour,
    assert_control_plane_store_round_trip,
    assert_control_plane_store_update_behaviour,
    assert_schedule_dispatch_behaviour,
    assert_schedule_dispatch_claim_is_exclusive,
    assert_schedule_dispatch_resilience_behaviour,
)


@pytest.fixture
def control_plane_store(tmp_path: Path) -> Iterator[ControlPlaneStore]:
    yield IngestionConfigRepository(tmp_path / "config.db")


@pytest.mark.parametrize(
    "assertion",
    [
        assert_control_plane_store_round_trip,
        assert_control_plane_store_update_behaviour,
        assert_schedule_dispatch_behaviour,
        assert_schedule_dispatch_resilience_behaviour,
        assert_schedule_dispatch_claim_is_exclusive,
        assert_action_proposal_store_behaviour,
        assert_action_proposal_resolution_is_exclusive,
        assert_action_proposal_changes_feed,
    ],
    ids=lambda assertion: assertion.__name__,
)
def test_sqlite_control_plane_store_matches_shared_contract(
    control_plane_store: ControlPlaneStore,
    assertion: Callable[[ControlPlaneStore], None],
) -> None:
    assertion(control_plane_store)


def test_dialect_bindings_resolve_to_shared_implementations() -> None:
    from packages.storage.action_proposal_store import ActionProposalStoreMixin
    from packages.storage.execution_control_plane import ExecutionControlPlaneMixin
    from packages.storage.postgres_ingestion_config import PostgresIngestionConfigRepository
    from packages.storage.source_contract_catalog import SourceContractCatalogMixin
    from packages.storage.sql_dialect import PostgresSessionMixin, SQLiteSessionMixin

    def owner(cls: type, name: str) -> type:
        return next(klass for klass in cls.__mro__ if name in vars(klass))

    for repository, session_mixin in (
        (IngestionConfigRepository, SQLiteSessionMixin),
        (PostgresIngestionConfigRepository, PostgresSessionMixin),
    ):
        # Stubs declared on sibling mixins must not shadow the shared implementations.
        assert owner(repository, "_session") is session_mixin
        for shared in (
            ExecutionControlPlaneMixin,
            SourceContractCatalogMixin,
            ActionProposalStoreMixin,
        ):
            for name in vars(shared):
                if not name.startswith("__"):
                    assert owner(repository, name) is shared, (repository.__name__, name)
