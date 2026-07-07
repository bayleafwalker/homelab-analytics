"""Content negotiation for publication rendering.

Given an HTTP-style Accept header and an optional publication-version
hint, select the renderer format and the eligible renderers for a
publication. This module is HTTP-agnostic: callers translate the
negotiation error reasons to HTTP status codes (406 for the misses,
415 for unsupported media types produced by the caller, and so on).
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.adapters.contracts import Renderer

FORMAT_MEDIA_TYPES: dict[str, tuple[str, ...]] = {
    "json": ("application/json",),
    "csv": ("text/csv",),
    "parquet": ("application/vnd.apache.parquet", "application/x-parquet"),
    "prometheus": ("text/plain; version=0.0.4", "text/plain"),
}


MEDIA_TYPE_TO_FORMAT: dict[str, str] = {
    media_type: fmt
    for fmt, media_types in FORMAT_MEDIA_TYPES.items()
    for media_type in media_types
}


NEGOTIATION_ERROR_NO_ACCEPTABLE_FORMAT = "no_acceptable_format"
NEGOTIATION_ERROR_UNSUPPORTED_PUBLICATION_VERSION = "unsupported_publication_version"
NEGOTIATION_ERROR_NO_ELIGIBLE_RENDERER = "no_eligible_renderer"


@dataclass(frozen=True)
class AcceptEntry:
    media_type: str
    quality: float


@dataclass(frozen=True)
class RendererNegotiationResult:
    """Outcome of an Accept-header + publication-version negotiation.

    On success, ``chosen_format`` and ``renderers`` are populated and
    ``error_reason`` is None. On failure, ``renderers`` is empty and
    ``error_reason`` names one of the module-level NEGOTIATION_ERROR_*
    constants so callers can map to HTTP 406 (or similar) with a stable
    diagnostic string.
    """

    renderers: tuple[Renderer, ...]
    chosen_format: str | None
    chosen_media_type: str | None
    error_reason: str | None

    @property
    def is_ok(self) -> bool:
        return self.error_reason is None and bool(self.renderers)


def parse_accept_header(accept: str) -> list[AcceptEntry]:
    """Parse an HTTP Accept header into media types ordered by q-preference.

    Missing or malformed q-values default to 1.0. Entries with q=0 are
    dropped. Ordering is stable within the same quality.
    """
    if not accept or not accept.strip():
        return []
    entries: list[tuple[int, float, str]] = []
    for index, raw in enumerate(accept.split(",")):
        part = raw.strip()
        if not part:
            continue
        segments = [segment.strip() for segment in part.split(";") if segment.strip()]
        media_type = segments[0].lower()
        params = segments[1:]
        quality = 1.0
        kept_params: list[str] = []
        for param in params:
            if param.startswith("q="):
                try:
                    quality = float(param[2:])
                except ValueError:
                    quality = 1.0
            else:
                kept_params.append(param)
        if quality <= 0.0:
            continue
        if kept_params:
            media_type = f"{media_type}; {'; '.join(kept_params)}"
        entries.append((index, quality, media_type))
    entries.sort(key=lambda item: (-item[1], item[0]))
    return [AcceptEntry(media_type=media_type, quality=quality) for _, quality, media_type in entries]


def _match_format(media_type: str) -> str | None:
    if media_type in ("*/*", "application/*"):
        return "json"
    if media_type == "text/*":
        return "csv"
    return MEDIA_TYPE_TO_FORMAT.get(media_type)


def resolve_format_from_accept(accept: str) -> tuple[str | None, str | None]:
    """Return (chosen_format, chosen_media_type) from an Accept header.

    Empty or unrecognised headers return (None, None). Wildcards prefer
    JSON; ``text/*`` prefers CSV. Callers translate a (None, None) result
    into HTTP 406 with the NEGOTIATION_ERROR_NO_ACCEPTABLE_FORMAT reason.
    """
    if not accept or not accept.strip():
        return "json", "application/json"
    for entry in parse_accept_header(accept):
        chosen = _match_format(entry.media_type.split(";")[0].strip())
        if chosen:
            return chosen, entry.media_type
    return None, None
