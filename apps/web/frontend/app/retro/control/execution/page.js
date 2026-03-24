import Link from "next/link";
import { redirect } from "next/navigation";

import { RetroShell } from "@/components/retro-shell";
import {
  getCurrentUser,
  getExecutionSchedules,
  getIngestionDefinitions,
  getOperationalSummary,
  getRuns,
  getScheduleDispatches,
  getSourceAssets,
  getSourceFreshness,
} from "@/lib/backend";

function noticeCopy(notice) {
  switch (notice) {
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
    case "schedule-dispatch-failed":
      return "Could not enqueue the schedule dispatch.";
    case "schedule-dispatch-retry-failed":
      return "Could not requeue the schedule dispatch.";
    default:
      return "";
  }
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

function isRetryableDispatch(record) {
  return record.status === "completed" || record.status === "failed";
}

export default async function RetroControlExecutionPage({ searchParams }) {
  const user = await getCurrentUser();
  if (user.role !== "admin") {
    redirect("/retro");
  }

  const [
    sourceAssets,
    ingestionDefinitions,
    executionSchedules,
    sourceFreshness,
    scheduleDispatches,
    operationalSummary,
    runs,
  ] = await Promise.all([
    getSourceAssets({ includeArchived: true }),
    getIngestionDefinitions({ includeArchived: true }),
    getExecutionSchedules({ includeArchived: true }),
    getSourceFreshness(),
    getScheduleDispatches(),
    getOperationalSummary(),
    getRuns(6),
  ]);

  const notice = noticeCopy(searchParams?.notice);
  const error = errorCopy(searchParams?.error);
  const activeDefinitions = ingestionDefinitions.filter((record) => !record.archived);
  const activeSchedules = executionSchedules.filter((record) => !record.archived);
  const enqueuedDispatches = scheduleDispatches.filter((record) => record.status === "enqueued");
  const ingestionDefinitionById = new Map(
    ingestionDefinitions.map((record) => [record.ingestion_definition_id, record])
  );
  const sourceAssetById = new Map(sourceAssets.map((record) => [record.source_asset_id, record]));
  const scheduleDispatchesByScheduleId = buildReferenceMap(scheduleDispatches, "schedule_id");
  const workers = operationalSummary.workers || [];
  const failedRuns = operationalSummary.recent_failed_runs || [];

  return (
    <RetroShell
      currentPath="/retro/control/execution"
      user={user}
      title="CRT Control / Execution"
      eyebrow="Admin GUI"
      lede="Dispatch queue, freshness, schedules, and recent run pressure rendered through the same control-plane endpoints and mutation handlers as the classic execution view."
    >
      {notice ? <div className="retroBanner retroBannerOk">{notice}</div> : null}
      {error ? <div className="retroBanner retroBannerWarn">{error}</div> : null}

      <section className="retroMetricGrid">
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Definitions</span>
          <strong>{activeDefinitions.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Schedules</span>
          <strong>{activeSchedules.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Queued Dispatches</span>
          <strong>{enqueuedDispatches.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Workers</span>
          <strong>{operationalSummary.queue?.active_workers || workers.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Stale Running</span>
          <strong>{operationalSummary.queue?.stale_running_dispatches || 0}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Freshness Rows</span>
          <strong>{sourceFreshness.length}</strong>
        </article>
      </section>

      <section className="retroSplit">
        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Queue Control</div>
              <h2>Manual dispatch actions</h2>
            </div>
            <Link className="retroActionLink" href="/control/execution">
              Classic execution
            </Link>
          </div>
          <div className="retroActionGrid">
            <form className="retroInlineForm" action="/retro/control/execution/schedule-dispatches" method="post">
              <label className="retroFieldLabel" htmlFor="retro-enqueue-limit">
                enqueue-due limit
              </label>
              <input id="retro-enqueue-limit" className="retroInput" name="limit" defaultValue="10" />
              <button className="retroActionButton" type="submit">
                Enqueue Due
              </button>
            </form>
            <div className="retroSubPanel">
              <div className="retroMonoStrong">Recent pressure</div>
              <div className="retroMuted">Failed runs: {failedRuns.length}</div>
              <div className="retroMuted">
                Recovered dispatches: {operationalSummary.queue?.recovered_dispatches || 0}
              </div>
              <div className="retroMuted">
                Oldest heartbeat age: {Math.round(operationalSummary.queue?.oldest_worker_heartbeat_age_seconds || 0)}s
              </div>
            </div>
          </div>
        </article>

        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Freshness Bus</div>
              <h2>Dataset freshness</h2>
            </div>
          </div>
          {sourceFreshness.length === 0 ? (
            <div className="retroEmptyState">No ingestion runs recorded yet.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Dataset</th>
                    <th>Status</th>
                    <th>Last Landed</th>
                    <th>Age</th>
                  </tr>
                </thead>
                <tbody>
                  {sourceFreshness.slice(0, 8).map((row) => {
                    const landedAt = new Date(row.landed_at);
                    const ageHours = Math.round((Date.now() - landedAt.getTime()) / 3_600_000);
                    return (
                      <tr key={row.dataset_name}>
                        <td>{row.dataset_name}</td>
                        <td>{row.status}</td>
                        <td>{row.landed_at}</td>
                        <td>{Number.isFinite(ageHours) ? `${ageHours}h` : "n/a"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>

      <section className="retroSplit retroSplitWide">
        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Schedule Deck</div>
              <h2>Execution schedules</h2>
            </div>
          </div>
          {activeSchedules.length === 0 ? (
            <div className="retroEmptyState">No active execution schedules configured.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Schedule</th>
                    <th>Target</th>
                    <th>Cadence</th>
                    <th>Next Due</th>
                    <th>Dispatches</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {activeSchedules.slice(0, 10).map((schedule) => {
                    const definition = ingestionDefinitionById.get(schedule.target_ref);
                    const sourceAsset = definition
                      ? sourceAssetById.get(definition.source_asset_id)
                      : null;
                    const dispatchCount = (scheduleDispatchesByScheduleId.get(schedule.schedule_id) || []).length;
                    return (
                      <tr key={schedule.schedule_id}>
                        <td>{schedule.schedule_id}</td>
                        <td>
                          {sourceAsset?.name || definition?.ingestion_definition_id || schedule.target_ref}
                        </td>
                        <td>{schedule.cron_expression}</td>
                        <td>{schedule.next_due_at || "n/a"}</td>
                        <td>{dispatchCount}</td>
                        <td>
                          <form action="/retro/control/execution/schedule-dispatches" method="post">
                            <input type="hidden" name="schedule_id" value={schedule.schedule_id} />
                            <button className="retroActionButton" type="submit">
                              Dispatch
                            </button>
                          </form>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </article>

        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Dispatch Feed</div>
              <h2>Recent queue events</h2>
            </div>
            <Link className="retroActionLink" href="/runs">
              Runs
            </Link>
          </div>
          {scheduleDispatches.length === 0 ? (
            <div className="retroEmptyState">No dispatches recorded yet.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Dispatch</th>
                    <th>Schedule</th>
                    <th>Status</th>
                    <th>Runs</th>
                    <th>Retry</th>
                  </tr>
                </thead>
                <tbody>
                  {scheduleDispatches.slice(0, 10).map((record) => (
                    <tr key={record.dispatch_id}>
                      <td>{record.dispatch_id}</td>
                      <td>{record.schedule_id}</td>
                      <td>{record.status}</td>
                      <td>{record.run_ids?.length || 0}</td>
                      <td>
                        {isRetryableDispatch(record) ? (
                          <form
                            action={`/retro/control/execution/dispatches/${record.dispatch_id}/retry`}
                            method="post"
                          >
                            <button className="retroActionButton" type="submit">
                              Retry
                            </button>
                          </form>
                        ) : (
                          <span className="retroMuted">n/a</span>
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

      <article className="retroPanel">
        <div className="retroSectionHeader">
          <div>
            <div className="retroEyebrow">Run Feed</div>
            <h2>Recent ingestion runs</h2>
          </div>
          <Link className="retroActionLink" href="/retro/terminal">
            Terminal
          </Link>
        </div>
        {runs.length === 0 ? (
          <div className="retroEmptyState">No runs recorded yet.</div>
        ) : (
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Dataset</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.run_id}>
                    <td>{run.run_id}</td>
                    <td>{run.status}</td>
                    <td>{run.dataset_name}</td>
                    <td>{run.created_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </article>
    </RetroShell>
  );
}
