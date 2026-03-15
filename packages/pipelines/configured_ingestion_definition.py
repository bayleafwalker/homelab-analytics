from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.shared.secrets import EnvironmentSecretResolver, SecretReference, SecretResolver
from packages.storage.blob import BlobStore, FilesystemBlobStore
from packages.storage.control_plane import ControlPlaneStore
from packages.storage.run_metadata import RunMetadataStore


@dataclass(frozen=True)
class ConfiguredIngestionProcessResult:
    ingestion_definition_id: str
    discovered_files: int
    processed_files: int
    rejected_files: int
    run_ids: tuple[str, ...] = ()


class ConfiguredIngestionDefinitionService:
    def __init__(
        self,
        landing_root: Path,
        metadata_repository: RunMetadataStore,
        config_repository: ControlPlaneStore,
        blob_store: BlobStore | None = None,
        secret_resolver: SecretResolver | None = None,
    ) -> None:
        self.landing_root = landing_root
        self.metadata_repository = metadata_repository
        self.config_repository = config_repository
        self.blob_store = blob_store or FilesystemBlobStore(landing_root)
        self.secret_resolver = secret_resolver or EnvironmentSecretResolver()
        self.csv_ingestion_service = ConfiguredCsvIngestionService(
            landing_root=landing_root,
            metadata_repository=metadata_repository,
            config_repository=config_repository,
            blob_store=self.blob_store,
        )

    def process_ingestion_definition(
        self,
        ingestion_definition_id: str,
    ) -> ConfiguredIngestionProcessResult:
        ingestion_definition = self.config_repository.get_ingestion_definition(
            ingestion_definition_id
        )
        if not ingestion_definition.enabled:
            raise ValueError(
                f"Ingestion definition is disabled: {ingestion_definition_id}"
            )
        if ingestion_definition.transport == "filesystem":
            return self._process_filesystem_definition(ingestion_definition)
        if ingestion_definition.transport in {"http", "https"}:
            return self._process_http_definition(ingestion_definition)
        raise ValueError(
            f"Unsupported ingestion transport: {ingestion_definition.transport}"
        )

    def _process_filesystem_definition(
        self,
        ingestion_definition,
    ) -> ConfiguredIngestionProcessResult:
        source_asset = self.config_repository.get_source_asset(
            ingestion_definition.source_asset_id
        )
        if not source_asset.enabled:
            raise ValueError(
                f"Source asset is disabled: {ingestion_definition.source_asset_id}"
            )
        source_system = self.config_repository.get_source_system(
            source_asset.source_system_id
        )
        if not source_system.enabled:
            raise ValueError(
                f"Source system is disabled: {source_asset.source_system_id}"
            )
        inbox_dir = Path(ingestion_definition.source_path)
        processed_dir = Path(
            ingestion_definition.processed_path or inbox_dir / "processed"
        )
        failed_dir = Path(ingestion_definition.failed_path or inbox_dir / "failed")
        inbox_dir.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)
        failed_dir.mkdir(parents=True, exist_ok=True)

        discovered_files = 0
        processed_files = 0
        rejected_files = 0
        run_ids: list[str] = []

        for source_path in sorted(inbox_dir.glob(ingestion_definition.file_pattern)):
            if not source_path.is_file():
                continue

            discovered_files += 1
            run = self.csv_ingestion_service.ingest_file(
                source_path=source_path,
                source_system_id=source_asset.source_system_id,
                dataset_contract_id=source_asset.dataset_contract_id,
                column_mapping_id=source_asset.column_mapping_id,
                source_name=ingestion_definition.source_name or "configured-folder",
            )
            run_ids.append(run.run_id)

            if run.passed:
                destination_path = processed_dir / f"{run.run_id}-{source_path.name}"
                processed_files += 1
            else:
                destination_path = failed_dir / f"{run.run_id}-{source_path.name}"
                rejected_files += 1
            source_path.replace(destination_path)

        return ConfiguredIngestionProcessResult(
            ingestion_definition_id=ingestion_definition.ingestion_definition_id,
            discovered_files=discovered_files,
            processed_files=processed_files,
            rejected_files=rejected_files,
            run_ids=tuple(run_ids),
        )

    def _process_http_definition(
        self,
        ingestion_definition,
    ) -> ConfiguredIngestionProcessResult:
        source_asset = self.config_repository.get_source_asset(
            ingestion_definition.source_asset_id
        )
        if not source_asset.enabled:
            raise ValueError(
                f"Source asset is disabled: {ingestion_definition.source_asset_id}"
            )
        source_system = self.config_repository.get_source_system(
            source_asset.source_system_id
        )
        if not source_system.enabled:
            raise ValueError(
                f"Source system is disabled: {source_asset.source_system_id}"
            )
        if not ingestion_definition.request_url:
            raise ValueError(
                "HTTP ingestion definitions must define request_url."
            )
        if ingestion_definition.response_format not in {None, "csv"}:
            raise ValueError(
                "Only CSV HTTP ingestion definitions are supported in the current implementation."
            )

        request = Request(
            ingestion_definition.request_url,
            method=ingestion_definition.request_method or "GET",
            headers={
                header.name: self.secret_resolver.resolve(
                    SecretReference(
                        secret_name=header.secret_name,
                        secret_key=header.secret_key,
                    )
                )
                for header in ingestion_definition.request_headers
            },
        )
        try:
            with urlopen(
                request,
                timeout=ingestion_definition.request_timeout_seconds,
            ) as response:
                response_bytes = response.read()
        except OSError as exc:
            raise ValueError(
                f"Failed to fetch HTTP ingestion source: {ingestion_definition.request_url}"
            ) from exc

        file_name = ingestion_definition.output_file_name or _derive_http_file_name(
            ingestion_definition.request_url
        )
        run = self.csv_ingestion_service.ingest_bytes(
            source_bytes=response_bytes,
            file_name=file_name,
            source_system_id=source_asset.source_system_id,
            dataset_contract_id=source_asset.dataset_contract_id,
            column_mapping_id=source_asset.column_mapping_id,
            source_name=ingestion_definition.source_name or "configured-http-pull",
        )

        return ConfiguredIngestionProcessResult(
            ingestion_definition_id=ingestion_definition.ingestion_definition_id,
            discovered_files=1,
            processed_files=1 if run.passed else 0,
            rejected_files=0 if run.passed else 1,
            run_ids=(run.run_id,),
        )


def _derive_http_file_name(request_url: str) -> str:
    path = urlparse(request_url).path
    file_name = Path(path).name
    if file_name:
        return file_name
    return "download.csv"
