"""File-format normalization: convert XLSX or JSON bytes to CSV bytes.

All ingest services accept raw bytes + a file name. This module normalises
XLSX and JSON inputs into CSV bytes so the rest of the pipeline is unchanged.
CSV bytes are returned as-is.
"""

from __future__ import annotations

import csv
import io
import json


def normalize_to_csv_bytes(source_bytes: bytes, file_name: str) -> bytes:
    """Return CSV bytes regardless of the source file format.

    - ``.xlsx`` — first sheet is read with openpyxl; rows written as CSV.
    - ``.json`` — expects a JSON array of objects; keys of the first record
      become the header row.
    - Anything else (including ``.csv``) — returned unchanged.

    Raises ``ValueError`` with a user-readable message when the XLSX or JSON
    payload cannot be parsed so callers can surface it as a validation issue.
    """
    suffix = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

    if suffix == "xlsx":
        return _xlsx_to_csv_bytes(source_bytes)
    if suffix == "json":
        return _json_to_csv_bytes(source_bytes)
    return source_bytes


def _xlsx_to_csv_bytes(source_bytes: bytes) -> bytes:
    try:
        import openpyxl  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise ValueError("openpyxl is required to upload XLSX files.") from exc

    try:
        workbook = openpyxl.load_workbook(io.BytesIO(source_bytes), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"Could not read XLSX file: {exc}") from exc

    sheet = workbook.active
    if sheet is None:
        raise ValueError("XLSX file contains no sheets.")

    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in sheet.iter_rows(values_only=True):
        writer.writerow([("" if cell is None else str(cell)) for cell in row])
    workbook.close()
    return buf.getvalue().encode("utf-8")


def _json_to_csv_bytes(source_bytes: bytes) -> bytes:
    try:
        data = json.loads(source_bytes)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse JSON file: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError("JSON ingestion expects an array of objects at the top level.")
    if len(data) == 0:
        raise ValueError("JSON file contains an empty array — nothing to ingest.")
    if not isinstance(data[0], dict):
        raise ValueError("JSON ingestion expects each array element to be an object.")

    header = list(dict.fromkeys(k for record in data if isinstance(record, dict) for k in record))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=header, extrasaction="ignore")
    writer.writeheader()
    for i, record in enumerate(data):
        if not isinstance(record, dict):
            raise ValueError(
                f"JSON ingestion expects each array element to be an object; "
                f"element {i} is {type(record).__name__}."
            )
        writer.writerow({k: ("" if record.get(k) is None else str(record.get(k))) for k in header})
    return buf.getvalue().encode("utf-8")
