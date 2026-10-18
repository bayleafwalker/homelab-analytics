"""Postgres binding of the shared action-proposal store."""

from __future__ import annotations

from packages.storage.action_proposal_store import ActionProposalStoreMixin
from packages.storage.sql_dialect import PostgresSessionMixin


class PostgresActionProposalStoreMixin(ActionProposalStoreMixin, PostgresSessionMixin):
    """Postgres binding of the shared action-proposal queue store."""
