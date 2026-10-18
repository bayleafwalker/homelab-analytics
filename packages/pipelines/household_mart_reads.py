"""Built-in mart-read composition: each domain pack owns its reporting readers."""

from __future__ import annotations

from packages.domains.finance.pipelines.mart_reads import FINANCE_MART_READERS
from packages.pipelines.mart_read_registry import MartReadRegistry

BUILTIN_MART_READERS = (FINANCE_MART_READERS,)


def register_builtin_mart_readers(registry: MartReadRegistry) -> None:
    for readers in BUILTIN_MART_READERS:
        for relation_name, reader in readers.items():
            registry.register(relation_name, reader)
