import Link from "next/link";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ControlNav } from "@/components/control-nav";
import {
  getCurrentUser,
  getExecutionSchedules,
  getIngestionDefinitions,
  getOperationalSummary,
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
    case "ingestion-definition-archived":
      return "Ingestion definition archive state updated.";
    case "ingestion-definition-deleted":
      return "Ingestion definition deleted.";
    case "execution-schedule-created":
      return "Execution schedule created.";
    case "execution-schedule-updated":
      return "Execution schedule updated.";
    case "execution-schedule-archived":
      return "Execution schedule archive state updated.";
    case "execution-schedule-deleted":
      return "Execution schedule deleted.";
    case "schedule-dispatch-created":
      return "Manual schedule dispatch enqueued.";
    case "due-dispatches-enqueued":
      return "Due schedules enqueued.";
    case "schedule-dispatch-retried":
      return "Schedule dispatch requeued.";
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
    case "ingestion-definition-archive-failed":
      return "Could not update the ingestion definition archive state.";
    case "ingestion-definition-delete-failed":
      return "Could not delete the ingestion definition.";
    case "execution-schedule-failed":
      return "Could not create the execution schedule.";
    case "execution-schedule-update-failed":
      return "Could not update the execution schedule.";
    case "execution-schedule-archive-failed":
      return "Could not update the execution schedule archive state.";
    case "execution-schedule-delete-failed":
      return "Could not delete the execution schedule.";
    case "ingestion-process-failed":
      return "Could not process the ingestion definition.";
    case "schedule-dispatch-failed":
      return "Could not enqueue the schedule dispatch.";
    case "schedule-dispatch-retry-failed":
      return "Could not requeue the schedule dispatch.";
    default:
      return "";
  }
}

function statusCopy(enabled) {
  return enabled ? "active" : "inactive";
}

function archiveCopy(archived) {
  return archived ? "archived" : "active";
}

function buildReferenceMap(records, field) {
  const references = new Map();
  for (const record of records) {
    const key = record[field];
    const current = references.get(key) || [];
    current.push(record);
    references.set(key, current);
  }
  return references;
}

function referenceSummary(records, field) {
  if (!records || records.length === 0) {
    return "none";
  }
  const values = records.map((record) => record[field]);
  if (values.length <= 3) {
    return values.join(", ");
  }
  return `${values.slice(0, 3).join(", ")} +${values.length - 3} more`;
}

function summaryFor(summaryMap, key) {
  return (summaryMap && key && summaryMap[key]) || null;
}

