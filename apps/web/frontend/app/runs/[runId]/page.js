import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { ONBOARDING_SOURCES } from "@/lib/onboarding-sources";
import {
  getCurrentUser,
  getPublicationAudit,
  getRun,
  getSourceLineage,
  getTransformationAudit
} from "@/lib/backend";

const DATASET_UPLOAD_PATH = Object.fromEntries(
  ONBOARDING_SOURCES.map((s) => [s.dataset, s.uploadPath])
);

function noticeCopy(notice) {
  switch (notice) {
    case "upload-created":
      return "Upload received. Review validation, lineage, and source remediation below.";
    case "retry-created":
      return "Retry landed successfully. Review the new run context and source freshness signals below.";
    default:
      return "";
  }
}

function errorCopy(error) {
  switch (error) {
    case "retry-failed":
      return "Could not retry this run. Check the saved binding context and source freshness state.";
    default:
      return "";
  }
}

function contextEntries(context) {
  if (!context) {
    return [];
  }
  return Object.entries(context).filter(([, value]) => Boolean(value));
}

export default async function RunDetailPage({ params, searchParams }) {
  const user = await getCurrentUser();
  const runId = params.runId;
  const [run, sourceLineage, publicationAudit, transformationAudit] = await Promise.all([
    getRun(runId),
    getSourceLineage({ runId }),
    getPublicationAudit({ runId }),
    getTransformationAudit(runId)
  ]);
  const transformationAuditColumns =
    transformationAudit.length > 0 ? Object.keys(transformationAudit[0]) : [];
  const notice = noticeCopy(searchParams?.notice);
  const error = errorCopy(searchParams?.error);
  const contextRows = contextEntries(run.context);
  const retrySupported = Boolean(run.recovery?.retry_supported);
  const canRetry = retrySupported && user.role !== "reader";
  const runFailed = run.status === "rejected" || run.status === "failed";
  const uploadPath = runFailed && run.dataset_name ? DATASET_UPLOAD_PATH[run.dataset_name] : null;

  return (
    <AppShell
      currentPath="/runs"
      user={user}
      title="Run Detail"
      eyebrow="Reader Access"
      lede="Run detail stays API-backed so operators can inspect validation, transformation lineage, and retry context. Source freshness remediation belongs on /sources, while publication trust stays in reporting surfaces."
    >
      <section className="stack">
        {notice ? <div className="successBanner">{notice}</div> : null}
        {error ? <div className="errorBanner">{error}</div> : null}
        <div className="buttonRow">
          <Link className="ghostButton" href="/runs">
            Back to runs
          </Link>
          {canRetry ? (
            <form action={`/runs/${run.run_id}/retry`} method="post">
              <button className="primaryButton inlineButton" type="submit">
                Retry run
              </button>
            </form>
          ) : null}
          {uploadPath ? (
            <Link className={canRetry ? "ghostButton" : "primaryButton"} href={uploadPath}>
              Upload corrected file
            </Link>
          ) : null}
          {runFailed ? (
            <Link className="ghostButton" href="/sources">
              Source remediation
            </Link>
          ) : null}
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
            <div className="metaItem spanTwo">
              <div className="metricLabel">Recovery</div>
              <div className="muted">
                {retrySupported
                  ? `Retry supported via ${run.recovery.retry_kind}.`
                  : run.recovery?.reason || "Retry metadata is not available for this run."}
              </div>
            </div>
          </div>
        </article>

        <section className="layout">
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Control Plane</div>
                <h2>Saved run context</h2>
              </div>
            </div>
            {contextRows.length === 0 ? (
              <div className="empty">No control-plane binding context was recorded for this run.</div>
            ) : (
              <div className="metaGrid">
                {contextRows.map(([key, value]) => (
                  <div className="metaItem" key={key}>
                    <div className="metricLabel">{key.replaceAll("_", " ")}</div>
                    <div>{value}</div>
                  </div>
                ))}
              </div>
            )}
          </article>

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
        </section>

        <section className="layout">
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

          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Transformation</div>
                <h2>Lineage</h2>
              </div>
            </div>
            {sourceLineage.length === 0 ? (
              <div className="empty">No lineage recorded for this run yet.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Target</th>
                      <th>Layer</th>
                      <th>Kind</th>
                      <th>Rows</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sourceLineage.map((record) => (
                      <tr key={record.lineage_id}>
                        <td>{record.target_name}</td>
                        <td>{record.target_layer}</td>
                        <td>{record.target_kind}</td>
                        <td>{record.row_count || "n/a"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </article>
        </section>

        <section className="layout">
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Transformation</div>
                <h2>Audit</h2>
              </div>
            </div>
            {transformationAudit.length === 0 ? (
              <div className="empty">No transformation audit rows recorded for this run.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      {transformationAuditColumns.map((column) => (
                        <th key={column}>{column.replaceAll("_", " ")}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {transformationAudit.map((record, index) => (
                      <tr key={`${record.input_run_id || run.run_id}-${index}`}>
                        {transformationAuditColumns.map((column) => (
                          <td key={`${column}-${index}`}>{record[column] ?? "n/a"}</td>
                        ))}
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
                <div className="eyebrow">Publication</div>
                <h2>Published relations</h2>
              </div>
            </div>
            {publicationAudit.length === 0 ? (
              <div className="empty">No publication audit rows recorded for this run.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Publication</th>
                      <th>Relation</th>
                      <th>Status</th>
                      <th>Published at</th>
                    </tr>
                  </thead>
                  <tbody>
                    {publicationAudit.map((record) => (
                      <tr key={record.publication_audit_id}>
                        <td>{record.publication_key}</td>
                        <td>{record.relation_name}</td>
                        <td>{record.status}</td>
                        <td>{record.published_at}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </article>
        </section>
      </section>
    </AppShell>
  );
}
