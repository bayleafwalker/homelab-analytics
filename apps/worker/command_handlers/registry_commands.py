"""Extension registry and introspection worker command handlers."""
from __future__ import annotations

from argparse import Namespace

from apps.worker.runtime import WorkerRuntime
from apps.worker.serialization import _write_json
from packages.pipelines.composition.publication_contract_inputs import (
    HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS,
)
from packages.pipelines.promotion_registry import serialize_promotion_handler_registry
from packages.shared.extensions import serialize_extension_registry
from packages.shared.external_registry import sync_extension_registry_source
from packages.shared.function_registry import serialize_function_registry
from packages.shared.secrets import EnvironmentSecretResolver
from packages.storage.ingestion_catalog import serialize_publication_keys


def handle_list_extension_registry_sources(
    args: Namespace,
    runtime: WorkerRuntime,
) -> int:
    _write_json(
        runtime.output,
        {
            "extension_registry_sources": runtime.config_repository.list_extension_registry_sources(
                include_archived=getattr(args, "include_archived", False)
            )
        },
    )
    return 0


def handle_list_extension_registry_revisions(
    args: Namespace,
    runtime: WorkerRuntime,
) -> int:
    _write_json(
        runtime.output,
        {
            "extension_registry_revisions": runtime.config_repository.list_extension_registry_revisions(
                extension_registry_source_id=getattr(args, "source_id", None) or None
            )
        },
    )
    return 0


def handle_list_extension_registry_activations(
    args: Namespace,
    runtime: WorkerRuntime,
) -> int:
    _write_json(
        runtime.output,
        {
            "extension_registry_activations": runtime.config_repository.list_extension_registry_activations()
        },
    )
    return 0


def handle_list_transformation_packages(
    args: Namespace,
    runtime: WorkerRuntime,
) -> int:
    _write_json(
        runtime.output,
        {
            "transformation_packages": runtime.config_repository.list_transformation_packages(
                include_archived=getattr(args, "include_archived", False)
            )
        },
    )
    return 0


def handle_list_publication_definitions(
    args: Namespace,
    runtime: WorkerRuntime,
) -> int:
    _write_json(
        runtime.output,
        {
            "publication_definitions": runtime.config_repository.list_publication_definitions(
                transformation_package_id=(
                    getattr(args, "transformation_package_id", None) or None
                ),
                include_archived=getattr(args, "include_archived", False),
            )
        },
    )
    return 0


def handle_list_transformation_handlers(
    args: Namespace,
    runtime: WorkerRuntime,
) -> int:
    _write_json(
        runtime.output,
        {
            "transformation_handlers": serialize_promotion_handler_registry(
                runtime.promotion_handler_registry
            )
        },
    )
    return 0


def handle_list_publication_keys(
    args: Namespace,
    runtime: WorkerRuntime,
) -> int:
    _write_json(
        runtime.output,
        {
            "publication_keys": serialize_publication_keys(
                extension_registry=runtime.extension_registry,
                promotion_handler_registry=runtime.promotion_handler_registry,
            )
        },
    )
    return 0


def handle_sync_extension_registry_source(
    args: Namespace,
    runtime: WorkerRuntime,
) -> int:
    result = sync_extension_registry_source(
        runtime.config_repository,
        args.source_id,
        activate=getattr(args, "activate", False),
        builtin_packs=runtime.container.capability_packs,
        publication_relations=(
            HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS.publication_relations
        ),
        current_dimension_relations=(
            HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS.current_dimension_relations
        ),
        current_dimension_contracts=(
            HOUSEHOLD_PUBLICATION_CONTRACT_REGISTRATIONS.current_dimension_contracts
        ),
        cache_root=runtime.settings.resolved_external_registry_cache_root,
        secret_resolver=EnvironmentSecretResolver(),
    )
    _write_json(
        runtime.output,
        {
            "extension_registry_source": result.source,
            "extension_registry_revision": result.revision,
            "extension_registry_activation": result.activation,
        },
    )
    return 0 if result.passed else 1


def handle_list_extensions(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {"extensions": serialize_extension_registry(runtime.extension_registry)},
    )
    return 0


def handle_list_functions(args: Namespace, runtime: WorkerRuntime) -> int:
    _write_json(
        runtime.output,
        {"functions": serialize_function_registry(runtime.function_registry)},
    )
    return 0
