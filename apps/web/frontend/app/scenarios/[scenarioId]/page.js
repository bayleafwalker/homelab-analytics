import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import {
  getCurrentUser,
  getScenarioCashflow,
  getScenarioComparison,
  getScenarioMetadata,
} from "@/lib/backend";

function fmt(val) {
  if (val == null || val === "") return "—";
  const n = Number(val);
  if (isNaN(n)) return String(val);
  return n.toLocaleString("en-IE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function deltaStyle(val) {
  if (val == null) return {};
  const n = Number(val);
  if (n < 0) return { color: "var(--ok)" };
  if (n > 0) return { color: "var(--warning)" };
  return {};
}

function sign(val) {
  const n = Number(val);
  return n >= 0 ? `+${fmt(val)}` : fmt(val);
}

export default async function ScenarioDetailPage({ params }) {
  const { scenarioId } = params;
  const user = await getCurrentUser();
  const scenario = await getScenarioMetadata(scenarioId);

  let comparison = null;
  let cashflow = null;

  if (scenario.scenario_type === "loan_what_if") {
    comparison = await getScenarioComparison(scenarioId);
  } else {
    cashflow = await getScenarioCashflow(scenarioId);
  }

  const isStale = comparison?.is_stale || cashflow?.is_stale;
  const assumptions = comparison?.assumptions || cashflow?.assumptions || [];
  const summaryRows = cashflow?.summary_rows || [];

  return (
    <AppShell
      currentPath="/scenarios"
      user={user}
      title={scenario.label}
      eyebrow="Scenario comparison"
      lede={isStale ? "This scenario may be stale — the underlying data has changed since it was created." : undefined}
    >
      <section className="stack">
        <div>
          <Link href="/scenarios" style={{ color: "var(--accent)" }}>
            ← Back to scenarios
          </Link>
        </div>

        {/* Loan what-if: repayment variance table */}
        {comparison?.variance_rows?.length > 0 && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Repayment variance</div>
                <h2>Baseline vs scenario</h2>
              </div>
            </div>
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Date</th>
                    <th>Baseline payment</th>
                    <th>Scenario payment</th>
                    <th>Payment delta</th>
                    <th>Scenario balance</th>
                    <th>Balance delta</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.variance_rows.map((row) => (
                    <tr key={row.period}>
                      <td>{row.period}</td>
                      <td>{row.payment_date}</td>
                      <td>{fmt(row.baseline_payment)} {row.currency}</td>
                      <td>{fmt(row.scenario_payment)} {row.currency}</td>
                      <td style={deltaStyle(row.payment_delta)}>
                        {row.payment_delta != null ? `${sign(row.payment_delta)} ${row.currency}` : "—"}
                      </td>
                      <td>{fmt(row.scenario_balance)} {row.currency}</td>
                      <td style={deltaStyle(row.balance_delta)}>
                        {row.balance_delta != null ? `${sign(row.balance_delta)} ${row.currency}` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        )}

        {/* Income/expense shock: cashflow projection */}
        {cashflow?.cashflow_rows?.length > 0 && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Cashflow projection</div>
                <h2>12-month outlook</h2>
              </div>
            </div>
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Month</th>
                    <th>Baseline income</th>
                    <th>Scenario income</th>
                    <th>Expenses</th>
                    <th>Baseline net</th>
                    <th>Scenario net</th>
                    <th>Net delta</th>
                  </tr>
                </thead>
                <tbody>
                  {cashflow.cashflow_rows.map((row) => {
                    const netDelta = Number(row.net_delta);
                    return (
                      <tr key={row.period}>
                        <td>{row.period}</td>
                        <td>{row.projected_month}</td>
                        <td>{fmt(row.baseline_income)}</td>
                        <td>{fmt(row.scenario_income)}</td>
                        <td>{fmt(row.baseline_expense)}</td>
                        <td>{fmt(row.baseline_net)}</td>
                        <td className={Number(row.scenario_net) < 0 ? "status-failed" : ""}>
                          {fmt(row.scenario_net)}
                        </td>
                        <td
                          className={
                            netDelta < 0
                              ? "status-failed"
                              : netDelta > 0
                              ? "status-completed"
                              : ""
                          }
                        >
                          {netDelta >= 0 ? "+" : ""}
                          {fmt(row.net_delta)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </article>
        )}

        {/* Homelab cost/benefit: summary-style comparison */}
        {summaryRows.length > 0 && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Cost/value summary</div>
                <h2>Baseline vs scenario</h2>
              </div>
            </div>
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Baseline</th>
                    <th>Scenario</th>
                    <th>Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {summaryRows.map((row, i) => {
                    const metric = row.metric || row.metric_name || row.summary_key || row.label || `metric_${i + 1}`;
                    const baselineValue = row.baseline_value ?? row.baseline ?? row.baseline_metric;
                    const scenarioValue = row.scenario_value ?? row.projected_value ?? row.scenario ?? row.projected_metric;
                    const deltaValue = row.delta_value ?? row.delta ?? row.metric_delta;
                    const unit = row.unit || row.currency || "";
                    return (
                      <tr key={`${metric}-${i}`}>
                        <td>{metric}</td>
                        <td>{baselineValue == null ? "—" : `${fmt(baselineValue)} ${unit}`.trim()}</td>
                        <td>{scenarioValue == null ? "—" : `${fmt(scenarioValue)} ${unit}`.trim()}</td>
                        <td style={deltaStyle(deltaValue)}>
                          {deltaValue == null ? "—" : `${sign(deltaValue)} ${unit}`.trim()}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </article>
        )}

        {/* Assumptions */}
        {assumptions.length > 0 && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Parameters</div>
                <h2>Assumptions</h2>
              </div>
            </div>
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Parameter</th>
                    <th>Baseline</th>
                    <th>Override</th>
                    <th>Unit</th>
                  </tr>
                </thead>
                <tbody>
                  {assumptions.map((a, i) => (
                    <tr key={i}>
                      <td>{a.assumption_key}</td>
                      <td>{a.baseline_value}</td>
                      <td>{a.override_value}</td>
                      <td>{a.unit || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        )}
      </section>
    </AppShell>
  );
}
