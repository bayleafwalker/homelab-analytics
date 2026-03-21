"""Platform-owned capability pack type definitions.

These types define the contract that domain packs must implement.
Domains import from here; platform never imports from domains.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDefinition:
    dataset_name: str
    display_name: str
    description: str
    retry_kind: str | None  # None means retry not supported


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: str
    display_name: str
    source_dataset_name: str
    retry_policy: str  # "always" | "on_failure" | "never"
    idempotency_mode: str  # "run_id" | "content_hash" | "none"
    required_permissions: tuple[str, ...]
    command_name: str  # maps workflow to the worker CLI command
    publication_keys: tuple[str, ...]  # output publication keys produced by this workflow
    identity_strategy_id: str | None = None  # declared per-source entity key strategy


@dataclass(frozen=True)
class PublicationDefinition:
    key: str
    schema_name: str
    display_name: str
    description: str
    visibility: str  # "public" | "admin"
    lineage_required: bool
    retention_policy: str  # e.g. "rolling_12_months" | "indefinite"


@dataclass(frozen=True)
class UiDescriptor:
    key: str
    nav_label: str
    nav_path: str
    kind: str  # "dashboard" | "report" | "table"
    publication_keys: tuple[str, ...]  # data publications this view consumes
    icon: str | None


@dataclass(frozen=True)
class CapabilityPack:
    name: str
    version: str
    sources: tuple[SourceDefinition, ...]
    workflows: tuple[WorkflowDefinition, ...]
    publications: tuple[PublicationDefinition, ...]
    ui_descriptors: tuple[UiDescriptor, ...]

    def validate(self) -> None:
        """Raise ValueError if required fields are missing or invalid.

        Checks both required-field presence and pack-local referential integrity:
        duplicate workflow IDs, duplicate publication/UI keys, and dangling
        publication_keys references from workflows and UI descriptors.
        """
        if not self.name:
            raise ValueError("CapabilityPack.name is required")
        if not self.version:
            raise ValueError("CapabilityPack.version is required")
        if not self.publications:
            raise ValueError(f"CapabilityPack '{self.name}' must declare at least one publication")

        # --- Duplicate detection ------------------------------------------------
        seen_wf_ids: set[str] = set()
        for workflow in self.workflows:
            if workflow.workflow_id in seen_wf_ids:
                raise ValueError(
                    f"Pack '{self.name}' has duplicate workflow_id: '{workflow.workflow_id}'"
                )
            seen_wf_ids.add(workflow.workflow_id)

        seen_pub_keys: set[str] = set()
        for publication in self.publications:
            if publication.key in seen_pub_keys:
                raise ValueError(
                    f"Pack '{self.name}' has duplicate publication key: '{publication.key}'"
                )
            seen_pub_keys.add(publication.key)

        seen_ui_keys: set[str] = set()
        for ui in self.ui_descriptors:
            if ui.key in seen_ui_keys:
                raise ValueError(
                    f"Pack '{self.name}' has duplicate UI descriptor key: '{ui.key}'"
                )
            seen_ui_keys.add(ui.key)

        # --- Per-workflow required fields ---------------------------------------
        for workflow in self.workflows:
            if not workflow.retry_policy:
                raise ValueError(
                    f"WorkflowDefinition '{workflow.workflow_id}' must declare retry_policy"
                )
            if not workflow.idempotency_mode:
                raise ValueError(
                    f"WorkflowDefinition '{workflow.workflow_id}' must declare idempotency_mode"
                )
            if workflow.required_permissions is None:
                raise ValueError(
                    f"WorkflowDefinition '{workflow.workflow_id}' must declare required_permissions"
                )
            if not workflow.command_name:
                raise ValueError(
                    f"WorkflowDefinition '{workflow.workflow_id}' must declare command_name"
                )

        # --- Per-publication required fields ------------------------------------
        for publication in self.publications:
            if not publication.key:
                raise ValueError("PublicationDefinition must declare key")
            if not publication.schema_name:
                raise ValueError(
                    f"PublicationDefinition '{publication.key}' must declare schema_name"
                )
            if not publication.visibility:
                raise ValueError(
                    f"PublicationDefinition '{publication.key}' must declare visibility"
                )
            if not publication.retention_policy:
                raise ValueError(
                    f"PublicationDefinition '{publication.key}' must declare retention_policy"
                )

        # --- Pack-local referential integrity -----------------------------------
        pack_pub_keys = seen_pub_keys  # already collected above
        for workflow in self.workflows:
            for pk in workflow.publication_keys:
                if pk not in pack_pub_keys:
                    raise ValueError(
                        f"Workflow '{workflow.workflow_id}' in pack '{self.name}' references "
                        f"publication key '{pk}' not declared by this pack"
                    )
        for ui in self.ui_descriptors:
            for pk in ui.publication_keys:
                if pk not in pack_pub_keys:
                    raise ValueError(
                        f"UI descriptor '{ui.key}' in pack '{self.name}' references "
                        f"publication key '{pk}' not declared by this pack"
                    )
