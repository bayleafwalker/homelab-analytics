"use client";

import Link from "next/link";
import { useState } from "react";

function fmt(val) {
  if (val == null) return "—";
  return Number(val).toLocaleString("en-IE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function HomelabCostBenefitPanel() {
  const [open, setOpen] = useState(false);
  const [monthlyCostDelta, setMonthlyCostDelta] = useState("");
  const [label, setLabel] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [compareHref, setCompareHref] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setComparison(null);
    setCompareHref("");

    const body = { monthly_cost_delta: monthlyCostDelta };
    if (label) body.label = label;

    try {
      const res = await fetch("/api/scenarios/homelab-cost-benefit", {
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

      const comparisonRes = await fetch(`/api/scenarios/${data.scenario_id}/comparison`);
      if (comparisonRes.ok) {
        setComparison(await comparisonRes.json());
      }

      const scenariosRes = await fetch("/api/scenarios");
      if (scenariosRes.ok) {
        const scenariosPayload = await scenariosRes.json();
        const partnerScenario = (scenariosPayload.rows || []).find(
          (scenario) => scenario.scenario_id !== data.scenario_id,
        );
        if (partnerScenario?.scenario_id) {
          setCompareHref(
            `/scenarios/compare?left=${encodeURIComponent(data.scenario_id)}&right=${encodeURIComponent(partnerScenario.scenario_id)}`,
          );
        } else {
          setCompareHref(`/scenarios/compare?left=${encodeURIComponent(data.scenario_id)}`);
        }
      } else {
        setCompareHref(`/scenarios/compare?left=${encodeURIComponent(data.scenario_id)}`);
      }
    } catch {
      setError("Network error — could not reach API.");
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setMonthlyCostDelta("");
    setLabel("");
    setResult(null);
    setComparison(null);
    setCompareHref("");
    setError(null);
  }

  const deltaValue = Number(monthlyCostDelta);
  const isSavings = Number.isFinite(deltaValue) && deltaValue < 0;

  return (
    <div
      style={{
        marginTop: "1rem",
        padding: "1rem",
        background: "var(--surface-1)",
        border: "1px solid var(--line)",
        borderRadius: "16px",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "12px",
          marginBottom: open ? "0.85rem" : 0,
        }}
      >
        <div>
          <div className="eyebrow">Scenario</div>
          <strong>Homelab cost/benefit</strong>
        </div>
        <button
          className="ghostButton"
          type="button"
          onClick={() => {
            setOpen((current) => !current);
            if (open) reset();
          }}
        >
          {open ? "Close" : "Run scenario"}
        </button>
      </div>

      {!open && (
        <p className="muted" style={{ margin: 0 }}>
          Model the cost impact of a monthly homelab change against the current ROI report.
        </p>
      )}

      {open && (
        <>
          <form className="formGrid threeCol" onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="homelab-monthly-cost-delta">Monthly cost delta</label>
              <input
                id="homelab-monthly-cost-delta"
                type="number"
                step="0.01"
                placeholder="e.g. -12.50"
                value={monthlyCostDelta}
                onChange={(e) => setMonthlyCostDelta(e.target.value)}
                required
              />
              <span className="fieldHint">Negative = savings, positive = additional spend</span>
            </div>
            <div className="field">
              <label htmlFor="homelab-scenario-label">Label (optional)</label>
              <input
                id="homelab-scenario-label"
                type="text"
                placeholder="e.g. Storage consolidation"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
              />
            </div>
            <div className="field" style={{ display: "flex", alignItems: "flex-end", gap: "8px" }}>
              <button className="primaryButton" type="submit" disabled={loading || !monthlyCostDelta}>
                {loading ? "Running…" : "Run"}
              </button>
              <button className="ghostButton" type="button" onClick={reset}>
                Reset
              </button>
            </div>
          </form>

          {error && <div className="errorBanner" style={{ marginTop: "0.75rem" }}>{error}</div>}

          {result && (
            <div style={{ marginTop: "1rem" }}>
              {(result.is_stale || comparison?.is_stale) && (
                <div className="errorBanner" style={{ marginBottom: "0.75rem" }}>
                  This scenario was computed against an older data run — results may be outdated.
                </div>
              )}

              <div className="metaGrid" style={{ marginBottom: "1rem" }}>
                <div className="metaItem">
                  <div className="metricLabel">Monthly cost delta</div>
                  <div className={`metricValue ${isSavings ? "status-completed" : "status-failed"}`}>
                    {deltaValue >= 0 ? "+" : ""}
                    {fmt(result.monthly_cost_delta)}
                  </div>
                </div>
                <div className="metaItem">
                  <div className="metricLabel">Baseline monthly cost</div>
                  <div className="metricValue">{fmt(result.baseline_monthly_cost)}</div>
                </div>
                <div className="metaItem">
                  <div className="metricLabel">New monthly cost</div>
                  <div className={`metricValue ${isSavings ? "status-completed" : "status-failed"}`}>
                    {fmt(result.new_monthly_cost)}
                  </div>
                </div>
                <div className="metaItem">
                  <div className="metricLabel">Annual cost delta</div>
                  <div className={`metricValue ${Number(result.annual_cost_delta) < 0 ? "status-completed" : "status-failed"}`}>
                    {Number(result.annual_cost_delta) >= 0 ? "+" : ""}
                    {fmt(result.annual_cost_delta)}
                  </div>
                </div>
              </div>

              <div className="buttonRow">
                <Link className="primaryButton inlineButton" href={`/scenarios/${result.scenario_id}`}>
                  View scenario
                </Link>
                <Link className="ghostButton inlineButton" href={compareHref || `/scenarios/compare?left=${encodeURIComponent(result.scenario_id)}`}>
                  Compare scenarios
                </Link>
                <button className="ghostButton inlineButton" type="button" onClick={reset}>
                  Run another
                </button>
              </div>

              {comparison?.summary_rows?.length > 0 && (
                <div style={{ marginTop: "1rem" }}>
                  <div className="eyebrow" style={{ marginBottom: "0.35rem" }}>Cost/value summary</div>
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
                        {comparison.summary_rows.map((row, index) => {
                          const metric = row.metric || row.metric_name || row.summary_key || row.label || `metric_${index + 1}`;
                          const baselineValue = row.baseline_value ?? row.baseline ?? row.baseline_metric;
                          const scenarioValue = row.scenario_value ?? row.projected_value ?? row.scenario ?? row.projected_metric;
                          const deltaValue = row.delta_value ?? row.delta ?? row.metric_delta;
                          const unit = row.unit || row.currency || "";
                          return (
                            <tr key={`${metric}-${index}`}>
                              <td>{metric}</td>
                              <td>{baselineValue == null ? "—" : `${fmt(baselineValue)} ${unit}`.trim()}</td>
                              <td>{scenarioValue == null ? "—" : `${fmt(scenarioValue)} ${unit}`.trim()}</td>
                              <td>
                                {deltaValue == null ? "—" : `${Number(deltaValue) >= 0 ? "+" : ""}${fmt(deltaValue)} ${unit}`.trim()}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {comparison?.assumptions?.length > 0 && (
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
                        {comparison.assumptions.map((a, i) => (
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
    </div>
  );
}
