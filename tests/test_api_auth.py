from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.main import build_app
from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.shared.auth import SessionManager, hash_password
from packages.shared.settings import AppSettings
from packages.storage.auth_store import LocalUserCreate, UserRole
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository
from tests.account_test_support import FIXTURES as ACCOUNT_FIXTURES
from tests.control_plane_test_support import seed_source_asset_graph


class _StubReportingService:
    def get_monthly_cashflow(self, from_month=None, to_month=None):
        return [
            {
                "booking_month": "2026-01",
                "income": "2500.00",
                "expense": "900.00",
                "net": "1600.00",
                "transaction_count": 2,
            }
        ]

    def get_spend_by_category_monthly(self):
        return [
            {
                "booking_month": "2026-01",
                "category": "groceries",
                "counterparty_name": "Supermarket",
                "total_expense": "84.15",
            }
        ]

    def get_upcoming_fixed_costs_30d(self):
        return [
            {
                "contract_name": "Rent",
                "expected_date": "2026-04-01",
            }
        ]


def _build_client(
    temp_dir: str,
    *,
    users: tuple[tuple[str, str, UserRole], ...],
    reporting_service: Any | None = None,
) -> TestClient:
    service = AccountTransactionService(
        landing_root=Path(temp_dir) / "landing",
        metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
    )
    repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
    for index, (username, password, role) in enumerate(users, start=1):
        repository.create_local_user(
            LocalUserCreate(
                user_id=f"user-{index}",
                username=username,
                password_hash=hash_password(password),
                role=role,
            )
        )
    return TestClient(
        create_app(
            service,
            config_repository=repository,
            auth_store=repository,
            identity_mode="local",
            session_manager=SessionManager("test-session-secret"),
            reporting_service=cast(Any, reporting_service),
        )
    )


def _csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("homelab_analytics_csrf")
    assert token
    return {"x-csrf-token": token}


def _build_local_single_user_break_glass_client(
    temp_dir: str,
    *,
    client: tuple[str, int] = ("testclient", 50000),
) -> TestClient:
    settings = AppSettings(
        data_dir=Path(temp_dir),
        landing_root=Path(temp_dir) / "landing",
        metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
        account_transactions_inbox_dir=Path(temp_dir) / "inbox" / "account-transactions",
        processed_files_dir=Path(temp_dir) / "processed" / "account-transactions",
        failed_files_dir=Path(temp_dir) / "failed" / "account-transactions",
        api_host="127.0.0.1",
        api_port=8080,
        web_host="127.0.0.1",
        web_port=8081,
        worker_poll_interval_seconds=30,
        identity_mode="local_single_user",
        session_secret="test-session-secret",
        break_glass_enabled=True,
        break_glass_internal_only=True,
        break_glass_ttl_minutes=5,
        break_glass_allowed_cidrs=("10.0.0.0/8",),
        proxy_trusted_cidrs=("10.0.0.0/8",),
        enable_bootstrap_local_admin=True,
        bootstrap_admin_username="admin",
        bootstrap_admin_password="admin-password",
    )
    return TestClient(build_app(settings), client=client)


def _build_proxy_client(
    temp_dir: str,
    *,
    client: tuple[str, int] = ("testclient", 50000),
) -> TestClient:
    settings = AppSettings(
        data_dir=Path(temp_dir),
        landing_root=Path(temp_dir) / "landing",
        metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
        account_transactions_inbox_dir=Path(temp_dir) / "inbox" / "account-transactions",
        processed_files_dir=Path(temp_dir) / "processed" / "account-transactions",
        failed_files_dir=Path(temp_dir) / "failed" / "account-transactions",
        api_host="127.0.0.1",
        api_port=8080,
        web_host="127.0.0.1",
        web_port=8081,
        worker_poll_interval_seconds=30,
        identity_mode="proxy",
        proxy_trusted_cidrs=("10.0.0.0/8",),
        proxy_username_header="x-auth-user",
        proxy_role_header="x-auth-role",
        proxy_permissions_header="x-auth-permissions",
    )
    return TestClient(build_app(settings), client=client)