function isRetryableDispatch(record) {
  return record.status === "completed" || record.status === "failed";
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
    scheduleDispatches,
    operationalSummary
  ] = await Promise.all([
    getSourceAssets({ includeArchived: true }),
    getIngestionDefinitions({ includeArchived: true }),
    getExecutionSchedules({ includeArchived: true }),
    getSourceLineage(),
    getPublicationAudit(),
    getScheduleDispatches(),
    getOperationalSummary()
  ]);
  const activeSourceAssets = sourceAssets.filter(
    (record) => record.enabled && !record.archived
  );
  const activeIngestionDefinitions = ingestionDefinitions.filter((record) => !record.archived);
  const archivedIngestionDefinitions = ingestionDefinitions.filter((record) => record.archived);
  const archivedExecutionSchedules = executionSchedules.filter((record) => record.archived);
  const sourceAssetById = new Map(
    sourceAssets.map((record) => [record.source_asset_id, record])
  );
  const ingestionDefinitionById = new Map(
    ingestionDefinitions.map((record) => [record.ingestion_definition_id, record])
  );
  const executionSchedulesByTargetRef = buildReferenceMap(
    executionSchedules.filter((record) => record.target_kind === "ingestion_definition"),
    "target_ref"
  );
  const scheduleDispatchesByScheduleId = buildReferenceMap(
    scheduleDispatches,
    "schedule_id"
  );
  const notice = noticeCopy(searchParams?.notice);
  const error = errorCopy(searchParams?.error);
  const enqueuedDispatches = scheduleDispatches.filter((record) => record.status === "enqueued");
  const failedDispatches = operationalSummary.recent_failed_dispatches || [];
  const recoveredDispatches = operationalSummary.recent_recovered_dispatches || [];
  const failedRuns = operationalSummary.recent_failed_runs || [];
  const staleDispatches = operationalSummary.stale_running_dispatches || [];
  const workers = operationalSummary.workers || [];

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
            <div className="metricValue">{activeIngestionDefinitions.length}</div>
            <div className="muted">{archivedIngestionDefinitions.length} archived definitions</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Execution schedules</div>
            <div className="metricValue">{executionSchedules.length - archivedExecutionSchedules.length}</div>
            <div className="muted">{archivedExecutionSchedules.length} archived schedules</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Queued dispatches</div>
            <div className="metricValue">{enqueuedDispatches.length}</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Failed runs / dispatches</div>
            <div className="metricValue">
              {failedRuns.length} / {failedDispatches.length}
            </div>
            <div className="muted">Latest queue and retry problems.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Active workers</div>
            <div className="metricValue">{operationalSummary.queue?.active_workers || 0}</div>
            <div className="muted">{workers.length} workers reporting heartbeats.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Stale running dispatches</div>
            <div className="metricValue">
              {operationalSummary.queue?.stale_running_dispatches || 0}
            </div>
            <div className="muted">Running dispatches with expired claims.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Recovered dispatches</div>
            <div className="metricValue">
              {operationalSummary.queue?.recovered_dispatches || 0}
            </div>
            <div className="muted">Expired claims requeued by worker recovery.</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Oldest heartbeat age</div>
            <div className="metricValue">
              {Math.round(operationalSummary.queue?.oldest_worker_heartbeat_age_seconds || 0)}s
            </div>
            <div className="muted">Alert if this keeps climbing while work is expected.</div>
          </article>
        </section>

        <section className="layout">
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Recovery</div>
                <h2>Recent failed runs</h2>
              </div>
            </div>
            {failedRuns.length === 0 ? (
              <div className="empty">No failed or rejected runs recorded in the current summary.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Run</th>
                      <th>Status</th>
                      <th>Dataset</th>
                      <th>Definition</th>
                      <th>Failure</th>
                    </tr>
                  </thead>
                  <tbody>
                    {failedRuns.slice(0, 8).map((run) => (
                      <tr key={run.run_id}>
                        <td>
                          <Link className="inlineLink" href={`/runs/${run.run_id}`}>
                            {run.run_id}
                          </Link>
                        </td>
                        <td>
                          <span className={`statusPill status-${run.status}`}>{run.status}</span>
                        </td>
                        <td>{run.dataset_name}</td>
                        <td>{run.context?.ingestion_definition_id || "manual / n/a"}</td>
                        <td>{run.issues?.[0]?.message || run.recovery?.reason || "n/a"}</td>
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
                <h2>Recent failed dispatches</h2>
              </div>
            </div>
            {failedDispatches.length === 0 ? (
              <div className="empty">No failed schedule dispatches recorded.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Dispatch</th>
                      <th>Schedule</th>
                      <th>Status</th>
                      <th>Failure</th>
                      <th>Runs</th>
                      <th>Enqueued</th>
                      <th>Completed</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {failedDispatches.slice(0, 8).map((record) => (
                      <tr key={record.dispatch_id}>
                        <td>
                          <Link
                            className="inlineLink"
                            href={`/control/execution/dispatches/${record.dispatch_id}`}
                          >
                            {record.dispatch_id}
                          </Link>
                        </td>
                        <td>{record.schedule_id}</td>
                        <td>
                          <span className={`statusPill status-${record.status}`}>{record.status}</span>
                        </td>
                        <td>{record.failure_reason || "n/a"}</td>
                        <td>
                          {record.run_ids?.length ? (
                            <div className="stack">
                              {record.run_ids.map((runId) => (
                                <Link
                                  key={runId}
                                  className="inlineLink"
                                  href={`/runs/${runId}`}
                                >
                                  {runId}
                                </Link>
                              ))}
                            </div>
                          ) : (
                            "n/a"
                          )}
                        </td>
                        <td>{record.enqueued_at}</td>
                        <td>{record.completed_at || "n/a"}</td>
                        <td>
                          {isRetryableDispatch(record) ? (
                            <form
                              action={`/control/execution/dispatches/${record.dispatch_id}/retry`}
                              method="post"
                            >
                              <button className="ghostButton" type="submit">
                                Retry
                              </button>
                            </form>
                          ) : (
                            "n/a"
                          )}
                        </td>
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
                <div className="eyebrow">Recovery</div>
                <h2>Recovered stale dispatches</h2>
              </div>
            </div>
            {recoveredDispatches.length === 0 ? (
              <div className="empty">No stale dispatch recoveries recorded.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Dispatch</th>
                      <th>Schedule</th>
                      <th>Failure</th>
                      <th>Completed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recoveredDispatches.slice(0, 8).map((record) => (
                      <tr key={record.dispatch_id}>
                        <td>
                          <Link
                            className="inlineLink"
                            href={`/control/execution/dispatches/${record.dispatch_id}`}
                          >
                            {record.dispatch_id}
                          </Link>
                        </td>
                        <td>{record.schedule_id}</td>
                        <td>{record.failure_reason || "n/a"}</td>
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
                <div className="eyebrow">Workers</div>
                <h2>Worker heartbeats</h2>
              </div>
            </div>
            {workers.length === 0 ? (
              <div className="empty">No workers have reported heartbeats yet.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Worker</th>
                      <th>Status</th>
                      <th>Active dispatch</th>
                      <th>Claim expires</th>
                      <th>Heartbeat age</th>
                      <th>Observed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {workers.map((worker) => (
                      <tr key={worker.worker_id}>
                        <td>{worker.worker_id}</td>
                        <td>
                          <span
                            className={`statusPill status-${worker.stale ? "failed" : worker.status}`}
                          >
                            {worker.stale ? "stale" : worker.status}
                          </span>
                        </td>
                        <td>
                          {worker.active_dispatch_id ? (
                            <Link
                              className="inlineLink"
                              href={`/control/execution/dispatches/${worker.active_dispatch_id}`}
                            >
                              {worker.active_dispatch_id}
                            </Link>
                          ) : (
                            "n/a"
                          )}
                        </td>
                        <td>{worker.claim_expires_at || "n/a"}</td>
                        <td>{Math.round(worker.heartbeat_age_seconds || 0)}s</td>
                        <td>{worker.observed_at}</td>
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
                <h2>Stale running dispatches</h2>
              </div>
            </div>
            {staleDispatches.length === 0 ? (
              <div className="empty">No stale running dispatches detected.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Dispatch</th>
                      <th>Worker</th>
                      <th>Claim expires</th>
                      <th>Started</th>
                    </tr>
                  </thead>
                  <tbody>
                    {staleDispatches.map((record) => (
                      <tr key={record.dispatch_id}>
                        <td>
                          <Link
                            className="inlineLink"
                            href={`/control/execution/dispatches/${record.dispatch_id}`}
                          >
                            {record.dispatch_id}
                          </Link>
                        </td>
                        <td>{record.claimed_by_worker_id || "n/a"}</td>
                        <td>{record.claim_expires_at || "n/a"}</td>
                        <td>{record.started_at || "n/a"}</td>
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

              {activeIngestionDefinitions.length === 0 ? (
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
                      {activeIngestionDefinitions.map((record) => (
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
              {ingestionDefinitions.map((record) => {
                const sourceAsset = sourceAssetById.get(record.source_asset_id);
                const dependentSchedules =
                  executionSchedulesByTargetRef.get(record.ingestion_definition_id) || [];
                const definitionSummary = summaryFor(
                  operationalSummary.ingestion_definitions,
                  record.ingestion_definition_id
                );
                return (
                <article className="entityCard" key={record.ingestion_definition_id}>
                  <div className="entityHeader">
                    <div>
                      <div className="metricLabel">{record.ingestion_definition_id}</div>
                      <h3>{record.source_asset_id}</h3>
                    </div>
                    <div className="buttonRow">
                      <span className={`statusPill status-${statusCopy(record.enabled)}`}>
                        {statusCopy(record.enabled)}
                      </span>
                      <span
                        className={`statusPill status-${record.archived ? "archived" : "active"}`}
                      >
                        {archiveCopy(record.archived)}
                      </span>
                    </div>
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
                    <div className="metaItem">
                      <div className="metricLabel">Source asset state</div>
                      <div className="muted">
                        {sourceAsset?.archived
                          ? "Referenced source asset is archived."
                          : sourceAsset?.enabled
                            ? "Referenced source asset is active."
                            : "Referenced source asset is inactive."}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Execution schedules</div>
                      <div>{dependentSchedules.length}</div>
                      <div className="muted">
                        {referenceSummary(dependentSchedules, "schedule_id")}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Observed runs</div>
                      <div>{definitionSummary?.run_count || 0}</div>
                      <div className="muted">
                        Last success {definitionSummary?.last_success_at || "n/a"}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Failure state</div>
                      <div>{definitionSummary?.failed_run_count || 0} failed runs</div>
                      <div className="muted">
                        Last failure {definitionSummary?.last_failure_at || "n/a"}
                      </div>
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
                    {!record.archived ? (
                      <form
                        action={`/control/execution/ingestion-definitions/${record.ingestion_definition_id}/process`}
                        method="post"
                      >
                        <button className="ghostButton" type="submit">
                          Process now
                        </button>
                      </form>
                    ) : null}
                    <form
                      action={`/control/execution/ingestion-definitions/${record.ingestion_definition_id}/archive`}
                      method="post"
                    >
                      <input
                        name="archived"
                        type="hidden"
                        value={record.archived ? "false" : "true"}
                      />
                      <button className="ghostButton" type="submit">
                        {record.archived ? "Restore definition" : "Archive definition"}
                      </button>
                    </form>
                    {record.archived ? (
                      <form
                        action={`/control/execution/ingestion-definitions/${record.ingestion_definition_id}/delete`}
                        method="post"
                      >
                        <button className="ghostButton" type="submit">
                          Delete archived definition
                        </button>
                      </form>
                    ) : null}
                  </div>
                </article>
              );
              })}
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
              {executionSchedules.map((record) => {
                const targetDefinition =
                  record.target_kind === "ingestion_definition"
                    ? ingestionDefinitionById.get(record.target_ref)
                    : null;
                const scheduleDispatchHistory =
                  scheduleDispatchesByScheduleId.get(record.schedule_id) || [];
                const scheduleSummary = summaryFor(
                  operationalSummary.execution_schedules,
                  record.schedule_id
                );
                return (
                <article className="entityCard" key={record.schedule_id}>
                  <div className="entityHeader">
                    <div>
                      <div className="metricLabel">{record.schedule_id}</div>
                      <h3>{record.target_ref}</h3>
                    </div>
                    <div className="buttonRow">
                      <span className={`statusPill status-${statusCopy(record.enabled)}`}>
                        {statusCopy(record.enabled)}
                      </span>
                      <span
                        className={`statusPill status-${record.archived ? "archived" : "active"}`}
                      >
                        {archiveCopy(record.archived)}
                      </span>
                    </div>
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
                    <div className="metaItem">
                      <div className="metricLabel">Target definition state</div>
                      <div className="muted">
                        {targetDefinition?.archived
                          ? "Target ingestion definition is archived."
                          : targetDefinition
                            ? "Target ingestion definition is active in the control plane."
                            : "Target definition is not available in the current catalog view."}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Dispatch history</div>
                      <div>{scheduleDispatchHistory.length}</div>
                      <div className="muted">
                        {referenceSummary(scheduleDispatchHistory, "dispatch_id")}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Observed runs</div>
                      <div>{scheduleSummary?.run_count || 0}</div>
                      <div className="muted">
                        Last success {scheduleSummary?.last_success_at || "n/a"}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Queue problems</div>
                      <div>{scheduleSummary?.failed_dispatch_count || 0} failed dispatches</div>
                      <div className="muted">
                        Last failure {scheduleSummary?.last_failed_dispatch_at || "n/a"}
                      </div>
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
                            {item.archived ? " / archived" : ""}
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
                    {!record.archived ? (
                      <form action="/control/execution/schedule-dispatches" method="post">
                        <input name="schedule_id" type="hidden" value={record.schedule_id} />
                        <button className="ghostButton" type="submit">
                          Re-dispatch now
                        </button>
                      </form>
                    ) : null}
                    <form
                      action={`/control/execution/execution-schedules/${record.schedule_id}/archive`}
                      method="post"
                    >
                      <input
                        name="archived"
                        type="hidden"
                        value={record.archived ? "false" : "true"}
                      />
                      <button className="ghostButton" type="submit">
                        {record.archived ? "Restore schedule" : "Archive schedule"}
                      </button>
                    </form>
                    {record.archived ? (
                      <form
                        action={`/control/execution/execution-schedules/${record.schedule_id}/delete`}
                        method="post"
                      >
                        <button className="ghostButton" type="submit">
                          Delete archived schedule
                        </button>
                      </form>
                    ) : null}
                  </div>
                </article>
              );
              })}
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
                      <th>Started</th>
                      <th>Worker</th>
                      <th>Claim expires</th>
                      <th>Failure</th>
                      <th>Runs</th>
                      <th>Enqueued</th>
                      <th>Completed</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scheduleDispatches.slice(0, 20).map((record) => (
                      <tr key={record.dispatch_id}>
                        <td>
                          <Link
                            className="inlineLink"
                            href={`/control/execution/dispatches/${record.dispatch_id}`}
                          >
                            {record.dispatch_id}
                          </Link>
                        </td>
                        <td>{record.schedule_id}</td>
                        <td>
                          <span className={`statusPill status-${record.status}`}>{record.status}</span>
                        </td>
                        <td>{record.started_at || "n/a"}</td>
                        <td>{record.claimed_by_worker_id || "n/a"}</td>
                        <td>{record.claim_expires_at || "n/a"}</td>
                        <td>{record.failure_reason || "n/a"}</td>
                        <td>
                          {record.run_ids?.length ? (
                            <div className="stack">
                              {record.run_ids.map((runId) => (
                                <Link
                                  key={runId}
                                  className="inlineLink"
                                  href={`/runs/${runId}`}
                                >
                                  {runId}
                                </Link>
                              ))}
                            </div>
                          ) : (
                            "n/a"
                          )}
                        </td>
                        <td>{record.enqueued_at}</td>
                        <td>{record.completed_at || "n/a"}</td>
                        <td>
                          {isRetryableDispatch(record) ? (
                            <form
                              action={`/control/execution/dispatches/${record.dispatch_id}/retry`}
                              method="post"
                            >
                              <button className="ghostButton" type="submit">
                                Retry
                              </button>
                            </form>
                          ) : (
                            "n/a"
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
