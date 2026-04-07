"""Export renderer — CSV and JSON output formats.

Implements the Renderer protocol for publication data export.
"""
from __future__ import annotations

import csv
import io
import json

from packages.adapters.contracts import RenderedOutput, RendererManifest

EXPORT_RENDERER_MANIFEST = RendererManifest(
    renderer_key="export_csv_json",
    display_name="Export Renderer — CSV / JSON",
    version="1.0",
    supported_formats=("csv", "json"),
    supported_publication_keys=(),   # empty = all publications
)


class ExportRenderer:
    """Renderer that outputs publication rows as CSV or JSON bytes.

    Conforms to the Renderer protocol from packages.adapters.contracts.
    """

    manifest: RendererManifest = EXPORT_RENDERER_MANIFEST

    def __init__(self, format: str = "json") -> None:
        """Initialize the renderer with a target format.

        Parameters
        ----------
        format : str
            Output format: "csv" or "json". Default is "json".

        Raises
        ------
        ValueError
            If format is not "csv" or "json".
        """
        if format not in ("csv", "json"):
            raise ValueError(f"Unsupported format: {format!r}. Must be 'csv' or 'json'.")
        self._format = format

    def render(self, publication_key: str, rows: list[dict]) -> RenderedOutput:
        """Render rows for the given publication.

        Parameters
        ----------
        publication_key : str
            The publication key (unused for format routing).
        rows : list[dict]
            List of row dictionaries to render.

        Returns
        -------
        RenderedOutput
            Rendered output with format, content bytes, and MIME type.
        """
        if self._format == "csv":
            return self._render_csv(rows)
        return self._render_json(rows)

    def _render_json(self, rows: list[dict]) -> RenderedOutput:
        """Render rows as JSON.

        Parameters
        ----------
        rows : list[dict]
            Rows to render.

        Returns
        -------
        RenderedOutput
            JSON-encoded output.
        """
        content = json.dumps(rows, default=str).encode("utf-8")
        return RenderedOutput(
            format="json",
            content=content,
            content_type="application/json",
        )

    def _render_csv(self, rows: list[dict]) -> RenderedOutput:
        """Render rows as CSV.

        Parameters
        ----------
        rows : list[dict]
            Rows to render.

        Returns
        -------
        RenderedOutput
            CSV-encoded output with header row.
        """
        if not rows:
            return RenderedOutput(
                format="csv",
                content=b"",
                content_type="text/csv",
            )
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        content = buf.getvalue().encode("utf-8")
        return RenderedOutput(
            format="csv",
            content=content,
            content_type="text/csv",
        )
