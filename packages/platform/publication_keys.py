"""Single resolver between contract publication keys and warehouse relation names.

Two key namespaces name the same publication:

- the **relation name** (``mart_monthly_cashflow``) used by the warehouse, refresh
  handlers, source lineage, control-plane publication definitions, and policies;
- the **contract key** (``monthly_cashflow``) a capability pack declares, used by
  publication contracts and agent surfaces.

Confidence snapshots are canonically keyed by the relation name, because every
writer (refresh, lineage) and most readers already speak it. Contract-facing reads
resolve through ``PublicationKeyResolver`` instead of ad hoc bridges. Relations that
are not pack publications (``rpt_*``, non-pack ``mart_*``) use the same string in both
namespaces and resolve to themselves.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from packages.platform.capability_types import CapabilityPack, PublicationDefinition


def pack_publication_relation_name(publication: PublicationDefinition) -> str:
    """Reporting relation that materializes a capability-pack publication."""
    return f"mart_{publication.schema_name}"


class PublicationKeyResolver:
    def __init__(self, relation_by_contract_key: Mapping[str, str] | None = None) -> None:
        self._relation_by_contract_key = dict(relation_by_contract_key or {})
        self._contract_key_by_relation = {
            relation: key for key, relation in self._relation_by_contract_key.items()
        }

    @classmethod
    def from_capability_packs(
        cls,
        capability_packs: Sequence[CapabilityPack],
    ) -> PublicationKeyResolver:
        return cls(
            {
                publication.key: pack_publication_relation_name(publication)
                for pack in capability_packs
                for publication in pack.publications
            }
        )

    def snapshot_key(self, key: str) -> str:
        """Canonical confidence-snapshot key (relation name) for either namespace."""
        return self._relation_by_contract_key.get(key, key)

    def contract_key(self, key: str) -> str:
        """Contract publication key for either namespace."""
        if key in self._relation_by_contract_key:
            return key
        return self._contract_key_by_relation.get(key, key)

    def snapshot_lookup_keys(self, key: str) -> tuple[str, ...]:
        """Keys to read snapshots under: canonical first, then the legacy contract key.

        Snapshots recorded under the contract key (callers that passed it before
        writes were canonicalized) stay readable without a data migration.
        """
        canonical = self.snapshot_key(key)
        legacy = self.contract_key(canonical)
        return (canonical,) if legacy == canonical else (canonical, legacy)
