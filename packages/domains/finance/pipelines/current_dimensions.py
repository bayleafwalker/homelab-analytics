"""Finance-pack current-dimension readers."""

from __future__ import annotations

from packages.domains.finance.pipelines.budget_models import CURRENT_DIM_BUDGET_VIEW
from packages.domains.finance.pipelines.loan_models import CURRENT_DIM_LOAN_VIEW
from packages.domains.finance.pipelines.subscription_models import (
    CURRENT_DIM_CATEGORY_VIEW,
    CURRENT_DIM_CONTRACT_VIEW,
)
from packages.domains.finance.pipelines.transaction_models import (
    CURRENT_DIM_ACCOUNT_VIEW,
    CURRENT_DIM_COUNTERPARTY_VIEW,
)
from packages.domains.finance.pipelines.transformation_assets import get_current_assets
from packages.pipelines.current_dimension_registry import (
    CurrentDimensionReader,
    CurrentViewReader,
)

FINANCE_CURRENT_DIMENSION_READERS: dict[str, CurrentDimensionReader] = {
    "dim_account": CurrentViewReader(CURRENT_DIM_ACCOUNT_VIEW, "account_id"),
    "dim_counterparty": CurrentViewReader(CURRENT_DIM_COUNTERPARTY_VIEW, "counterparty_name"),
    "dim_contract": CurrentViewReader(CURRENT_DIM_CONTRACT_VIEW, "contract_name"),
    "dim_category": CurrentViewReader(CURRENT_DIM_CATEGORY_VIEW, "category_id"),
    "dim_budget": CurrentViewReader(CURRENT_DIM_BUDGET_VIEW, "budget_id"),
    "dim_loan": CurrentViewReader(CURRENT_DIM_LOAN_VIEW, "loan_id"),
    "dim_asset": get_current_assets,
}
