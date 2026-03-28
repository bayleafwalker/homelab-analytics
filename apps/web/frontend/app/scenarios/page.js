import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { ArchiveScenarioButton } from "@/components/archive-scenario-button";
import { getCurrentUser, getScenarios } from "@/lib/backend";

const TYPE_LABELS = {
  loan_what_if: "Loan what-if",
  income_change: "Income change",
  expense_shock: "Expense shock",
  tariff_shock: "Tariff shock",
};

const TYPE_COLORS = {
  loan_what_if: "var(--accent)",
  income_change: "var(--ok)",
  expense_shock: "var(--warning)",
  tariff_shock: "var(--warning)",
};

function typeBadge(type) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "4px",
        fontSize: "0.75rem",
        background: TYPE_COLORS[type] || "var(--surface-2)",
        color: "var(--bg)",
        fontWeight: 600,
        letterSpacing: "0.03em",
      }}
    >
      {TYPE_LABELS[type] || type}
    </span>
  );
}

export default async function ScenariosPage() {
  const user = await getCurrentUser();
  const scenarios = await getScenarios();

  return (
    <AppShell
      currentPath="/scenarios"
      user={user}
      title="Scenarios"
      eyebrow="Simulation History"
      lede="All active what-if scenarios. Click a label to view the comparison, or archive to remove it from this list."
    >
      <section className="stack">
        <article className="panel section">
          <div className="tableWrap">
            {scenarios.length === 0 ? (
              <p className="muted">
                No active scenarios. Create one from the Loans or Reports pages.
              </p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Label</th>
                    <th>Subject</th>
                    <th>Created</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {scenarios.map((row) => (
                    <tr key={row.scenario_id}>
                      <td>{typeBadge(row.scenario_type)}</td>
                      <td>
                        <Link
                          href={`/scenarios/${row.scenario_id}`}
                          style={{ color: "var(--accent)" }}
                        >
                          {row.label}
                        </Link>
                      </td>
                      <td>{row.subject_id}</td>
                      <td>{row.created_at ? row.created_at.slice(0, 10) : "—"}</td>
                      <td>
                        <ArchiveScenarioButton scenarioId={row.scenario_id} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </article>
      </section>
    </AppShell>
  );
}
