from __future__ import annotations

from datetime import datetime
from typing import cast

import psycopg
from psycopg.rows import dict_row

from packages.storage.ingestion_catalog import (
    SourceFreshnessConfigCreate,
    SourceFreshnessConfigRecord,
)


def _deserialize_source_freshness_config_row(
    row: dict[str, object],
) -> SourceFreshnessConfigRecord:
    return SourceFreshnessConfigRecord(
        source_asset_id=str(row["source_asset_id"]),
        acquisition_mode=str(row["acquisition_mode"]),
        expected_frequency=str(row["expected_frequency"]),
        coverage_kind=str(row["coverage_kind"]),
        due_day_of_month=(
            _coerce_int_value(row["due_day_of_month"])
            if row["due_day_of_month"] is not None
            else None
        ),
        expected_window_days=_coerce_int_value(row["expected_window_days"]),
        freshness_sla_days=_coerce_int_value(row["freshness_sla_days"]),
        sensitivity_class=str(row["sensitivity_class"]),
        reminder_channel=str(row["reminder_channel"]),
        requires_human_action=bool(row["requires_human_action"]),
        created_at=_coerce_datetime_value(row["created_at"]),
        updated_at=_coerce_datetime_value(row["updated_at"]),
    )


def _coerce_datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def _coerce_int_value(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Unsupported integer value: {value!r}")


def _coerce_row_mapping(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        raise TypeError(f"Unsupported row value: {row!r}")
    return cast(dict[str, object], row)


class PostgresSourceFreshnessCatalogMixin:
    def _connect(
        self,
        *,
        row_factory: object = None,
    ) -> psycopg.Connection[object]:
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
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    freshness_config.requires_human_action,
                    freshness_config.created_at,
                    freshness_config.updated_at,
                ),
            )
        return self.get_source_freshness_config(freshness_config.source_asset_id)

    def update_source_freshness_config(
        self,
        freshness_config: SourceFreshnessConfigCreate,
    ) -> SourceFreshnessConfigRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE source_freshness_configs
                SET acquisition_mode = %s,
                    expected_frequency = %s,
                    coverage_kind = %s,
                    due_day_of_month = %s,
                    expected_window_days = %s,
                    freshness_sla_days = %s,
                    sensitivity_class = %s,
                    reminder_channel = %s,
                    requires_human_action = %s,
                    updated_at = %s
                WHERE source_asset_id = %s
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
                    freshness_config.requires_human_action,
                    freshness_config.updated_at,
                    freshness_config.source_asset_id,
                ),
            )
        if cursor.rowcount == 0:
            raise KeyError(
                f"Unknown source freshness config: {freshness_config.source_asset_id}"
            )
        return self.get_source_freshness_config(freshness_config.source_asset_id)

    def get_source_freshness_config(self, source_asset_id: str) -> SourceFreshnessConfigRecord:
        with self._connect(row_factory=dict_row) as connection:
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
                WHERE source_asset_id = %s
                """,
                (source_asset_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown source freshness config: {source_asset_id}")
        return _deserialize_source_freshness_config_row(_coerce_row_mapping(row))

    def list_source_freshness_configs(self) -> list[SourceFreshnessConfigRecord]:
        with self._connect(row_factory=dict_row) as connection:
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
        return [_deserialize_source_freshness_config_row(_coerce_row_mapping(row)) for row in rows]

    def delete_source_freshness_config(self, source_asset_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM source_freshness_configs WHERE source_asset_id = %s",
                (source_asset_id,),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown source freshness config: {source_asset_id}")