def test_api_local_auth_login_logout_and_me() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client(
            temp_dir,
            users=(("reader", "reader-password", UserRole.READER),),
        )

        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200
        assert client.get("/metrics").status_code == 200
        assert client.get("/runs").status_code == 401

        invalid_login = client.post(
            "/auth/login",
            json={"username": "reader", "password": "wrong-password"},
        )
        assert invalid_login.status_code == 401

        login = client.post(
            "/auth/login",
            json={"username": "reader", "password": "reader-password"},
            headers={"x-forwarded-proto": "https"},
        )
        assert login.status_code == 200
        assert "homelab_analytics_session" in login.headers["set-cookie"]
        assert "Secure" not in login.headers["set-cookie"]
        assert client.cookies.get("homelab_analytics_csrf")

        me = client.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["user"]["username"] == "reader"
        assert me.json()["principal"]["role"] == "reader"

        logout = client.post("/auth/logout", headers=_csrf_headers(client))
        assert logout.status_code == 200
        assert client.get("/auth/me").status_code == 401


def test_api_local_auth_enforces_newly_mapped_api_surfaces() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client(
            temp_dir,
            users=(
                ("reader", "reader-password", UserRole.READER),
                ("admin", "admin-password", UserRole.ADMIN),
            ),
            reporting_service=_StubReportingService(),
        )

        assert client.get("/contracts/publications").status_code == 401
        assert client.get("/api/scenarios").status_code == 401
        assert client.get("/api/ha/entities").status_code == 401
        assert (
            client.get(
                "/api/assistant/answer",
                params={"question": "what is our current monthly burn?"},
            ).status_code
            == 401
        )

        assert (
            client.post(
                "/auth/login",
                json={"username": "reader", "password": "reader-password"},
            ).status_code
            == 200
        )

        contracts = client.get("/contracts/publications")
        assert contracts.status_code == 200

        scenarios = client.get("/api/scenarios")
        assert scenarios.status_code == 503

        denied_scenario_create = client.post(
            "/api/scenarios/income-change",
            json={"monthly_income_delta": "100.00"},
            headers=_csrf_headers(client),
        )
        assert denied_scenario_create.status_code == 403

        ha_entities = client.get("/api/ha/entities")
        assert ha_entities.status_code == 503
        assistant = client.get(
            "/api/assistant/answer",
            params={"question": "what is our current monthly burn?"},
        )
        assert assistant.status_code == 200
        assistant_payload = assistant.json()
        assert assistant_payload["resolved_domain"] == "finance"
        assert assistant_payload["sources"][0]["publication_key"] == "mart_monthly_cashflow"

        denied_ha_ingest = client.post(
            "/api/ha/ingest",
            json={"states": []},
            headers=_csrf_headers(client),
        )
        assert denied_ha_ingest.status_code == 403

        denied_ha_proposal_create = client.post(
            "/api/ha/actions/proposals",
            json={
                "policy_id": "monthly_cashflow_review",
                "policy_name": "Monthly Cashflow Review",
                "verdict": "warning",
                "value": "Needs operator review",
            },
            headers=_csrf_headers(client),
        )
        assert denied_ha_proposal_create.status_code == 403

        denied_ha_proposal_approve = client.post(
            "/api/ha/actions/proposals/approval_device_control/approve",
            headers=_csrf_headers(client),
        )
        assert denied_ha_proposal_approve.status_code == 403

        denied_functions = client.get("/functions")
        assert denied_functions.status_code == 403

        assert client.post("/auth/logout", headers=_csrf_headers(client)).status_code == 200
        assert (
            client.post(
                "/auth/login",
                json={"username": "admin", "password": "admin-password"},
            ).status_code
            == 200
        )
        functions = client.get("/functions")
        assert functions.status_code == 200


