"use client";

import { useState } from "react";

function fmt(val, currency) {
  if (val == null) return "—";
  return `${Number(val).toLocaleString("en-IE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency || ""}`;
}

function fmtDate(iso) {
  if (!iso) return "—";
  return iso.slice(0, 7); // YYYY-MM
}

export function LoanWhatIfPanel({ loanId, loanName, currency }) {
  const [open, setOpen] = useState(false);
  const [extraRepayment, setExtraRepayment] = useState("");
  const [annualRate, setAnnualRate] = useState("");
  const [termMonths, setTermMonths] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [comparison, setComparison] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setComparison(null);

    const body = { loan_id: loanId };
    if (extraRepayment) body.extra_repayment = extraRepayment;
    if (annualRate) body.annual_rate = annualRate;
    if (termMonths) body.term_months = parseInt(termMonths, 10);

    try {
      const res = await fetch("/api/scenarios/loan-what-if", {
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

      // Fetch comparison
      const compRes = await fetch(`/api/scenarios/${data.scenario_id}/comparison`);
      if (compRes.ok) {
        setComparison(await compRes.json());
      }
    } catch {
      setError("Network error — could not reach API.");
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setOpen(false);
    setResult(null);
    setComparison(null);
    setError(null);
    setExtraRepayment("");
    setAnnualRate("");
    setTermMonths("");
  }

  if (!open) {
    return (
      <button
        className="ghostButton"
        style={{ marginTop: "0.75rem", fontSize: "0.85rem" }}
        onClick={() => setOpen(true)}
      >
        What-if…
      </button>
    );
  }

  return (
    <div
      style={{
        marginTop: "1rem",
        padding: "1rem",
        background: "var(--surface-1)",
        border: "1px solid var(--border)",
        borderRadius: "6px",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "0.75rem",
        }}
      >
        <strong>What-if: {loanName}</strong>
        <button className="ghostButton" onClick={reset} style={{ fontSize: "0.8rem" }}>
          Close
        </button>
      </div>

      {!result && (
        <form onSubmit={handleSubmit}>
          <div className="formGrid threeCol" style={{ marginBottom: "0.75rem" }}>
            <div className="field">
              <label>Extra repayment / month ({currency})</label>
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="e.g. 500"
                value={extraRepayment}
                onChange={(e) => setExtraRepayment(e.target.value)}
              />
            </div>
            <div className="field">
              <label>New annual rate (decimal, e.g. 0.035)</label>
              <input
                type="number"
                min="0"
                max="1"
                step="0.0001"
                placeholder="e.g. 0.035"
                value={annualRate}
                onChange={(e) => setAnnualRate(e.target.value)}
              />
            </div>
            <div className="field">
              <label>New term (months)</label>
              <input
                type="number"
                min="1"
                step="1"
                placeholder="e.g. 180"
                value={termMonths}
                onChange={(e) => setTermMonths(e.target.value)}
              />
            </div>
          </div>
          <button className="primaryButton" type="submit" disabled={loading}>
            {loading ? "Computing…" : "Run scenario"}
          </button>
        </form>
      )}

      {error && <div className="errorBanner" style={{ marginTop: "0.5rem" }}>{error}</div>}

      {result && (
        <div style={{ marginTop: "0.75rem" }}>
          {comparison?.is_stale && (
            <div
              className="errorBanner"
              style={{ marginBottom: "0.75rem" }}
            >
              This scenario was computed against an older data run — results may be outdated.
            </div>
          )}

          {/* Headline summary */}
          <div className="metaGrid" style={{ marginBottom: "1rem" }}>
            <div className="metaItem">
              <div className="metricLabel">Months saved</div>
              <div className="metricValue" style={{ color: result.months_saved > 0 ? "var(--ok)" : "var(--warning)" }}>
                {result.months_saved > 0 ? `−${result.months_saved}` : result.months_saved}
              </div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Interest saved</div>
              <div className="metricValue" style={{ color: Number(result.interest_saved) > 0 ? "var(--ok)" : "var(--warning)" }}>
                {fmt(result.interest_saved, currency)}
              </div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">New payoff</div>
              <div className="metricValue">{fmtDate(result.new_payoff_date)}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Baseline payoff</div>
              <div className="metricValue muted">{fmtDate(result.baseline_payoff_date)}</div>
            </div>
          </div>

          {/* Assumptions */}
          {comparison?.assumptions?.length > 0 && (
            <div style={{ marginBottom: "1rem" }}>
              <div className="eyebrow" style={{ marginBottom: "0.25rem" }}>Assumptions</div>
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
                    {comparison.assumptions.map((a, i) => (
                      <tr key={i}>
                        <td>{a.assumption_key}</td>
                        <td className="muted">{a.baseline_value ?? "—"}</td>
                        <td><strong>{a.override_value}</strong></td>
                        <td className="muted">{a.unit ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Variance table — first 12 periods */}
          {comparison?.variance_rows?.length > 0 && (
            <div>
              <div className="eyebrow" style={{ marginBottom: "0.25rem" }}>
                Period comparison (first 12 periods)
              </div>
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Period</th>
                      <th>Date</th>
                      <th>Baseline payment</th>
                      <th>Scenario payment</th>
                      <th>Balance delta</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.variance_rows.slice(0, 12).map((row, i) => {
                      const delta = row.balance_delta != null ? Number(row.balance_delta) : null;
                      return (
                        <tr key={i}>
                          <td>{row.period}</td>
                          <td>{row.payment_date}</td>
                          <td className="muted">{fmt(row.baseline_payment, row.currency)}</td>
                          <td>{fmt(row.scenario_payment, row.currency)}</td>
                          <td
                            style={{
                              color:
                                delta == null
                                  ? "inherit"
                                  : delta < 0
                                  ? "var(--ok)"
                                  : delta > 0
                                  ? "var(--warning)"
                                  : "inherit",
                            }}
                          >
                            {delta != null
                              ? `${delta >= 0 ? "+" : ""}${delta.toFixed(2)} ${row.currency}`
                              : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <button
            className="ghostButton"
            style={{ marginTop: "1rem", fontSize: "0.85rem" }}
            onClick={() => { setResult(null); setComparison(null); }}
          >
            Try another scenario
          </button>
        </div>
      )}
    </div>
  );
}
