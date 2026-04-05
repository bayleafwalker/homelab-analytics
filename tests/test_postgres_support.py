from __future__ import annotations

import psycopg
import pytest

from packages.storage import postgres_support


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None

    def execute(self, sql: str) -> None:
        self.executed.append(sql)


def test_connect_with_retry_retries_operational_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}
    fake_connection = _FakeConnection()

    def fake_connect(*args, **kwargs):  # noqa: ANN002, ANN003
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise psycopg.OperationalError("database starting up")
        return fake_connection

    monkeypatch.setattr(postgres_support.psycopg, "connect", fake_connect)
    monkeypatch.setattr(postgres_support.time, "sleep", lambda *_: None)

    connection = postgres_support.connect_with_retry("postgresql://example")

    assert connection is fake_connection
    assert attempts["count"] == 3


def test_connect_with_retry_raises_after_retry_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        postgres_support,
        "_CONNECT_RETRY_ATTEMPTS",
        3,
    )

    def failing_connect(*args, **kwargs):  # noqa: ANN002, ANN003
        raise psycopg.OperationalError("database unavailable")

    monkeypatch.setattr(postgres_support.psycopg, "connect", failing_connect)
    monkeypatch.setattr(postgres_support.time, "sleep", lambda *_: None)

    with pytest.raises(psycopg.OperationalError, match="database unavailable"):
        postgres_support.connect_with_retry("postgresql://example")


def test_initialize_schema_uses_retrying_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_connection = _FakeConnection()
    call_args: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_connect(*args, **kwargs):  # noqa: ANN002, ANN003
        call_args.append((args, kwargs))
        return fake_connection

    monkeypatch.setattr(postgres_support.psycopg, "connect", fake_connect)

    postgres_support.initialize_schema("postgresql://example", "control")

    assert call_args == [(("postgresql://example",), {"row_factory": None})]
    assert fake_connection.executed == ["CREATE SCHEMA IF NOT EXISTS control"]