def test_api_local_auth_enforces_reader_operator_and_admin_roles() -> None:
    with TemporaryDirectory() as temp_dir:
        reader_client = _build_client(
            temp_dir,
            users=(
                ("reader", "reader-password", UserRole.READER),
                ("operator", "operator-password", UserRole.OPERATOR),
                ("admin", "admin-password", UserRole.ADMIN),
            ),
            reporting_service=_StubReportingService(),
        )

        assert (
            reader_client.post(
                "/auth/login",
                json={"username": "reader", "password": "reader-password"},
            ).status_code
            == 200
        )
        assert reader_client.get("/runs").status_code == 200
        assistant = reader_client.get(
            "/api/assistant/answer",
            params={"question": "what is our current monthly burn?"},
        )
        assert assistant.status_code == 200
        assert "Latest monthly cashflow" in assistant.json()["answer"]
        assert (
            reader_client.post(
                "/ingest",
                json={
                    "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "manual-upload",
                },
                headers=_csrf_headers(reader_client),
            ).status_code
            == 403
        )
        assert (
            reader_client.post(
                "/runs/example-run/retry",
                headers=_csrf_headers(reader_client),
            ).status_code
            == 403
        )
        assert reader_client.get("/control/schedule-dispatches").status_code == 200
        assert (
            reader_client.post(
                "/control/schedule-dispatches",
                json={},
                headers=_csrf_headers(reader_client),
            ).status_code
            == 403
        )
        assert reader_client.get("/config/source-systems").status_code == 403

    with TemporaryDirectory() as temp_dir:
        operator_client = _build_client(
            temp_dir,
            users=(("operator", "operator-password", UserRole.OPERATOR),),
        )

        assert (
            operator_client.post(
                "/auth/login",
                json={"username": "operator", "password": "operator-password"},
            ).status_code
            == 200
        )
        ingest = operator_client.post(
            "/ingest",
            json={
                "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                "source_name": "manual-upload",
            },
            headers=_csrf_headers(operator_client),
        )
        assert ingest.status_code == 201
        assert (
            operator_client.post(
                f"/runs/{ingest.json()['run']['run_id']}/retry",
                headers=_csrf_headers(operator_client),
            ).status_code
            == 201
        )
        assert operator_client.get("/control/schedule-dispatches").status_code == 200
        assert (
            operator_client.post(
                "/control/schedule-dispatches",
                json={},
                headers=_csrf_headers(operator_client),
            ).status_code
            == 201
        )
        assert operator_client.get("/config/source-systems").status_code == 403

    with TemporaryDirectory() as temp_dir:
        admin_client = _build_client(
            temp_dir,
            users=(("admin", "admin-password", UserRole.ADMIN),),
        )

        assert (
            admin_client.post(
                "/auth/login",
                json={"username": "admin", "password": "admin-password"},
            ).status_code
            == 200
        )
        config_response = admin_client.get("/config/source-systems")
        assert config_response.status_code == 200
        assert config_response.json()["source_systems"] == []


def test_api_local_auth_restricts_terminal_manifest_and_execute_to_admins() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client(
            temp_dir,
            users=(
                ("reader", "reader-password", UserRole.READER),
                ("admin", "admin-password", UserRole.ADMIN),
            ),
        )

        assert (
            client.post(
                "/auth/login",
                json={"username": "reader", "password": "reader-password"},
            ).status_code
            == 200
        )
        assert client.get("/control/terminal/commands").status_code == 403
        assert (
            client.post(
                "/control/terminal/execute",
                json={"command_line": "help"},
                headers=_csrf_headers(client),
            ).status_code
            == 403
        )

        assert client.post("/auth/logout", headers=_csrf_headers(client)).status_code == 200
        assert (
            client.post(
                "/auth/login",
                json={"username": "admin", "password": "admin-password"},
            ).status_code
            == 200
        )

        commands = client.get("/control/terminal/commands")
        assert commands.status_code == 200
        assert "help" in {command["name"] for command in commands.json()["commands"]}

        execution = client.post(
            "/control/terminal/execute",
            json={"command_line": "help"},
            headers=_csrf_headers(client),
        )
        assert execution.status_code == 200
        assert execution.json()["execution"]["command_name"] == "help"


