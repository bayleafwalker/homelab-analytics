from __future__ import annotations

from packages.storage.source_contract_catalog import SourceContractCatalogMixin
from packages.storage.sql_dialect import SQLiteSessionMixin


class SQLiteSourceContractCatalogMixin(SourceContractCatalogMixin, SQLiteSessionMixin):
    """SQLite binding of the shared source-contract catalog."""
