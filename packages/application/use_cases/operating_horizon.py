"""Merge dated household actions into the seven-day operating horizon.

The Operating Picture's horizon is a read-only projection over four existing
sources:

* pending action proposals (still awaiting a human decision),
* due manual exports from the source-freshness views,
* upcoming fixed costs from the reporting mart, and
* contract renewals from the reporting mart.

Every row keeps a stable ``kind``, an ISO ``date`` and a display ``label``,
plus enough source identity to keep two same-day actions distinct. Rows are
sorted by date with deterministic ties; empty days are the view's concern,
so a day with no actions simply contributes no row.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any

HORIZON_DAYS = 7

# Acquisition modes that mean a machine pulls the data. A source in one of
# these modes is never a manual export, even if it is due.
AUTOMATIC_ACQUISITION_MODES = frozenset(
    {"pull", "api_pull", "automatic", "automatic_pull", "scheduled"}
)

KIND_ORDER = {
    "approval": 0,
    "export": 1,
    "fixed_cost": 2,
    "renewal": 3,
}


def horizon_end(start_date: date) -> date:
    """Last day in the inclusive seven-day window starting at ``start_date``."""
    return start_date + timedelta(days=HORIZON_DAYS - 1)


def in_horizon(value: Any, start_date: date) -> date | None:
    """Return ``value`` as a date when it falls inside the horizon, else None."""
    resolved = coerce_date(value)
    if resolved is None or resolved < start_date or resolved > horizon_end(start_date):
        return None
    return resolved


def coerce_date(value: Any) -> date | None:
    """Best-effort date for a mart/view value without inventing one."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    return None


def build_operating_horizon(
    *,
    start_date: date,
    fixed_costs: Iterable[Mapping[str, Any]] = (),
    contract_renewals: Iterable[Mapping[str, Any]] = (),
    freshness_views: Iterable[Any] = (),
    freshness_configs: Iterable[Any] = (),
    pending_proposals: Iterable[Any] = (),
) -> dict[str, Any]:
    """Build the merged feed for the window starting at ``start_date``."""
    rows: list[dict[str, Any]] = []
    rows.extend(_approval_rows(pending_proposals or (), start_date))
    configs = _config_index(freshness_configs or ())
    rows.extend(_export_rows(freshness_views or (), configs, start_date))
    rows.extend(_fixed_cost_rows(fixed_costs or (), start_date))
    rows.extend(_renewal_rows(contract_renewals or (), start_date))
    _disambiguate_ids(rows)
    rows.sort(
        key=lambda row: (
            row["date"],
            KIND_ORDER.get(str(row["kind"]), len(KIND_ORDER)),
            str(row["label"]).casefold(),
            str(row["id"]),
        )
    )
    return {"start_date": start_date.isoformat(), "rows": rows}


def _approval_rows(
    pending_proposals: Iterable[Any], start_date: date
) -> list[dict[str, Any]]:
    """Pending approvals are actionable now; today is not their deadline."""
    rows: list[dict[str, Any]] = []
    for proposal in pending_proposals:
        action_id = _field(proposal, "action_id")
        if not action_id:
            continue
        if _field(proposal, "status", "pending") not in (None, "pending"):
            continue
        label = (
            _field(proposal, "policy_name")
            or _field(proposal, "source_summary")
            or "Approval"
        )
        rows.append(
            {
                "id": f"approval:{action_id}",
                "kind": "approval",
                "date": start_date.isoformat(),
                "label": label,
                "action_id": action_id,
                "actionable_now": True,
            }
        )
    return rows


def _export_rows(
    freshness_views: Iterable[Any],
    freshness_configs: Mapping[str, Any],
    start_date: date,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for view in freshness_views:
        source_asset_id = _field(view, "source_asset_id")
        if not source_asset_id:
            continue
        config = freshness_configs.get(str(source_asset_id))
        if not _is_due_manual_export(config):
            continue
        expected = in_horizon(_field(view, "next_expected_at"), start_date)
        if expected is None:
            continue
        name = _field(view, "name") or _field(view, "dataset_name") or source_asset_id
        rows.append(
            {
                "id": f"export:{source_asset_id}",
                "kind": "export",
                "date": expected.isoformat(),
                "label": name,
                "source_asset_id": source_asset_id,
                "dataset_name": _field(view, "dataset_name"),
                "suggested_action": _field(view, "suggested_action"),
            }
        )
    return rows


def _fixed_cost_rows(
    fixed_costs: Iterable[Mapping[str, Any]], start_date: date
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost in fixed_costs:
        expected = in_horizon(cost.get("expected_date"), start_date)
        if expected is None:
            continue
        label = cost.get("contract_name") or cost.get("provider") or "Fixed cost"
        charge_id = cost.get("charge_id")
        identity = charge_id or f"{label}:{expected.isoformat()}"
        row = {
            "id": f"fixed_cost:{identity}",
            "kind": "fixed_cost",
            "date": expected.isoformat(),
            "label": label,
            "contract_name": cost.get("contract_name"),
            "provider": cost.get("provider"),
            "frequency": cost.get("frequency"),
            "expected_date": expected.isoformat(),
            "charge_id": charge_id,
            "confidence": cost.get("confidence"),
        }
        _carry_amount(row, cost, amount_key="expected_amount")
        rows.append(row)
    return rows


def _renewal_rows(
    contract_renewals: Iterable[Mapping[str, Any]], start_date: date
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for renewal in contract_renewals:
        renewal_date = in_horizon(renewal.get("renewal_date"), start_date)
        if renewal_date is None:
            continue
        label = renewal.get("contract_name") or renewal.get("provider") or "Renewal"
        contract_id = renewal.get("contract_id")
        identity = contract_id or f"{label}:{renewal_date.isoformat()}"
        row = {
            "id": f"renewal:{identity}",
            "kind": "renewal",
            "date": renewal_date.isoformat(),
            "label": label,
            "contract_id": contract_id,
            "contract_name": renewal.get("contract_name"),
            "provider": renewal.get("provider"),
            "utility_type": renewal.get("utility_type"),
            "renewal_date": renewal_date.isoformat(),
            "days_until_renewal": renewal.get("days_until_renewal"),
        }
        _carry_amount(row, renewal, amount_key="current_price")
        rows.append(row)
    return rows


def _carry_amount(
    row: dict[str, Any], source: Mapping[str, Any], *, amount_key: str
) -> None:
    """Copy an existing amount and currency without inventing either one."""
    amount = source.get(amount_key)
    currency = source.get("currency")
    if amount is not None:
        row["amount"] = amount
    if currency is not None:
        row["currency"] = currency


def _is_due_manual_export(config: Any) -> bool:
    if config is None:
        return False
    if not bool(_field(config, "requires_human_action", False)):
        return False
    mode = str(_field(config, "acquisition_mode", "") or "").strip().lower()
    return mode not in AUTOMATIC_ACQUISITION_MODES


def _config_index(freshness_configs: Any) -> dict[str, Any]:
    if isinstance(freshness_configs, Mapping):
        return {str(source_asset_id): config for source_asset_id, config in freshness_configs.items()}
    return {
        str(_field(config, "source_asset_id", "")): config
        for config in freshness_configs
    }


def _disambiguate_ids(rows: list[dict[str, Any]]) -> None:
    """Keep ids unique even when two source rows share every natural key."""
    used: set[str] = set()
    for row in rows:
        base = str(row["id"])
        candidate = base
        index = 1
        while candidate in used:
            index += 1
            candidate = f"{base}#{index}"
        row["id"] = candidate
        used.add(candidate)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)
