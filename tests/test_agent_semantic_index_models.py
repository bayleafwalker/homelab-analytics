"""The typed semantic-index response models must not drift from the validator.

``validate_agent_semantic_index_payload`` is the contract agents rely on; the
pydantic models in ``packages.platform.agent_semantic_index_models`` give the
routes a typed OpenAPI schema. These tests hold the two together:

- both accept every payload the builder and the API actually produce;
- for every single-field mutation of those payloads (drop the key, or swap
  in a value of another type, an empty or blank string, a negative number),
  the validator and the models agree on accept or reject;
- the model fields are exactly the keys the builder emits;
- OpenAPI references the models instead of an untyped object.
"""
from __future__ import annotations

import copy
import typing
from collections.abc import Iterator
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from packages.application.use_cases.agent_trust import assess_publication_trust
from packages.platform.agent_semantic_index import (
    AGENT_SEMANTIC_INDEX_SCHEMA_VERSION,
    build_agent_semantic_index,
    validate_agent_semantic_index_entry_payload,
    validate_agent_semantic_index_payload,
)
from packages.platform.agent_semantic_index_models import (
    AgentColumnGlossaryModel,
    AgentPublicationSampleModel,
    AgentPublicationTrustModel,
    AgentSemanticIndexEntryModel,
    AgentSemanticIndexEntryResponseModel,
    AgentSemanticIndexPageModel,
    SchemaVersion,
)
from tests.test_agent_semantic_index import _build_client, _semantic_entries

_SWAPS: tuple[Any, ...] = (None, 3, -1, 0, True, "x", "", "  ", [], {}, [3], ["x"])


def _builder_entries() -> list[dict[str, Any]]:
    variants = [
        None,  # no sample
        lambda relation: ([{"booking_month": "2026-01", "amount": "1.00"}], 1),
        lambda relation: ([{"amount": str(n)} for n in range(8)], 8),  # truncated
        lambda relation: ([{"amount": "1"}], None),  # total unknown
    ]
    entries = []
    for fetcher in variants:
        built = build_agent_semantic_index(_semantic_entries(), sample_fetcher=fetcher)[0]
        payload = built.as_dict()
        payload["trust"] = assess_publication_trust(built.publication_key, None).as_dict()
        entries.append(payload)
    return entries


def _builder_page() -> dict[str, Any]:
    return {
        "schema_version": AGENT_SEMANTIC_INDEX_SCHEMA_VERSION,
        "generated_at": "2026-10-18T00:00:00+00:00",
        "publications": _builder_entries(),
        "total": 9,
        "next_cursor": "o4",
    }


def _api_payloads() -> tuple[dict[str, Any], dict[str, Any]]:
    with TemporaryDirectory() as tmp:
        client = _build_client(tmp, load_cashflow=True)
        page = client.get("/api/agent/semantic-index", params={"limit": 2}).json()
        entry = client.get("/api/agent/semantic-index/monthly_cashflow").json()
    return page, entry


def _model_accepts(model: type[BaseModel], payload: Any) -> bool:
    try:
        model.model_validate(payload)
    except ValidationError:
        return False
    return True


def _mutations(value: Any, path: tuple[Any, ...] = ()) -> Iterator[tuple[str, Any]]:
    """Yield (description, mutated payload) for every single-field change."""
    if isinstance(value, dict):
        children = list(value.items())
    elif isinstance(value, list):
        children = list(enumerate(value))
    else:
        return
    for key, child in children:
        here = (*path, key)
        if isinstance(value, dict):
            yield f"drop {here}", ("drop", here)
        for swap in _SWAPS:
            if swap != child or type(swap) is not type(child):
                yield f"set {here} = {swap!r}", ("set", here, swap)
        yield from _mutations(child, here)


def _apply(payload: Any, mutation: tuple[Any, ...]) -> Any:
    mutated = copy.deepcopy(payload)
    *parents, last = mutation[1]
    target = mutated
    for key in parents:
        target = target[key]
    if mutation[0] == "drop":
        del target[last]
    else:
        target[last] = copy.deepcopy(mutation[2])
    return mutated


def _assert_agree(
    payload: dict[str, Any],
    validator: typing.Callable[[Any], list[str]],
    model: type[BaseModel],
) -> int:
    assert validator(payload) == []
    assert _model_accepts(model, payload)
    checked = 0
    for description, mutation in _mutations(payload):
        mutated = _apply(payload, mutation)
        validator_accepts = validator(mutated) == []
        assert validator_accepts == _model_accepts(model, mutated), (
            f"{description}: validator {'accepts' if validator_accepts else 'rejects'} "
            f"but {model.__name__} does not; {validator(mutated)}"
        )
        checked += 1
    return checked


def test_builder_page_validator_and_models_agree_on_every_mutation() -> None:
    assert (
        _assert_agree(
            _builder_page(), validate_agent_semantic_index_payload, AgentSemanticIndexPageModel
        )
        > 500
    )


def test_builder_entry_validator_and_models_agree_on_every_mutation() -> None:
    for entry in _builder_entries():
        payload = {
            "schema_version": AGENT_SEMANTIC_INDEX_SCHEMA_VERSION,
            "generated_at": "2026-10-18T00:00:00+00:00",
            "publication": entry,
        }
        _assert_agree(
            payload,
            validate_agent_semantic_index_entry_payload,
            AgentSemanticIndexEntryResponseModel,
        )


def test_api_payloads_validator_and_models_agree_on_every_mutation() -> None:
    page, entry = _api_payloads()
    assert page["publications"] and page["next_cursor"]
    assert entry["publication"]["sample"] is not None
    _assert_agree(page, validate_agent_semantic_index_payload, AgentSemanticIndexPageModel)
    _assert_agree(
        entry,
        validate_agent_semantic_index_entry_payload,
        AgentSemanticIndexEntryResponseModel,
    )


@pytest.mark.parametrize(
    "model,emitted_keys",
    [
        (AgentSemanticIndexEntryModel, lambda entry: set(entry)),
        (AgentColumnGlossaryModel, lambda entry: set(entry["columns"][0])),
        (AgentPublicationSampleModel, lambda entry: set(entry["sample"])),
        (AgentPublicationTrustModel, lambda entry: set(entry["trust"])),
    ],
)
def test_model_fields_are_exactly_the_emitted_keys(
    model: type[BaseModel], emitted_keys: typing.Callable[[dict[str, Any]], set[str]]
) -> None:
    entry = _builder_entries()[1]
    assert set(model.model_fields) == emitted_keys(entry)


def test_envelope_fields_match_the_routes() -> None:
    page, entry = _api_payloads()
    assert set(AgentSemanticIndexPageModel.model_fields) == set(page)
    assert set(AgentSemanticIndexEntryResponseModel.model_fields) == set(entry)
    assert typing.get_args(SchemaVersion) == (AGENT_SEMANTIC_INDEX_SCHEMA_VERSION,)


def test_openapi_types_the_semantic_index_routes() -> None:
    with TemporaryDirectory() as tmp:
        spec = _build_client(tmp).get("/openapi.json").json()
    paths = spec["paths"]
    for path, model in (
        ("/api/agent/semantic-index", "AgentSemanticIndexPageModel"),
        ("/api/agent/semantic-index/{publication_key}", "AgentSemanticIndexEntryResponseModel"),
    ):
        schema = paths[path]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema == {"$ref": f"#/components/schemas/{model}"}, path
    entry_schema = spec["components"]["schemas"]["AgentSemanticIndexEntryModel"]
    assert {"publication_key", "columns", "trust", "sample"} <= set(entry_schema["properties"])
