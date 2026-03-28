"""Finance source contract protocol types."""

from packages.domains.finance.contracts.base import (
    STANDARD_FINANCE_CONTRACT_TAXONOMIES,
    FinanceContractTaxonomy,
    FinanceDatasetType,
    FinanceIngestionLane,
    ParseResult,
    SourceContractParser,
    ValidationIssue,
    ValidationResult,
)
from packages.domains.finance.contracts.fi_credit_registry_snapshot_v1 import (
    CONTRACT_ID as FINNISH_POSITIVE_CREDIT_REGISTRY_CONTRACT_ID,
)
from packages.domains.finance.contracts.fi_credit_registry_snapshot_v1 import (
    PositiveCreditRegistryCreditRecord,
    PositiveCreditRegistryIncomeRecord,
    PositiveCreditRegistrySnapshotParser,
    PositiveCreditRegistrySnapshotRecord,
    load_positive_credit_registry_snapshot_bytes,
)
from packages.domains.finance.contracts.op_account_csv_v1 import (
    CONTRACT_ID as OP_ACCOUNT_TRANSACTION_CONTRACT_ID,
)
from packages.domains.finance.contracts.op_account_csv_v1 import (
    OPAccountTransactionCsvParser,
    OPAccountTransactionRecord,
    load_op_account_transactions_bytes,
)
from packages.domains.finance.contracts.op_gold_invoice_pdf_v1 import (
    CONTRACT_ID as OP_GOLD_CREDIT_CARD_INVOICE_CONTRACT_ID,
)
from packages.domains.finance.contracts.op_gold_invoice_pdf_v1 import (
    OPGoldCreditCardInvoiceLineItemRecord,
    OPGoldCreditCardInvoicePdfParser,
    OPGoldCreditCardInvoiceSnapshotRecord,
    load_op_gold_credit_card_invoice_bytes,
)
from packages.domains.finance.contracts.revolut_personal_account_statement_v1 import (
    CONTRACT_ID as REVOLUT_PERSONAL_ACCOUNT_STATEMENT_CONTRACT_ID,
)
from packages.domains.finance.contracts.revolut_personal_account_statement_v1 import (
    DEFAULT_ACCOUNT_ID,
    RevolutPersonalAccountStatementCsvParser,
    RevolutPersonalAccountStatementRecord,
    load_revolut_personal_account_transactions_bytes,
)

__all__ = [
    "FinanceContractTaxonomy",
    "FinanceDatasetType",
    "FinanceIngestionLane",
    "FINNISH_POSITIVE_CREDIT_REGISTRY_CONTRACT_ID",
    "REVOLUT_PERSONAL_ACCOUNT_STATEMENT_CONTRACT_ID",
    "OP_GOLD_CREDIT_CARD_INVOICE_CONTRACT_ID",
    "PositiveCreditRegistryCreditRecord",
    "PositiveCreditRegistryIncomeRecord",
    "PositiveCreditRegistrySnapshotParser",
    "PositiveCreditRegistrySnapshotRecord",
    "OP_ACCOUNT_TRANSACTION_CONTRACT_ID",
    "OPAccountTransactionCsvParser",
    "OPAccountTransactionRecord",
    "DEFAULT_ACCOUNT_ID",
    "RevolutPersonalAccountStatementCsvParser",
    "RevolutPersonalAccountStatementRecord",
    "OPGoldCreditCardInvoiceLineItemRecord",
    "OPGoldCreditCardInvoicePdfParser",
    "OPGoldCreditCardInvoiceSnapshotRecord",
    "ParseResult",
    "SourceContractParser",
    "STANDARD_FINANCE_CONTRACT_TAXONOMIES",
    "ValidationIssue",
    "ValidationResult",
    "load_positive_credit_registry_snapshot_bytes",
    "load_op_gold_credit_card_invoice_bytes",
    "load_op_account_transactions_bytes",
    "load_revolut_personal_account_transactions_bytes",
]
