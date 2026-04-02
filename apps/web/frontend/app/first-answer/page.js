import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { SparklineChart } from "@/components/sparkline-chart";
import { stateIndicatorBadge } from "@/lib/state-indicators";
import {
  getAffordabilityRatios,
  getAttentionItems,
  getCurrentUser,
  getMonthlyCashflow,
  getRecurringCostBaseline,
  getSourceFreshness,
  getSubscriptionSummary,
} from "@/lib/backend";

const SOURCE_UNLOCK_MAP = {
  account_transactions: [
    "Monthly cashflow trend",
    "Spend-by-category breakdown",
    "Transaction anomalies",
    "Attention items",
  ],
  subscriptions: [
    "Recurring cost baseline",
    "Subscription review queue",
    "Cost model (subscription layer)",
  ],
  contract_prices: [
    "Affordability ratios",
    "Contract renewal watchlist",
    "Utility contract pricing",
  ],
  budgets: [
    "Budget variance report",
    "Envelope tracking",
  ],
  loan_repayments: [
    "Loan overview",
    "Debt service ratio",
    "Loan repayment schedule",
  ],
};

const PENDING_SOURCE_SUGGESTIONS = [
  {
    dataset: "account_transactions",
    label: "Account transactions",
    unlocks: "cashflow, categories, anomalies",
    uploadPath: "/upload/account-transactions",
    priority: 1,
  },
  {
    dataset: "subscriptions",
    label: "Subscriptions",
    unlocks: "recurring cost baseline, subscription review",
    uploadPath: "/upload/subscriptions",
    priority: 2,
  },
  {
    dataset: "contract_prices",
    label: "Contract prices",
    unlocks: "affordability ratios, contract watchlist",
    uploadPath: "/upload/contract-prices",
    priority: 3,
  },
  {
    dataset: "budgets",
    label: "Budgets",
    unlocks: "budget variance, envelope tracking",
    uploadPath: "/upload/budgets",
    priority: 4,
  },
  {
    dataset: "loan_repayments",
    label: "Loan repayments",
    unlocks: "loan overview, debt service ratio",
    uploadPath: "/upload/loan-repayments",
    priority: 5,
  },
];

