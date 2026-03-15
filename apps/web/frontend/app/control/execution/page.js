import Link from "next/link";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ControlNav } from "@/components/control-nav";
import {
  getCurrentUser,
  getExecutionSchedules,
  getIngestionDefinitions,
  getPublicationAudit,
  getScheduleDispatches,
  getSourceAssets,
  getSourceLineage
} from "@/lib/backend";

function noticeCopy(notice) {
  switch (notice) {
    case "ingestion-definition-created":
      return "Ingestion definition created.";
    case "execution-schedule-created":
      return "Execution schedule created.";
    default:
      return "";
  }
}

function errorCopy(error) {
  switch (error) {
    case "ingestion-definition-failed":
      return "Could not create the ingestion definition.";
    case "execution-schedule-failed":
      return "Could not create the execution schedule.";
    case "ingestion-process-failed":
      return "Could not process the ingestion definition.";
    default:
      return "";
  }
}

export default async function ControlExecutionPage({ searchParams }) {
  const user = await getCurrentUser();
  if (user.role !== "admin") {
    redirect("/");
  }

  const [
    sourceAssets,
    ingestionDefinitions,
    executionSchedules,
    sourceLineage,
    publicationAudit,
    scheduleDispatches
  ] = await Promise.all([
    getSourceAssets(),
    getIngestionDefinitions(),
    getExecutionSchedules(),
    getSourceLineage(),
    getPublicationAudit(),
    getScheduleDispatches()
  ]);
  const notice = noticeCopy(searchParams?.notice);
  const error = errorCopy(searchParams?.error);

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title="Execution Control"
      eyebrow="Admin Access"
      lede="Manage configured ingestion, define execution schedules, and inspect the control-plane outputs that connect ingestion to transformation and publication."
    >
      <section className="stack">
        <ControlNav currentPath="/control/execution" />
        {notice ? <div className="successBanner">{notice}</div> : null}
        {error ? <div className="errorBanner">{error}</div> : null}

        <section className="cards">
          <article className="panel metricCard">
            <div className="metricLabel">Ingestion definitions</div>
            <div className="metricValue">{ingestionDefinitions.length}</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Execution schedules</div>
            <div className="metricValue">{executionSchedules.length}</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Queued history</div>
            <div className="metricValue">{scheduleDispatches.length}</div>
          </article>
        </section>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Configured Ingestion</div>
              <h2>Create ingestion definition</h2>
            </div>
          </div>
          {sourceAssets.length === 0 ? (
            <div className="empty">Create a source asset before defining ingestion.</div>
          ) : (
            <form
              className="formGrid fourCol"
              action="/control/execution/ingestion-definitions"
              method="post"
            >
              <div className="field">
                <label htmlFor="ingestion-definition-id">Definition id</label>
                <input id="ingestion-definition-id" name="ingestion_definition_id" type="text" required />
              </div>
              <div className="field">
                <label htmlFor="source-asset-select">Source asset</label>
                <select id="source-asset-select" name="source_asset_id" required defaultValue="">
                  <option value="" disabled>
                    Select source asset
                  </option>
                  {sourceAssets.map((record) => (
                    <option key={record.source_asset_id} value={record.source_asset_id}>
                      {record.source_asset_id}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="ingestion-transport">Transport</label>
                <input
                  id="ingestion-transport"
                  name="transport"
                  type="text"
                  defaultValue="filesystem"
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="ingestion-schedule-mode">Schedule mode</label>
                <input
                  id="ingestion-schedule-mode"
                  name="schedule_mode"
                  type="text"
                  defaultValue="watch-folder"
                  required
                />
              </div>
              <div className="field spanTwo">
                <label htmlFor="ingestion-source-path">Source path</label>
                <input id="ingestion-source-path" name="source_path" type="text" required />
              </div>
              <div className="field">
                <label htmlFor="ingestion-file-pattern">File pattern</label>
                <input
                  id="ingestion-file-pattern"
                  name="file_pattern"
                  type="text"
                  defaultValue="*.csv"
                />
              </div>
              <div className="field">
                <label htmlFor="ingestion-poll-interval">Poll interval</label>
                <input
                  id="ingestion-poll-interval"
                  name="poll_interval_seconds"
                  type="number"
                  defaultValue="30"
                  min="1"
                />
              </div>
              <div className="field spanTwo">
                <label htmlFor="ingestion-processed-path">Processed path</label>
                <input id="ingestion-processed-path" name="processed_path" type="text" />
              </div>
              <div className="field spanTwo">
                <label htmlFor="ingestion-failed-path">Failed path</label>
                <input id="ingestion-failed-path" name="failed_path" type="text" />
              </div>
              <div className="field">
                <label htmlFor="ingestion-source-name">Source name</label>
                <input
                  id="ingestion-source-name"
                  name="source_name"
                  type="text"
                  defaultValue="configured-ingestion"
                />
              </div>
              <div className="field">
                <label htmlFor="ingestion-enabled">Enabled</label>
                <select id="ingestion-enabled" name="enabled" defaultValue="true">
                  <option value="true">enabled</option>
                  <option value="false">disabled</option>
                </select>
              </div>
              <button className="primaryButton inlineButton" type="submit">
                Create ingestion definition
              </button>
            </form>
          )}
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Scheduler</div>
              <h2>Create execution schedule</h2>
            </div>
          </div>
          {ingestionDefinitions.length === 0 ? (
            <div className="empty">Create an ingestion definition before scheduling it.</div>
          ) : (
            <form
              className="formGrid fourCol"
              action="/control/execution/execution-schedules"
              method="post"
            >
              <div className="field">
                <label htmlFor="schedule-id">Schedule id</label>
                <input id="schedule-id" name="schedule_id" type="text" required />
              </div>
              <div className="field">
                <label htmlFor="schedule-target-kind">Target kind</label>
                <input
                  id="schedule-target-kind"
                  name="target_kind"
                  type="text"
                  defaultValue="ingestion_definition"
                  required
                />
              </div>
              <div className="field spanTwo">
                <label htmlFor="schedule-target-ref">Target ref</label>
                <select id="schedule-target-ref" name="target_ref" required defaultValue="">
                  <option value="" disabled>
                    Select ingestion definition
                  </option>
                  {ingestionDefinitions.map((record) => (
                    <option
                      key={record.ingestion_definition_id}
                      value={record.ingestion_definition_id}
                    >
                      {record.ingestion_definition_id}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="schedule-cron-expression">Cron expression</label>
                <input
                  id="schedule-cron-expression"
                  name="cron_expression"
                  type="text"
                  defaultValue="*/5 * * * *"
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="schedule-timezone">Timezone</label>
                <input id="schedule-timezone" name="timezone" type="text" defaultValue="UTC" />
              </div>
              <div className="field">
                <label htmlFor="schedule-max-concurrency">Max concurrency</label>
                <input
                  id="schedule-max-concurrency"
                  name="max_concurrency"
                  type="number"
                  defaultValue="1"
                  min="1"
                />
              </div>
              <div className="field">
                <label htmlFor="schedule-enabled">Enabled</label>
                <select id="schedule-enabled" name="enabled" defaultValue="true">
                  <option value="true">enabled</option>
                  <option value="false">disabled</option>
                </select>
              </div>
              <button className="primaryButton inlineButton" type="submit">
                Create execution schedule
              </button>
            </form>
          )}
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Configured Ingestion</div>
              <h2>Definitions and run-now actions</h2>
            </div>
          </div>
          {ingestionDefinitions.length === 0 ? (
            <div className="empty">No ingestion definitions configured yet.</div>
          ) : (
            <div className="stack">
              {ingestionDefinitions.map((record) => (
                <section className="adminCard" key={record.ingestion_definition_id}>
                  <div className="adminCardHeader">
                    <div>
                      <div className="metricLabel">{record.ingestion_definition_id}</div>
                      <div className="muted">
                        {record.source_asset_id} / {record.transport} / {record.schedule_mode}
                      </div>
                    </div>
                    <span className="userBadge">
                      {record.enabled ? "enabled" : "disabled"}
                    </span>
                  </div>
                  <div className="metaGrid">
                    <div className="metaItem">
                      <div>Source path</div>
                      <div className="muted">{record.source_path || "n/a"}</div>
                    </div>
                    <div className="metaItem">
                      <div>Processed path</div>
                      <div className="muted">{record.processed_path || "n/a"}</div>
                    </div>
                    <div className="metaItem">
                      <div>Failed path</div>
                      <div className="muted">{record.failed_path || "n/a"}</div>
                    </div>
                    <div className="metaItem">
                      <div>Poll interval</div>
                      <div className="muted">{record.poll_interval_seconds || "n/a"}</div>
                    </div>
                  </div>
                  <div className="buttonRow">
                    <form
                      action={`/control/execution/ingestion-definitions/${record.ingestion_definition_id}/process`}
                      method="post"
                    >
                      <button className="primaryButton" type="submit">
                        Process now
                      </button>
                    </form>
                  </div>
                </section>
              ))}
            </div>
          )}
        </article>

        <section className="layout">
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Scheduler</div>
                <h2>Execution schedules</h2>
              </div>
            </div>
            {executionSchedules.length === 0 ? (
              <div className="empty">No execution schedules configured yet.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Id</th>
                      <th>Target</th>
                      <th>Cron</th>
                      <th>Next due</th>
                      <th>Last enqueued</th>
                    </tr>
                  </thead>
                  <tbody>
                    {executionSchedules.map((record) => (
                      <tr key={record.schedule_id}>
                        <td>{record.schedule_id}</td>
                        <td>{record.target_ref}</td>
                        <td>{record.cron_expression}</td>
                        <td>{record.next_due_at || "n/a"}</td>
                        <td>{record.last_enqueued_at || "n/a"}</td>
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
                <div className="eyebrow">Queue</div>
                <h2>Schedule dispatches</h2>
              </div>
            </div>
            {scheduleDispatches.length === 0 ? (
              <div className="empty">No schedule dispatches recorded yet.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Dispatch</th>
                      <th>Schedule</th>
                      <th>Status</th>
                      <th>Enqueued</th>
                      <th>Completed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scheduleDispatches.map((record) => (
                      <tr key={record.dispatch_id}>
                        <td>{record.dispatch_id}</td>
                        <td>{record.schedule_id}</td>
                        <td>
                          <span className={`statusPill status-${record.status}`}>{record.status}</span>
                        </td>
                        <td>{record.enqueued_at}</td>
                        <td>{record.completed_at || "n/a"}</td>
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
                <div className="eyebrow">Lineage</div>
                <h2>Source lineage</h2>
              </div>
            </div>
            {sourceLineage.length === 0 ? (
              <div className="empty">No lineage recorded yet.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Input run</th>
                      <th>Target</th>
                      <th>Layer</th>
                      <th>Rows</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sourceLineage.map((record) => (
                      <tr key={record.lineage_id}>
                        <td>
                          {record.input_run_id ? (
                            <Link className="inlineLink" href={`/runs/${record.input_run_id}`}>
                              {record.input_run_id}
                            </Link>
                          ) : (
                            "n/a"
                          )}
                        </td>
                        <td>{record.target_name}</td>
                        <td>{record.target_layer}</td>
                        <td>{record.row_count || "n/a"}</td>
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
                <h2>Publication audit</h2>
              </div>
            </div>
            {publicationAudit.length === 0 ? (
              <div className="empty">No publication audit records yet.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Run</th>
                      <th>Publication</th>
                      <th>Relation</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {publicationAudit.map((record) => (
                      <tr key={record.publication_audit_id}>
                        <td>
                          {record.run_id ? (
                            <Link className="inlineLink" href={`/runs/${record.run_id}`}>
                              {record.run_id}
                            </Link>
                          ) : (
                            "n/a"
                          )}
                        </td>
                        <td>{record.publication_key}</td>
                        <td>{record.relation_name}</td>
                        <td>{record.status}</td>
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
