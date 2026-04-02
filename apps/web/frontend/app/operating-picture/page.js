import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { SparklineChart } from "@/components/sparkline-chart";
import { stateIndicatorBadge } from "@/lib/state-indicators";
import {
  getAffordabilityRatios,
  getAttentionItems,
  getCurrentUser,
  getMonthlyCashflow,
  getRecentChanges,
  getRecurringCostBaseline,
  getSourceFreshness,
  getSubscriptionSummary,
  getUpcomingFixedCosts,
  getUtilityCostTrend,
} from "@/lib/backend";

function staleness(landedAt) {
  if (!landedAt) return { label: "Never", band: "red" };
  const diffDays = (Date.now() - new Date(landedAt)) / (1000 * 60 * 60 * 24);
  if (diffDays < 2)  return { label: "Fresh", band: "green" };
  if (diffDays < 7)  return { label: `${Math.floor(diffDays)}d ago`, band: "yellow" };
  return { label: `${Math.floor(diffDays)}d — stale`, band: "red" };
}

function domainFreshnessBand(freshDatasets, datasetNames) {
  const bands = datasetNames.map((ds) => {
    const f = freshDatasets.find((r) => r.dataset_name === ds);
    return staleness(f?.landed_at).band;
  });
  if (bands.some((b) => b === "red")) return { band: "red", color: "var(--error)", label: "Stale" };
  if (bands.some((b) => b === "yellow")) return { band: "yellow", color: "var(--warning)", label: "Aging" };
  if (bands.every((b) => b === "green")) return { band: "green", color: "var(--ok)", label: "Fresh" };
  return { band: "grey", color: "var(--muted-text)", label: "No data" };
}

