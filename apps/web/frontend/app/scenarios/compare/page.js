import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import {
  getCurrentUser,
  getScenarioCashflow,
  getScenarioComparison,
  getScenarioMetadata,
  getScenarios,
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

const TYPE_LABELS = {
  loan_what_if: "Loan what-if",
  income_change: "Income change",
  expense_shock: "Expense shock",
  tariff_shock: "Tariff shock",
  homelab_cost_benefit: "Homelab cost/benefit",
};

const TYPE_COLORS = {
  loan_what_if: "var(--accent)",
  income_change: "var(--ok)",
  expense_shock: "var(--warning)",
  tariff_shock: "var(--warning)",
  homelab_cost_benefit: "var(--accent-2)",
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

async function loadScenarioSnapshot(scenarioId) {
  const scenario = await getScenarioMetadata(scenarioId);
  let comparison = null;
  let cashflow = null;

  if (scenario.scenario_type === "loan_what_if") {
    comparison = await getScenarioComparison(scenarioId);
  } else {
    cashflow = await getScenarioCashflow(scenarioId);
  }

  return { scenario, comparison, cashflow };
}

function ComparisonPanel({ snapshot, title }) {
  const { scenario, comparison, cashflow } = snapshot;
  const isStale = comparison?.is_stale || cashflow?.is_stale;
  const assumptions = comparison?.assumptions || cashflow?.assumptions || [];
  const summaryRows = cashflow?.summary_rows || [];

  return (
    <article className="panel section">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">{title}</div>
          <h2>{scenario.label}</h2>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.5rem" }}>
            {typeBadge(scenario.scenario_type)}
            <span className={`statusPill ${isStale ? "warning" : "positive"}`}>
              {isStale ? "stale" : "current"}
            </span>
          </div>
        </div>
      </div>

      <div className="stack">
        <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
          <div className="panel" style={{ padding: "0.75rem" }}>
            <div className="eyebrow">Scenario ID</div>
            <div>{scenario.scenario_id}</div>
          </div>
          <div className="panel" style={{ padding: "0.75rem" }}>
            <div className="eyebrow">Created</div>
            <div>{scenario.created_at ? scenario.created_at.slice(0, 10) : "—"}</div>
          </div>
          <div className="panel" style={{ padding: "0.75rem" }}>
            <div className="eyebrow">Subject</div>
            <div>{scenario.subject_id || "—"}</div>
          </div>
        </div>

        {/* Loan what-if: repayment variance table */}
        {comparison?.variance_rows?.length > 0 && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Repayment variance</div>
                <h3>Baseline vs scenario</h3>
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
                      <td>
                        {fmt(row.baseline_payment)} {row.currency}
                      </td>
                      <td>
                        {fmt(row.scenario_payment)} {row.currency}
                      </td>
                      <td style={deltaStyle(row.payment_delta)}>
                        {row.payment_delta != null ? `${sign(row.payment_delta)} ${row.currency}` : "—"}
                      </td>
                      <td>
                        {fmt(row.scenario_balance)} {row.currency}
                      </td>
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
                <h3>12-month outlook</h3>
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
                <h3>Baseline vs scenario</h3>
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
                    const metric =
                      row.metric || row.metric_name || row.summary_key || row.label || `metric_${i + 1}`;
                    const baselineValue = row.baseline_value ?? row.baseline ?? row.baseline_metric;
                    const scenarioValue =
                      row.scenario_value ?? row.projected_value ?? row.scenario ?? row.projected_metric;
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

        {assumptions.length > 0 && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Parameters</div>
                <h3>Assumptions</h3>
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
      </div>
    </article>
  );
}

export default async function ScenariosComparePage({ searchParams }) {
  const user = await getCurrentUser();
  const scenarios = await getScenarios();
  const scenarioIdSet = new Set(scenarios.map((row) => row.scenario_id));

  const fallbackLeft = scenarios[0]?.scenario_id || "";
  const fallbackRight = scenarios[1]?.scenario_id || scenarios[0]?.scenario_id || "";
  const leftScenarioCandidate =
    typeof searchParams?.left === "string" && searchParams.left
      ? searchParams.left
      : fallbackLeft;
  const rightScenarioCandidate =
    typeof searchParams?.right === "string" && searchParams.right
      ? searchParams.right
      : fallbackRight;
  const leftScenarioId = scenarioIdSet.has(leftScenarioCandidate) ? leftScenarioCandidate : fallbackLeft;
  const rightScenarioId =
    scenarioIdSet.has(rightScenarioCandidate) ? rightScenarioCandidate : fallbackRight;

  const hasSelection = leftScenarioId && rightScenarioId;
  const sameScenario = leftScenarioId && rightScenarioId && leftScenarioId === rightScenarioId;

  const [leftSnapshot, rightSnapshot] = hasSelection
    ? await Promise.all([loadScenarioSnapshot(leftScenarioId), loadScenarioSnapshot(rightScenarioId)])
    : [null, null];

  const leftScenario = leftSnapshot?.scenario || null;
  const rightScenario = rightSnapshot?.scenario || null;

  return (
    <AppShell
      currentPath="/scenarios"
      user={user}
      title="Compare scenarios"
      eyebrow="Simulation History"
      lede="Pick two saved scenarios and view their assumptions and outcomes side by side."
    >
      <section className="stack">
        <div>
          <Link href="/scenarios" style={{ color: "var(--accent)" }}>
            ← Back to scenarios
          </Link>
        </div>

        <article className="panel section">
          <form method="get" className="stack" style={{ gap: "1rem" }}>
            <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
              <label className="stack" style={{ gap: "0.35rem" }}>
                <span className="eyebrow">Left scenario</span>
                <select
                  name="left"
                  defaultValue={leftScenarioId}
                  style={{ padding: "0.75rem", borderRadius: "8px" }}
                >
                  {scenarios.map((row) => (
                    <option key={row.scenario_id} value={row.scenario_id}>
                      {row.label} ({TYPE_LABELS[row.scenario_type] || row.scenario_type})
                    </option>
                  ))}
                </select>
              </label>

              <label className="stack" style={{ gap: "0.35rem" }}>
                <span className="eyebrow">Right scenario</span>
                <select
                  name="right"
                  defaultValue={rightScenarioId}
                  style={{ padding: "0.75rem", borderRadius: "8px" }}
                >
                  {scenarios.map((row) => (
                    <option key={row.scenario_id} value={row.scenario_id}>
                      {row.label} ({TYPE_LABELS[row.scenario_type] || row.scenario_type})
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
              <button type="submit" className="primaryButton">
                Compare scenarios
              </button>
              <span className="muted" style={{ alignSelf: "center" }}>
                Use two different saved scenarios to inspect their assumptions and outputs side by side.
              </span>
            </div>
          </form>
        </article>

        {!hasSelection && (
          <article className="panel section">
            <p className="muted">
              Pick two different scenarios to compare. If there is only one scenario, create another one from the
              Loans or Reports pages first.
            </p>
          </article>
        )}

        {sameScenario && (
          <article className="panel section">
            <p className="muted">
              The same scenario is selected on both sides. That is safe, but the view will duplicate the snapshot
              until you choose a different right-hand scenario.
            </p>
          </article>
        )}

        {leftSnapshot && rightSnapshot && (
          <div
            className="grid gap-4"
            style={{ gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", alignItems: "start" }}
          >
            <ComparisonPanel snapshot={leftSnapshot} title="Scenario A" />
            <ComparisonPanel snapshot={rightSnapshot} title="Scenario B" />
          </div>
        )}

        {leftSnapshot && rightSnapshot && leftScenario && rightScenario && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">At a glance</div>
                <h2>{leftScenario.label} vs {rightScenario.label}</h2>
              </div>
            </div>
            <p className="muted">
              This page compares the saved scenario snapshots directly. Open each scenario detail page for the
              single-scenario baseline view.
            </p>
          </article>
        )}
      </section>
    </AppShell>
  );
}
