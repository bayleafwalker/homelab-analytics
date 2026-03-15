import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { getCurrentUser, getRunsPage } from "@/lib/backend";

export default async function RunsPage({ searchParams }) {
  const user = await getCurrentUser();
  const dataset = searchParams?.dataset || "";
  const status = searchParams?.status || "";
  const fromDate = searchParams?.from_date || "";
  const toDate = searchParams?.to_date || "";
  const limit = Number.parseInt(String(searchParams?.limit || "50"), 10) || 50;
  const payload = await getRunsPage({
    dataset,
    status,
    fromDate,
    toDate,
    limit
  });
  const runs = payload.runs || [];
  const pagination = payload.pagination || { total: runs.length, limit, offset: 0 };

  return (
    <AppShell
      currentPath="/runs"
      user={user}
      title="Ingestion Runs"
      eyebrow="Reader Access"
      lede="Run visibility comes from the API only, with filterable history and drill-downs into validation, lineage, and publication records."
    >
      <section className="stack">
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Operational History</div>
              <h2>Filter runs</h2>
            </div>
          </div>
          <form className="formGrid fourCol" method="get">
            <div className="field">
              <label htmlFor="runs-dataset">Dataset</label>
              <input id="runs-dataset" name="dataset" type="text" defaultValue={dataset} />
            </div>
            <div className="field">
              <label htmlFor="runs-status">Status</label>
              <select id="runs-status" name="status" defaultValue={status}>
                <option value="">All</option>
                <option value="received">received</option>
                <option value="landed">landed</option>
                <option value="rejected">rejected</option>
                <option value="failed">failed</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="runs-from">From</label>
              <input id="runs-from" name="from_date" type="datetime-local" defaultValue={fromDate} />
            </div>
            <div className="field">
              <label htmlFor="runs-to">To</label>
              <input id="runs-to" name="to_date" type="datetime-local" defaultValue={toDate} />
            </div>
            <div className="field">
              <label htmlFor="runs-limit">Limit</label>
              <input id="runs-limit" name="limit" type="number" defaultValue={limit} min="1" max="250" />
            </div>
            <div className="buttonRow spanThree">
              <button className="primaryButton inlineButton" type="submit">
                Apply filters
              </button>
              <Link className="ghostButton" href="/runs">
                Clear filters
              </Link>
            </div>
          </form>
          <div className="muted">
            Showing {runs.length} of {pagination.total} total runs.
          </div>
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Operational History</div>
              <h2>Recent runs</h2>
            </div>
          </div>
          {runs.length === 0 ? (
            <div className="empty">No runs matched the current filters.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Created</th>
                    <th>Status</th>
                    <th>Source</th>
                    <th>Dataset</th>
                    <th>File</th>
                    <th>Rows</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.run_id}>
                      <td>
                        <Link className="inlineLink" href={`/runs/${run.run_id}`}>
                          {run.created_at}
                        </Link>
                      </td>
                      <td>
                        <span className={`statusPill status-${run.status}`}>{run.status}</span>
                      </td>
                      <td>{run.source_name}</td>
                      <td>{run.dataset_name}</td>
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
