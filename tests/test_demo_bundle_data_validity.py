"""
Data validity tests for the committed demo bundle at infra/examples/demo-data/.

Goal: catch drift between bundle.py/demo-generate and the committed files at the
ingest-format level (column schema, non-empty rows). Does not pin row counts or
field values — those are too brittle and would fight legitimate data updates.

If any test here fails after a demo-generate run, update the committed bundle with:
    python scripts/generate_walkthrough_reference.py   # keep walkthrough in sync too
    make demo-generate                                 # regenerate committed files
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

DEMO_DATA_ROOT = Path(__file__).parents[1] / "infra" / "examples" / "demo-data"
MANIFEST_PATH = DEMO_DATA_ROOT / "manifest.json"


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def csv_artifacts(manifest) -> list[dict]:
    return [a for a in manifest["artifacts"] if a["format"] == "csv"]


# ---------------------------------------------------------------------------
# Manifest integrity
# ---------------------------------------------------------------------------


def test_manifest_exists():
    assert MANIFEST_PATH.exists(), f"Committed manifest not found at {MANIFEST_PATH}"


def test_manifest_has_artifacts(manifest):
    assert len(manifest.get("artifacts", [])) > 0, "Manifest must contain at least one artifact"


def test_all_manifest_artifacts_exist_on_disk(manifest):
    missing = []
    for artifact in manifest["artifacts"]:
        path = DEMO_DATA_ROOT / artifact["relative_path"]
        if not path.exists():
            missing.append(artifact["relative_path"])
    assert not missing, f"Manifest references files not on disk: {missing}"


def test_all_csv_artifacts_are_non_empty(csv_artifacts):
    empty = []
    for artifact in csv_artifacts:
        path = DEMO_DATA_ROOT / artifact["relative_path"]
        if path.exists() and path.stat().st_size == 0:
            empty.append(artifact["relative_path"])
    assert not empty, f"CSV files are empty (no content): {empty}"


# ---------------------------------------------------------------------------
# Canonical CSV column schema contracts
# ---------------------------------------------------------------------------

_CANONICAL_REQUIRED_COLUMNS: dict[str, set[str]] = {
    "canonical/account_transactions.csv": {
        "booked_at", "account_id", "counterparty_name", "amount", "currency",
    },
    "canonical/budgets.csv": {
        "budget_name", "category", "period_type", "target_amount", "currency", "effective_from",
    },
    "canonical/subscriptions.csv": {
        "service_name", "provider", "billing_cycle", "amount", "currency", "start_date",
    },
    "canonical/contract_prices.csv": {
        "contract_name", "provider", "contract_type", "price_component",
        "billing_cycle", "unit_price", "currency",
    },
    "canonical/loan_repayments.csv": {
        "loan_id", "loan_name", "lender", "principal", "annual_rate", "term_months",
        "start_date", "repayment_date", "payment_amount", "currency",
    },
    "canonical/utility_bills.csv": {
        "meter_id", "provider", "utility_type", "billing_period_start",
        "billing_period_end", "billed_amount", "currency",
    },
}

# OP format is semicolon-delimited with Finnish column names
_OP_REQUIRED_COLUMNS = {"Kirjauspäivä", "Arvopäivä", "Määrä EUROA", "Selitys", "Saaja/Maksaja"}
_OP_SOURCE_FILES = {
    "sources/personal account/tapahtumat20250101-20251231.csv",
    "sources/common account/tapahtumat20250101-20251231.csv",
}

# Revolut format is comma-delimited
_REVOLUT_REQUIRED_COLUMNS = {"Type", "Product", "Started Date", "Amount", "Currency", "State"}
_REVOLUT_SOURCE_FILES = {
    "sources/revolut/account-statement_2025-01-01_2025-12-31_en-us_demo.csv",
}


def _read_csv_columns(path: Path, delimiter: str = ",") -> set[str]:
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration:
            return set()
    return {col.strip().strip('"') for col in header}


def _read_csv_row_count(path: Path, delimiter: str = ",") -> int:
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=delimiter)
        next(reader, None)  # skip header
        return sum(1 for _ in reader)


@pytest.mark.parametrize("relative_path,required_cols", _CANONICAL_REQUIRED_COLUMNS.items())
def test_canonical_csv_has_required_columns(relative_path: str, required_cols: set[str]):
    path = DEMO_DATA_ROOT / relative_path
    if not path.exists():
        pytest.skip(f"File not in committed bundle: {relative_path}")
    actual = _read_csv_columns(path, delimiter=",")
    missing = required_cols - actual
    assert not missing, (
        f"{relative_path} is missing columns: {missing}. "
        f"Run make demo-generate to regenerate the committed bundle."
    )


@pytest.mark.parametrize("relative_path,required_cols", _CANONICAL_REQUIRED_COLUMNS.items())
def test_canonical_csv_has_data_rows(relative_path: str, required_cols: set[str]):
    path = DEMO_DATA_ROOT / relative_path
    if not path.exists():
        pytest.skip(f"File not in committed bundle: {relative_path}")
    count = _read_csv_row_count(path, delimiter=",")
    assert count > 0, (
        f"{relative_path} has no data rows. "
        f"Run make demo-generate to regenerate the committed bundle."
    )


@pytest.mark.parametrize("relative_path", sorted(_OP_SOURCE_FILES))
def test_op_source_csv_has_required_columns(relative_path: str):
    path = DEMO_DATA_ROOT / relative_path
    if not path.exists():
        pytest.skip(f"File not in committed bundle: {relative_path}")
    actual = _read_csv_columns(path, delimiter=";")
    missing = _OP_REQUIRED_COLUMNS - actual
    assert not missing, (
        f"{relative_path} is missing OP format columns: {missing}. "
        f"Run make demo-generate to regenerate the committed bundle."
    )


@pytest.mark.parametrize("relative_path", sorted(_OP_SOURCE_FILES))
def test_op_source_csv_has_data_rows(relative_path: str):
    path = DEMO_DATA_ROOT / relative_path
    if not path.exists():
        pytest.skip(f"File not in committed bundle: {relative_path}")
    count = _read_csv_row_count(path, delimiter=";")
    assert count > 0, (
        f"{relative_path} has no data rows. "
        f"Run make demo-generate to regenerate the committed bundle."
    )


@pytest.mark.parametrize("relative_path", sorted(_REVOLUT_SOURCE_FILES))
def test_revolut_source_csv_has_required_columns(relative_path: str):
    path = DEMO_DATA_ROOT / relative_path
    if not path.exists():
        pytest.skip(f"File not in committed bundle: {relative_path}")
    actual = _read_csv_columns(path, delimiter=",")
    missing = _REVOLUT_REQUIRED_COLUMNS - actual
    assert not missing, (
        f"{relative_path} is missing Revolut format columns: {missing}. "
        f"Run make demo-generate to regenerate the committed bundle."
    )


@pytest.mark.parametrize("relative_path", sorted(_REVOLUT_SOURCE_FILES))
def test_revolut_source_csv_has_data_rows(relative_path: str):
    path = DEMO_DATA_ROOT / relative_path
    if not path.exists():
        pytest.skip(f"File not in committed bundle: {relative_path}")
    count = _read_csv_row_count(path, delimiter=",")
    assert count > 0, (
        f"{relative_path} has no data rows. "
        f"Run make demo-generate to regenerate the committed bundle."
    )
