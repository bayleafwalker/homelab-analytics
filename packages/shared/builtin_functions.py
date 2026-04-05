from __future__ import annotations

import re

from packages.shared.function_registry import FunctionRegistry, RegisteredFunction

_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _transform_flexible_decimal(*, value: object, **_: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    normalized = (
        text.replace("\xa0", " ")
        .replace("EUR", "")
        .replace("eur", "")
        .replace("€", "")
        .strip()
        .replace(" ", "")
    )

    if "," in normalized and "." in normalized:
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
    elif "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")

    return normalized


def _transform_iso_datetime_to_date(*, value: object, **_: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = _DATE_PREFIX_RE.match(text)
    if match is not None:
        return match.group(0)
    return text


def register_builtin_functions(registry: FunctionRegistry) -> None:
    registry.register(
        RegisteredFunction(
            function_key="transform_flexible_decimal",
            kind="column_mapping_value",
            description=(
                "Normalize flexible decimal strings such as Finnish comma decimals"
                " into canonical dot-decimal text."
            ),
            module="packages.shared.builtin_functions",
            source="builtin",
            handler=_transform_flexible_decimal,
        )
    )
    registry.register(
        RegisteredFunction(
            function_key="transform_iso_datetime_to_date",
            kind="column_mapping_value",
            description=(
                "Extract the YYYY-MM-DD date component from ISO-style date"
                " or datetime text."
            ),
            module="packages.shared.builtin_functions",
            source="builtin",
            handler=_transform_iso_datetime_to_date,
        )
    )
