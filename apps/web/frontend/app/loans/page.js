import { AppShell } from "@/components/app-shell";
import { LoanWhatIfPanel } from "@/components/loan-whatif-panel";
import { getCurrentUser, getLoanOverview, getLoanVariance } from "@/lib/backend";

function formatAmount(val, currency) {
  if (val == null) return "—";
  return `${Number(val).toLocaleString("en-IE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency || ""}`;
}

function progressBar(paidPct) {
  const clamped = Math.min(Math.max(paidPct, 0), 100);
  return (
    <div
      style={{
        width: "100%",
        height: "8px",
        background: "var(--surface-2)",
        borderRadius: "4px",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${clamped}%`,
          height: "100%",
          background: "var(--accent)",
          borderRadius: "4px",
        }}
      />
    </div>
  );
}

export default async function LoansPage({ searchParams }) {
  const user = await getCurrentUser();
  const loanId = searchParams?.loan_id || undefined;

  const [overview, variance] = await Promise.all([
    getLoanOverview(),
    getLoanVariance(loanId),
  ]);

  return (
    <AppShell
      currentPath="/loans"
      user={user}
      title="Loans"
      eyebrow="Reader Access"
      lede="Amortization schedules, repayment tracking, and projected vs actual variance."
    >
      <section className="stack">
        {/* Loan cards */}
        {overview.length === 0 ? (
          <div className="empty">No loan data loaded yet.</div>
        ) : (
          <section className="cards">
            {overview.map((loan) => {
              const original = Number(loan.original_principal);
              const balance = Number(loan.current_balance_estimate);
              const paidAmt = original - balance;
              const paidPct = original > 0 ? (paidAmt / original) * 100 : 0;
              return (
                <article key={loan.loan_id} className="panel section">
                  <div className="sectionHeader">
                    <div>
                      <div className="eyebrow">{loan.lender}</div>
                      <h2>{loan.loan_name}</h2>
                    </div>
                  </div>
                  <div className="metaGrid">
                    <div className="metaItem">
                      <div className="metricLabel">Original principal</div>
                      <div className="metricValue">
                        {formatAmount(loan.original_principal, loan.currency)}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Current balance</div>
                      <div className="metricValue">
                        {formatAmount(loan.current_balance_estimate, loan.currency)}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Monthly payment</div>
                      <div className="metricValue">
                        {formatAmount(loan.monthly_payment, loan.currency)}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Remaining months</div>
                      <div className="metricValue">{loan.remaining_months}</div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Interest paid</div>
                      <div className="metricValue">
                        {formatAmount(loan.total_interest_paid, loan.currency)}
                      </div>
                    </div>
                    <div className="metaItem">
                      <div className="metricLabel">Interest projected</div>
                      <div className="metricValue">
                        {formatAmount(loan.total_interest_projected, loan.currency)}
                      </div>
                    </div>
                  </div>
                  <div className="stack compactStack" style={{ marginTop: "0.75rem" }}>
                    <div className="metricLabel">
                      Paid off: {paidPct.toFixed(1)}%
                    </div>
                    {progressBar(paidPct)}
                  </div>
                  <LoanWhatIfPanel
                    loanId={loan.loan_id}
                    loanName={loan.loan_name}
                    currency={loan.currency}
                  />
                </article>
              );
            })}
          </section>
        )}

        {/* Variance filter */}
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Filters</div>
              <h2>Repayment variance</h2>
            </div>
          </div>
          <form className="formGrid threeCol" method="get">
            <div className="field">
              <label htmlFor="loan_id">Loan</label>
              <select id="loan_id" name="loan_id" defaultValue={loanId || ""}>
                <option value="">All loans</option>
                {overview.map((loan) => (
                  <option key={loan.loan_id} value={loan.loan_id}>
                    {loan.loan_name}
                  </option>
                ))}
              </select>
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
              <p className="muted">No repayment variance data available.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Loan</th>
                    <th>Month</th>
                    <th>Projected</th>
                    <th>Actual</th>
                    <th>Variance</th>
                    <th>Balance estimate</th>
                  </tr>
                </thead>
                <tbody>
                  {variance.map((row, i) => {
                    const varianceAmt = Number(row.variance);
                    return (
                      <tr key={i}>
                        <td>{row.loan_name}</td>
                        <td>{row.repayment_month}</td>
                        <td>{formatAmount(row.projected_payment, row.currency)}</td>
                        <td>{formatAmount(row.actual_payment, row.currency)}</td>
                        <td
                          style={{
                            color:
                              Math.abs(varianceAmt) < 1
                                ? "inherit"
                                : varianceAmt > 0
                                ? "var(--warning)"
                                : "var(--ok)",
                          }}
                        >
                          {varianceAmt >= 0 ? "+" : ""}
                          {varianceAmt.toFixed(2)} {row.currency}
                        </td>
                        <td>{formatAmount(row.actual_balance_estimate, row.currency)}</td>
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