export default async function FirstAnswerPage() {
  const user = await getCurrentUser();

  const [cashflowRows, recurringBaseline, affordabilityRatios, attentionItems, subscriptions, freshnessDatasets] =
    await Promise.all([
      getMonthlyCashflow(),
      getRecurringCostBaseline(),
      getAffordabilityRatios(),
      getAttentionItems(),
      getSubscriptionSummary(),
      getSourceFreshness(),
    ]);

  const freshDatasets = new Set(
    freshnessDatasets
      .filter((ds) => {
        if (!ds.landed_at) return false;
        const diffDays = (Date.now() - new Date(ds.landed_at)) / (1000 * 60 * 60 * 24);
        return diffDays < 7;
      })
      .map((ds) => ds.dataset_name)
  );

  const latestCashflow = cashflowRows.at(-1);
  const recurringTotal = subscriptions
    .filter((r) => r.status === "active")
    .reduce((sum, r) => sum + Number(r.monthly_equivalent || 0), 0);

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

  // Pending sources: not in freshDatasets
  const pendingSources = PENDING_SOURCE_SUGGESTIONS
    .filter((s) => !freshDatasets.has(s.dataset))
    .sort((a, b) => a.priority - b.priority);

  // Active sources with their unlocked features
  const activeSources = PENDING_SOURCE_SUGGESTIONS
    .filter((s) => freshDatasets.has(s.dataset));

  const hasCashflow = cashflowRows.length > 0;
  const hasRecurring = recurringBaseline.length > 0;
  const hasAffordability = affordabilityRatios.length > 0;
  const hasAttention = attentionItems.length > 0;

  return (
    <AppShell
      currentPath="/first-answer"
      user={user}
      title="First Answer"
      eyebrow="Operating Picture"
      lede="Your household financial picture, composed from active sources. Add more sources to unlock additional views."
    >
      <section className="stack">
        {/* Cashflow inline summary */}
        {hasCashflow ? (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Cashflow</div>
                <h2>
                  {latestCashflow?.booking_month}: Net {latestCashflow?.net}
                </h2>
              </div>
              <Link className="inlineLink" href="/">
                Full dashboard
              </Link>
            </div>
            <div className="metaGrid">
              <div className="metaItem">
                <div className="metricLabel">Income</div>
                <div className="metricValue" style={{ fontSize: "1.2rem" }}>
                  {latestCashflow?.income}
                </div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Expense</div>
                <div className="metricValue" style={{ fontSize: "1.2rem" }}>
                  {latestCashflow?.expense}
                </div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Net</div>
                <div className="metricValue" style={{ fontSize: "1.2rem" }}>
                  {latestCashflow?.net}
                </div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Rows</div>
                <div>{latestCashflow?.transaction_count}</div>
              </div>
            </div>
            {trendLabels.length > 0 && (
              <SparklineChart series={trendSeries} labels={trendLabels} height={100} width={600} />
            )}
          </article>
        ) : (
          <article className="panel section">
            <div className="eyebrow">Cashflow</div>
            <div className="empty" style={{ marginTop: "8px" }}>
              No cashflow data yet.{" "}
              <Link className="inlineLink" href="/upload/account-transactions">
                Upload account transactions
              </Link>{" "}
              to populate this view.
            </div>
          </article>
        )}

        {/* Recurring baseline */}
        {hasRecurring ? (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Recurring Baseline</div>
                <h2>{recurringTotal.toFixed(2)} / mo committed</h2>
              </div>
              <Link className="inlineLink" href="/costs">
                Cost model
              </Link>
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
                  {recurringBaseline.slice(0, 6).map((row, i) => (
                    <tr key={i}>
                      <td>{row.cost_source}</td>
                      <td>{row.counterparty_or_contract}</td>
                      <td>
                        {Number(row.monthly_amount).toFixed(2)} {row.currency}
                      </td>
                      <td>
                        <span className="muted">{row.confidence}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        ) : (
          <article className="panel section">
            <div className="eyebrow">Recurring Baseline</div>
            <div className="empty" style={{ marginTop: "8px" }}>
              No recurring baseline yet.{" "}
              <Link className="inlineLink" href="/upload/subscriptions">
                Upload subscriptions
              </Link>{" "}
              to see committed monthly costs.
            </div>
          </article>
        )}

        {/* Affordability ratios */}
        {hasAffordability ? (
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
                  <div className="muted" style={{ color: state.color, fontSize: "0.85rem" }}>
                    {state.label}
                  </div>
                </article>
              );
            })}
          </section>
        ) : (
          <article className="panel section">
            <div className="eyebrow">Affordability</div>
            <div className="empty" style={{ marginTop: "8px" }}>
              Affordability ratios require contract price data.{" "}
              <Link className="inlineLink" href="/upload/contract-prices">
                Upload contract prices
              </Link>{" "}
              to unlock this view.
            </div>
          </article>
        )}

        {/* Attention items */}
        {hasAttention && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Attention</div>
                <h2>Items requiring review</h2>
              </div>
              <Link className="inlineLink" href="/review">
                See all →
              </Link>
            </div>
            <div className="stack compactStack">
              {attentionItems
                .sort((a, b) => (a.severity ?? 9) - (b.severity ?? 9))
                .slice(0, 6)
                .map((item, i) => (
                  <div key={i} style={{ display: "flex", gap: "8px", alignItems: "flex-start" }}>
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
                  </div>
                ))}
            </div>
          </article>
        )}

        {/* Progressive disclosure: what additional sources unlock */}
        {pendingSources.length > 0 && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Progressive Disclosure</div>
                <h2>What additional sources unlock</h2>
              </div>
              <Link className="inlineLink" href="/onboarding">
                Onboarding guide
              </Link>
            </div>
            <div className="stack compactStack">
              {pendingSources.map((src) => (
                <div
                  key={src.dataset}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "12px",
                    padding: "10px 0",
                    borderBottom: "1px solid var(--border)",
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <strong>{src.label}</strong>
                      <span className="statusPill status-pending">not yet active</span>
                    </div>
                    <div className="muted" style={{ fontSize: "0.85rem", marginTop: "2px" }}>
                      Unlocks: {src.unlocks}
                    </div>
                    <div className="muted" style={{ fontSize: "0.82rem", marginTop: "2px" }}>
                      {(SOURCE_UNLOCK_MAP[src.dataset] || []).join(" · ")}
                    </div>
                  </div>
                  <Link className="ghostButton" href={src.uploadPath}>
                    Upload
                  </Link>
                </div>
              ))}
            </div>
          </article>
        )}

        {activeSources.length > 0 && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Active sources</div>
                <h2>Currently contributing to this view</h2>
              </div>
            </div>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              {activeSources.map((src) => (
                <span key={src.dataset} className="statusPill status-landed">
                  {src.label}
                </span>
              ))}
            </div>
          </article>
        )}
      </section>
    </AppShell>
  );
}
