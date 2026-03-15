import { AppShell } from "@/components/app-shell";
import { getCurrentUser, getMonthlyCashflow, getRuns } from "@/lib/backend";

export default async function DashboardPage() {
  const user = await getCurrentUser();
  const cashflowRows = await getMonthlyCashflow();
  const runs = await getRuns(8);
  const latest = cashflowRows.at(-1);

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
          <div className="eyebrow">Published Reporting</div>
          <h1>Dashboard and control-plane visibility from one API surface.</h1>
          <p className="heroCopy muted">
            The current slice keeps the UI intentionally narrow: recent runs,
            monthly cashflow, and authenticated navigation built entirely on the API.
          </p>
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
                      <td>{run.source_name}</td>
                      <td>{run.file_name}</td>
                      <td>{run.row_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>
    </AppShell>
  );
}
