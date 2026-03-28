import { AppShell } from "@/components/app-shell";
import {
  getBudgetEnvelopes,
  getBudgetProgress,
  getBudgetVariance,
  getCurrentUser,
} from "@/lib/backend";
import { stateIndicatorBadge } from "@/lib/state-indicators";

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
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Budget</th>
                    <th>Category</th>
                    <th>Target</th>
                    <th>Spent</th>
                    <th>Remaining</th>
                    <th>Utilization</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {progress.map((row, i) => {
                    const pct = Number(row.utilization_pct);
                    const badge = stateIndicatorBadge(row.state ?? row.status);
                    return (
                      <tr key={i}>
                        <td>{row.budget_name}</td>
                        <td>{row.category_id}</td>
                        <td>{Number(row.target_amount).toFixed(2)} {row.currency}</td>
                        <td>{Number(row.spent_amount).toFixed(2)} {row.currency}</td>
                        <td>{Number(row.remaining).toFixed(2)} {row.currency}</td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <div
                              style={{
                                width: "80px",
                                height: "8px",
                                background: "var(--surface-2)",
                                borderRadius: "4px",
                                overflow: "hidden",
                              }}
                            >
                              <div
                                style={{
                                  width: `${Math.min(pct, 100)}%`,
                                  height: "100%",
                                  background: badge.color,
                                  borderRadius: "4px",
                                }}
                              />
                            </div>
                            <span>{pct.toFixed(0)}%</span>
                          </div>
                        </td>
                        <td>
                          <span style={{ color: badge.color }}>{badge.label}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
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
          <div className="tableWrap">
            {envelopes.length === 0 ? (
              <p className="muted">No budget envelope data for the selected filters.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Budget</th>
                    <th>Category</th>
                    <th>Period</th>
                    <th>Envelope</th>
                    <th>Actual</th>
                    <th>Drift</th>
                    <th>Drift %</th>
                    <th>State</th>
                  </tr>
                </thead>
                <tbody>
                  {envelopes.map((row, i) => {
                    const driftAmt = Number(row.drift_amount);
                    const badge = stateIndicatorBadge(row.state ?? row.drift_state);
                    return (
                      <tr key={i}>
                        <td>{row.budget_name}</td>
                        <td>{row.category_id}</td>
                        <td>{row.period_label}</td>
                        <td>{Number(row.envelope_amount).toFixed(2)} {row.currency}</td>
                        <td>{Number(row.actual_amount).toFixed(2)} {row.currency}</td>
                        <td style={{ color: driftAmt <= 0 ? "var(--ok)" : "var(--error)" }}>
                          {driftAmt <= 0 ? "" : "+"}
                          {driftAmt.toFixed(2)} {row.currency}
                        </td>
                        <td>
                          {row.drift_pct != null ? `${Number(row.drift_pct).toFixed(1)}%` : "—"}
                        </td>
                        <td>
                          <span style={{ color: badge.color }}>{badge.label}</span>
                          <div className="muted" style={{ fontSize: "0.8rem" }}>
                            {row.drift_state}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
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
          <div className="tableWrap">
            {variance.length === 0 ? (
              <p className="muted">No budget variance data for the selected filters.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Budget</th>
                    <th>Category</th>
                    <th>Period</th>
                    <th>Target</th>
                    <th>Actual</th>
                    <th>Variance</th>
                    <th>%</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {variance.map((row, i) => {
                    const badge = stateIndicatorBadge(row.state ?? row.status);
                    const varianceAmt = Number(row.variance);
                    return (
                      <tr key={i}>
                        <td>{row.budget_name}</td>
                        <td>{row.category_id}</td>
                        <td>{row.period_label}</td>
                        <td>{Number(row.target_amount).toFixed(2)} {row.currency}</td>
                        <td>{Number(row.actual_amount).toFixed(2)} {row.currency}</td>
                        <td style={{ color: varianceAmt >= 0 ? "var(--ok)" : "var(--error)" }}>
                          {varianceAmt >= 0 ? "+" : ""}
                          {varianceAmt.toFixed(2)} {row.currency}
                        </td>
                        <td>
                          {row.variance_pct != null
                            ? `${Number(row.variance_pct).toFixed(1)}%`
                            : "—"}
                        </td>
                        <td>
                          <span style={{ color: badge.color }}>{badge.label}</span>
                          <div className="muted" style={{ fontSize: "0.8rem" }}>
                            {row.status}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </article>
      </section>
    </AppShell>
  );
}
