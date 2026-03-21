"""Per-source row identity resolution.

An IdentityStrategy declares how to derive a stable entity key from a source
row.  Tiers are tried in priority order; the first tier where all required
fields are present and non-empty wins.

Usage::

    result = resolve_entity_key(row, BANK_TRANSACTION_IDENTITY_STRATEGY)
    # result.entity_key  — 16-char SHA-256 hex
    # result.match_tier  — which tier matched (1, 2, …; 99 = fallback)
    # result.confidence  — 1.0 for exact tier match, 0.0 for fallback
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IdentityTier:
    """One priority tier in an identity resolution strategy.

    Fields are tried in declaration order; if every field resolves to a
    non-empty string the tier matches and produces an entity key.
    """

    tier: int  # lower number = higher priority
    fields: tuple[str, ...]  # ordered field names contributing to the key


@dataclass(frozen=True)
class EntityKeyResult:
    """Result of resolving an entity key for a source row."""

    entity_key: str  # 16-char SHA-256 hex digest
    match_tier: int  # tier number that matched; 99 means fallback
    confidence: float  # 1.0 for an exact tier match, 0.0 for fallback


@dataclass(frozen=True)
class IdentityStrategy:
    """Declarative per-source identity resolution strategy.

    Tiers are evaluated in ascending ``tier`` order.  The first tier where
    all declared fields are present and non-empty in the row wins.

    ``fallback_mode`` controls behaviour when no tier matches:

    - ``"reject"`` — raise ``ValueError`` (safe default; surfaces data gaps)
    - ``"fuzzy"``  — hash all present row fields deterministically
    """

    strategy_id: str
    tiers: tuple[IdentityTier, ...]
    fallback_mode: str = "reject"  # "reject" | "fuzzy"


def resolve_entity_key(
    row: dict[str, Any],
    strategy: IdentityStrategy,
) -> EntityKeyResult:
    """Walk priority tiers and return the first matching entity key.

    A tier matches when *all* of its declared fields are present and non-empty
    in *row*.  The entity key is the first 16 hex characters of a SHA-256
    digest of a stable, ordered encoding of the matched field values.

    Raises:
        ValueError: if no tier matches and ``strategy.fallback_mode == "reject"``.
    """
    for tier in sorted(strategy.tiers, key=lambda t: t.tier):
        values = [str(row.get(f) or "").strip() for f in tier.fields]
        if all(values):
            raw = "|".join(f"{f}:{v}" for f, v in zip(tier.fields, values))
            key = hashlib.sha256(raw.encode()).hexdigest()[:16]
            return EntityKeyResult(entity_key=key, match_tier=tier.tier, confidence=1.0)

    if strategy.fallback_mode == "reject":
        raise ValueError(
            f"No identity tier matched row for strategy '{strategy.strategy_id}'"
        )

    # fuzzy fallback: hash all present fields in a stable order
    present = {k: str(v) for k, v in sorted(row.items()) if v is not None}
    raw = "|".join(f"{k}:{v}" for k, v in present.items())
    key = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return EntityKeyResult(entity_key=key, match_tier=99, confidence=0.0)
