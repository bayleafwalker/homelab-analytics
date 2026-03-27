# Finance Ingestion Model

## Purpose

This document defines the ingestion architecture for personal-finance sources. It introduces a contract taxonomy, three ingestion lanes, four canonical dataset types, and the lifecycle from raw evidence to published output. It extends the platform's existing data architecture without replacing it.

**Sprint reference:** `docs/sprints/finance-ingestion-subsystem.md`
**Platform reference:** `docs/architecture/data-platform-architecture.md`

---

## Problem

The platform already ingests structured CSV data through a config-driven pipeline (source system → dataset contract → column mapping → landing → promotion). This works well for tabular transaction exports.

Personal finance adds three source shapes that do not fit the CSV column-mapping model cleanly:

1. **Structured CSV exports with provider-specific conventions** — semicolons, decimal commas, Finnish headers, provider-specific enrichment fields. These need source-aware parsers, not just column remapping.
2. **Document sources** — PDF invoices and structured text exports that require extraction before normalization. These produce snapshots, not transaction streams.
3. **Sparse manual facts** — loan policy metadata, classification overrides, account ownership mappings. These are operator-entered reference data, not file-based imports.

The ingestion model must support all three without muddying the existing pipeline or losing raw evidence lineage.

---

## Ingestion lanes

### Lane A — Structured contract import

For sources with a known, stable columnar format. The parser understands the provider's conventions and maps to canonical fields directly.

| Property | Value |
|----------|-------|
| Input shape | CSV or tabular file with known schema |
| Parser type | Source contract parser (provider-specific) |
| Landing model | Raw file → blob store; parsed rows → landing records |
| Canonical output | Transaction event stream or balance snapshot |
| Dedupe | SHA-256 file hash + identity strategy row dedup |
| Examples | OP account CSV, Revolut account CSV |

Lane A sources use the `SourceContractParser` protocol. They bypass the generic column-mapping pipeline because provider-specific conventions (locale, delimiter, enrichment) are handled inside the parser.

Lane A sources may still register a `DatasetContract` for downstream validation — the parser emits rows conforming to a canonical contract, which the existing validation and promotion infrastructure consumes.

### Lane B — Raw document + parser

For sources where the input is a document (PDF, HTML, structured text) rather than a tabular file. The parser extracts structured data from unstructured or semi-structured content.

| Property | Value |
|----------|-------|
| Input shape | PDF, HTML, or structured text file |
| Parser type | Document contract parser (provider-specific) |
| Landing model | Raw document → blob store; extracted records → structured output |
| Canonical output | Statement snapshot or external reconciliation snapshot |
| Dedupe | SHA-256 document hash + snapshot/statement timestamp uniqueness |
| Examples | OP Gold credit card invoice PDF, Finnish positive credit registry text export |

Lane B sources also implement `SourceContractParser`, but their `parse()` method reads document content rather than CSV rows. The parser produces a `ParseResult` with structured records and confidence/warning metadata.

Lane B parsers must:
- Preserve the original document unchanged in blob storage
- Surface extraction confidence explicitly — high/medium/low per field
- Prefer correct summary extraction over fragile line-item extraction
- Tolerate layout variation without hallucinating structure

### Lane C — Manual reference input

For sparse operator-entered facts that do not come from file-based sources. These are reference data, not bulk events.

| Property | Value |
|----------|-------|
| Input shape | Dashboard form or API call |
| Landing model | Versioned fact record in control plane |
| Canonical output | Manual reference dataset |
| Dedupe | Entity key + effective_from versioning |
| Examples | Loan policy metadata, classification overrides, account ownership |

Lane C does not use `SourceContractParser`. Manual inputs enter through the API or dashboard and are stored as versioned reference facts with effective dating and audit metadata.

Lane C is explicitly limited to sparse facts. Bulk data entry belongs in Lane A (structured import) or the existing configured CSV pipeline.

---

## Canonical dataset types

### 1. Transaction event stream

An append-only sequence of cash movement events. One row per transaction. This is the existing `fact_transaction` pattern.

| Property | Value |
|----------|-------|
| Grain | One row per cash movement |
| Time semantics | Event time (booked_at, value_date) |
| Mutability | Append-only; corrections via reversal events |
| Identity | Content-addressed via identity strategy tiers |
| Sources | OP account CSV, Revolut CSV, any bank export |

Canonical fields: `booked_at`, `value_date`, `amount`, `currency`, `counterparty_name`, `description`, `account_id`, `direction`, `source_row_fingerprint`.

