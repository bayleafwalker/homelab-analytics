"use client";

import { useState } from "react";

function fmt(val) {
  if (val == null) return "—";
  return Number(val).toLocaleString("en-IE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function TariffShockPanel() {
  const [open, setOpen] = useState(false);
  const [pct, setPct] = useState("");
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

    const pctDecimal = (parseFloat(pct) / 100).toFixed(6);
    const body = { tariff_pct_delta: pctDecimal, utility_type: "electricity" };
    if (label) body.label = label;

    try {
      const res = await fetch("/api/scenarios/tariff-shock", {
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
    setPct("");
    setLabel("");
    setResult(null);
    setCashflow(null);
    setError(null);
  }

  const pctNum = parseFloat(pct);
  const isIncrease = !Number.isNaN(pctNum) && pctNum > 0;

  return (
    <article className="panel section">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">Simulation</div>
          <h2>Tariff shock what-if</h2>
        </div>
        <button
          className="ghostButton"
          type="button"
          onClick={() => {
            setOpen((o) => !o);
            if (open) reset();
          }}
        >
          {open ? "Close" : "Run scenario"}
        </button>
      </div>

      {!open && (
        <p className="lede">
          Model the cashflow impact of an electricity tariff increase or decrease on the current utility base.
        </p>
      )}

      {open && (
        <>
          <form className="formGrid fourCol" onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="tariff-pct">Tariff change (%)</label>
              <input
                id="tariff-pct"
                type="number"
                step="0.1"
                placeholder="e.g. 10 or -5"
                value={pct}
                onChange={(e) => setPct(e.target.value)}
                required
              />
              <span className="fieldHint">Positive = higher utility tariff, negative = lower tariff</span>
            </div>
            <div className="field">
              <label htmlFor="tariff-label">Label (optional)</label>
              <input
                id="tariff-label"
                type="text"
                placeholder="e.g. Electricity tariff shock 2026"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
              />
            </div>
            <div className="field" style={{ display: "flex", alignItems: "flex-end", gap: "8px" }}>
              <button className="primaryButton" type="submit" disabled={loading || !pct}>
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
                  <div className="metricLabel">Tariff change</div>
                  <div className={`metricValue ${isIncrease ? "status-failed" : ""}`}>
                    {pctNum >= 0 ? "+" : ""}
                    {pctNum.toFixed(1)}%
                  </div>
                </div>
                <div className="metaItem">
                  <div className="metricLabel">Baseline utility cost</div>
                  <div className="metricValue">{fmt(result.baseline_monthly_utility_cost)}</div>
                </div>
                <div className="metaItem">
                  <div className="metricLabel">New utility cost</div>
                  <div className={`metricValue ${isIncrease ? "status-failed" : ""}`}>
                    {fmt(result.new_monthly_utility_cost)}
                  </div>
                </div>
                <div className="metaItem">
                  <div className="metricLabel">Annual additional cost</div>
                  <div className={`metricValue ${Number(result.annual_additional_cost) > 0 ? "status-failed" : ""}`}>
                    {Number(result.annual_additional_cost) > 0 ? "+" : ""}
                    {fmt(result.annual_additional_cost)}
                  </div>
                </div>
                {result.months_until_deficit != null && (
                  <div className="metaItem">
                    <div className="metricLabel">Months until deficit</div>
                    <div className="metricValue status-failed">{result.months_until_deficit}</div>
                  </div>
                )}
                {result.months_until_deficit == null && isIncrease && (
                  <div className="metaItem">
                    <div className="metricLabel">Deficit risk</div>
                    <div className="metricValue" style={{ color: "var(--ok)" }}>
                      None (income covers tariff shock)
                    </div>
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
                        <th>Income</th>
                        <th>Baseline expense</th>
                        <th>Scenario expense</th>
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
                            <td>{fmt(row.baseline_expense)}</td>
                            <td className={Number(row.scenario_expense) > Number(row.baseline_expense) ? "status-failed" : ""}>
                              {fmt(row.scenario_expense)}
                            </td>
                            <td>{fmt(row.baseline_net)}</td>
                            <td className={Number(row.scenario_net) < 0 ? "status-failed" : ""}>
                              {fmt(row.scenario_net)}
                            </td>
                            <td className={netDelta < 0 ? "status-failed" : netDelta > 0 ? "status-completed" : ""}>
                              {netDelta >= 0 ? "+" : ""}
                              {fmt(row.net_delta)}
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
                            <td>{a.baseline_value}</td>
                            <td>{a.override_value}</td>
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
