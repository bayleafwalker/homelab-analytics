import { AppShell } from "@/components/app-shell";
import { getCurrentUser, getRuns } from "@/lib/backend";

export default async function RunsPage() {
  const user = await getCurrentUser();
  const runs = await getRuns(50);

  return (
    <AppShell
      currentPath="/runs"
      user={user}
      title="Ingestion Runs"
      eyebrow="Reader Access"
      lede="Run visibility comes from the API only, keeping the web workload out of the warehouse and control-plane internals."
    >
      <section className="panel section">
        <div className="sectionHeader">
          <div>
            <div className="eyebrow">Operational History</div>
            <h2>Recent runs</h2>
          </div>
        </div>
        {runs.length === 0 ? (
          <div className="empty">No runs recorded yet.</div>
        ) : (
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Status</th>
                  <th>Source</th>
                  <th>Dataset</th>
                  <th>Rows</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.run_id}>
                    <td>{run.created_at}</td>
                    <td>
                      <span className={`statusPill status-${run.status}`}>{run.status}</span>
                    </td>
                    <td>{run.source_name}</td>
                    <td>{run.dataset_name}</td>
                    <td>{run.row_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </AppShell>
  );
}
