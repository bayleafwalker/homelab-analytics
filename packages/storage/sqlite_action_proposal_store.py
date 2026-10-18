"""SQLite binding of the shared action-proposal store."""

from __future__ import annotations

from packages.storage.action_proposal_store import ActionProposalStoreMixin
from packages.storage.sql_dialect import SQLiteSessionMixin


class SQLiteActionProposalStoreMixin(ActionProposalStoreMixin, SQLiteSessionMixin):
    """SQLite binding of the shared action-proposal queue store."""
