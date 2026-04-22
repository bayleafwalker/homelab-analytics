from __future__ import annotations

import importlib
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

VALID_EXTENSION_LAYERS = (
    "landing",
    "transformation",
    "reporting",
    "application",
)
VALID_REPORTING_DATA_ACCESS = (
    "published",
    "warehouse",
)


@dataclass(frozen=True)
class LayerExtension:
    layer: str
    key: str
    kind: str
    description: str
    module: str
    source: str
    data_access: str = "none"
    publication_relations: tuple["ExtensionPublication", ...] = ()
    handler: Callable[..., object] | None = field(
        default=None,
        repr=False,
        compare=False,
    )


@dataclass(frozen=True)
class ExtensionPublication:
    relation_name: str
    columns: tuple[tuple[str, str], ...]
    source_query: str
    order_by: str


def _run_monthly_cashflow_summary(
    *,
    reporting_service=None,
):
    if reporting_service is not None:
        return reporting_service.get_monthly_cashflow()
    raise ValueError("monthly_cashflow_summary requires a reporting service")


BUILTIN_EXTENSIONS = (
    LayerExtension(
        layer="landing",
        key="account_transactions_csv_contract",
        kind="contract",
        description="Built-in CSV contract validation for account transaction imports.",
        module="packages.pipelines.csv_validation",
        source="builtin",
    ),
    LayerExtension(
        layer="landing",
        key="account_transaction_manual_ingest",
        kind="connector",
        description="Built-in manual file ingestion flow for account transaction CSV files.",
        module="packages.domains.finance.pipelines.account_transaction_service",
        source="builtin",
        handler=lambda *, service, source_path, source_name="manual-upload": service.ingest_file(
            Path(source_path), source_name=source_name
        ),
    ),
    LayerExtension(
        layer="landing",
        key="account_transaction_folder_watch",
        kind="connector",
        description="Built-in watched-folder ingestion flow for account transaction CSV files.",
        module="packages.domains.finance.pipelines.account_transaction_inbox",
        source="builtin",
        handler=lambda *, service, inbox_dir, processed_dir, failed_dir, source_name="folder-watch": (
            service.process_inbox(
                inbox_dir=Path(inbox_dir),
                processed_dir=Path(processed_dir),
                failed_dir=Path(failed_dir),
                source_name=source_name,
            )
        ),
    ),
    LayerExtension(
        layer="transformation",
        key="account_transactions_canonical",
        kind="transformation",
        description="Built-in canonical transaction normalization from landed account transaction CSV data.",
        module="packages.domains.finance.pipelines.account_transactions",
        source="builtin",
        handler=lambda *, service, run_id: service.get_canonical_transactions(run_id),
    ),
    LayerExtension(
        layer="reporting",
        key="monthly_cashflow_summary",
        kind="mart",
        description="Built-in monthly cash-flow mart derived from canonical account transactions.",
        module="packages.domains.finance.pipelines.cashflow_analytics",
        source="builtin",
        data_access="published",
        handler=_run_monthly_cashflow_summary,
    ),
    LayerExtension(
        layer="application",
        key="ingestion_runs_api",
        kind="api",
        description="Built-in API surface for ingestion run listing and reporting access.",
        module="apps.api.app",
        source="builtin",
    ),
    LayerExtension(
        layer="application",
        key="cashflow_dashboard",
        kind="web",
        description="Built-in dashboard surface for the current cash-flow reporting view.",
        module="apps.web.frontend",
        source="builtin",
    ),
)


class ExtensionRegistry:
    def __init__(self) -> None:
        self._extensions_by_layer: dict[str, dict[str, LayerExtension]] = {
            layer: {} for layer in VALID_EXTENSION_LAYERS
        }

    def register(self, extension: LayerExtension) -> None:
        if extension.layer not in self._extensions_by_layer:
            raise ValueError(f"Unsupported extension layer: {extension.layer}")
        _validate_extension_contract(extension)
        _validate_publication_relation_uniqueness(
            self.list_reporting_publications(),
            extension,
        )

        existing = self._extensions_by_layer[extension.layer].get(extension.key)
        if existing is not None and existing != extension:
            raise ValueError(
                f"Extension already registered for layer={extension.layer} key={extension.key}"
            )

        self._extensions_by_layer[extension.layer][extension.key] = extension

    def list_extensions(self, layer: str | None = None) -> list[LayerExtension]:
        if layer is None:
            extensions: list[LayerExtension] = []
            for layer_name in VALID_EXTENSION_LAYERS:
                extensions.extend(self.list_extensions(layer_name))
            return extensions

        if layer not in self._extensions_by_layer:
            raise ValueError(f"Unsupported extension layer: {layer}")

        return sorted(
            self._extensions_by_layer[layer].values(),
            key=lambda extension: extension.key,
        )

    def get_extension(self, layer: str, key: str) -> LayerExtension:
        if layer not in self._extensions_by_layer:
            raise ValueError(f"Unsupported extension layer: {layer}")

        extension = self._extensions_by_layer[layer].get(key)
        if extension is None:
            raise KeyError(f"Unknown extension for layer={layer}: {key}")
        return extension

    def list_reporting_publications(self) -> list[ExtensionPublication]:
        publications: list[ExtensionPublication] = []
        for extension in self.list_extensions("reporting"):
            publications.extend(extension.publication_relations)
        return publications

    def get_reporting_publication(self, relation_name: str) -> ExtensionPublication:
        for publication in self.list_reporting_publications():
            if publication.relation_name == relation_name:
                return publication
        raise KeyError(f"Unknown reporting publication relation: {relation_name}")

    def execute(self, layer: str, key: str, **kwargs: Any) -> object:
        extension = self.get_extension(layer, key)
        if extension.handler is None:
            raise ValueError(f"Extension is not executable for layer={layer} key={key}")
        _validate_execution_contract(extension, **kwargs)
        handler_signature = inspect.signature(extension.handler)
        if any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in handler_signature.parameters.values()
        ):
            return extension.handler(**kwargs)

        accepted_kwargs = {
            name: value for name, value in kwargs.items() if name in handler_signature.parameters
        }
        return extension.handler(**accepted_kwargs)

    def to_mapping(self) -> dict[str, list[LayerExtension]]:
        return {layer: self.list_extensions(layer) for layer in VALID_EXTENSION_LAYERS}


