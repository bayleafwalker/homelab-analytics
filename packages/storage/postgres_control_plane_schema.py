from __future__ import annotations

from datetime import UTC, datetime

import psycopg

from packages.storage.ingestion_catalog import (
    _BUILTIN_PUBLICATION_DEFINITIONS,
    _BUILTIN_TRANSFORMATION_PACKAGES,
)


def initialize_postgres_control_plane_schema(
    connection: psycopg.Connection[object],
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS source_systems (
            source_system_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            transport TEXT NOT NULL,
            schedule_mode TEXT NOT NULL,
            description TEXT,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS dataset_contracts (
            dataset_contract_id TEXT PRIMARY KEY,
            dataset_name TEXT NOT NULL,
            version INTEGER NOT NULL,
            allow_extra_columns BOOLEAN NOT NULL,
            archived BOOLEAN NOT NULL DEFAULT FALSE,
            columns_json TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS column_mappings (
            column_mapping_id TEXT PRIMARY KEY,
            source_system_id TEXT NOT NULL REFERENCES source_systems (source_system_id),
            dataset_contract_id TEXT NOT NULL REFERENCES dataset_contracts (dataset_contract_id),
            version INTEGER NOT NULL,
            archived BOOLEAN NOT NULL DEFAULT FALSE,
            rules_json TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS transformation_packages (
            transformation_package_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            handler_key TEXT NOT NULL,
            version INTEGER NOT NULL,
            description TEXT,
            archived BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS publication_definitions (
            publication_definition_id TEXT PRIMARY KEY,
            transformation_package_id TEXT NOT NULL REFERENCES transformation_packages (transformation_package_id),
            publication_key TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            archived BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS source_assets (
            source_asset_id TEXT PRIMARY KEY,
            source_system_id TEXT NOT NULL REFERENCES source_systems (source_system_id),
            dataset_contract_id TEXT NOT NULL REFERENCES dataset_contracts (dataset_contract_id),
            column_mapping_id TEXT NOT NULL REFERENCES column_mappings (column_mapping_id),
            transformation_package_id TEXT REFERENCES transformation_packages (transformation_package_id),
            name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            description TEXT,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            archived BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ingestion_definitions (
            ingestion_definition_id TEXT PRIMARY KEY,
            source_asset_id TEXT NOT NULL REFERENCES source_assets (source_asset_id),
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
            enabled BOOLEAN NOT NULL,
            archived BOOLEAN NOT NULL DEFAULT FALSE,
            source_name TEXT,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS extension_registry_sources (
            extension_registry_source_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            location TEXT NOT NULL,
            desired_ref TEXT,
            subdirectory TEXT,
            auth_secret_name TEXT,
            auth_secret_key TEXT,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            archived BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS extension_registry_revisions (
            extension_registry_revision_id TEXT PRIMARY KEY,
            extension_registry_source_id TEXT NOT NULL REFERENCES extension_registry_sources (extension_registry_source_id),
            resolved_ref TEXT,
            runtime_path TEXT,
            manifest_path TEXT,
            manifest_digest TEXT,
            manifest_version INTEGER,
            content_fingerprint TEXT,
            import_paths_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            extension_modules_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            function_modules_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            minimum_platform_version TEXT,
            sync_status TEXT NOT NULL,
            validation_error TEXT,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS extension_registry_activations (
            extension_registry_source_id TEXT PRIMARY KEY REFERENCES extension_registry_sources (extension_registry_source_id),
            extension_registry_revision_id TEXT NOT NULL REFERENCES extension_registry_revisions (extension_registry_revision_id),
            activated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS execution_schedules (
            schedule_id TEXT PRIMARY KEY,
            target_kind TEXT NOT NULL,
            target_ref TEXT NOT NULL,
            cron_expression TEXT NOT NULL,
            timezone TEXT NOT NULL,
            enabled BOOLEAN NOT NULL,
            archived BOOLEAN NOT NULL DEFAULT FALSE,
            max_concurrency INTEGER NOT NULL,
            next_due_at TIMESTAMPTZ,
            last_enqueued_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schedule_dispatches (
            dispatch_id TEXT PRIMARY KEY,
            schedule_id TEXT NOT NULL REFERENCES execution_schedules (schedule_id),
            target_kind TEXT NOT NULL,
            target_ref TEXT NOT NULL,
            enqueued_at TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL,
            started_at TIMESTAMPTZ,
            run_ids_json TEXT NOT NULL DEFAULT '[]',
            failure_reason TEXT,
            worker_detail TEXT,
            claimed_by_worker_id TEXT,
            claimed_at TIMESTAMPTZ,
            claim_expires_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_heartbeats (
            worker_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            active_dispatch_id TEXT,
            detail TEXT,
            observed_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS source_lineage (
            lineage_id TEXT PRIMARY KEY,
            input_run_id TEXT,
            target_layer TEXT NOT NULL,
            target_name TEXT NOT NULL,
            target_kind TEXT NOT NULL,
            row_count INTEGER,
            source_system TEXT,
            source_run_id TEXT,
            recorded_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS publication_audit (
            publication_audit_id TEXT PRIMARY KEY,
            run_id TEXT,
            publication_key TEXT NOT NULL,
            relation_name TEXT NOT NULL,
            status TEXT NOT NULL,
            published_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS local_users (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            enabled BOOLEAN NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            last_login_at TIMESTAMPTZ
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_audit_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            success BOOLEAN NOT NULL,
            actor_user_id TEXT,
            actor_username TEXT,
            subject_user_id TEXT,
            subject_username TEXT,
            remote_addr TEXT,
            user_agent TEXT,
            detail TEXT,
            occurred_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS service_tokens (
            token_id TEXT PRIMARY KEY,
            token_name TEXT NOT NULL,
            token_secret_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            scopes_json JSONB NOT NULL,
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL,
            last_used_at TIMESTAMPTZ,
            revoked_at TIMESTAMPTZ
        )
        """
    )
    connection.execute(
        """
        ALTER TABLE source_systems
        ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE
        """
    )
    connection.execute(
        """
        ALTER TABLE dataset_contracts
        ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    connection.execute(
        """
        ALTER TABLE column_mappings
        ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    connection.execute(
        """
        ALTER TABLE transformation_packages
        ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    connection.execute(
        """
        ALTER TABLE publication_definitions
        ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    connection.execute(
        """
        ALTER TABLE source_assets
        ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE
        """
    )
    connection.execute(
        """
        ALTER TABLE source_assets
        ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    connection.execute(
        """
        ALTER TABLE ingestion_definitions
        ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    connection.execute(
        """
        ALTER TABLE execution_schedules
        ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    connection.execute(
        """
        ALTER TABLE schedule_dispatches
        ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ
        """
    )
    connection.execute(
        """
        ALTER TABLE schedule_dispatches
        ADD COLUMN IF NOT EXISTS run_ids_json TEXT NOT NULL DEFAULT '[]'
        """
    )
    connection.execute(
        """
        ALTER TABLE schedule_dispatches
        ADD COLUMN IF NOT EXISTS failure_reason TEXT
        """
    )
    connection.execute(
        """
        ALTER TABLE schedule_dispatches
        ADD COLUMN IF NOT EXISTS worker_detail TEXT
        """
    )
    connection.execute(
        """
        ALTER TABLE schedule_dispatches
        ADD COLUMN IF NOT EXISTS claimed_by_worker_id TEXT
        """
    )
    connection.execute(
        """
        ALTER TABLE schedule_dispatches
        ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ
        """
    )
    connection.execute(
        """
        ALTER TABLE schedule_dispatches
        ADD COLUMN IF NOT EXISTS claim_expires_at TIMESTAMPTZ
        """
    )
    _seed_builtins(connection)


def _seed_builtins(connection: psycopg.Connection[object]) -> None:
    now = datetime.now(UTC)
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO transformation_packages (
                transformation_package_id, name, handler_key, version, description, archived, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (transformation_package_id) DO NOTHING
            """,
            [
                (
                    package.transformation_package_id,
                    package.name,
                    package.handler_key,
                    package.version,
                    package.description,
                    package.archived,
                    now,
                )
                for package in _BUILTIN_TRANSFORMATION_PACKAGES
            ],
        )
        cursor.executemany(
            """
            INSERT INTO publication_definitions (
                publication_definition_id, transformation_package_id, publication_key, name, description, archived, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (publication_definition_id) DO NOTHING
            """,
            [
                (
                    publication.publication_definition_id,
                    publication.transformation_package_id,
                    publication.publication_key,
                    publication.name,
                    publication.description,
                    publication.archived,
                    now,
                )
                for publication in _BUILTIN_PUBLICATION_DEFINITIONS
            ],
        )
