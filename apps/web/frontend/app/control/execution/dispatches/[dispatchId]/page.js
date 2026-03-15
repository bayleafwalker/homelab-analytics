import Link from "next/link";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ControlNav } from "@/components/control-nav";
import {
  getCurrentUser,
  getOperationalSummary,
  getScheduleDispatch
} from "@/lib/backend";

function summaryFor(summaryMap, key) {
  return (summaryMap && key && summaryMap[key]) || null;
}

export default async function DispatchDetailPage({ params }) {
  const user = await getCurrentUser();
  if (user.role !== "admin") {
    redirect("/");
  }

  const [{ dispatch, schedule, ingestion_definition: ingestionDefinition, source_asset: sourceAsset }, operationalSummary] =
    await Promise.all([
      getScheduleDispatch(params.dispatchId),
      getOperationalSummary()
    ]);
  const scheduleSummary = summaryFor(
    operationalSummary.execution_schedules,
    schedule?.schedule_id
  );
  const definitionSummary = summaryFor(
    operationalSummary.ingestion_definitions,
    ingestionDefinition?.ingestion_definition_id
  );
  const sourceAssetSummary = summaryFor(
    operationalSummary.source_assets,
    sourceAsset?.source_asset_id
  );

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title="Dispatch Detail"
      eyebrow="Admin Access"
      lede="Schedule dispatch drill-down stays API-backed and tied to the control plane so queue recovery does not depend on worker shell access."
    >
      <section className="stack">
        <ControlNav currentPath="/control/execution" />
        <div className="buttonRow">
          <Link className="ghostButton" href="/control/execution">
            Back to execution
          </Link>
        </div>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Queue</div>
              <h2>{dispatch.dispatch_id}</h2>
            </div>
            <span className={`statusPill status-${dispatch.status}`}>{dispatch.status}</span>
          </div>
          <div className="metaGrid">
            <div className="metaItem">
              <div className="metricLabel">Schedule</div>
              <div>{dispatch.schedule_id}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Target</div>
              <div>{dispatch.target_ref}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Enqueued</div>
              <div>{dispatch.enqueued_at}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Completed</div>
              <div>{dispatch.completed_at || "n/a"}</div>
            </div>
          </div>
        </article>

        <section className="layout">
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Schedule</div>
                <h2>Execution schedule</h2>
              </div>
            </div>
            <div className="metaGrid">
              <div className="metaItem">
                <div className="metricLabel">Cron</div>
                <div>{schedule.cron_expression}</div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Next due</div>
                <div>{schedule.next_due_at || "n/a"}</div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Last enqueued</div>
                <div>{schedule.last_enqueued_at || "n/a"}</div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Failed dispatches</div>
                <div>{scheduleSummary?.failed_dispatch_count || 0}</div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Observed runs</div>
                <div>{scheduleSummary?.run_count || 0}</div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Last failure</div>
                <div>{scheduleSummary?.last_failure_at || "n/a"}</div>
              </div>
            </div>
          </article>

          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Target</div>
                <h2>Ingestion binding</h2>
              </div>
            </div>
            <div className="metaGrid">
              <div className="metaItem">
                <div className="metricLabel">Definition</div>
                <div>{ingestionDefinition?.ingestion_definition_id || "n/a"}</div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Source asset</div>
                <div>{sourceAsset?.source_asset_id || "n/a"}</div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Definition runs</div>
                <div>{definitionSummary?.run_count || 0}</div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Asset runs</div>
                <div>{sourceAssetSummary?.run_count || 0}</div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Last success</div>
                <div>{definitionSummary?.last_success_at || "n/a"}</div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Last failed run</div>
                <div>{definitionSummary?.last_failure_at || "n/a"}</div>
              </div>
            </div>
          </article>
        </section>
      </section>
    </AppShell>
  );
}
