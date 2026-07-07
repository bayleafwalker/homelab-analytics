from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContractArtifactsSnapshot:
    openapi: dict[str, Any]
    publication_contracts: dict[str, Any]


@dataclass(frozen=True)
class ContractChange:
    severity: str
    scope: str
    identifier: str
    detail: str


@dataclass(frozen=True)
class UnionSchemaMember:
    identifier: str
    member: dict[str, Any]