def test_api_local_auth_rejects_state_changing_requests_without_csrf_token() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client(
            temp_dir,
            users=(("operator", "operator-password", UserRole.OPERATOR),),
        )

        assert (
            client.post(
                "/auth/login",
                json={"username": "operator", "password": "operator-password"},
            ).status_code
            == 200
        )
        ingest = client.post(
            "/ingest",
            json={
                "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                "source_name": "manual-upload",
            },
        )
        assert ingest.status_code == 403
        assert ingest.json()["detail"] == "CSRF validation failed."


def test_api_local_auth_supports_admin_user_management_and_audit() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client(
            temp_dir,
            users=(("admin", "admin-password", UserRole.ADMIN),),
            reporting_service=_StubReportingService(),
        )

        assert (
            client.post(
                "/auth/login",
                json={"username": "admin", "password": "admin-password"},
            ).status_code
            == 200
        )
        headers = _csrf_headers(client)

        created = client.post(
            "/auth/users",
            json={
                "username": "reader-two",
                "password": "reader-password",
                "role": "reader",
            },
            headers=headers,
        )
        assert created.status_code == 201
        created_user = created.json()["user"]
        assert created_user["username"] == "reader-two"
        assert created_user["role"] == "reader"

        updated = client.patch(
            f"/auth/users/{created_user['user_id']}",
            json={"role": "operator", "enabled": False},
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json()["user"]["role"] == "operator"
        assert updated.json()["user"]["enabled"] is False

        reset = client.post(
            f"/auth/users/{created_user['user_id']}/password",
            json={"password": "rotated-password"},
            headers=headers,
        )
        assert reset.status_code == 200

        users_response = client.get("/auth/users")
        assert users_response.status_code == 200
        assert any(
            user["username"] == "reader-two" and user["enabled"] is False
            for user in users_response.json()["users"]
        )

        audit_response = client.get("/control/auth-audit?limit=10")
        assert audit_response.status_code == 200
        event_types = [
            event["event_type"] for event in audit_response.json()["auth_audit_events"]
        ]
        assert "password_reset" in event_types
        assert "user_updated" in event_types
        assert "user_created" in event_types


def test_api_local_auth_supports_service_token_management_and_bearer_auth() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client(
            temp_dir,
            users=(("admin", "admin-password", UserRole.ADMIN),),
            reporting_service=_StubReportingService(),
        )

        assert (
            client.post(
                "/auth/login",
                json={"username": "admin", "password": "admin-password"},
            ).status_code
            == 200
        )
        headers = _csrf_headers(client)

        created = client.post(
            "/auth/service-tokens",
            json={
                "token_name": "home-assistant",
                "role": "operator",
                "scopes": ["reports:read", "runs:read", "ingest:write"],
            },
            headers=headers,
        )
        assert created.status_code == 201
        created_payload = created.json()
        assert created_payload["token_value"].startswith("hst_")
        assert created_payload["service_token"]["token_name"] == "home-assistant"
        token_id = created_payload["service_token"]["token_id"]
        token_value = created_payload["token_value"]

        listed = client.get("/auth/service-tokens")
        assert listed.status_code == 200
        assert [token["token_id"] for token in listed.json()["service_tokens"]] == [token_id]

        me = client.get(
            "/auth/me",
            headers={"authorization": f"Bearer {token_value}"},
        )
        assert me.status_code == 200
        assert me.json()["principal"]["auth_provider"] == "service_token"
        assert me.json()["user"]["scopes"] == [
            "reports:read",
            "runs:read",
            "ingest:write",
        ]

        ingest = client.post(
            "/ingest",
            json={
                "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                "source_name": "service-token-upload",
            },
            headers={"authorization": f"Bearer {token_value}"},
        )
        assert ingest.status_code == 201
        assert (
            client.get(
                "/config/source-systems",
                headers={"authorization": f"Bearer {token_value}"},
            ).status_code
            == 403
        )

        revoked = client.post(
            f"/auth/service-tokens/{token_id}/revoke",
            headers=headers,
        )
        assert revoked.status_code == 200
        assert revoked.json()["service_token"]["revoked"] is True

        rejected = client.get(
            "/runs",
            headers={"authorization": f"Bearer {token_value}"},
        )
        assert rejected.status_code == 401

        audit_response = client.get("/control/auth-audit?limit=20")
        assert audit_response.status_code == 200
        event_types = [
            event["event_type"] for event in audit_response.json()["auth_audit_events"]
        ]
        assert "service_token_created" in event_types
        assert "service_token_revoked" in event_types
        assert "service_token_auth_failed" in event_types


def test_api_service_tokens_enforce_scope_boundaries() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client(
            temp_dir,
            users=(("admin", "admin-password", UserRole.ADMIN),),
            reporting_service=_StubReportingService(),
        )
        assert (
            client.post(
                "/auth/login",
                json={"username": "admin", "password": "admin-password"},
            ).status_code
            == 200
        )
        created = client.post(
            "/auth/service-tokens",
            json={
                "token_name": "dashboard-reader",
                "role": "reader",
                "scopes": ["reports:read"],
            },
            headers=_csrf_headers(client),
        )
        assert created.status_code == 201
        token_value = created.json()["token_value"]

        assert (
            client.get(
                "/reports/monthly-cashflow",
                headers={"authorization": f"Bearer {token_value}"},
            ).status_code
            == 200
        )
        denied = client.get(
            "/runs",
            headers={"authorization": f"Bearer {token_value}"},
        )
        assert denied.status_code == 403
        assert denied.json()["detail"] == "runs:read scope required."


def test_api_local_auth_locks_out_repeated_failed_logins() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_client(
            temp_dir,
            users=(("reader", "reader-password", UserRole.READER),),
        )

        for _ in range(5):
            failed = client.post(
                "/auth/login",
                json={"username": "reader", "password": "wrong-password"},
            )
            assert failed.status_code == 401

        locked = client.post(
            "/auth/login",
            json={"username": "reader", "password": "reader-password"},
        )
        assert locked.status_code == 429
        assert locked.json()["detail"] == "Too many failed login attempts. Try again later."


def test_api_local_auth_allows_reader_run_lineage_and_publication_visibility() -> None:
    with TemporaryDirectory() as temp_dir:
        service = AccountTransactionService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
        )
        repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
        seed_source_asset_graph(repository)
        repository.create_local_user(
            LocalUserCreate(
                user_id="user-reader",
                username="reader",
                password_hash=hash_password("reader-password"),
                role=UserRole.READER,
            )
        )
        client = TestClient(
            create_app(
                service,
                config_repository=repository,
                auth_store=repository,
                identity_mode="local",
                session_manager=SessionManager("test-session-secret"),
            )
        )

        assert (
            client.post(
                "/auth/login",
                json={"username": "reader", "password": "reader-password"},
            ).status_code
            == 200
        )
        assert client.get("/control/source-lineage", params={"run_id": "run-001"}).status_code == 200
        assert client.get("/control/publication-audit", params={"run_id": "run-001"}).status_code == 200


