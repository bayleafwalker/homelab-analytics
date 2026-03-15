import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { getCurrentUser, getRun } from "@/lib/backend";

export default async function RunDetailPage({ params }) {
  const user = await getCurrentUser();
  const run = await getRun(params.runId);

  return (
    <AppShell
      currentPath="/runs"
      user={user}
      title="Run Detail"
      eyebrow="Reader Access"
      lede="Run detail stays API-backed so operators can inspect validation and lineage inputs without exposing warehouse internals in the web workload."
    >
      <section className="stack">
        <div className="buttonRow">
          <Link className="ghostButton" href="/runs">
            Back to runs
          </Link>
        </div>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Run</div>
              <h2>{run.run_id}</h2>
            </div>
            <span className={`statusPill status-${run.status}`}>{run.status}</span>
          </div>
          <div className="metaGrid">
            <div className="metaItem">
              <div className="metricLabel">Source</div>
              <div>{run.source_name}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Dataset</div>
              <div>{run.dataset_name}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">File</div>
              <div>{run.file_name}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Rows</div>
              <div>{run.row_count}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Created</div>
              <div>{run.created_at}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Passed</div>
              <div>{run.passed ? "true" : "false"}</div>
            </div>
            <div className="metaItem spanTwo">
              <div className="metricLabel">Raw path</div>
              <div className="muted">{run.raw_path}</div>
            </div>
            <div className="metaItem spanTwo">
              <div className="metricLabel">Manifest path</div>
              <div className="muted">{run.manifest_path}</div>
            </div>
            <div className="metaItem spanTwo">
              <div className="metricLabel">SHA-256</div>
              <div className="muted">{run.sha256}</div>
            </div>
          </div>
        </article>

        <section className="layout">
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Validation</div>
                <h2>Issues</h2>
              </div>
            </div>
            {run.issues.length === 0 ? (
              <div className="empty">No issues recorded for this run.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Message</th>
                      <th>Column</th>
                      <th>Row</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.issues.map((issue, index) => (
                      <tr key={`${run.run_id}-${index}-${issue.code}`}>
                        <td>{issue.code}</td>
                        <td>{issue.message}</td>
                        <td>{issue.column || "n/a"}</td>
                        <td>{issue.row_number || "n/a"}</td>
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
                <div className="eyebrow">Payload</div>
                <h2>Header</h2>
              </div>
            </div>
            {run.header.length === 0 ? (
              <div className="empty">No header metadata recorded.</div>
            ) : (
              <div className="metaGrid">
                {run.header.map((column) => (
                  <div className="metaItem" key={column}>
                    <div className="metricLabel">Column</div>
                    <div>{column}</div>
                  </div>
                ))}
              </div>
            )}
          </article>
        </section>
      </section>
    </AppShell>
  );
}
