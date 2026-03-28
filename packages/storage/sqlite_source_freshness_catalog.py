from __future__ import annotations

import sqlite3
from datetime import datetime

from packages.storage.ingestion_catalog import (
    SourceFreshnessConfigCreate,
    SourceFreshnessConfigRecord,
)


def _deserialize_source_freshness_config_row(
    row: sqlite3.Row,
) -> SourceFreshnessConfigRecord:
    return SourceFreshnessConfigRecord(
        source_asset_id=row["source_asset_id"],
        acquisition_mode=row["acquisition_mode"],
        expected_frequency=row["expected_frequency"],
        coverage_kind=row["coverage_kind"],
        due_day_of_month=row["due_day_of_month"],
        expected_window_days=row["expected_window_days"],
        freshness_sla_days=row["freshness_sla_days"],
        sensitivity_class=row["sensitivity_class"],
        reminder_channel=row["reminder_channel"],
        requires_human_action=bool(row["requires_human_action"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class SQLiteSourceFreshnessCatalogMixin:
    def _connect(self) -> sqlite3.Connection:
        raise NotImplementedError

    def create_source_freshness_config(
        self,
        freshness_config: SourceFreshnessConfigCreate,
    ) -> SourceFreshnessConfigRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO source_freshness_configs (
                    source_asset_id,
                    acquisition_mode,
                    expected_frequency,
                    coverage_kind,
                    due_day_of_month,
                    expected_window_days,
                    freshness_sla_days,
                    sensitivity_class,
                    reminder_channel,
                    requires_human_action,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    freshness_config.source_asset_id,
                    freshness_config.acquisition_mode,
                    freshness_config.expected_frequency,
                    freshness_config.coverage_kind,
                    freshness_config.due_day_of_month,
                    freshness_config.expected_window_days,
                    freshness_config.freshness_sla_days,
                    freshness_config.sensitivity_class,
                    freshness_config.reminder_channel,
                    int(freshness_config.requires_human_action),
                    freshness_config.created_at.isoformat(),
                    freshness_config.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return self.get_source_freshness_config(freshness_config.source_asset_id)

    def update_source_freshness_config(
        self,
        freshness_config: SourceFreshnessConfigCreate,
    ) -> SourceFreshnessConfigRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE source_freshness_configs
                SET acquisition_mode = ?,
                    expected_frequency = ?,
                    coverage_kind = ?,
                    due_day_of_month = ?,
                    expected_window_days = ?,
                    freshness_sla_days = ?,
                    sensitivity_class = ?,
                    reminder_channel = ?,
                    requires_human_action = ?,
                    updated_at = ?
                WHERE source_asset_id = ?
                """,
                (
                    freshness_config.acquisition_mode,
                    freshness_config.expected_frequency,
                    freshness_config.coverage_kind,
                    freshness_config.due_day_of_month,
                    freshness_config.expected_window_days,
                    freshness_config.freshness_sla_days,
                    freshness_config.sensitivity_class,
                    freshness_config.reminder_channel,
                    int(freshness_config.requires_human_action),
                    freshness_config.updated_at.isoformat(),
                    freshness_config.source_asset_id,
                ),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(
                f"Unknown source freshness config: {freshness_config.source_asset_id}"
            )
        return self.get_source_freshness_config(freshness_config.source_asset_id)

    def get_source_freshness_config(self, source_asset_id: str) -> SourceFreshnessConfigRecord:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT
                    source_asset_id,
                    acquisition_mode,
                    expected_frequency,
                    coverage_kind,
                    due_day_of_month,
                    expected_window_days,
                    freshness_sla_days,
                    sensitivity_class,
                    reminder_channel,
                    requires_human_action,
                    created_at,
                    updated_at
                FROM source_freshness_configs
                WHERE source_asset_id = ?
                """,
                (source_asset_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown source freshness config: {source_asset_id}")
        return _deserialize_source_freshness_config_row(row)

    def list_source_freshness_configs(self) -> list[SourceFreshnessConfigRecord]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    source_asset_id,
                    acquisition_mode,
                    expected_frequency,
                    coverage_kind,
                    due_day_of_month,
                    expected_window_days,
                    freshness_sla_days,
                    sensitivity_class,
                    reminder_channel,
                    requires_human_action,
                    created_at,
                    updated_at
                FROM source_freshness_configs
                ORDER BY created_at, source_asset_id
                """
            ).fetchall()
        return [_deserialize_source_freshness_config_row(row) for row in rows]

    def delete_source_freshness_config(self, source_asset_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM source_freshness_configs WHERE source_asset_id = ?",
                (source_asset_id,),
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown source freshness config: {source_asset_id}")
