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
        """Raise ValueError if required fields are missing or invalid."""
        if not self.name:
            raise ValueError("CapabilityPack.name is required")
        if not self.version:
            raise ValueError("CapabilityPack.version is required")
        if not self.publications:
            raise ValueError(f"CapabilityPack '{self.name}' must declare at least one publication")
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
