from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PromotionResult:
    """Summary of a completed run promotion."""

    run_id: str
    facts_loaded: int
    marts_refreshed: list[str]
    publication_keys: list[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None
