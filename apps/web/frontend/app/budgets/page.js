import { AppShell } from "@/components/app-shell";
import { ResponsiveTable } from "@/components/responsive-table";
import {
  getBudgetEnvelopes,
  getBudgetProgress,
  getBudgetVariance,
  getCurrentUser,
} from "@/lib/backend";
import { stateIndicatorBadge } from "@/lib/state-indicators";

function money(value, currency) {
  return `${Number(value).toFixed(2)} ${currency}`;
}

export default async function BudgetsPage({ searchParams }) {
  const user = await getCurrentUser();
  const budgetName = searchParams?.budget_name || "";
  const category = searchParams?.category || "";
  const periodLabel = searchParams?.period_label || "";

  const [progress, envelopes, variance] = await Promise.all([
    getBudgetProgress(),
    getBudgetEnvelopes(budgetName || undefined, category || undefined, periodLabel || undefined),
    getBudgetVariance(budgetName || undefined, category || undefined, periodLabel || undefined),
  ]);

  const periods = [...new Set(variance.map((r) => r.period_label))].sort().reverse();

  return (
    <AppShell
      currentPath="/budgets"
      user={user}
      title="Budgets"
      eyebrow="Reader Access"
      lede="Budget targets vs actual spend by category and period."
    >
      <section className="stack">
        {/* Current month progress */}
        {progress.length > 0 && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Current month</div>
                <h2>Budget progress</h2>
              </div>
            </div>
            <ResponsiveTable
              label="Budget progress"
              rows={progress}
              columns={[
                { key: "budget_name", header: "Budget", primary: true },
                { key: "category_id", header: "Category" },
                { key: "target_amount", header: "Target", align: "end", cell: (row) => money(row.target_amount, row.currency) },
                { key: "spent_amount", header: "Spent", align: "end", cell: (row) => money(row.spent_amount, row.currency) },
                { key: "remaining", header: "Remaining", align: "end", cell: (row) => money(row.remaining, row.currency) },
                {
                  key: "utilization_pct",
                  header: "Utilization",
                  cell: (row) => {
                    const pct = Number(row.utilization_pct);
                    const badge = stateIndicatorBadge(row.state ?? row.status);
                    return (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}>
                        <span
                          aria-hidden="true"
                          style={{
                            display: "inline-block",
                            width: "80px",
                            height: "8px",
                            background: "var(--surface-2)",
                            borderRadius: "4px",
                            overflow: "hidden",
                          }}
                        >
                          <span
                            style={{
                              display: "block",
                              width: `${Math.min(pct, 100)}%`,
                              height: "100%",
                              background: badge.color,
                              borderRadius: "4px",
                            }}
                          />
                        </span>
                        <span>{pct.toFixed(0)}%</span>
                      </span>
                    );
                  },
                },
                {
                  key: "status",
                  header: "Status",
                  cell: (row) => {
                    const badge = stateIndicatorBadge(row.state ?? row.status);
                    return <span style={{ color: badge.color }}>{badge.label}</span>;
                  },
                },
              ]}
            />
          </article>
        )}

        {/* Envelope drift */}
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Envelope drift</div>
              <h2>Category cost envelopes</h2>
            </div>
          </div>
          <ResponsiveTable
            label="Category cost envelopes"
            rows={envelopes}
            empty={<p className="muted">No budget envelope data for the selected filters.</p>}
            columns={[
              { key: "budget_name", header: "Budget", primary: true },
              { key: "category_id", header: "Category" },
              { key: "period_label", header: "Period" },
              { key: "envelope_amount", header: "Envelope", align: "end", cell: (row) => money(row.envelope_amount, row.currency) },
              { key: "actual_amount", header: "Actual", align: "end", cell: (row) => money(row.actual_amount, row.currency) },
              {
                key: "drift_amount",
                header: "Drift",
                align: "end",
                cell: (row) => {
                  const driftAmt = Number(row.drift_amount);
                  return (
                    <span style={{ color: driftAmt <= 0 ? "var(--ok)" : "var(--warn)" }}>
                      {driftAmt <= 0 ? "" : "+"}
                      {driftAmt.toFixed(2)} {row.currency}
                    </span>
                  );
                },
              },
              {
                key: "drift_pct",
                header: "Drift %",
                align: "end",
                cell: (row) => (row.drift_pct != null ? `${Number(row.drift_pct).toFixed(1)}%` : "—"),
              },
              {
                key: "drift_state",
                header: "State",
                cell: (row) => {
                  const badge = stateIndicatorBadge(row.state ?? row.drift_state);
                  return (
                    <>
                      <span style={{ color: badge.color }}>{badge.label}</span>
                      <span className="muted" style={{ display: "block", fontSize: "0.8rem" }}>
                        {row.drift_state}
                      </span>
                    </>
                  );
                },
              },
            ]}
          />
        </article>

        {/* Variance filters */}
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Filters</div>
              <h2>Variance by period</h2>
            </div>
          </div>
          <form className="formGrid fourCol" method="get">
            <div className="field">
              <label htmlFor="budget_name">Budget name</label>
              <input
                id="budget_name"
                name="budget_name"
                type="text"
                defaultValue={budgetName}
                placeholder="e.g. Monthly Budget"
              />
            </div>
            <div className="field">
              <label htmlFor="category">Category</label>
              <input
                id="category"
                name="category"
                type="text"
                defaultValue={category}
                placeholder="e.g. groceries"
              />
            </div>
            <div className="field">
              <label htmlFor="period_label">Period</label>
              <input
                id="period_label"
                name="period_label"
                type="text"
                defaultValue={periodLabel}
                placeholder="e.g. 2026-01"
                list="period-options"
              />
              {periods.length > 0 && (
                <datalist id="period-options">
                  {periods.map((p) => (
                    <option key={p} value={p} />
                  ))}
                </datalist>
              )}
            </div>
            <div className="field" style={{ alignSelf: "flex-end" }}>
              <button type="submit" className="btn">Apply</button>
            </div>
          </form>
        </article>

        {/* Variance table */}
        <article className="panel section">
          <ResponsiveTable
            label="Budget variance by period"
            rows={variance}
            empty={<p className="muted">No budget variance data for the selected filters.</p>}
            columns={[
              { key: "budget_name", header: "Budget", primary: true },
              { key: "category_id", header: "Category" },
              { key: "period_label", header: "Period" },
              { key: "target_amount", header: "Target", align: "end", cell: (row) => money(row.target_amount, row.currency) },
              { key: "actual_amount", header: "Actual", align: "end", cell: (row) => money(row.actual_amount, row.currency) },
              {
                key: "variance",
                header: "Variance",
                align: "end",
                cell: (row) => {
                  const varianceAmt = Number(row.variance);
                  return (
                    <span style={{ color: varianceAmt >= 0 ? "var(--ok)" : "var(--warn)" }}>
                      {varianceAmt >= 0 ? "+" : ""}
                      {varianceAmt.toFixed(2)} {row.currency}
                    </span>
                  );
                },
              },
              {
                key: "variance_pct",
                header: "%",
                align: "end",
                cell: (row) => (row.variance_pct != null ? `${Number(row.variance_pct).toFixed(1)}%` : "—"),
              },
              {
                key: "status",
                header: "Status",
                cell: (row) => {
                  const badge = stateIndicatorBadge(row.state ?? row.status);
                  return (
                    <>
                      <span style={{ color: badge.color }}>{badge.label}</span>
                      <span className="muted" style={{ display: "block", fontSize: "0.8rem" }}>
                        {row.status}
                      </span>
                    </>
                  );
                },
              },
            ]}
          />
        </article>
      </section>
    </AppShell>
  );
}
