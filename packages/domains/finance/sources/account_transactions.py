"""Account transactions source definition for the finance capability pack."""
from __future__ import annotations

from packages.platform.capability_types import SourceDefinition

ACCOUNT_TRANSACTIONS_SOURCE = SourceDefinition(
    dataset_name="account_transactions",
    display_name="Account Transactions",
    description="Bank account transaction records imported from CSV exports.",
    retry_kind="account_transactions",
)
