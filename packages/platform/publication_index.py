from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from packages.platform.publication_contracts import (
    PublicationContract,
    UiDescriptorContract,
)


@dataclass(frozen=True)
class PublicationSemanticIndexEntry:
    publication: PublicationContract
    ui_descriptor_keys: tuple[str, ...]
    supported_renderers: tuple[str, ...]
    search_terms: tuple[str, ...]
    summary: str


def _normalize_term(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _collect_terms(
    *,
    publication: PublicationContract,
    ui_descriptor_keys: Sequence[str],
    supported_renderers: Sequence[str],
) -> tuple[str, ...]:
    terms: set[str] = {
        publication.publication_key,
        publication.relation_name,
        publication.schema_name,
        publication.schema_version,
        publication.display_name,
        publication.visibility,
        publication.retention_policy,
    }
    if publication.description:
        terms.add(publication.description)
    if publication.pack_name:
        terms.add(publication.pack_name)
    if publication.pack_version:
        terms.add(publication.pack_version)

    terms.update(ui_descriptor_keys)
    terms.update(supported_renderers)
    terms.update(publication.renderer_hints.values())

    for column in publication.columns:
        terms.update(
            {
                column.name,
                column.storage_type,
                column.json_type,
                column.description,
                column.semantic_role,
            }
        )
        if column.unit:
            terms.add(column.unit)
        if column.grain:
            terms.add(column.grain)
        if column.aggregation:
            terms.add(column.aggregation)

    return tuple(sorted(_normalize_term(term) for term in terms if term.strip()))


def build_publication_semantic_index(
    publication_contracts: Sequence[PublicationContract],
    ui_descriptors: Sequence[UiDescriptorContract],
) -> list[PublicationSemanticIndexEntry]:
    descriptor_keys_by_publication: dict[str, set[str]] = {}
    renderers_by_publication: dict[str, set[str]] = {}
    for descriptor in ui_descriptors:
        for publication_key in descriptor.publication_keys:
            descriptor_keys_by_publication.setdefault(publication_key, set()).add(
                descriptor.key
            )
            renderers_by_publication.setdefault(publication_key, set()).update(
                descriptor.supported_renderers
            )

    entries: list[PublicationSemanticIndexEntry] = []
    for publication in sorted(publication_contracts, key=lambda item: item.publication_key):
        ui_descriptor_keys = tuple(
            sorted(
                _normalize_term(key)
                for key in descriptor_keys_by_publication.get(
                    publication.publication_key, set()
                )
            )
        )
        supported_renderers = tuple(
            sorted(
                _normalize_term(renderer)
                for renderer in renderers_by_publication.get(
                    publication.publication_key, {"web"}
                )
            )
        )
        entries.append(
            PublicationSemanticIndexEntry(
                publication=publication,
                ui_descriptor_keys=ui_descriptor_keys,
                supported_renderers=supported_renderers,
                search_terms=_collect_terms(
                    publication=publication,
                    ui_descriptor_keys=ui_descriptor_keys,
                    supported_renderers=supported_renderers,
                ),
                summary=publication.description
                or f"{publication.display_name} publication contract.",
            )
        )
    return entries


def filter_publication_semantic_index(
    entries: Sequence[PublicationSemanticIndexEntry],
    *,
    query: str | None = None,
    renderer: str | None = None,
    ui_descriptor_key: str | None = None,
) -> list[PublicationSemanticIndexEntry]:
    filtered = list(entries)
    if renderer:
        normalized_renderer = _normalize_term(renderer)
        filtered = [
            entry
            for entry in filtered
            if normalized_renderer in entry.supported_renderers
        ]
    if ui_descriptor_key:
        normalized_descriptor_key = _normalize_term(ui_descriptor_key)
        filtered = [
            entry
            for entry in filtered
            if normalized_descriptor_key in entry.ui_descriptor_keys
        ]
    if query:
        normalized_query = _normalize_term(query)
        filtered = [
            entry
            for entry in filtered
            if any(normalized_query in term for term in entry.search_terms)
        ]
    return filtered
