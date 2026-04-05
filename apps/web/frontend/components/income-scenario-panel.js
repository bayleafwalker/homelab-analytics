"use client";

import { useState } from "react";

function fmt(val, currency) {
  if (val == null) return "—";
  return `${Number(val).toLocaleString("en-IE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${currency ? " " + currency : ""}`;
}

export function IncomeScenarioPanel() {
  const [open, setOpen] = useState(false);
  const [delta, setDelta] = useState("");
  const [label, setLabel] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [cashflow, setCashflow] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setCashflow(null);

    const body = { monthly_income_delta: delta };
    if (label) body.label = label;

    try {
      const res = await fetch("/api/scenarios/income-change", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || "Failed to create scenario.");
        return;
      }
      const data = await res.json();
      setResult(data);

      const cfRes = await fetch(`/api/scenarios/${data.scenario_id}/cashflow`);
      if (cfRes.ok) {
        setCashflow(await cfRes.json());
      }
    } catch {
      setError("Network error — could not reach API.");
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setDelta("");
    setLabel("");
    setResult(null);
    setCashflow(null);
    setError(null);
  }

  const deltaNum = parseFloat(delta);
  const isNegative = !isNaN(deltaNum) && deltaNum < 0;

  return (
    <article className="panel section">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">Simulation</div>
          <h2>Income change what-if</h2>
        </div>
        <button
          className="ghostButton"
          type="button"
          onClick={() => { setOpen((o) => !o); if (open) reset(); }}
        >
          {open ? "Close" : "Run scenario"}
        </button>
      </div>

      {!open && (
        <p className="lede">
          Model the household cashflow impact of an income increase, decrease, or job loss over 12 months.
        </p>
      )}

      {open && (
        <>
          <form className="formGrid fourCol" onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="income-delta">Monthly income change</label>
              <input
                id="income-delta"
                type="number"
                step="0.01"
                placeholder="e.g. -2000 or 500"
                value={delta}
                onChange={(e) => setDelta(e.target.value)}
                required
              />
              <span className="fieldHint">Negative = income loss</span>
            </div>
            <div className="field">
              <label htmlFor="income-label">Label (optional)</label>
              <input
                id="income-label"
                type="text"
                placeholder="e.g. Job loss scenario"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
              />
            </div>
            <div className="field" style={{ display: "flex", alignItems: "flex-end", gap: "8px" }}>
              <button className="primaryButton" type="submit" disabled={loading || !delta}>
                {loading ? "Running…" : "Run"}
              </button>
              <button className="ghostButton" type="button" onClick={reset}>
                Reset
              </button>
            </div>
          </form>

          {error && <div className="errorBanner">{error}</div>}

          {result && (
            <div className="stack" style={{ marginTop: "1rem" }}>
              <div className="metaGrid">
                <div className="metaItem">
                  <div className="metricLabel">Monthly income change</div>
                  <div className={`metricValue ${isNegative ? "status-failed" : ""}`}>
                    {deltaNum >= 0 ? "+" : ""}{fmt(result.monthly_income_delta)}
                  </div>
                </div>
                <div className="metaItem">
                  <div className="metricLabel">Baseline monthly income</div>
                  <div className="metricValue">{fmt(result.baseline_monthly_income)}</div>
                </div>
                <div className="metaItem">
                  <div className="metricLabel">New monthly income</div>
                  <div className="metricValue">{fmt(result.new_monthly_income)}</div>
                </div>
                <div className="metaItem">
                  <div className="metricLabel">Annual net change</div>
                  <div className={`metricValue ${Number(result.annual_net_change) < 0 ? "status-failed" : ""}`}>
                    {Number(result.annual_net_change) >= 0 ? "+" : ""}{fmt(result.annual_net_change)}
                  </div>
                </div>
                {result.months_until_deficit != null && (
                  <div className="metaItem">
                    <div className="metricLabel">Months until deficit</div>
                    <div className="metricValue status-failed">{result.months_until_deficit}</div>
                  </div>
                )}
                {result.months_until_deficit == null && isNegative && (
                  <div className="metaItem">
                    <div className="metricLabel">Deficit risk</div>
                    <div className="metricValue" style={{ color: "var(--ok)" }}>None (income covers expenses)</div>
                  </div>
                )}
              </div>

              {cashflow && cashflow.cashflow_rows && cashflow.cashflow_rows.length > 0 && (
                <div className="tableWrap" style={{ marginTop: "1rem" }}>
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
                            <td className={netDelta < 0 ? "status-failed" : netDelta > 0 ? "status-completed" : ""}>
                              {netDelta >= 0 ? "+" : ""}{fmt(row.net_delta)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {cashflow && cashflow.assumptions && cashflow.assumptions.length > 0 && (
                <details style={{ marginTop: "0.75rem" }}>
                  <summary style={{ cursor: "pointer", color: "var(--text-2)" }}>Assumptions</summary>
                  <div className="tableWrap" style={{ marginTop: "0.5rem" }}>
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
                        {cashflow.assumptions.map((a, i) => (
                          <tr key={i}>
                            <td>{a.assumption_key}</td>
                            <td>{fmt(a.baseline_value)}</td>
                            <td>{fmt(a.override_value)}</td>
                            <td>{a.unit || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              )}
            </div>
          )}
        </>
      )}
    </article>
  );
}
