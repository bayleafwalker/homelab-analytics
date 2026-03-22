from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitExtensionRepository:
    repo_root: Path
    commit_sha: str
    module_name: str
    extension_key: str


@dataclass(frozen=True)
class PathFunctionExtension:
    root: Path
    module_name: str
    function_key: str


@dataclass(frozen=True)
class PathPipelineExtension:
    root: Path
    module_name: str
    handler_key: str
    publication_key: str
    transformation_package_id: str


@dataclass(frozen=True)
class PathCapabilityPackExtension:
    root: Path
    module_name: str
    pack_name: str
    publication_key: str


def create_git_extension_repository(
    root: Path,
    *,
    module_name: str,
    extension_key: str,
) -> GitExtensionRepository:
    repo_root = root / "git-extension-repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / f"{module_name}.py").write_text(
        "\n".join(
            [
                "from packages.shared.extensions import LayerExtension",
                "",
                "def register_extensions(registry):",
                "    registry.register(",
                "        LayerExtension(",
                '            layer=\"reporting\",',
                f'            key=\"{extension_key}\",',
                '            kind=\"mart\",',
                '            description=\"Git-backed projection.\",',
                f'            module=\"{module_name}\",',
                '            source=\"git-external-registry\",',
                "        )",
                "    )",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (repo_root / "homelab-analytics.registry.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "import_paths": ["."],
                "extension_modules": [module_name],
                "function_modules": [],
                "minimum_platform_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    _run_git(("git", "init", "-b", "main", str(repo_root)))
    _run_git(("git", "-C", str(repo_root), "config", "user.name", "Test User"))
    _run_git(
        ("git", "-C", str(repo_root), "config", "user.email", "test@example.com")
    )
    _run_git(("git", "-C", str(repo_root), "add", "."))
    _run_git(("git", "-C", str(repo_root), "commit", "-m", "Initial commit"))
    commit_sha = _run_git(("git", "-C", str(repo_root), "rev-parse", "HEAD"))
    return GitExtensionRepository(
        repo_root=repo_root,
        commit_sha=commit_sha,
        module_name=module_name,
        extension_key=extension_key,
    )


def create_path_function_extension(
    root: Path,
    *,
    module_name: str,
    function_key: str,
) -> PathFunctionExtension:
    extension_root = root / "path-function-extension"
    extension_root.mkdir(parents=True, exist_ok=True)
    (extension_root / f"{module_name}.py").write_text(
        "\n".join(
            [
                "from packages.shared.function_registry import RegisteredFunction",
                "",
                "def _transform(*, value, row, target_column, source_column=None, default_value=None):",
                '    return f\"normalized:{value}\" if value else \"\"',
                "",
                "def register_functions(registry):",
                "    registry.register(",
                "        RegisteredFunction(",
                f'            function_key=\"{function_key}\",',
                '            kind=\"column_mapping_value\",',
                '            description=\"Normalize mapped values.\",',
                f'            module=\"{module_name}\",',
                '            source=\"path-function-extension\",',
                "            handler=_transform,",
                "        )",
                "    )",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (extension_root / "homelab-analytics.registry.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "import_paths": ["."],
                "extension_modules": [],
                "function_modules": [module_name],
                "minimum_platform_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    return PathFunctionExtension(
        root=extension_root,
        module_name=module_name,
        function_key=function_key,
    )


def create_path_pipeline_extension(
    root: Path,
    *,
    module_name: str,
    handler_key: str,
    publication_key: str,
    transformation_package_id: str,
) -> PathPipelineExtension:
    extension_root = root / "path-pipeline-extension"
    extension_root.mkdir(parents=True, exist_ok=True)
    (extension_root / f"{module_name}.py").write_text(
        "\n".join(
            [
                "from packages.pipelines.pipeline_catalog import (",
                "    PipelinePackageSpec,",
                "    PipelinePublicationSpec,",
                ")",
                "from packages.pipelines.promotion_registry import PromotionHandler",
                "from packages.pipelines.promotion_types import PromotionResult",
                "from packages.shared.extensions import (",
                "    ExtensionPublication,",
                "    LayerExtension,",
                ")",
                "",
                "def register_extensions(registry):",
                "    registry.register(",
                "        LayerExtension(",
                '            layer="reporting",',
                '            key="custom_pipeline_publication",',
                '            kind="mart",',
                '            description="External pipeline publication.",',
                f'            module="{module_name}",',
                '            source="path-pipeline-extension",',
                '            data_access="published",',
                "            publication_relations=(",
                "                ExtensionPublication(",
                f'                    relation_name="{publication_key}",',
                '                    columns=(("metric", "VARCHAR NOT NULL"),),',
                '                    source_query="SELECT booking_month AS metric FROM mart_monthly_cashflow",',
                '                    order_by="metric",',
                "                ),",
                "            ),",
                "        )",
                "    )",
                "",
                "def register_pipeline_registries(*, pipeline_catalog_registry, promotion_handler_registry):",
                "    pipeline_catalog_registry.register(",
                "        PipelinePackageSpec(",
                f'            transformation_package_id="{transformation_package_id}",',
                f'            handler_key="{handler_key}",',
                '            name="External pipeline package",',
                "            version=1,",
                '            description="External pipeline package.",',
                "            publications=(",
                "                PipelinePublicationSpec(",
                '                    publication_definition_id="pub_external_pipeline",',
                f'                    publication_key="{publication_key}",',
                '                    name="External pipeline publication",',
                "                ),",
                "            ),",
                "        )",
                "    )",
                "    promotion_handler_registry.register(",
                "        PromotionHandler(",
                f'            handler_key="{handler_key}",',
                f'            default_publications=("{publication_key}",),',
                f'            supported_publications=("{publication_key}",),',
                "            runner=lambda runtime: PromotionResult(",
                "                run_id=runtime.run_id,",
                "                facts_loaded=0,",
                f'                marts_refreshed=["{publication_key}"],',
                f'                publication_keys=["{publication_key}"],',
                "                skipped=True,",
                '                skip_reason="test pipeline handler",',
                "            ),",
                "        )",
                "    )",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (extension_root / "homelab-analytics.registry.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "import_paths": ["."],
                "extension_modules": [module_name],
                "function_modules": [],
                "minimum_platform_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    return PathPipelineExtension(
        root=extension_root,
        module_name=module_name,
        handler_key=handler_key,
        publication_key=publication_key,
        transformation_package_id=transformation_package_id,
    )


def create_path_capability_pack_extension(
    root: Path,
    *,
    module_name: str,
    pack_name: str,
    publication_key: str,
    schema_name: str | None = None,
    relation_name: str | None = None,
) -> PathCapabilityPackExtension:
    extension_root = root / "path-capability-pack-extension"
    extension_root.mkdir(parents=True, exist_ok=True)
    resolved_schema_name = schema_name or publication_key.removeprefix("mart_")
    resolved_relation_name = relation_name or publication_key
    ui_key = f"{pack_name}-dashboard"
    (extension_root / f"{module_name}.py").write_text(
        "\n".join(
            [
                "from packages.platform.capability_types import (",
                "    CapabilityPack,",
                "    PublicationDefinition,",
                "    UiDescriptor,",
                "    dimension_field,",
                ")",
                "from packages.shared.extensions import (",
                "    ExtensionPublication,",
                "    LayerExtension,",
                ")",
                "",
                "def register_extensions(registry):",
                "    registry.register(",
                "        LayerExtension(",
                '            layer="reporting",',
                f'            key="{pack_name}_reporting_extension",',
                '            kind="mart",',
                '            description="External pack reporting relation.",',
                f'            module="{module_name}",',
                '            source="path-capability-pack-extension",',
                '            data_access="published",',
                "            publication_relations=(",
                "                ExtensionPublication(",
                f'                    relation_name="{resolved_relation_name}",',
                '                    columns=(("metric", "VARCHAR NOT NULL"),),',
                '                    source_query="SELECT booking_month AS metric FROM mart_monthly_cashflow",',
                '                    order_by="metric",',
                "                ),",
                "            ),",
                "        )",
                "    )",
                "",
                "def register_capability_packs(registry):",
                "    registry.register(",
                "        CapabilityPack(",
                f'            name="{pack_name}",',
                '            version="1.0.0",',
                "            sources=(),",
                "            workflows=(),",
                "            publications=(",
                "                PublicationDefinition(",
                f'                    key="{publication_key}",',
                f'                    schema_name="{resolved_schema_name}",',
                '                    schema_version="1.0.0",',
                '                    display_name="External Projection",',
                '                    description="External projection contract.",',
                '                    visibility="public",',
                '                    lineage_required=True,',
                '                    retention_policy="indefinite",',
                '                    field_semantics={"metric": dimension_field("External metric label.")},',
                "                ),",
                "            ),",
                "            ui_descriptors=(",
                "                UiDescriptor(",
                f'                    key="{ui_key}",',
                '                    nav_label="External Projection",',
                f'                    nav_path="/external/{pack_name}",',
                '                    kind="table",',
                f'                    publication_keys=("{publication_key}",),',
                '                    icon="box",',
                '                    supported_renderers=("web",),',
                "                ),",
                "            ),",
                "        )",
                "    )",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (extension_root / "homelab-analytics.registry.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "import_paths": ["."],
                "extension_modules": [module_name],
                "function_modules": [],
                "minimum_platform_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    return PathCapabilityPackExtension(
        root=extension_root,
        module_name=module_name,
        pack_name=pack_name,
        publication_key=publication_key,
    )


def _run_git(command: tuple[str, ...]) -> str:
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
