from .blob import BlobStore, FilesystemBlobStore, InMemoryBlobStore
try:
    from .duckdb_store import DimensionColumn, DimensionDefinition, DuckDBStore
except ModuleNotFoundError as exc:
    if exc.name != "duckdb":
        raise
from .landing_service import LandingRunResult, LandingService
from .ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRecord,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    DatasetContractConfigRecord,
    IngestionDefinitionCreate,
    IngestionDefinitionRecord,
    IngestionConfigRepository,
    PublicationDefinitionCreate,
    PublicationDefinitionRecord,
    RequestHeaderSecretRef,
    SourceAssetCreate,
    SourceAssetRecord,
    SourceSystemCreate,
    SourceSystemRecord,
    TransformationPackageCreate,
    TransformationPackageRecord,
    resolve_dataset_contract,
)
from .local_landing import ingest_csv_file
from .run_metadata import (
    IngestionRunCreate,
    IngestionRunRecord,
    IngestionRunStatus,
    RunMetadataStore,
    RunMetadataRepository,
)

__all__ = [
    "BlobStore",
    "FilesystemBlobStore",
    "InMemoryBlobStore",
    "IngestionRunCreate",
    "IngestionRunRecord",
    "IngestionRunStatus",
    "ColumnMappingCreate",
    "ColumnMappingRecord",
    "ColumnMappingRule",
    "DatasetColumnConfig",
    "DatasetContractConfigCreate",
    "DatasetContractConfigRecord",
    "IngestionDefinitionCreate",
    "IngestionDefinitionRecord",
    "IngestionConfigRepository",
    "LandingRunResult",
    "LandingService",
    "PublicationDefinitionCreate",
    "PublicationDefinitionRecord",
    "RequestHeaderSecretRef",
    "RunMetadataStore",
    "RunMetadataRepository",
    "SourceAssetCreate",
    "SourceAssetRecord",
    "SourceSystemCreate",
    "SourceSystemRecord",
    "TransformationPackageCreate",
    "TransformationPackageRecord",
    "resolve_dataset_contract",
    "ingest_csv_file",
]

if "DuckDBStore" in globals():
    __all__.extend(
        [
            "DimensionColumn",
            "DimensionDefinition",
            "DuckDBStore",
        ]
    )
