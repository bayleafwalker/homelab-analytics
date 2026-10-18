from __future__ import annotations

from packages.storage.execution_control_plane import ExecutionControlPlaneMixin
from packages.storage.sql_dialect import SQLiteSessionMixin


class SQLiteExecutionControlPlaneMixin(ExecutionControlPlaneMixin, SQLiteSessionMixin):
    """SQLite binding of the shared execution control plane."""
