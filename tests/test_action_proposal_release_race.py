"""Approve/dismiss compare-and-set before the HA release.

Two API replicas share one durable control plane. When two operators resolve
the same HA proposal at the same moment, exactly one resolution wins the
compare-and-set and only that request releases the approval notification in
HA; the other gets ``409`` and never reaches HA. A failed release returns the
winner's proposal to pending (``release_failed``) and answers ``502``.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository


class _Record:
    def __init__(self, result: str) -> None:
        self.result = result


class _SlowDispatcher:
    """Records every HA release; holds each one open long enough to overlap."""

    def __init__(self, *, result: str = "success", delay: float = 0.2) -> None:
        self.releases: list[tuple[str, str, str]] = []
        self._lock = threading.Lock()
        self._result = result
        self._delay = delay

    async def resolve_approval(self, proposal, resolution) -> _Record:
        with self._lock:
            # The proposal handed to HA is already resolved: the CAS ran first.
            self.releases.append((proposal.action_id, resolution, proposal.status))
        time.sleep(self._delay)
        return _Record(self._result)


def _replica(tmp: str, dispatcher: _SlowDispatcher) -> TestClient:
    service = AccountTransactionService(
        landing_root=Path(tmp) / "landing",
        metadata_repository=RunMetadataRepository(Path(tmp) / "runs.db"),
    )
    return TestClient(
        create_app(
            service,
            config_repository=IngestionConfigRepository(Path(tmp) / "config.db"),
            transformation_service=TransformationService(DuckDBStore.memory()),
            ha_action_dispatcher=dispatcher,
        )
    )


def _draft_ha_proposal(client: TestClient) -> str:
    response = client.post(
        "/api/ha/actions/proposals",
        json={
            "policy_id": "office_temp_low",
            "policy_name": "Office temperature low",
            "verdict": "approval_required",
            "value": "17.0",
        },
    )
    assert response.status_code == 200
    return str(response.json()["action_id"])


def _race(clients: list[TestClient], paths: list[str]) -> list[int]:
    barrier = threading.Barrier(len(clients))
    statuses: list[int] = [0] * len(clients)

    def run(index: int) -> None:
        barrier.wait()
        statuses[index] = clients[index].post(paths[index]).status_code

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(clients))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return statuses


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("/api/actions/proposals/{id}/approve", "/api/ha/actions/proposals/{id}/approve"),
        ("/api/actions/proposals/{id}/approve", "/api/actions/proposals/{id}/dismiss"),
        ("/api/ha/actions/proposals/{id}/dismiss", "/api/ha/actions/proposals/{id}/dismiss"),
    ],
)
def test_racing_resolutions_release_in_ha_exactly_once(first: str, second: str) -> None:
    dispatcher = _SlowDispatcher()
    with TemporaryDirectory() as tmp:
        replica_a = _replica(tmp, dispatcher)
        replica_b = _replica(tmp, dispatcher)
        action_id = _draft_ha_proposal(replica_a)

        statuses = _race(
            [replica_a, replica_b],
            [first.format(id=action_id), second.format(id=action_id)],
        )

        assert sorted(statuses) == [200, 409]
        assert len(dispatcher.releases) == 1
        released_id, resolution, status_at_release = dispatcher.releases[0]
        assert released_id == action_id
        assert status_at_release == resolution
        stored = replica_b.get(f"/api/actions/proposals/{action_id}").json()
        assert stored["status"] == resolution
        kinds = [event["kind"] for event in stored["history"]]
        assert kinds == ["drafted", resolution]


def test_failed_release_reverts_the_winner_to_pending_for_retry() -> None:
    failing = _SlowDispatcher(result="failure", delay=0)
    with TemporaryDirectory() as tmp:
        client = _replica(tmp, failing)
        action_id = _draft_ha_proposal(client)

        response = client.post(f"/api/actions/proposals/{action_id}/approve")
        assert response.status_code == 502
        stored = client.get(f"/api/actions/proposals/{action_id}").json()
        assert stored["status"] == "pending"
        assert stored["approved_at"] is None
        assert stored["resolved_by"] is None
        assert [event["kind"] for event in stored["history"]] == [
            "drafted",
            "approved",
            "release_failed",
        ]

        # A retry through a healthy replica resolves it and releases once.
        healthy = _SlowDispatcher(delay=0)
        retry = _replica(tmp, healthy).post(f"/api/ha/actions/proposals/{action_id}/approve")
        assert retry.status_code == 200
        assert retry.json()["status"] == "approved"
        assert [release[1] for release in healthy.releases] == ["approved"]


def test_resolving_a_resolved_proposal_never_reaches_ha() -> None:
    dispatcher = _SlowDispatcher(delay=0)
    with TemporaryDirectory() as tmp:
        client = _replica(tmp, dispatcher)
        action_id = _draft_ha_proposal(client)
        assert client.post(f"/api/actions/proposals/{action_id}/dismiss").status_code == 200
        assert client.post(f"/api/actions/proposals/{action_id}/approve").status_code == 409
        assert client.post(f"/api/ha/actions/proposals/{action_id}/dismiss").status_code == 409
        assert [release[1] for release in dispatcher.releases] == ["dismissed"]
