from __future__ import annotations

import hashlib


def build_contract_id(
    contract_name: str,
    provider: str,
    contract_type: str,
) -> str:
    raw = f"{contract_type.strip().lower()}|{provider.strip().lower()}|{contract_name.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