### 2. Statement snapshot

A point-in-time summary of a statement period, typically from a credit card or billing document. One header record per statement, with optional line-item detail rows.

| Property | Value |
|----------|-------|
| Grain | One header per statement period; optional line items |
| Time semantics | Statement date + billing period (start/end) |
| Mutability | Immutable once landed; replacement via new statement version |
| Identity | Statement date + account/contract identifier |
| Sources | OP Gold credit card invoice PDF |

Header fields: `statement_date`, `period_start`, `period_end`, `due_date`, `previous_balance`, `payments_total`, `purchases_total`, `interest_amount`, `service_fee`, `minimum_due`, `ending_balance`.

Line-item fields: `posted_at`, `merchant`, `amount`, `confidence`.

Statement snapshots should not replace account transaction data for payment truth. They capture the issuer's view at a point in time.

### 3. External reconciliation snapshot

A point-in-time inventory from an external authority. Contains multiple entity records (loans, credits, income rows) as of a specific date. Used for debt inventory and cross-checking, not as operational truth.

| Property | Value |
|----------|-------|
| Grain | One header per snapshot; one row per entity |
| Time semantics | Snapshot timestamp (report generation date) |
| Mutability | Immutable; new snapshot replaces old for current view |
| Identity | Snapshot timestamp + report reference |
| Sources | Finnish positive credit registry export |

Header fields: `snapshot_at`, `report_reference`, `requester_id`, `credit_count`.

Entity fields: `credit_type`, `creditor`, `credit_identifier`, `agreement_date`, `granted_amount`, `balance`, `monthly_payment`, plus type-specific fields.

Companion tables: income snapshot rows (month + reported amount).

External reconciliation snapshots should carry explicit warnings when used for decision-making — registry balances may lag real-time balances.

### 4. Manual reference dataset

Versioned, effective-dated facts entered by the operator. Sparse, auditable, and limited to reference data that cannot be derived from file-based sources.

| Property | Value |
|----------|-------|
| Grain | One record per attribute value per effective period |
| Time semantics | Effective dating (effective_from, effective_to) |
| Mutability | New versions supersede old; history preserved |
| Identity | Entity type + entity key + attribute + effective_from |
| Sources | Dashboard/API manual entry |

Fields: `entity_type`, `entity_key`, `attribute`, `value`, `effective_from`, `effective_to`, `source`, `created_by`.

---

## Source contract parser protocol

The `SourceContractParser` protocol is the shared interface for Lane A and Lane B parsers. It lives in `packages/domains/finance/contracts/base.py`.

```python
@dataclass(frozen=True)
class ParseResult:
    dataset_type: str                      # canonical dataset type identifier
    records: list[dict[str, Any]]          # normalized output rows
    warnings: list[ValidationIssue]        # parser warnings / confidence flags
    metadata: dict[str, Any]              # parser-specific metadata
    raw_sha256: str                        # content hash of input

class SourceContractParser(Protocol):
    contract_id: str                       # unique parser identifier
    dataset_type: str                      # canonical dataset type

    def detect(self, file_name: str, header_bytes: bytes) -> bool:
        """Return True if the file matches this parser's expected format."""
        ...

    def parse(self, source_bytes: bytes, file_name: str) -> ParseResult:
        """Parse source bytes into normalized records."""
        ...

    def validate(self, result: ParseResult) -> ValidationResult:
        """Validate parsed records against the contract's expectations."""
        ...
```

### ParseResult semantics

- `records` contains normalized rows ready for downstream consumption. For transaction event streams, each dict is one transaction. For snapshots, the list may contain header records and entity records distinguished by a `record_type` field.
- `warnings` surfaces extraction issues without blocking ingestion. A warning does not make validation fail — it annotates the result.
- `metadata` carries parser-specific context: snapshot timestamps, statement periods, detected locale, parser version. Downstream consumers may use this for freshness tracking and reconciliation.
- `raw_sha256` is computed by the parser from the input bytes and used for file-level dedup before row-level identity strategy runs.

### Integration with existing pipeline

Source contract parsers do not replace the existing `ConfiguredCsvIngestionService` and column-mapping pipeline. They run alongside it:

- **Configured CSV pipeline:** Generic, config-driven. Operator defines column mappings in the control plane. Best for sources where the operator controls the mapping without code changes.
- **Source contract parsers:** Code-defined, provider-specific. Parser logic is in Python. Best for sources with provider-specific conventions that need programmatic handling (locale, enrichment, document extraction).