export default async function OperatingPicturePage() {
  const user = await getCurrentUser();

  const [
    cashflowRows,
    recurringBaseline,
    affordabilityRatios,
    attentionItems,
    recentChanges,
    subscriptions,
    utilityTrend,
    upcomingFixedCosts,
    freshnessDatasets,
  ] = await Promise.all([
    getMonthlyCashflow(),
    getRecurringCostBaseline(),
    getAffordabilityRatios(),
    getAttentionItems(),
    getRecentChanges(),
    getSubscriptionSummary(),
    getUtilityCostTrend(undefined),
    getUpcomingFixedCosts(),
    getSourceFreshness(),
  ]);

  const latestCashflow = cashflowRows.at(-1);
  const recurringTotal = subscriptions
    .filter((r) => r.status === "active")
    .reduce((sum, r) => sum + Number(r.monthly_equivalent || 0), 0);

  // Utility snapshot
  const utilityMonths = [...new Set(utilityTrend.map((r) => r.billing_month))].sort();
  const latestUtilityMonth = utilityMonths.at(-1);
  const prevUtilityMonth = utilityMonths.at(-2);
  const utilityLatestTotal = utilityTrend
    .filter((r) => r.billing_month === latestUtilityMonth)
    .reduce((sum, r) => sum + Number(r.total_cost || 0), 0);
  const utilityPrevTotal = utilityTrend
    .filter((r) => r.billing_month === prevUtilityMonth)
    .reduce((sum, r) => sum + Number(r.total_cost || 0), 0);
  const utilityDelta = utilityPrevTotal > 0
    ? ((utilityLatestTotal - utilityPrevTotal) / utilityPrevTotal) * 100
    : null;

  // Cashflow trend
  const trendLabels = cashflowRows.slice(-6).map((r) => r.booking_month);
  const cashflowTrendSeries = [
    {
      label: "Net",
      color: "var(--accent)",
      values: cashflowRows.slice(-6).map((r) => Number(r.net)),
    },
  ];

  // Confidence bands per domain
  const financeFreshness = domainFreshnessBand(freshnessDatasets, [
    "account_transactions",
    "subscriptions",
  ]);
  // contract_prices feeds both utility affordability and contract renewal watchlist
  const contractFreshness = domainFreshnessBand(freshnessDatasets, [
    "contract_prices",
  ]);
  const loanFreshness = domainFreshnessBand(freshnessDatasets, [
    "loan_repayments",
  ]);
  const budgetFreshness = domainFreshnessBand(freshnessDatasets, [
    "budgets",
  ]);

  // Upcoming actions: next 7 days
  const now = new Date();
  const in7Days = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
  const upcomingActions = upcomingFixedCosts.filter((r) => {
    if (!r.due_date) return false;
    const due = new Date(r.due_date);
    return due >= now && due <= in7Days;
  });

  // Urgency-ranked attention queue
  const rankedAttention = [...attentionItems]
    .sort((a, b) => (a.severity ?? 9) - (b.severity ?? 9));

  return (
    <AppShell
      currentPath="/operating-picture"
      user={user}
      title="Operating Picture"
      eyebrow="Household Intelligence"
      lede="Structured view of your household's financial and operational state across all active domains."
    >
      <section className="stack">
        {/* Domain cards */}
        <section className="cards">
          {/* Finance domain card */}
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Finance</div>
                <h2 style={{ margin: "4px 0" }}>
                  {latestCashflow ? `Net ${latestCashflow.net}` : "No data"}
                </h2>
              </div>
              <span
                className="statusPill"
                style={{
                  background: financeFreshness.color,
                  color: "#fff",
                  border: "none",
                }}
              >
                {financeFreshness.label}
              </span>
            </div>
            {latestCashflow && (
              <div className="muted" style={{ fontSize: "0.85rem", marginBottom: "8px" }}>
                {latestCashflow.booking_month} &nbsp;·&nbsp; Income: {latestCashflow.income} &nbsp;·&nbsp; Expense: {latestCashflow.expense}
              </div>
            )}
            {trendLabels.length > 0 && (
              <SparklineChart series={cashflowTrendSeries} labels={trendLabels} height={60} width={240} />
            )}
            <div style={{ marginTop: "8px" }}>
              <Link className="inlineLink" href="/">
                Dashboard
              </Link>
            </div>
            {rankedAttention.slice(0, 1).map((item, i) => (
              <div key={i} className="muted" style={{ fontSize: "0.82rem", marginTop: "6px" }}>
                Attention: {item.title}
              </div>
            ))}
          </article>

          {/* Recurring costs domain card */}
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Recurring Costs</div>
                <h2 style={{ margin: "4px 0" }}>
                  {subscriptions.length > 0 ? `${recurringTotal.toFixed(2)} / mo` : "No data"}
                </h2>
              </div>
              <span
                className="statusPill"
                style={{
                  background: financeFreshness.color,
                  color: "#fff",
                  border: "none",
                }}
              >
                {financeFreshness.label}
              </span>
            </div>
            <div className="muted" style={{ fontSize: "0.85rem" }}>
              {subscriptions.filter((r) => r.status === "active").length} active subscriptions
            </div>
            <div style={{ marginTop: "8px" }}>
              <Link className="inlineLink" href="/costs">
                Cost model
              </Link>
            </div>
          </article>

          {/* Utilities domain card */}
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Utilities</div>
                <h2 style={{ margin: "4px 0" }}>
                  {latestUtilityMonth ? `${utilityLatestTotal.toFixed(2)}` : "No data"}
                </h2>
              </div>
              <span
                className="statusPill"
                style={{
                  background: contractFreshness.color,
                  color: "#fff",
                  border: "none",
                }}
              >
                {contractFreshness.label}
              </span>
            </div>
            {utilityDelta !== null && (
              <div className="muted" style={{ fontSize: "0.85rem" }}>
                {utilityDelta >= 0 ? "▲" : "▼"} {Math.abs(utilityDelta).toFixed(1)}% vs {prevUtilityMonth}
              </div>
            )}
            <div style={{ marginTop: "8px" }}>
              <Link className="inlineLink" href="/utilities">
                Utilities
              </Link>
            </div>
          </article>

          {/* Affordability domain card */}
          {affordabilityRatios.length > 0 && (
            <article className="panel section">
              <div className="sectionHeader">
                <div>
                  <div className="eyebrow">Affordability</div>
                  <h2 style={{ margin: "4px 0" }}>
                    {affordabilityRatios.length} ratio{affordabilityRatios.length !== 1 ? "s" : ""}
                  </h2>
                </div>
                <span
                  className="statusPill"
                  style={{
                    background: contractFreshness.color,
                    color: "#fff",
                    border: "none",
                  }}
                >
                  {contractFreshness.label}
                </span>
              </div>
              <div className="stack compactStack">
                {affordabilityRatios.slice(0, 2).map((r) => {
                  const state = stateIndicatorBadge(r.state ?? r.assessment);
                  return (
                    <div key={r.ratio_name} style={{ fontSize: "0.85rem" }}>
                      <span className="muted">
                        {r.ratio_name.replace(/_/g, " ")}:{" "}
                      </span>
                      <span style={{ color: state.color }}>
                        {(Number(r.ratio) * 100).toFixed(1)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </article>
          )}
        </section>

        {/* Upcoming actions strip — next 7 days */}
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Upcoming Actions</div>
              <h2>Next 7 days</h2>
            </div>
          </div>
          {upcomingActions.length === 0 ? (
            <div className="muted">
              No upcoming obligations in the next 7 days.{" "}
              {upcomingFixedCosts.length > 0 && (
                <Link className="inlineLink" href="/costs">
                  View all scheduled costs
                </Link>
              )}
            </div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Due</th>
                    <th>Description</th>
                    <th>Amount</th>
                    <th>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {upcomingActions.map((item, i) => (
                    <tr key={i}>
                      <td>{item.due_date}</td>
                      <td>{item.description || item.counterparty || "—"}</td>
                      <td>{item.amount != null ? `${Number(item.amount).toFixed(2)} ${item.currency || ""}`.trim() : "—"}</td>
                      <td><span className="muted">{item.cost_type || "—"}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        {/* Cross-domain attention queue */}
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Attention Queue</div>
              <h2>Items ranked by urgency</h2>
            </div>
            <Link className="inlineLink" href="/review">
              See all →
            </Link>
          </div>
          {rankedAttention.length === 0 ? (
            <div className="empty">No attention items. All clear.</div>
          ) : (
            <div className="stack compactStack">
              {rankedAttention.slice(0, 8).map((item, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    gap: "8px",
                    alignItems: "flex-start",
                    padding: "8px 0",
                    borderBottom: "1px solid var(--border)",
                  }}
                >
                  {item.severity === 1 && (
                    <span className="statusPill status-failed">warn</span>
                  )}
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700 }}>{item.title}</div>
                    {item.source_domain && (
                      <div className="muted" style={{ fontSize: "0.82rem" }}>
                        {item.source_domain}
                      </div>
                    )}
                    {item.detail && (
                      <div className="muted" style={{ fontSize: "0.82rem" }}>
                        {item.detail}
                      </div>
                    )}
                  </div>
                  {item.action_href && (
                    <Link className="inlineLink" href={item.action_href}>
                      {item.action_label || "Review"}
                    </Link>
                  )}
                </div>
              ))}
            </div>
          )}
        </article>

        {/* Recent changes feed */}
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Recent Changes</div>
              <h2>Last 5 material changes</h2>
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
                    <th>Period</th>
                  </tr>
                </thead>
                <tbody>
                  {recentChanges.slice(0, 5).map((row, i) => (
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
                      <td>
                        <span className="muted">{row.booking_month || row.period_label || "—"}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        {/* Source confidence band */}
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Confidence</div>
              <h2>Freshness indicator per domain</h2>
            </div>
            <Link className="inlineLink" href="/sources">
              Manage sources
            </Link>
          </div>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Domain</th>
                  <th>Freshness</th>
                  <th>Source datasets</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Finance / Cashflow</td>
                  <td>
                    <span
                      style={{
                        display: "inline-block",
                        width: "10px",
                        height: "10px",
                        borderRadius: "50%",
                        background: financeFreshness.color,
                        marginRight: "6px",
                      }}
                    />
                    {financeFreshness.label}
                  </td>
                  <td className="muted">account_transactions, subscriptions</td>
                  <td>
                    {financeFreshness.band !== "green" && (
                      <Link className="inlineLink" href="/upload/account-transactions">
                        Upload
                      </Link>
                    )}
                  </td>
                </tr>
                <tr>
                  <td>Utilities / Affordability</td>
                  <td>
                    <span
                      style={{
                        display: "inline-block",
                        width: "10px",
                        height: "10px",
                        borderRadius: "50%",
                        background: contractFreshness.color,
                        marginRight: "6px",
                      }}
                    />
                    {contractFreshness.label}
                  </td>
                  <td className="muted">contract_prices</td>
                  <td>
                    {contractFreshness.band !== "green" && (
                      <Link className="inlineLink" href="/upload/contract-prices">
                        Upload
                      </Link>
                    )}
                  </td>
                </tr>
                <tr>
                  <td>Loans / Debt</td>
                  <td>
                    <span
                      style={{
                        display: "inline-block",
                        width: "10px",
                        height: "10px",
                        borderRadius: "50%",
                        background: loanFreshness.color,
                        marginRight: "6px",
                      }}
                    />
                    {loanFreshness.label}
                  </td>
                  <td className="muted">loan_repayments</td>
                  <td>
                    {loanFreshness.band !== "green" && (
                      <Link className="inlineLink" href="/upload/loan-repayments">
                        Upload
                      </Link>
                    )}
                  </td>
                </tr>
                <tr>
                  <td>Budgets</td>
                  <td>
                    <span
                      style={{
                        display: "inline-block",
                        width: "10px",
                        height: "10px",
                        borderRadius: "50%",
                        background: budgetFreshness.color,
                        marginRight: "6px",
                      }}
                    />
                    {budgetFreshness.label}
                  </td>
                  <td className="muted">budgets</td>
                  <td>
                    {budgetFreshness.band !== "green" && (
                      <Link className="inlineLink" href="/upload/budgets">
                        Upload
                      </Link>
                    )}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </AppShell>
  );
}
