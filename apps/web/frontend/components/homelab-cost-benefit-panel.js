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

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

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
      setResult(await res.json());
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
              {result.is_stale && (
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
                <button className="ghostButton inlineButton" type="button" onClick={reset}>
                  Run another
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
