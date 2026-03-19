"""Unit tests for packages/pipelines/file_format.py."""
from __future__ import annotations

import csv
import io
import json

import openpyxl
import pytest

from packages.pipelines.file_format import normalize_to_csv_bytes

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_xlsx_bytes(rows: list[list[str]]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _parse_csv(data: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(data.decode("utf-8"))))


# ---------------------------------------------------------------------------
# CSV pass-through
# ---------------------------------------------------------------------------


def test_csv_bytes_returned_unchanged() -> None:
    csv_bytes = b"date,amount\n2024-01-01,100\n"
    result = normalize_to_csv_bytes(csv_bytes, "data.csv")
    assert result == csv_bytes


def test_unknown_extension_returned_unchanged() -> None:
    raw = b"some random content"
    assert normalize_to_csv_bytes(raw, "data.tsv") == raw


# ---------------------------------------------------------------------------
# XLSX conversion
# ---------------------------------------------------------------------------


def test_xlsx_header_and_rows_converted_to_csv() -> None:
    rows = [
        ["booked_at", "account_id", "amount"],
        ["2024-01-01", "acc-1", "42.50"],
        ["2024-01-02", "acc-2", "-10.00"],
    ]
    xlsx_bytes = _make_xlsx_bytes(rows)
    result = normalize_to_csv_bytes(xlsx_bytes, "transactions.xlsx")
    parsed = _parse_csv(result)
    assert parsed[0] == ["booked_at", "account_id", "amount"]
    assert parsed[1] == ["2024-01-01", "acc-1", "42.50"]
    assert parsed[2] == ["2024-01-02", "acc-2", "-10.00"]


def test_xlsx_none_cells_become_empty_string() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["col_a", "col_b"])
    ws.append([None, "value"])
    buf = io.BytesIO()
    wb.save(buf)
    xlsx_bytes = buf.getvalue()

    result = normalize_to_csv_bytes(xlsx_bytes, "data.xlsx")
    parsed = _parse_csv(result)
    assert parsed[1][0] == ""
    assert parsed[1][1] == "value"


def test_xlsx_invalid_bytes_raise_value_error() -> None:
    with pytest.raises(ValueError, match="Could not read XLSX"):
        normalize_to_csv_bytes(b"not an xlsx file", "data.xlsx")


# ---------------------------------------------------------------------------
# JSON conversion
# ---------------------------------------------------------------------------


def test_json_array_of_objects_converted_to_csv() -> None:
    records = [
        {"booked_at": "2024-01-01", "amount": "99.99", "account_id": "acc-1"},
        {"booked_at": "2024-01-02", "amount": "-5.00", "account_id": "acc-2"},
    ]
    json_bytes = json.dumps(records).encode("utf-8")
    result = normalize_to_csv_bytes(json_bytes, "data.json")
    parsed = _parse_csv(result)
    assert parsed[0] == ["booked_at", "amount", "account_id"]
    assert parsed[1] == ["2024-01-01", "99.99", "acc-1"]
    assert parsed[2] == ["2024-01-02", "-5.00", "acc-2"]


def test_json_null_values_become_empty_string() -> None:
    records = [{"col": None}, {"col": "value"}]
    json_bytes = json.dumps(records).encode("utf-8")
    result = normalize_to_csv_bytes(json_bytes, "data.json")
    parsed = _parse_csv(result)
    assert parsed[1][0] == ""
    assert parsed[2][0] == "value"


def test_json_not_array_raises_value_error() -> None:
    with pytest.raises(ValueError, match="array of objects"):
        normalize_to_csv_bytes(b'{"key": "value"}', "data.json")


def test_json_empty_array_raises_value_error() -> None:
    with pytest.raises(ValueError, match="empty array"):
        normalize_to_csv_bytes(b"[]", "data.json")


def test_json_invalid_bytes_raise_value_error() -> None:
    with pytest.raises(ValueError, match="Could not parse JSON"):
        normalize_to_csv_bytes(b"not json", "data.json")
