from __future__ import annotations

from packages.storage.source_contract_catalog import SourceContractCatalogMixin
from packages.storage.sql_dialect import PostgresSessionMixin


class PostgresSourceContractCatalogMixin(SourceContractCatalogMixin, PostgresSessionMixin):
    """Postgres binding of the shared source-contract catalog."""
