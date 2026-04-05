from __future__ import annotations

import pytest

from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.homelab.manifest import HOMELAB_PACK
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.pipelines.composition.current_dimension_contracts import (
    CURRENT_DIMENSION_CONTRACTS,
)
from packages.pipelines.household_reporting import (
    CURRENT_DIMENSION_RELATIONS,
    PUBLICATION_RELATIONS,
)
from packages.platform.publication_contracts import build_publication_contract_catalog
from packages.platform.publication_index import (
    build_publication_semantic_index,
    filter_publication_semantic_index,
)

pytestmark = [pytest.mark.architecture]


def test_publication_semantic_index_exposes_search_terms_and_ui_metadata() -> None:
    catalog = build_publication_contract_catalog(
        (FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK, HOMELAB_PACK),
        publication_relations=PUBLICATION_RELATIONS,
        current_dimension_relations=CURRENT_DIMENSION_RELATIONS,
        current_dimension_contracts=CURRENT_DIMENSION_CONTRACTS,
    )
    index = build_publication_semantic_index(
        catalog["publication_contracts"],
        catalog["ui_descriptors"],
    )

    monthly_cashflow = next(
        entry for entry in index if entry.publication.publication_key == "monthly_cashflow"
    )

    assert "cashflow" in " ".join(monthly_cashflow.search_terms)
    assert "web" in monthly_cashflow.supported_renderers
    assert monthly_cashflow.summary


def test_publication_semantic_index_filters_by_query_and_renderer() -> None:
    catalog = build_publication_contract_catalog(
        (FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK, HOMELAB_PACK),
        publication_relations=PUBLICATION_RELATIONS,
        current_dimension_relations=CURRENT_DIMENSION_RELATIONS,
        current_dimension_contracts=CURRENT_DIMENSION_CONTRACTS,
    )
    index = build_publication_semantic_index(
        catalog["publication_contracts"],
        catalog["ui_descriptors"],
    )

    filtered = filter_publication_semantic_index(
        index,
        query="cashflow",
        renderer="web",
    )

    assert any(
        entry.publication.publication_key == "monthly_cashflow"
        for entry in filtered
    )