def test_api_local_single_user_break_glass_enforces_cidr_and_ttl_session_cookie() -> None:
    with TemporaryDirectory() as temp_dir:
        with _build_local_single_user_break_glass_client(temp_dir) as client:
            blocked = client.post(
                "/auth/login",
                json={"username": "admin", "password": "admin-password"},
                headers={"x-forwarded-for": "10.23.45.67"},
            )
            assert blocked.status_code == 403
            assert "internal addresses" in blocked.json()["detail"]

        with _build_local_single_user_break_glass_client(
            temp_dir,
            client=("10.0.0.10", 50000),
        ) as trusted_client:
            login = trusted_client.post(
                "/auth/login",
                json={"username": "admin", "password": "admin-password"},
                headers={
                    "x-forwarded-for": "10.23.45.67",
                    "x-forwarded-proto": "https",
                },
            )
            assert login.status_code == 200
            assert "Max-Age=300" in login.headers["set-cookie"]
            assert "Secure" in login.headers["set-cookie"]
            assert login.json()["auth_mode"] == "local_single_user"

            session_cookie = trusted_client.cookies.get("homelab_analytics_session")
            assert session_cookie is not None
            ready = trusted_client.get(
                "/ready",
                headers={"x-forwarded-for": "10.23.45.67"},
            )
            assert ready.status_code == 200
            payload = ready.json()
            assert payload["identity_mode"] == "local_single_user"
            assert payload["break_glass"]["enabled"] is True
            assert payload["break_glass"]["active"] is True
            assert payload["break_glass"]["ttl_minutes"] == 5

            me = trusted_client.get(
                "/auth/me",
                headers={"x-forwarded-for": "10.23.45.67"},
                cookies={"homelab_analytics_session": session_cookie},
            )
            assert me.status_code == 200


