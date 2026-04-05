import Link from "next/link";
import { redirect } from "next/navigation";

import { RetroTerminalPanel } from "@/components/retro-terminal-panel";
import { RetroShell } from "@/components/retro-shell";
import { getCurrentUser, getOperationalSummary, getTerminalCommands } from "@/lib/backend";

export default async function RetroTerminalPage() {
  const user = await getCurrentUser();
  if (user.role !== "admin") {
    redirect("/retro");
  }

  const [commands, operationalSummary] = await Promise.all([
    getTerminalCommands(),
    getOperationalSummary(),
  ]);

  return (
    <RetroShell
      currentPath="/retro/terminal"
      user={user}
      title="CRT Control / Terminal"
      eyebrow="Admin GUI"
      lede="A synchronous, allowlisted terminal boundary over control-plane reads and a narrow enqueue path. No host shell, no arbitrary worker flags, no streaming session state."
    >
      <section className="retroMetricGrid">
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Allowlisted Commands</span>
          <strong>{commands.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Queued Dispatches</span>
          <strong>{operationalSummary.queue?.enqueued_dispatches || 0}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Workers</span>
          <strong>{operationalSummary.queue?.active_workers || 0}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Failed Dispatches</span>
          <strong>{(operationalSummary.recent_failed_dispatches || []).length}</strong>
        </article>
      </section>

      <section className="retroSplit">
        <RetroTerminalPanel initialCommands={commands} />

        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Terminal Guardrails</div>
              <h2>V1 scope</h2>
            </div>
            <Link className="retroActionLink" href="/retro/control/execution">
              Execution
            </Link>
          </div>
          <div className="retroListBlock">
            <div className="retroListRow">Read queue, run, schedule, heartbeat, freshness, auth, and publication state.</div>
            <div className="retroListRow">Read users, lineage, source systems, source assets, ingestion definitions, and publication definitions.</div>
            <div className="retroListRow">Allow one mutating queue operation: <span className="retroMonoStrong">enqueue-due [limit]</span>.</div>
            <div className="retroListRow">Every execution attempt is audited through the auth/control audit log.</div>
            <div className="retroListRow">Classic admin flows remain the mutation surface for broader catalog and execution editing.</div>
          </div>
          <div className="retroSubPanel">
            <div className="retroMonoStrong">Non-goals</div>
            <div className="retroMuted">No shell access, file paths, import/export, or long-running streaming sessions.</div>
          </div>
        </article>
      </section>
    </RetroShell>
  );
}
