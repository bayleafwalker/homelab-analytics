from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from packages.storage.ingestion_catalog import (
    _BUILTIN_PUBLICATION_DEFINITIONS,
    _BUILTIN_TRANSFORMATION_PACKAGES,
)


def initialize_sqlite_control_plane_schema(connection: sqlite3.Connection) -> None:
    """Bootstrap SQLite control-plane schema for local/dev convenience.

    SQLite is retained as a best-effort fallback and is not the canonical
    control-plane schema evolution target.
    """
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS source_systems (
            source_system_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            transport TEXT NOT NULL,
            schedule_mode TEXT NOT NULL,
            description TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dataset_contracts (
            dataset_contract_id TEXT PRIMARY KEY,
            dataset_name TEXT NOT NULL,
            version INTEGER NOT NULL,
            allow_extra_columns INTEGER NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            columns_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS column_mappings (
            column_mapping_id TEXT PRIMARY KEY,
            source_system_id TEXT NOT NULL,
            dataset_contract_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            rules_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (source_system_id) REFERENCES source_systems (source_system_id),
            FOREIGN KEY (dataset_contract_id) REFERENCES dataset_contracts (dataset_contract_id)
        );

        CREATE TABLE IF NOT EXISTS transformation_packages (
            transformation_package_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            handler_key TEXT NOT NULL,
            version INTEGER NOT NULL,
            description TEXT,
            archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS publication_definitions (
            publication_definition_id TEXT PRIMARY KEY,
            transformation_package_id TEXT NOT NULL,
            publication_key TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (transformation_package_id) REFERENCES transformation_packages (transformation_package_id)
        );

        CREATE TABLE IF NOT EXISTS source_assets (
            source_asset_id TEXT PRIMARY KEY,
            source_system_id TEXT NOT NULL,
            dataset_contract_id TEXT NOT NULL,
            column_mapping_id TEXT NOT NULL,
            transformation_package_id TEXT,
            name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            description TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (source_system_id) REFERENCES source_systems (source_system_id),
            FOREIGN KEY (dataset_contract_id) REFERENCES dataset_contracts (dataset_contract_id),
            FOREIGN KEY (column_mapping_id) REFERENCES column_mappings (column_mapping_id),
            FOREIGN KEY (transformation_package_id) REFERENCES transformation_packages (transformation_package_id)
        );

        CREATE TABLE IF NOT EXISTS ingestion_definitions (
            ingestion_definition_id TEXT PRIMARY KEY,
            source_asset_id TEXT NOT NULL,
            transport TEXT NOT NULL,
            schedule_mode TEXT NOT NULL,
            source_path TEXT NOT NULL,
            file_pattern TEXT NOT NULL,
            processed_path TEXT,
            failed_path TEXT,
            poll_interval_seconds INTEGER,
            request_url TEXT,
            request_method TEXT,
            request_headers_json TEXT,
            request_timeout_seconds INTEGER,
            response_format TEXT,
            output_file_name TEXT,
            enabled INTEGER NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            source_name TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (source_asset_id) REFERENCES source_assets (source_asset_id)
        );

        CREATE TABLE IF NOT EXISTS extension_registry_sources (
            extension_registry_source_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            location TEXT NOT NULL,
            desired_ref TEXT,
            subdirectory TEXT,
            auth_secret_name TEXT,
            auth_secret_key TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS extension_registry_revisions (
            extension_registry_revision_id TEXT PRIMARY KEY,
            extension_registry_source_id TEXT NOT NULL,
            resolved_ref TEXT,
            runtime_path TEXT,
            manifest_path TEXT,
            manifest_digest TEXT,
            manifest_version INTEGER,
            content_fingerprint TEXT,
            import_paths_json TEXT NOT NULL DEFAULT '[]',
            extension_modules_json TEXT NOT NULL DEFAULT '[]',
            function_modules_json TEXT NOT NULL DEFAULT '[]',
            minimum_platform_version TEXT,
            sync_status TEXT NOT NULL,
            validation_error TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (extension_registry_source_id) REFERENCES extension_registry_sources (extension_registry_source_id)
        );

        CREATE TABLE IF NOT EXISTS extension_registry_activations (
            extension_registry_source_id TEXT PRIMARY KEY,
            extension_registry_revision_id TEXT NOT NULL,
            activated_at TEXT NOT NULL,
            FOREIGN KEY (extension_registry_source_id) REFERENCES extension_registry_sources (extension_registry_source_id),
            FOREIGN KEY (extension_registry_revision_id) REFERENCES extension_registry_revisions (extension_registry_revision_id)
        );

        CREATE TABLE IF NOT EXISTS execution_schedules (
            schedule_id TEXT PRIMARY KEY,
            target_kind TEXT NOT NULL,
            target_ref TEXT NOT NULL,
            cron_expression TEXT NOT NULL,
            timezone TEXT NOT NULL,
            enabled INTEGER NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            max_concurrency INTEGER NOT NULL,
            next_due_at TEXT,
            last_enqueued_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS schedule_dispatches (
            dispatch_id TEXT PRIMARY KEY,
            schedule_id TEXT NOT NULL,
            target_kind TEXT NOT NULL,
            target_ref TEXT NOT NULL,
            enqueued_at TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            run_ids_json TEXT NOT NULL DEFAULT '[]',
            failure_reason TEXT,
            worker_detail TEXT,
            claimed_by_worker_id TEXT,
            claimed_at TEXT,
            claim_expires_at TEXT,
            FOREIGN KEY (schedule_id) REFERENCES execution_schedules (schedule_id)
        );

        CREATE TABLE IF NOT EXISTS worker_heartbeats (
            worker_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            active_dispatch_id TEXT,
            detail TEXT,
            observed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS source_lineage (
            lineage_id TEXT PRIMARY KEY,
            input_run_id TEXT,
            target_layer TEXT NOT NULL,
            target_name TEXT NOT NULL,
            target_kind TEXT NOT NULL,
            row_count INTEGER,
            source_system TEXT,
            source_run_id TEXT,
            recorded_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS publication_audit (
            publication_audit_id TEXT PRIMARY KEY,
            run_id TEXT,
            publication_key TEXT NOT NULL,
            relation_name TEXT NOT NULL,
            status TEXT NOT NULL,
            published_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS local_users (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            enabled INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            last_login_at TEXT
        );

        CREATE TABLE IF NOT EXISTS auth_audit_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            success INTEGER NOT NULL,
            actor_user_id TEXT,
            actor_username TEXT,
            subject_user_id TEXT,
            subject_username TEXT,
            remote_addr TEXT,
            user_agent TEXT,
            detail TEXT,
            occurred_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS service_tokens (
            token_id TEXT PRIMARY KEY,
            token_name TEXT NOT NULL,
            token_secret_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            scopes_json TEXT NOT NULL,
            expires_at TEXT,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            revoked_at TEXT
        );
        """
    )
    _ensure_dataset_contract_columns(connection)
    _ensure_column_mapping_columns(connection)
    _ensure_source_system_columns(connection)
    _ensure_transformation_package_columns(connection)
    _ensure_publication_definition_columns(connection)
    _ensure_source_asset_columns(connection)
    _ensure_ingestion_definition_columns(connection)
    _ensure_execution_schedule_columns(connection)
    _ensure_schedule_dispatch_columns(connection)
    _ensure_worker_heartbeat_table(connection)
    _seed_builtin_transformation_packages(connection)


def _ensure_source_system_columns(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(source_systems)").fetchall()}
    if "enabled" in columns:
        return
    connection.execute(
        "ALTER TABLE source_systems ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1"
    )


def _ensure_dataset_contract_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(dataset_contracts)").fetchall()
    }
    if "archived" not in columns:
        connection.execute(
            "ALTER TABLE dataset_contracts ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
        )


def _ensure_column_mapping_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(column_mappings)").fetchall()
    }
    if "archived" not in columns:
        connection.execute(
            "ALTER TABLE column_mappings ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
        )


def _ensure_ingestion_definition_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(ingestion_definitions)").fetchall()
    }
    required_columns = {
        "request_url": "TEXT",
        "request_method": "TEXT",
        "request_headers_json": "TEXT",
        "request_timeout_seconds": "INTEGER",
        "response_format": "TEXT",
        "output_file_name": "TEXT",
    }
    for column_name, column_type in required_columns.items():
        if column_name in columns:
            continue
        connection.execute(
            f"ALTER TABLE ingestion_definitions ADD COLUMN {column_name} {column_type}"
        )
    if "archived" not in columns:
        connection.execute(
            "ALTER TABLE ingestion_definitions ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
        )


def _ensure_source_asset_columns(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(source_assets)").fetchall()}
    if "transformation_package_id" not in columns:
        connection.execute(
            "ALTER TABLE source_assets ADD COLUMN transformation_package_id TEXT"
        )
    if "enabled" not in columns:
        connection.execute(
            "ALTER TABLE source_assets ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1"
        )
    if "archived" not in columns:
        connection.execute(
            "ALTER TABLE source_assets ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
        )


def _ensure_transformation_package_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(transformation_packages)").fetchall()
    }
    if "archived" not in columns:
        connection.execute(
            "ALTER TABLE transformation_packages ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
        )


def _ensure_publication_definition_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(publication_definitions)").fetchall()
    }
    if "archived" not in columns:
        connection.execute(
            "ALTER TABLE publication_definitions ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
        )


def _ensure_execution_schedule_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(execution_schedules)").fetchall()
    }
    if "archived" not in columns:
        connection.execute(
            "ALTER TABLE execution_schedules ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
        )


def _ensure_schedule_dispatch_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(schedule_dispatches)").fetchall()
    }
    if "started_at" not in columns:
        connection.execute("ALTER TABLE schedule_dispatches ADD COLUMN started_at TEXT")
    if "run_ids_json" not in columns:
        connection.execute(
            "ALTER TABLE schedule_dispatches ADD COLUMN run_ids_json TEXT NOT NULL DEFAULT '[]'"
        )
    if "failure_reason" not in columns:
        connection.execute(
            "ALTER TABLE schedule_dispatches ADD COLUMN failure_reason TEXT"
        )
    if "worker_detail" not in columns:
        connection.execute("ALTER TABLE schedule_dispatches ADD COLUMN worker_detail TEXT")
    if "claimed_by_worker_id" not in columns:
        connection.execute(
            "ALTER TABLE schedule_dispatches ADD COLUMN claimed_by_worker_id TEXT"
        )
    if "claimed_at" not in columns:
        connection.execute("ALTER TABLE schedule_dispatches ADD COLUMN claimed_at TEXT")
    if "claim_expires_at" not in columns:
        connection.execute(
            "ALTER TABLE schedule_dispatches ADD COLUMN claim_expires_at TEXT"
        )


def _ensure_worker_heartbeat_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_heartbeats (
            worker_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            active_dispatch_id TEXT,
            detail TEXT,
            observed_at TEXT NOT NULL
        )
        """
    )


def _seed_builtin_transformation_packages(connection: sqlite3.Connection) -> None:
    now = datetime.now(UTC).isoformat()
    for package in _BUILTIN_TRANSFORMATION_PACKAGES:
        connection.execute(
            """
            INSERT OR IGNORE INTO transformation_packages (
                transformation_package_id,
                name,
                handler_key,
                version,
                description,
                archived,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                package.transformation_package_id,
                package.name,
                package.handler_key,
                package.version,
                package.description,
                int(package.archived),
                now,
            ),
        )
    for publication in _BUILTIN_PUBLICATION_DEFINITIONS:
        connection.execute(
            """
            INSERT OR IGNORE INTO publication_definitions (
                publication_definition_id,
                transformation_package_id,
                publication_key,
                name,
                description,
                archived,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                publication.publication_definition_id,
                publication.transformation_package_id,
                publication.publication_key,
                publication.name,
                publication.description,
                int(publication.archived),
                now,
            ),
        )
