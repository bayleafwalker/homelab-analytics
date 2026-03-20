import { AppShell } from "@/components/app-shell";
import { getCostTrend, getCurrentUser, getHouseholdCostModel } from "@/lib/backend";

const COST_TYPE_LABELS = {
  housing: "Housing",
  utilities: "Utilities",
  transport: "Transport",
  food: "Food",
  subscriptions: "Subscriptions",
  loans: "Loans",
  discretionary: "Discretionary",
  other: "Other",
};

const COST_TYPE_COLORS = {
  housing: "var(--accent)",
  utilities: "#6ab0f5",
  transport: "#f5a623",
  food: "#7ed321",
  subscriptions: "#bd10e0",
  loans: "#d0021b",
  discretionary: "#9b9b9b",
  other: "#4a4a4a",
};

function formatAmount(val, currency) {
  if (val == null || val === "") return "—";
  return `${Number(val).toLocaleString("en-IE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${currency ? ` ${currency}` : ""}`;
}

export default async function CostsPage({ searchParams }) {
  const user = await getCurrentUser();
  const periodLabel = searchParams?.period_label || undefined;
  const costType = searchParams?.cost_type || undefined;

  const [costModel, trend] = await Promise.all([
    getHouseholdCostModel(periodLabel, costType),
    getCostTrend(),
  ]);

  // Aggregate by cost_type for the selected period (or all periods)
  const byType = {};
  for (const row of costModel) {
    const t = row.cost_type;
    if (!byType[t]) byType[t] = { amount: 0, currency: row.currency };
    byType[t].amount += Number(row.amount);
  }

  const totalAmount = Object.values(byType).reduce((s, v) => s + v.amount, 0);

  // Available periods from trend data
  const periods = [...new Set(trend.map((r) => r.period_label))].sort().reverse();

  return (
    <AppShell
      currentPath="/costs"
      user={user}
      title="Costs"
      eyebrow="Reader Access"
      lede="Unified household cost model across all domains — finance, utilities, subscriptions, and loans."
    >
      <section className="stack">
        {/* Filters */}
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Filters</div>
              <h2>Cost model</h2>
            </div>
          </div>
          <form className="formGrid threeCol" method="get">
            <div className="field">
              <label htmlFor="period_label">Period</label>
              <input
                id="period_label"
                name="period_label"
                type="text"
                defaultValue={periodLabel || ""}
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
            <div className="field">
              <label htmlFor="cost_type">Cost type</label>
              <select id="cost_type" name="cost_type" defaultValue={costType || ""}>
                <option value="">All types</option>
                {Object.entries(COST_TYPE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div className="field" style={{ alignSelf: "flex-end" }}>
              <button type="submit" className="btn">Apply</button>
            </div>
          </form>
        </article>

        {/* Cost breakdown cards */}
        {Object.keys(byType).length === 0 ? (
          <div className="empty">No cost data available for the selected filters.</div>
        ) : (
          <section className="cards">
            {Object.entries(byType)
              .sort((a, b) => b[1].amount - a[1].amount)
              .map(([type, { amount, currency }]) => {
                const pct = totalAmount > 0 ? (amount / totalAmount) * 100 : 0;
                return (
                  <article key={type} className="panel section">
                    <div className="sectionHeader">
                      <div>
                        <div
                          className="eyebrow"
                          style={{ color: COST_TYPE_COLORS[type] || "inherit" }}
                        >
                          {COST_TYPE_LABELS[type] || type}
                        </div>
                        <div className="metricValue">{formatAmount(amount, currency)}</div>
                      </div>
                      <span className="metricLabel">{pct.toFixed(1)}%</span>
                    </div>
                    <div
                      style={{
                        height: "4px",
                        background: "var(--surface-2)",
                        borderRadius: "2px",
                        overflow: "hidden",
                        marginTop: "0.5rem",
                      }}
                    >
                      <div
                        style={{
                          width: `${pct}%`,
                          height: "100%",
                          background: COST_TYPE_COLORS[type] || "var(--accent)",
                        }}
                      />
                    </div>
                  </article>
                );
              })}
          </section>
        )}

        {/* 12-month trend table */}
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Trend</div>
              <h2>12-month rolling costs</h2>
            </div>
          </div>
          <div className="tableWrap">
            {trend.length === 0 ? (
              <p className="muted">No trend data available.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Cost type</th>
                    <th>Amount</th>
                    <th>Prev</th>
                    <th>Change</th>
                  </tr>
                </thead>
                <tbody>
                  {trend.map((row, i) => {
                    const changePct = row.change_pct != null ? Number(row.change_pct) : null;
                    return (
                      <tr key={i}>
                        <td>{row.period_label}</td>
                        <td>{COST_TYPE_LABELS[row.cost_type] || row.cost_type}</td>
                        <td>{formatAmount(row.amount, row.currency)}</td>
                        <td>{row.prev_amount != null ? formatAmount(row.prev_amount, row.currency) : "—"}</td>
                        <td
                          style={{
                            color:
                              changePct == null
                                ? "inherit"
                                : changePct > 10
                                ? "var(--error)"
                                : changePct < -10
                                ? "var(--ok)"
                                : "inherit",
                          }}
                        >
                          {changePct != null
                            ? `${changePct >= 0 ? "+" : ""}${changePct.toFixed(1)}%`
                            : "—"}
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
