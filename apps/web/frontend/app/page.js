import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { OnboardingChecklist } from "@/components/onboarding-checklist";
import { SparklineChart } from "@/components/sparkline-chart";
import { stateIndicatorBadge } from "@/lib/state-indicators";
import {
  getAffordabilityRatios,
  getAttentionItems,
  getCurrentUser,
  getHouseholdOverview,
  getMonthlyCashflow,
  getRecentChanges,
  getRecurringCostBaseline,
  getRuns,
  getSourceFreshness,
  getSpendByCategoryMonthly,
  getSubscriptionSummary,
  getUtilityCostTrend,
} from "@/lib/backend";

export default async function DashboardPage() {
  const user = await getCurrentUser();
  const [cashflowRows, runs, overview, attentionItems, recentChanges, spendByCategory, subscriptions, utilityTrend, affordabilityRatios, recurringBaseline, freshnessDatasets] =
    await Promise.all([
      getMonthlyCashflow(),
      getRuns(8),
      getHouseholdOverview(),
      getAttentionItems(),
      getRecentChanges(),
      getSpendByCategoryMonthly(),
      getSubscriptionSummary(),
      getUtilityCostTrend(),
      getAffordabilityRatios(),
      getRecurringCostBaseline(),
      getSourceFreshness(),
    ]);
  const latest = cashflowRows.at(-1);

  // Top-5 categories for current month
  const latestMonth = latest?.booking_month;
  const currentMonthSpend = spendByCategory.filter((r) => r.booking_month === latestMonth);
  const categoryTotals = Object.values(
    currentMonthSpend.reduce((acc, r) => {
      const cat = r.category || "Uncategorised";
      acc[cat] = acc[cat] || { category: cat, total: 0 };
      acc[cat].total += Number(r.total_expense || 0);
      return acc;
    }, {})
  )
    .sort((a, b) => b.total - a.total)
    .slice(0, 5);

  // Utility snapshot: latest month total and previous month for delta
  const utilityMonths = [...new Set(utilityTrend.map((r) => r.billing_month))].sort();
  const latestUtilityMonth = utilityMonths.at(-1);
  const prevUtilityMonth = utilityMonths.at(-2);
  const utilityLatestTotal = utilityTrend
    .filter((r) => r.billing_month === latestUtilityMonth)
    .reduce((sum, r) => sum + Number(r.total_cost || 0), 0);
  const utilityPrevTotal = utilityTrend
    .filter((r) => r.billing_month === prevUtilityMonth)
    .reduce((sum, r) => sum + Number(r.total_cost || 0), 0);
  const utilityDelta = utilityPrevTotal > 0 ? ((utilityLatestTotal - utilityPrevTotal) / utilityPrevTotal) * 100 : null;

  // Recurring cost: sum of active subscription monthly equivalents
  const recurringTotal = subscriptions
    .filter((r) => r.status === "active")
    .reduce((sum, r) => sum + Number(r.monthly_equivalent || 0), 0);

  // Onboarding checklist: compute fresh datasets and next suggestion
  const freshDatasetNames = freshnessDatasets
    .filter((ds) => {
      if (!ds.landed_at) return false;
      const diffDays = (Date.now() - new Date(ds.landed_at)) / (1000 * 60 * 60 * 24);
      return diffDays < 7;
    })
    .map((ds) => ds.dataset_name);

  const ONBOARDING_ORDER = [
    { dataset: "account_transactions", label: "Account transactions", uploadPath: "/upload/account-transactions" },
    { dataset: "subscriptions", label: "Subscriptions", uploadPath: "/upload/subscriptions" },
    { dataset: "contract_prices", label: "Contract prices", uploadPath: "/upload/contract-prices" },
    { dataset: "budgets", label: "Budgets", uploadPath: "/upload/budgets" },
    { dataset: "loan_repayments", label: "Loan repayments", uploadPath: "/upload/loan-repayments" },
  ];
  const nextSuggestion = ONBOARDING_ORDER.find((s) => !freshDatasetNames.includes(s.dataset)) || null;

  const trendLabels = cashflowRows.slice(-12).map((r) => r.booking_month);
  const trendSeries = [
    {
      label: "Income",
      color: "var(--ok)",
      values: cashflowRows.slice(-12).map((r) => Number(r.income)),
    },
    {
      label: "Expense",
      color: "var(--warn)",
      values: cashflowRows.slice(-12).map((r) => Number(r.expense)),
    },
    {
      label: "Net",
      color: "var(--accent)",
      values: cashflowRows.slice(-12).map((r) => Number(r.net)),
    },
  ];

  return (
    <AppShell
      currentPath="/"
      user={user}
      title="Homelab Analytics"
      eyebrow="API-Backed Dashboard"
      lede="A minimal Next.js shell over the reporting and run APIs. The web workload no longer computes or reads reporting data directly."
    >
      <section className="hero">
        <article className="panel heroCard">
          <div className="eyebrow">Household Overview</div>
          {overview ? (
            <>
              <h1>
                {overview.net != null
                  ? `Net ${overview.net}`
                  : "Dashboard and control-plane visibility from one API surface."}
              </h1>
              <div className="heroCopy muted">
                {overview.income != null && (
                  <span>Income: {overview.income} &nbsp;·&nbsp; </span>
                )}
                {overview.expense != null && (
                  <span>Expense: {overview.expense}</span>
                )}
              </div>
            </>
          ) : (
            <>
              <h1>Dashboard and control-plane visibility from one API surface.</h1>
              <p className="heroCopy muted">
                The current slice keeps the UI intentionally narrow: recent runs,
                monthly cashflow, and authenticated navigation built entirely on the API.
              </p>
            </>
          )}
        </article>
        <aside className="panel heroMetric">
          <div className="eyebrow">Latest Net</div>
          <div className="value">{latest ? latest.net : "No successful imports yet."}</div>
          <div className="muted">
            {latest
              ? `${latest.booking_month} / ${latest.transaction_count} rows`
              : "Import a valid dataset to populate the reporting layer."}
          </div>
        </aside>
      </section>

      <OnboardingChecklist freshDatasets={freshDatasetNames} nextSuggestion={nextSuggestion} />

      <section className="cards">
        <article className="panel metricCard">
          <div className="metricLabel">Income</div>
          <div className="metricValue">{latest ? latest.income : "No data"}</div>
        </article>
        <article className="panel metricCard">
          <div className="metricLabel">Expense</div>
          <div className="metricValue">{latest ? latest.expense : "No data"}</div>
        </article>
        <article className="panel metricCard">
          <div className="metricLabel">Net</div>
          <div className="metricValue">{latest ? latest.net : "No data"}</div>
        </article>
      </section>

      {affordabilityRatios.length > 0 && (
        <section className="cards">
          {affordabilityRatios.map((r) => {
            const state = stateIndicatorBadge(r.state ?? r.assessment);
            const label = {
              housing_to_income: "Housing / income",
              total_cost_to_income: "Total cost / income",
              debt_service_ratio: "Debt service ratio",
            }[r.ratio_name] || r.ratio_name;
            return (
              <article key={r.ratio_name} className="panel metricCard">
                <div className="metricLabel">{label}</div>
                <div className="metricValue" style={{ color: state.color }}>
                  {(Number(r.ratio) * 100).toFixed(1)}%
                </div>
                <div className="muted" style={{ color: state.color }}>{state.label}</div>
                <div className="muted" style={{ fontSize: "0.82rem" }}>{r.assessment}</div>
              </article>
            );
          })}
        </section>
      )}

      {recurringBaseline.length > 0 && (
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Recurring baseline</div>
              <h2>Fixed monthly commitments</h2>
            </div>
            <Link className="inlineLink" href="/costs">View cost model</Link>
          </div>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Description</th>
                  <th>Monthly</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {recurringBaseline.map((row, i) => (
                  <tr key={i}>
                    <td>{row.cost_source}</td>
                    <td>{row.counterparty_or_contract}</td>
                    <td>{Number(row.monthly_amount).toFixed(2)} {row.currency}</td>
                    <td><span className="muted">{row.confidence}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      )}

      {cashflowRows.length > 0 && (
        <article className="panel section" style={{ marginBottom: "24px" }}>
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Trend</div>
              <h2>Cashflow — last 12 months</h2>
            </div>
          </div>
          <SparklineChart series={trendSeries} labels={trendLabels} height={120} width={600} />
        </article>
      )}

      <section className="cards" style={{ marginBottom: "24px" }}>
        <article className="panel section">
          <div className="eyebrow">Top Categories</div>
          <h3 style={{ margin: "4px 0 12px" }}>{latestMonth || "—"}</h3>
          {categoryTotals.length === 0 ? (
            <div className="empty">No category data yet.</div>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "8px" }}>
              {categoryTotals.map((c) => (
                <li key={c.category} style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>{c.category}</span>
                  <span className="muted">{c.total.toFixed(2)}</span>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="panel section">
          <div className="eyebrow">Utilities</div>
          <h3 style={{ margin: "4px 0 4px" }}>
            {latestUtilityMonth ? `${latestUtilityMonth}: ${utilityLatestTotal.toFixed(2)}` : "No data"}
          </h3>
          {utilityDelta !== null && (
            <div className="muted" style={{ fontSize: "0.85rem" }}>
              {utilityDelta >= 0 ? "▲" : "▼"} {Math.abs(utilityDelta).toFixed(1)}% vs {prevUtilityMonth}
            </div>
          )}
        </article>

        <article className="panel section">
          <div className="eyebrow">Recurring Costs</div>
          <h3 style={{ margin: "4px 0 4px" }}>
            {subscriptions.length > 0 ? `${recurringTotal.toFixed(2)} / mo` : "No data"}
          </h3>
          <div className="muted" style={{ fontSize: "0.85rem" }}>
            {subscriptions.filter((r) => r.status === "active").length} active subscriptions
          </div>
        </article>
      </section>

      <section className="layout">
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Reporting</div>
              <h2>Monthly cashflow</h2>
            </div>
          </div>
          {cashflowRows.length === 0 ? (
            <div className="empty">No successful imports yet.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Income</th>
                    <th>Expense</th>
                    <th>Net</th>
                    <th>Rows</th>
                  </tr>
                </thead>
                <tbody>
                  {cashflowRows.map((row) => (
                    <tr key={row.booking_month}>
                      <td>{row.booking_month}</td>
                      <td>{row.income}</td>
                      <td>{row.expense}</td>
                      <td>{row.net}</td>
                      <td>{row.transaction_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        <div className="stack">
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Attention</div>
                <h2>Items to review</h2>
              </div>
              <Link className="inlineLink" href="/review">See all →</Link>
            </div>
            {attentionItems.length === 0 ? (
              <div className="empty">Nothing requires attention.</div>
            ) : (
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "10px" }}>
                {attentionItems
                  .sort((a, b) => (a.severity ?? 9) - (b.severity ?? 9))
                  .map((item, i) => (
                    <li key={i} style={{ display: "flex", gap: "8px", alignItems: "flex-start" }}>
                      {item.severity === 1 && (
                        <span className="statusPill status-failed">warn</span>
                      )}
                      <div>
                        <div style={{ fontWeight: 700 }}>{item.title}</div>
                        {item.source_domain && (
                          <div className="muted" style={{ fontSize: "0.82rem" }}>
                            {item.source_domain}
                          </div>
                        )}
                      </div>
                    </li>
                  ))}
              </ul>
            )}
          </article>

          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Activity</div>
                <h2>Recent changes</h2>
              </div>
            </div>
            {recentChanges.length === 0 ? (
              <div className="empty">No recent changes recorded.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Metric</th>
                      <th>Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentChanges.map((row, i) => (
                      <tr key={i}>
                        <td>
                          <span className="statusPill status-enqueued">{row.change_type}</span>
                        </td>
                        <td>{row.metric_name}</td>
                        <td>
                          {row.direction === "up" ? "▲" : "▼"}{" "}
                          {row.current_value}
                          {row.previous_value != null && (
                            <span className="muted"> / {row.previous_value}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </article>

          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Pipeline State</div>
                <h2>Recent runs</h2>
              </div>
            </div>
            {runs.length === 0 ? (
              <div className="empty">No ingestion runs recorded yet.</div>
            ) : (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Source</th>
                      <th>File</th>
                      <th>Rows</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <tr key={run.run_id}>
                        <td>
                          <span className={`statusPill status-${run.status}`}>{run.status}</span>
                          {(run.issues || []).slice(0, 2).map((issue) => (
                            <div className="issue" key={`${run.run_id}-${issue.code}-${issue.message}`}>
                              {issue.code}: {issue.message}
                            </div>
                          ))}
                        </td>
                        <td>
                          <Link className="inlineLink" href={`/runs/${run.run_id}`}>
                            {run.source_name}
                          </Link>
                        </td>
                        <td>{run.file_name}</td>
                        <td>{run.row_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </article>
        </div>
      </section>
    </AppShell>
  );
}