Both paths converge at the landing service: raw evidence is stored in blob storage, and run metadata is recorded in the control plane. Both paths produce records that can feed into the same promotion and publication infrastructure.

---

## Lifecycle

```
┌─────────────────────────────────────────────────────────┐
│  Source                                                  │
│  (file export, document, manual entry)                   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Ingestion lane selection                                │
│  (detect parser, or route manual entry)                  │
└──────────────────────┬──────────────────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
┌──────────────────┐  ┌──────────────────┐
│  Lane A/B:       │  │  Lane C:         │
│  File-based      │  │  Manual entry    │
│  ┌────────────┐  │  │  ┌────────────┐  │
│  │ Raw → blob │  │  │  │ Versioned  │  │
│  │ store      │  │  │  │ fact       │  │
│  └─────┬──────┘  │  │  │ record     │  │
│        ▼         │  │  └────────────┘  │
│  ┌────────────┐  │  └──────────────────┘
│  │ Parse +    │  │
│  │ validate   │  │
│  └─────┬──────┘  │
│        ▼         │
│  ┌────────────┐  │
│  │ Landing    │  │
│  │ record     │  │
│  └────────────┘  │
└──────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Promotion                                               │
│  (identity strategy, canonical fact/dim upsert)          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Publication                                             │
│  (reporting marts, API, dashboard)                       │
└─────────────────────────────────────────────────────────┘
```

### Evidence preservation

Every ingest path preserves raw evidence:

- **Lane A/B:** Original file bytes stored in blob store before any parsing. Run manifest JSON records the SHA-256, file name, source name, and parser contract ID.
- **Lane C:** Each manual fact version is an immutable record with created_by and created_at audit fields. Superseded versions remain queryable.

### Lineage chain

Each downstream record must be traceable to its origin:

1. **Raw evidence** — blob store path + SHA-256 of original file
2. **Landing record** — run_id linking raw evidence to parsed output
3. **Canonical record** — source_run_id linking fact/dim row to the landing record that produced it
4. **Publication record** — lineage metadata linking mart row to contributing canonical records

---

## Idempotency and deduplication

### File-level dedup

The existing `LandingService` computes SHA-256 of the uploaded file and checks for prior runs with the same hash and dataset name. This applies to Lane A and Lane B sources unchanged.

### Row-level dedup (Lane A)

Transaction event streams use the existing identity strategy system. Each parser declares or reuses an identity strategy that computes a stable entity key from row fields. The promotion handler uses the entity key to detect and skip duplicate rows.

### Snapshot-level dedup (Lane B)

Statement and reconciliation snapshots use snapshot timestamp + account/report identifier as the uniqueness key. Re-uploading the same document is caught by SHA-256 file dedup. Uploading a corrected document for the same period creates a new snapshot version — the latest snapshot for a period is the current one.

### Fact-level dedup (Lane C)

Manual reference facts use entity type + entity key + attribute + effective_from as the uniqueness constraint. Creating a new fact for the same attribute with a later effective_from supersedes the previous version without deleting it.

---

## Security and privacy

Financial source files contain sensitive personal data. The ingestion model enforces:

- **Blob storage isolation:** Raw financial files are stored in the same blob store as other landing payloads. Operators should configure blob storage with appropriate access controls for their deployment.
- **Sensitivity classification:** Source freshness configs carry a `sensitivity_class` field (`financial`, `personal`, `operational`) to support future access-control and retention policies.
- **No credential storage:** Source contract parsers do not handle bank credentials, API tokens, or login sessions. Source acquisition is the operator's responsibility.
- **Audit trail:** All ingestion runs, manual fact entries, and promotion outcomes produce audit records in the control plane.

---

## Relationship to existing architecture

### What stays the same

- The three-layer data model (landing/silver/gold) is unchanged
- The `ConfiguredCsvIngestionService` and column-mapping pipeline remain the default for generic CSV sources
- The landing service, blob store, and run metadata model are reused as-is
- Identity strategies and promotion handlers are reused for transaction event streams
- Publication contracts and capability pack registration are unchanged

### What is new

- `SourceContractParser` protocol for provider-specific parsers (both CSV and document)
- `ParseResult` and `ExtractionConfidence` types for parser output
- Statement snapshot and external reconciliation snapshot as canonical dataset types
- Manual reference dataset type with effective dating
- Source freshness config as a companion to source assets
- Finance contracts package under the finance domain pack
