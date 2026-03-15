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
    case "ingestion-definition-updated":
      return "Ingestion definition updated.";
    case "execution-schedule-created":
      return "Execution schedule created.";
    case "execution-schedule-updated":
      return "Execution schedule updated.";
    case "schedule-dispatch-created":
      return "Manual schedule dispatch enqueued.";
    case "due-dispatches-enqueued":
      return "Due schedules enqueued.";
    default:
      return "";
  }
}

function errorCopy(error) {
  switch (error) {
    case "ingestion-definition-failed":
      return "Could not create the ingestion definition.";
    case "ingestion-definition-update-failed":
      return "Could not update the ingestion definition.";
    case "execution-schedule-failed":
      return "Could not create the execution schedule.";
    case "execution-schedule-update-failed":
      return "Could not update the execution schedule.";
    case "ingestion-process-failed":
      return "Could not process the ingestion definition.";
    case "schedule-dispatch-failed":
      return "Could not enqueue the schedule dispatch.";
    default:
      return "";
  }
}

function statusCopy(enabled) {
  return enabled ? "active" : "inactive";
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
  const activeSourceAssets = sourceAssets.filter((record) => record.enabled);
  const notice = noticeCopy(searchParams?.notice);
  const error = errorCopy(searchParams?.error);
  const enqueuedDispatches = scheduleDispatches.filter((record) => record.status === "enqueued");

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title="Execution Control"
      eyebrow="Admin Access"
      lede="Keep ingestion definitions, schedules, and queue state in one place while using control-plane lineage and publication records to diagnose what each run produced."
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
            <div className="metricLabel">Queued dispatches</div>
            <div className="metricValue">{enqueuedDispatches.length}</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Publication records</div>
            <div className="metricValue">{publicationAudit.length}</div>
          </article>
        </section>

        <section className="layout">
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Configured Ingestion</div>
                <h2>Create ingestion definition</h2>
              </div>
            </div>
            {activeSourceAssets.length === 0 ? (
              <div className="empty">Create an active source asset before defining ingestion.</div>
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
                    {activeSourceAssets.map((record) => (
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
                  <label htmlFor="ingestion-enabled">Status</label>
                  <select id="ingestion-enabled" name="enabled" defaultValue="true">
                    <option value="true">active</option>
                    <option value="false">inactive</option>
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
                <h2>Queue and create schedules</h2>
              </div>
            </div>
            <div className="stack">
              <form
                className="formGrid threeCol"
                action="/control/execution/schedule-dispatches"
                method="post"
              >
                <div className="field">
                  <label htmlFor="enqueue-limit">Enqueue due limit</label>
                  <input id="enqueue-limit" name="limit" type="number" defaultValue="10" min="1" />
                </div>
                <div className="field spanTwo">
                  <label>Scheduler action</label>
                  <div className="muted">
                    Queue due schedules only. Worker execution still consumes the dispatch queue.
                  </div>
                </div>
                <button className="primaryButton inlineButton" type="submit">
                  Enqueue due schedules
                </button>
              </form>

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
                    <label htmlFor="schedule-enabled">Status</label>
                    <select id="schedule-enabled" name="enabled" defaultValue="true">
                      <option value="true">active</option>
                      <option value="false">inactive</option>
                    </select>
                  </div>
                  <button className="primaryButton inlineButton" type="submit">
                    Create execution schedule
                  </button>
                </form>
              )}
            </div>
          </article>
        </section>

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
            <div className="entityList">
              {ingestionDefinitions.map((record) => (
                <article className="entityCard" key={record.ingestion_definition_id}>
                  <div className="entityHeader">
                    <div>
                      <div className="metricLabel">{record.ingestion_definition_id}</div>
                      <h3>{record.source_asset_id}</h3>
                    </div>
                    <span className={`statusPill status-${statusCopy(record.enabled)}`}>
                      {statusCopy(record.enabled)}
                    </span>
                  </div>
                  <div className="metaGrid">
                    <div className="metaItem">
                      <div className="metricLabel">Transport</div>
                      <div>{record.transport}</div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Schedule mode</div>
                      <div>{record.schedule_mode}</div>
                    </div>
                    <div className="metaItem spanTwo">
                      <div className="metricLabel">Source path</div>
                      <div className="muted">{record.source_path || "n/a"}</div>
                    </div>
                  </div>
                  <form
                    className="formGrid fourCol"
                    action={`/control/execution/ingestion-definitions/${record.ingestion_definition_id}`}
                    method="post"
                  >
                    <input
                      name="ingestion_definition_id"
                      type="hidden"
                      value={record.ingestion_definition_id}
                    />
                    <div className="field">
                      <label htmlFor={`definition-source-asset-${record.ingestion_definition_id}`}>
                        Source asset
                      </label>
                      <select
                        id={`definition-source-asset-${record.ingestion_definition_id}`}
                        name="source_asset_id"
                        defaultValue={record.source_asset_id}
                        required
                      >
                        {sourceAssets.map((item) => (
                          <option key={item.source_asset_id} value={item.source_asset_id}>
                            {item.source_asset_id}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="field">
                      <label htmlFor={`definition-transport-${record.ingestion_definition_id}`}>
                        Transport
                      </label>
                      <input
                        id={`definition-transport-${record.ingestion_definition_id}`}
                        name="transport"
                        type="text"
                        defaultValue={record.transport}
                        required
                      />
                    </div>
                    <div className="field">
                      <label htmlFor={`definition-mode-${record.ingestion_definition_id}`}>
                        Schedule mode
                      </label>
                      <input
                        id={`definition-mode-${record.ingestion_definition_id}`}
                        name="schedule_mode"
                        type="text"
                        defaultValue={record.schedule_mode}
                        required
                      />
                    </div>
                    <div className="field">
                      <label htmlFor={`definition-enabled-${record.ingestion_definition_id}`}>
                        Status
                      </label>
                      <select
                        id={`definition-enabled-${record.ingestion_definition_id}`}
                        name="enabled"
                        defaultValue={record.enabled ? "true" : "false"}
                      >
                        <option value="true">active</option>
                        <option value="false">inactive</option>
                      </select>
                    </div>
                    <div className="field spanTwo">
                      <label htmlFor={`definition-source-path-${record.ingestion_definition_id}`}>
                        Source path
                      </label>
                      <input
                        id={`definition-source-path-${record.ingestion_definition_id}`}
                        name="source_path"
                        type="text"
                        defaultValue={record.source_path}
                        required
                      />
                    </div>
                    <div className="field">
                      <label htmlFor={`definition-file-pattern-${record.ingestion_definition_id}`}>
                        File pattern
                      </label>
                      <input
                        id={`definition-file-pattern-${record.ingestion_definition_id}`}
                        name="file_pattern"
                        type="text"
                        defaultValue={record.file_pattern}
                      />
                    </div>
                    <div className="field">
                      <label htmlFor={`definition-poll-${record.ingestion_definition_id}`}>
                        Poll interval
                      </label>
                      <input
                        id={`definition-poll-${record.ingestion_definition_id}`}
                        name="poll_interval_seconds"
                        type="number"
                        defaultValue={record.poll_interval_seconds || ""}
                        min="1"
                      />
                    </div>
                    <div className="field spanTwo">
                      <label htmlFor={`definition-processed-${record.ingestion_definition_id}`}>
                        Processed path
                      </label>
                      <input
                        id={`definition-processed-${record.ingestion_definition_id}`}
                        name="processed_path"
                        type="text"
                        defaultValue={record.processed_path || ""}
                      />
                    </div>
                    <div className="field spanTwo">
                      <label htmlFor={`definition-failed-${record.ingestion_definition_id}`}>
                        Failed path
                      </label>
                      <input
                        id={`definition-failed-${record.ingestion_definition_id}`}
                        name="failed_path"
                        type="text"
                        defaultValue={record.failed_path || ""}
                      />
                    </div>
                    <div className="field spanTwo">
                      <label htmlFor={`definition-source-name-${record.ingestion_definition_id}`}>
                        Source name
                      </label>
                      <input
                        id={`definition-source-name-${record.ingestion_definition_id}`}
                        name="source_name"
                        type="text"
                        defaultValue={record.source_name || ""}
                      />
                    </div>
                    <button className="primaryButton inlineButton" type="submit">
                      Save ingestion definition
                    </button>
                  </form>
                  <div className="buttonRow">
                    <form
                      action={`/control/execution/ingestion-definitions/${record.ingestion_definition_id}/process`}
                      method="post"
                    >
                      <button className="ghostButton" type="submit">
                        Process now
                      </button>
                    </form>
                  </div>
                </article>
              ))}
            </div>
          )}
        </article>

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
            <div className="entityList">
              {executionSchedules.map((record) => (
                <article className="entityCard" key={record.schedule_id}>
                  <div className="entityHeader">
                    <div>
                      <div className="metricLabel">{record.schedule_id}</div>
                      <h3>{record.target_ref}</h3>
                    </div>
                    <span className={`statusPill status-${statusCopy(record.enabled)}`}>
                      {statusCopy(record.enabled)}
                    </span>
                  </div>
                  <div className="metaGrid">
                    <div className="metaItem">
                      <div className="metricLabel">Target kind</div>
                      <div>{record.target_kind}</div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Cron</div>
                      <div>{record.cron_expression}</div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Next due</div>
                      <div>{record.next_due_at || "n/a"}</div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Last enqueued</div>
                      <div>{record.last_enqueued_at || "n/a"}</div>
                    </div>
                  </div>
                  <form
                    className="formGrid fourCol"
                    action={`/control/execution/execution-schedules/${record.schedule_id}`}
                    method="post"
                  >
                    <input name="schedule_id" type="hidden" value={record.schedule_id} />
                    <div className="field">
                      <label htmlFor={`schedule-target-kind-${record.schedule_id}`}>Target kind</label>
                      <input
                        id={`schedule-target-kind-${record.schedule_id}`}
                        name="target_kind"
                        type="text"
                        defaultValue={record.target_kind}
                        required
                      />
                    </div>
                    <div className="field spanTwo">
                      <label htmlFor={`schedule-target-ref-${record.schedule_id}`}>Target ref</label>
                      <select
                        id={`schedule-target-ref-${record.schedule_id}`}
                        name="target_ref"
                        defaultValue={record.target_ref}
                        required
                      >
                        {ingestionDefinitions.map((item) => (
                          <option
                            key={item.ingestion_definition_id}
                            value={item.ingestion_definition_id}
                          >
                            {item.ingestion_definition_id}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="field">
                      <label htmlFor={`schedule-enabled-${record.schedule_id}`}>Status</label>
                      <select
                        id={`schedule-enabled-${record.schedule_id}`}
                        name="enabled"
                        defaultValue={record.enabled ? "true" : "false"}
                      >
                        <option value="true">active</option>
                        <option value="false">inactive</option>
                      </select>
                    </div>
                    <div className="field spanTwo">
                      <label htmlFor={`schedule-cron-${record.schedule_id}`}>Cron expression</label>
                      <input
                        id={`schedule-cron-${record.schedule_id}`}
                        name="cron_expression"
                        type="text"
                        defaultValue={record.cron_expression}
                        required
                      />
                    </div>
                    <div className="field">
                      <label htmlFor={`schedule-timezone-${record.schedule_id}`}>Timezone</label>
                      <input
                        id={`schedule-timezone-${record.schedule_id}`}
                        name="timezone"
                        type="text"
                        defaultValue={record.timezone}
                        required
                      />
                    </div>
                    <div className="field">
                      <label htmlFor={`schedule-concurrency-${record.schedule_id}`}>Max concurrency</label>
                      <input
                        id={`schedule-concurrency-${record.schedule_id}`}
                        name="max_concurrency"
                        type="number"
                        defaultValue={record.max_concurrency}
                        min="1"
                      />
                    </div>
                    <button className="primaryButton inlineButton" type="submit">
                      Save execution schedule
                    </button>
                  </form>
                  <div className="buttonRow">
                    <form action="/control/execution/schedule-dispatches" method="post">
                      <input name="schedule_id" type="hidden" value={record.schedule_id} />
                      <button className="ghostButton" type="submit">
                        Re-dispatch now
                      </button>
                    </form>
                  </div>
                </article>
              ))}
            </div>
          )}
        </article>

        <section className="layout">
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
                    {scheduleDispatches.slice(0, 20).map((record) => (
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

          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Lineage</div>
                <h2>Recent source lineage</h2>
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
                    {sourceLineage.slice(0, 20).map((record) => (
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
        </section>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Publication</div>
              <h2>Recent publication audit</h2>
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
                  {publicationAudit.slice(0, 20).map((record) => (
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
    </AppShell>
  );
}