def build_builtin_extension_registry() -> ExtensionRegistry:
    registry = ExtensionRegistry()
    for extension in BUILTIN_EXTENSIONS:
        registry.register(extension)
    return registry


def load_extension_registry(
    *,
    extension_paths: tuple[Path, ...] = (),
    extension_modules: tuple[str, ...] = (),
) -> ExtensionRegistry:
    registry = build_builtin_extension_registry()
    loaded_modules = load_extension_modules(
        extension_paths=extension_paths,
        extension_modules=extension_modules,
    )

    for module_name, module in zip(extension_modules, loaded_modules, strict=True):
        register_extensions = getattr(module, "register_extensions", None)
        if not callable(register_extensions):
            raise ValueError(
                f"Extension module {module_name!r} must define register_extensions(registry)"
            )
        register_extensions(registry)

    return registry


def load_extension_modules(
    *,
    extension_paths: tuple[Path, ...] = (),
    extension_modules: tuple[str, ...] = (),
) -> tuple[ModuleType, ...]:
    _install_extension_paths(extension_paths)
    importlib.invalidate_caches()
    return tuple(importlib.import_module(module_name) for module_name in extension_modules)


def serialize_extension(extension: LayerExtension) -> dict[str, Any]:
    return {
        "layer": extension.layer,
        "key": extension.key,
        "kind": extension.kind,
        "description": extension.description,
        "module": extension.module,
        "source": extension.source,
        "data_access": extension.data_access,
        "publication_relations": [
            publication.relation_name for publication in extension.publication_relations
        ],
        "executable": "true" if extension.handler is not None else "false",
    }


def serialize_extension_registry(
    registry: ExtensionRegistry,
) -> dict[str, list[dict[str, Any]]]:
    return {
        layer: [serialize_extension(extension) for extension in registry.list_extensions(layer)]
        for layer in VALID_EXTENSION_LAYERS
    }


def _install_extension_paths(extension_paths: tuple[Path, ...]) -> None:
    for path in extension_paths:
        resolved_path = str(path)
        if not path.exists():
            raise FileNotFoundError(f"Extension path does not exist: {path}")
        if resolved_path not in sys.path:
            sys.path.insert(0, resolved_path)


def _validate_extension_contract(extension: LayerExtension) -> None:
    if extension.layer != "reporting":
        if extension.data_access != "none" or extension.publication_relations:
            raise ValueError(
                "Only reporting extensions may declare data_access or publication_relations; use the default contract for other layers."
            )
        return

    if extension.handler is None:
        if extension.data_access not in {"none", *VALID_REPORTING_DATA_ACCESS}:
            raise ValueError(
                "Reporting extensions must use data_access='none', 'published', or 'warehouse'."
            )
        if extension.publication_relations and extension.data_access != "published":
            raise ValueError("Reporting publication_relations require data_access='published'.")
        return

    if extension.data_access not in VALID_REPORTING_DATA_ACCESS:
        raise ValueError(
            "Executable reporting extensions must declare data_access='published' or 'warehouse'."
        )
    if extension.publication_relations and extension.data_access != "published":
        raise ValueError("Reporting publication_relations require data_access='published'.")


def _validate_execution_contract(extension: LayerExtension, **kwargs: Any) -> None:
    if extension.layer != "reporting" or extension.handler is None:
        return

    if extension.data_access == "published" and kwargs.get("reporting_service") is None:
        raise ValueError(
            f"Reporting extension {extension.key!r} requires reporting_service because data_access='published'."
        )

    if extension.data_access == "warehouse" and kwargs.get("transformation_service") is None:
        raise ValueError(
            f"Reporting extension {extension.key!r} requires transformation_service because data_access='warehouse'."
        )


def _validate_publication_relation_uniqueness(
    existing_publications: list[ExtensionPublication],
    extension: LayerExtension,
) -> None:
    existing_relation_names = {publication.relation_name for publication in existing_publications}
    extension_relation_names = [
        publication.relation_name for publication in extension.publication_relations
    ]

    if len(extension_relation_names) != len(set(extension_relation_names)):
        raise ValueError("Reporting publication_relations must use unique relation names.")

    duplicates = existing_relation_names & set(extension_relation_names)
    if duplicates:
        duplicate_names = ", ".join(sorted(duplicates))
        raise ValueError(f"Reporting publication relations already registered: {duplicate_names}")

