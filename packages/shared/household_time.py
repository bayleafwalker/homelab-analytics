"""Household timezone: the wall clock the household reads reports in.

Configured with ``HOMELAB_ANALYTICS_HOUSEHOLD_TIMEZONE`` (an IANA name such as
``Europe/Helsinki``; default ``UTC``). Storage stays UTC everywhere; the zone
is applied at read time where a report talks about hours of the day or
calendar dates: the spend heatmap's hour columns, the wallboard's power
buckets and the morning brief's dates.

The zone database comes from the system (``/usr/share/zoneinfo``) or, when the
host has none (slim images), from the ``tzdata`` package.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

HOUSEHOLD_TIMEZONE_ENV = "HOMELAB_ANALYTICS_HOUSEHOLD_TIMEZONE"
DEFAULT_HOUSEHOLD_TIMEZONE = "UTC"


@lru_cache(maxsize=32)
def household_zone(name: str | None) -> ZoneInfo:
    """Return the ``ZoneInfo`` for an IANA name; ``None``/blank means UTC.

    Raises ``ValueError`` naming the setting for anything that is not a
    loadable IANA zone, so a typo fails startup instead of silently
    reporting in UTC.
    """
    key = (name or "").strip() or DEFAULT_HOUSEHOLD_TIMEZONE
    # ZoneInfo accepts relative paths such as "../etc/passwd" poorly and
    # POSIX TZ strings not at all; insist on a plain IANA key.
    if key.startswith(("/", ".")) or ".." in key or "\\" in key:
        raise ValueError(
            f"{HOUSEHOLD_TIMEZONE_ENV} must be an IANA timezone name such as "
            f"'Europe/Helsinki', got {key!r}."
        )
    try:
        return ZoneInfo(key)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(
            f"{HOUSEHOLD_TIMEZONE_ENV} must be an IANA timezone name such as "
            f"'Europe/Helsinki', got {key!r}."
        ) from exc


def local_date(value: datetime, zone: ZoneInfo) -> date:
    """Calendar date of ``value`` on the household clock (naive means UTC)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(zone).date()
