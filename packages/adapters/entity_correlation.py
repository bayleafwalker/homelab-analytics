"""Entity correlation registry.

Runtime companion to the ``EntityAlias`` and ``CanonicalEntityId``
contracts declared in ``packages.adapters.contracts``. The registry
lets an operator ask two independent questions:

- "This adapter sees ``source_entity_id`` X. What is the canonical
  household entity behind it?" — ``resolve``.
- "What are all the adapter-scoped source ids that refer to this
  canonical entity?" — ``aliases_for``.

Conflicts on the same ``(adapter_key, entity_class, source_entity_id)``
key are resolved by ``TrustLevel``: VERIFIED beats COMMUNITY beats
LOCAL. At equal trust, the latest registration wins so operators can
correct a stale mapping without needing to first release the old one.
"""

from __future__ import annotations

from packages.adapters.contracts import (
    CanonicalEntityId,
    EntityAlias,
    TrustLevel,
)

_TRUST_RANK = {
    TrustLevel.LOCAL: 0,
    TrustLevel.COMMUNITY: 1,
    TrustLevel.VERIFIED: 2,
}


def _trust_rank(level: TrustLevel) -> int:
    return _TRUST_RANK.get(level, 0)


class EntityCorrelationRegistry:
    """In-memory correlation registry keyed by adapter-scoped source ids.

    The registry does not persist. Callers seed it from adapter
    manifests, from control-plane records, or from operator input; a
    later sprint can back the same interface with a durable store.
    """

    def __init__(self) -> None:
        self._aliases: dict[tuple[str, str, str], EntityAlias] = {}

    def register_alias(self, alias: EntityAlias) -> EntityAlias:
        """Register or replace an alias.

        Returns the alias that ends up in the registry (which may be the
        existing one if the incoming alias has lower trust).
        """
        key = (alias.adapter_key, alias.entity_class, alias.source_entity_id)
        existing = self._aliases.get(key)
        if existing is None:
            self._aliases[key] = alias
            return alias

        if _trust_rank(alias.trust_level) > _trust_rank(existing.trust_level):
            self._aliases[key] = alias
            return alias
        if _trust_rank(alias.trust_level) < _trust_rank(existing.trust_level):
            return existing
        # Equal trust: latest registration wins.
        self._aliases[key] = alias
        return alias

    def resolve(
        self,
        *,
        adapter_key: str,
        entity_class: str,
        source_entity_id: str,
    ) -> CanonicalEntityId | None:
        """Return the canonical id for an adapter-scoped source id."""
        alias = self._aliases.get((adapter_key, entity_class, source_entity_id))
        if alias is None:
            return None
        return alias.canonical_id

    def aliases_for(self, canonical_id: CanonicalEntityId) -> tuple[EntityAlias, ...]:
        """Return every registered alias pointing at ``canonical_id``."""
        return tuple(
            sorted(
                (
                    alias
                    for alias in self._aliases.values()
                    if alias.canonical_id == canonical_id
                ),
                key=lambda item: (item.adapter_key, item.source_entity_id),
            )
        )

    def all_aliases(self) -> tuple[EntityAlias, ...]:
        return tuple(
            sorted(
                self._aliases.values(),
                key=lambda item: (item.adapter_key, item.entity_class, item.source_entity_id),
            )
        )


__all__ = ["EntityCorrelationRegistry"]
