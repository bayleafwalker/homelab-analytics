import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { SparklineChart } from "@/components/sparkline-chart";
import {
  getAttentionItems,
  getCurrentUser,
  getHouseholdOverview,
  getMonthlyCashflow,
  getRecentChanges,
  getRuns,
} from "@/lib/backend";

export default async function DashboardPage() {
  const user = await getCurrentUser();
  const [cashflowRows, runs, overview, attentionItems, recentChanges] =
    await Promise.all([
      getMonthlyCashflow(),
      getRuns(8),
      getHouseholdOverview(),
      getAttentionItems(),
      getRecentChanges(),
    ]);
  const latest = cashflowRows.at(-1);

  const trendLabels = cashflowRows.slice(-12).map((r) => r.booking_month);
  const trendSeries = [
    {
      label: "Income",
      color: "var(--ok)",
      values: cashflowRows.slice(-12).map((r) => Number(r.income)),
    },
    {
      label: "Expense",
      color: "var(--warn)",
      values: cashflowRows.slice(-12).map((r) => Number(r.expense)),
    },
    {
      label: "Net",
      color: "var(--accent)",
      values: cashflowRows.slice(-12).map((r) => Number(r.net)),
    },
  ];

  return (
    <AppShell
      currentPath="/"
      user={user}
      title="Homelab Analytics"
      eyebrow="API-Backed Dashboard"
      lede="A minimal Next.js shell over the reporting and run APIs. The web workload no longer computes or reads reporting data directly."
    >
      <section className="hero">
        <article className="panel heroCard">
          <div className="eyebrow">Household Overview</div>
          {overview ? (
            <>
              <h1>
                {overview.net != null
                  ? `Net ${overview.net}`
                  : "Dashboard and control-plane visibility from one API surface."}
              </h1>
              <div className="heroCopy muted">
                {overview.income != null && (
                  <span>Income: {overview.income} &nbsp;·&nbsp; </span>
                )}
                {overview.expense != null && (
                  <span>Expense: {overview.expense}</span>
                )}
              </div>
            </>
          ) : (
            <>
              <h1>Dashboard and control-plane visibility from one API surface.</h1>
              <p className="heroCopy muted">
                The current slice keeps the UI intentionally narrow: recent runs,
                monthly cashflow, and authenticated navigation built entirely on the API.
              </p>
            </>
          )}
        </article>
        <aside className="panel heroMetric">
          <div className="eyebrow">Latest Net</div>
          <div className="value">{latest ? latest.net : "No successful imports yet."}</div>
          <div className="muted">
            {latest
              ? `${latest.booking_month} / ${latest.transaction_count} rows`
              : "Import a valid dataset to populate the reporting layer."}
          </div>
        </aside>
      </section>

      <section className="cards">
        <article className="panel metricCard">
          <div className="metricLabel">Income</div>
          <div className="metricValue">{latest ? latest.income : "No data"}</div>
        </article>
        <article className="panel metricCard">
          <div className="metricLabel">Expense</div>
          <div className="metricValue">{latest ? latest.expense : "No data"}</div>
        </article>
        <article className="panel metricCard">
          <div className="metricLabel">Net</div>
          <div className="metricValue">{latest ? latest.net : "No data"}</div>
        </article>
      </section>

      {cashflowRows.length > 0 && (
        <article className="panel section" style={{ marginBottom: "24px" }}>
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Trend</div>
              <h2>Cashflow — last 12 months</h2>
            </div>
          </div>
          <SparklineChart series={trendSeries} labels={trendLabels} height={120} width={600} />
        </article>
      )}

      <section className="layout">
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Reporting</div>
              <h2>Monthly cashflow</h2>
            </div>
          </div>
          {cashflowRows.length === 0 ? (
            <div className="empty">No successful imports yet.</div>
          ) : (
            <div className="tableWrap">
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
                <tbody>
                  {cashflowRows.map((row) => (
                    <tr key={row.booking_month}>
                      <td>{row.booking_month}</td>
                      <td>{row.income}</td>
                      <td>{row.expense}</td>
                      <td>{row.net}</td>
                      <td>{row.transaction_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        <div className="stack">
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Attention</div>
                <h2>Items to review</h2>
              </div>
              <Link className="inlineLink" href="/review">See all →</Link>
            </div>
            {attentionItems.length === 0 ? (
              <div className="empty">Nothing requires attention.</div>
            ) : (
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "10px" }}>
                {attentionItems
                  .sort((a, b) => (a.severity ?? 9) - (b.severity ?? 9))
                  .map((item, i) => (
                    <li key={i} style={{ display: "flex", gap: "8px", alignItems: "flex-start" }}>
                      {item.severity === 1 && (
                        <span className="statusPill status-failed">warn</span>
                      )}
                      <div>
                        <div style={{ fontWeight: 700 }}>{item.title}</div>
                        {item.source_domain && (
                          <div className="muted" style={{ fontSize: "0.82rem" }}>
                            {item.source_domain}
                          </div>
                        )}
                      </div>
                    </li>
                  ))}
              </ul>
            )}
          </article>

          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Activity</div>
                <h2>Recent changes</h2>
              </div>
            </div>
            {recentChanges.length === 0 ? (
              <div className="empty">No recent changes recorded.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Metric</th>
                      <th>Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentChanges.map((row, i) => (
                      <tr key={i}>
                        <td>
                          <span className="statusPill status-enqueued">{row.change_type}</span>
                        </td>
                        <td>{row.metric_name}</td>
                        <td>
                          {row.direction === "up" ? "▲" : "▼"}{" "}
                          {row.current_value}
                          {row.previous_value != null && (
                            <span className="muted"> / {row.previous_value}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </article>

          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Pipeline State</div>
                <h2>Recent runs</h2>
              </div>
            </div>
            {runs.length === 0 ? (
              <div className="empty">No ingestion runs recorded yet.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Source</th>
                      <th>File</th>
                      <th>Rows</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <tr key={run.run_id}>
                        <td>
                          <span className={`statusPill status-${run.status}`}>{run.status}</span>
                          {(run.issues || []).slice(0, 2).map((issue) => (
                            <div className="issue" key={`${run.run_id}-${issue.code}-${issue.message}`}>
                              {issue.code}: {issue.message}
                            </div>
                          ))}
                        </td>
                        <td>
                          <Link className="inlineLink" href={`/runs/${run.run_id}`}>
                            {run.source_name}
                          </Link>
                        </td>
                        <td>{run.file_name}</td>
                        <td>{run.row_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </article>
        </div>
      </section>
    </AppShell>
  );
}
