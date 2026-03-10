from __future__ import annotations

from decimal import Decimal
from html import escape

from packages.analytics.cashflow import MonthlyCashflowSummary
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.run_metadata import IngestionRunRecord


def create_app(
    service: AccountTransactionService,
    transformation_service: TransformationService | None = None,
    reporting_service: ReportingService | None = None,
):
    resolved_reporting_service = (
        reporting_service
        or (
            ReportingService(transformation_service)
            if transformation_service is not None
            else None
        )
    )

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "/")
        method = environ.get("REQUEST_METHOD", "GET")

        if method == "GET" and path == "/health":
            body = "ok".encode("utf-8")
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                ],
            )
            return [body]

        if method == "GET" and path == "/":
            runs = service.list_runs()
            summaries = (
                _rows_to_summaries(resolved_reporting_service.get_monthly_cashflow())
                if resolved_reporting_service is not None
                else []
            )
            body = render_dashboard(runs=runs, summaries=summaries).encode("utf-8")
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/html; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                ],
            )
            return [body]

        body = "not found".encode("utf-8")
        start_response(
            "404 Not Found",
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    return app


def render_dashboard(
    runs: list[IngestionRunRecord],
    summaries: list[MonthlyCashflowSummary],
) -> str:
    latest_summary = summaries[-1] if summaries else None
    cards = _render_summary_cards(latest_summary)
    history = _render_summary_history(summaries)
    run_table = _render_run_table(runs[:8])
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Homelab Analytics</title>
    <style>
      :root {{
        --bg: #f4efe6;
        --ink: #1b2b34;
        --muted: #5a6a73;
        --panel: rgba(255, 252, 246, 0.92);
        --accent: #0f766e;
        --accent-2: #e07a5f;
        --line: rgba(27, 43, 52, 0.12);
        --ok: #2a9d8f;
        --bad: #d1495b;
        --shadow: 0 20px 60px rgba(27, 43, 52, 0.12);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "Avenir Next", "Trebuchet MS", "Segoe UI", sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(224, 122, 95, 0.18), transparent 34%),
          radial-gradient(circle at top right, rgba(15, 118, 110, 0.18), transparent 28%),
          linear-gradient(180deg, #f7f2ea, var(--bg));
      }}
      .page {{
        max-width: 1180px;
        margin: 0 auto;
        padding: 32px 20px 60px;
      }}
      .hero {{
        display: grid;
        grid-template-columns: 1.2fr 0.8fr;
        gap: 20px;
        align-items: end;
        margin-bottom: 24px;
      }}
      .hero-card, .panel {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 24px;
        box-shadow: var(--shadow);
      }}
      .hero-card {{
        padding: 28px;
      }}
      .eyebrow {{
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--accent);
        font-size: 0.74rem;
        font-weight: 700;
      }}
      h1, h2 {{
        font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
        margin: 0;
      }}
      h1 {{
        font-size: clamp(2.5rem, 5vw, 4.6rem);
        line-height: 0.98;
        margin-top: 12px;
        max-width: 10ch;
      }}
      .lede {{
        max-width: 56ch;
        color: var(--muted);
        line-height: 1.55;
        margin-top: 14px;
      }}
      .hero-metric {{
        padding: 24px;
        display: grid;
        gap: 10px;
      }}
      .hero-metric .value {{
        font-size: clamp(2rem, 4vw, 3rem);
        font-weight: 800;
      }}
      .grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 16px;
        margin-bottom: 24px;
      }}
      .panel {{
        padding: 20px;
      }}
      .metric {{
        font-size: 0.88rem;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}
      .value {{
        margin-top: 8px;
        font-size: 2rem;
        font-weight: 700;
      }}
      .layout {{
        display: grid;
        grid-template-columns: 1.1fr 0.9fr;
        gap: 18px;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
      }}
      th, td {{
        text-align: left;
        padding: 12px 0;
        border-bottom: 1px solid var(--line);
        vertical-align: top;
      }}
      th {{
        font-size: 0.76rem;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}
      .status {{
        display: inline-flex;
        align-items: center;
        padding: 0.18rem 0.58rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: lowercase;
      }}
      .status.landed {{
        background: rgba(42, 157, 143, 0.14);
        color: var(--ok);
      }}
      .status.rejected {{
        background: rgba(209, 73, 91, 0.12);
        color: var(--bad);
      }}
      .muted {{
        color: var(--muted);
      }}
      .empty {{
        padding: 18px 0 8px;
        color: var(--muted);
      }}
      .issue {{
        color: var(--bad);
        font-size: 0.82rem;
        margin-top: 6px;
      }}
      @media (max-width: 900px) {{
        .hero, .grid, .layout {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="page">
      <section class="hero">
        <article class="hero-card">
          <div class="eyebrow">Household + Homelab Reporting</div>
          <h1>Homelab Analytics</h1>
          <p class="lede">
            A compact reporting surface over the current account transaction model.
            It tracks ingestion runs, highlights the latest successful cash-flow picture,
            and keeps failed imports visible instead of hiding them downstream.
          </p>
        </article>
        <aside class="hero-card hero-metric">
          <div class="eyebrow">Latest Net</div>
          <div class="value">{escape(str(latest_summary.net)) if latest_summary else "No successful imports yet."}</div>
          <div class="muted">
            {escape(latest_summary.booking_month) if latest_summary else "Import a valid account transaction CSV to populate the dashboard."}
          </div>
        </aside>
      </section>
      <section class="grid">
        {cards}
      </section>
      <section class="layout">
        <article class="panel">
          <div class="eyebrow">Cash Flow</div>
          <h2>Monthly history</h2>
          {history}
        </article>
        <article class="panel">
          <div class="eyebrow">Pipeline State</div>
          <h2>Recent ingestion runs</h2>
          {run_table}
        </article>
      </section>
    </main>
  </body>
</html>"""


def _rows_to_summaries(rows: list[dict[str, object]]) -> list[MonthlyCashflowSummary]:
    return [
        MonthlyCashflowSummary(
            booking_month=str(row["booking_month"]),
            income=_coerce_decimal(row["income"]),
            expense=_coerce_decimal(row["expense"]),
            net=_coerce_decimal(row["net"]),
            transaction_count=_coerce_int(row["transaction_count"]),
        )
        for row in rows
    ]


def _coerce_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _coerce_int(value: object) -> int:
    if isinstance(value, int):
        return value
    return int(str(value))


def _render_summary_cards(summary: MonthlyCashflowSummary | None) -> str:
    if summary is None:
        return "".join(
            [
                _render_card("Income", "No data"),
                _render_card("Expense", "No data"),
                _render_card("Net", "No data"),
            ]
        )

    return "".join(
        [
            _render_card("Income", str(summary.income)),
            _render_card("Expense", str(summary.expense)),
            _render_card("Net", str(summary.net)),
        ]
    )


def _render_card(label: str, value: str) -> str:
    return f"""
    <article class="panel">
      <div class="metric">{escape(label)}</div>
      <div class="value">{escape(value)}</div>
    </article>
    """


def _render_summary_history(summaries: list[MonthlyCashflowSummary]) -> str:
    if not summaries:
        return '<div class="empty">No successful imports yet.</div>'

    rows = "".join(
        f"""
        <tr>
          <td>{escape(summary.booking_month)}</td>
          <td>{escape(str(summary.income))}</td>
          <td>{escape(str(summary.expense))}</td>
          <td>{escape(str(summary.net))}</td>
          <td>{summary.transaction_count}</td>
        </tr>
        """
        for summary in summaries
    )
    return f"""
    <table>
      <thead>
        <tr>
          <th>Month</th>
          <th>Income</th>
          <th>Expense</th>
          <th>Net</th>
          <th>Rows</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """


def _render_run_table(runs: list[IngestionRunRecord]) -> str:
    if not runs:
        return '<div class="empty">No ingestion runs recorded yet.</div>'

    rows = "".join(_render_run_row(run) for run in runs)
    return f"""
    <table>
      <thead>
        <tr>
          <th>Status</th>
          <th>Source</th>
          <th>File</th>
          <th>Rows</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """


def _render_run_row(run: IngestionRunRecord) -> str:
    issues = "".join(
        f'<div class="issue">{escape(issue.code)}: {escape(issue.message)}</div>'
        for issue in run.issues[:2]
    )
    return f"""
    <tr>
      <td><span class="status {escape(run.status.value)}">{escape(run.status.value)}</span>{issues}</td>
      <td>{escape(run.source_name)}</td>
      <td>{escape(run.file_name)}</td>
      <td>{run.row_count}</td>
    </tr>
    """