def test_api_local_single_user_disables_multi_user_local_management() -> None:
    with TemporaryDirectory() as temp_dir:
        client = _build_local_single_user_break_glass_client(
            temp_dir,
            client=("10.0.0.10", 50000),
        )

        login = client.post(
            "/auth/login",
            json={"username": "admin", "password": "admin-password"},
            headers={"x-forwarded-for": "10.23.45.67"},
        )
        assert login.status_code == 200

        csrf_token = client.cookies.get("homelab_analytics_csrf")
        assert csrf_token is not None
        headers = {
            "x-csrf-token": csrf_token,
            "x-forwarded-for": "10.23.45.67",
        }

        create_user = client.post(
            "/auth/users",
            json={
                "username": "operator-two",
                "password": "operator-password",
                "role": "operator",
            },
            headers=headers,
        )
        assert create_user.status_code == 403
        assert "local_single_user mode" in create_user.json()["detail"]


def test_api_proxy_auth_enforces_trusted_source_and_header_identity() -> None:
    with TemporaryDirectory() as temp_dir:
        with _build_proxy_client(temp_dir) as direct_client:
            untrusted = direct_client.get(
                "/runs",
                headers={
                    "x-forwarded-for": "10.2.3.4",
                    "x-auth-user": "reader@example.test",
                    "x-auth-role": "reader",
                },
            )
            assert untrusted.status_code == 403

        with _build_proxy_client(temp_dir, client=("10.0.0.10", 50000)) as trusted_client:
            missing_identity = trusted_client.get(
                "/runs",
                headers={"x-forwarded-for": "10.2.3.4"},
            )
            assert missing_identity.status_code == 401
            assert "x-auth-user" in missing_identity.json()["detail"]

            reader_runs = trusted_client.get(
                "/runs",
                headers={
                    "x-forwarded-for": "10.2.3.4",
                    "x-auth-user": "reader@example.test",
                    "x-auth-role": "reader",
                },
            )
            assert reader_runs.status_code == 200

            denied_ingest = trusted_client.post(
                "/ingest",
                json={
                    "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "proxy-reader-upload",
                },
                headers={
                    "x-forwarded-for": "10.2.3.4",
                    "x-auth-user": "reader@example.test",
                    "x-auth-role": "reader",
                },
            )
            assert denied_ingest.status_code == 403

            operator_ingest = trusted_client.post(
                "/ingest",
                json={
                    "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "proxy-operator-upload",
                },
                headers={
                    "x-forwarded-for": "10.2.3.4",
                    "x-auth-user": "operator@example.test",
                    "x-auth-role": "operator",
                    "x-auth-permissions": "ingest.write,runs.retry",
                },
            )
            assert operator_ingest.status_code == 201

            me = trusted_client.get(
                "/auth/me",
                headers={
                    "x-forwarded-for": "10.2.3.4",
                    "x-auth-user": "operator@example.test",
                    "x-auth-role": "operator",
                    "x-auth-permissions": "ingest.write,runs.retry",
                },
            )
            assert me.status_code == 200
            payload = me.json()
            assert payload["auth_mode"] == "proxy"
            assert payload["principal"]["auth_provider"] == "proxy"
            assert "ingest.write" in payload["principal"]["permissions"]
