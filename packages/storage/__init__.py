from .blob import BlobStore, FilesystemBlobStore, InMemoryBlobStore
from .ingestion_catalog import (
    ColumnMappingCreate,
    ColumnMappingRecord,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    DatasetContractConfigRecord,
    IngestionDefinitionCreate,
    IngestionDefinitionRecord,
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
from .ingestion_config import IngestionConfigRepository
from .runtime import build_blob_store, build_reporting_store, build_run_metadata_store

try:
    from .duckdb_store import DimensionColumn, DimensionDefinition, DuckDBStore  # noqa: F401
except ModuleNotFoundError as exc:
    if exc.name != "duckdb":
        raise
try:
    from .postgres_reporting import PostgresReportingStore  # noqa: F401
except ModuleNotFoundError as exc:
    if exc.name != "psycopg":
        raise
try:
    from .postgres_run_metadata import PostgresRunMetadataRepository  # noqa: F401
except ModuleNotFoundError as exc:
    if exc.name != "psycopg":
        raise
try:
    from .s3_blob import S3BlobStore  # noqa: F401
except ModuleNotFoundError as exc:
    if exc.name not in {"boto3", "botocore"}:
        raise
from .landing_service import LandingRunResult, LandingService
from .local_landing import ingest_csv_file
from .run_metadata import (
    IngestionRunCreate,
    IngestionRunRecord,
    IngestionRunStatus,
    RunMetadataRepository,
    RunMetadataStore,
)

__all__ = [
    "BlobStore",
    "FilesystemBlobStore",
    "InMemoryBlobStore",
    "build_blob_store",
    "build_reporting_store",
    "build_run_metadata_store",
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
if "PostgresReportingStore" in globals():
    __all__.append("PostgresReportingStore")
if "PostgresRunMetadataRepository" in globals():
    __all__.append("PostgresRunMetadataRepository")
if "S3BlobStore" in globals():
    __all__.append("S3BlobStore")
