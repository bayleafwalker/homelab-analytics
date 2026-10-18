import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { RendererDiscovery } from "@/components/renderer-discovery";
import { ResponsiveTable } from "@/components/responsive-table";
import { SparklineChart } from "@/components/sparkline-chart";
import { IncomeScenarioPanel } from "@/components/income-scenario-panel";
import { ExpenseShockPanel } from "@/components/expense-shock-panel";
import {
  getAccountBalanceTrend,
  getBriefing,
  getCurrentUser,
  getMonthlyCashflow,
  getPublicationConfidenceDetail,
  getSpendByCategoryMonthly,
  getSubscriptionSummary,
  getUtilityCostTrend,
} from "@/lib/backend";
import { getWebRendererDiscovery } from "@/lib/renderer-discovery";

function formatConfidenceLabel(value) {
  if (!value) return "Unknown";
  return String(value)
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// Publication trust for the monthly cashflow read. The confidence snapshot
// route is admin-scoped, so admins read it directly; every other role gets the
// same snapshot verdict through the reader-scoped morning brief money item.
const MONTHLY_CASHFLOW_PUBLICATION_KEY = "mart_monthly_cashflow";

async function loadMonthlyCashflowTrust(user) {
  if (user?.role === "admin") {
    const detail = await getPublicationConfidenceDetail(MONTHLY_CASHFLOW_PUBLICATION_KEY).catch(
      () => null
    );
    if (detail) {
      return { ...detail, remediation: null, via: "snapshot" };
    }
  }
  const brief = await getBriefing().catch(() => null);
  const item = (brief?.sections || [])
    .flatMap((section) => section.items || [])
    .find((entry) => entry.confidence?.publication_key === MONTHLY_CASHFLOW_PUBLICATION_KEY);
  if (!item?.confidence) {
    return null;
  }
  return {
    confidence_verdict: item.confidence.verdict,
    freshness_state: item.confidence.freshness_state,
    completeness_pct: item.confidence.completeness_pct,
    assessed_at: item.confidence.assessed_at,
    remediation: item.remediation,
    via: "brief",
  };
}

export default async function ReportsPage() {
  const user = await getCurrentUser();
  const [
    discovery,
    rows,
    balanceTrend,
    spendByCategory,
    subscriptions,
    utilityTrend,
    monthlyCashflowTrust,
  ] = await Promise.all([
    getWebRendererDiscovery(),
    getMonthlyCashflow(),
    getAccountBalanceTrend(),
    getSpendByCategoryMonthly(),
    getSubscriptionSummary(),
    getUtilityCostTrend(),
    loadMonthlyCashflowTrust(user),
  ]);

  const descriptorByKey = Object.fromEntries(
    discovery.reports.map((descriptor) => [descriptor.key, descriptor])
  );
  const cashflowDescriptor = descriptorByKey.cashflow;
  const balanceTrendDescriptor = descriptorByKey["balance-trend"];
  const spendingDescriptor = descriptorByKey["spending-by-category"];
  const subscriptionsDescriptor = descriptorByKey.subscriptions;
  const utilityTrendDescriptor = descriptorByKey["utility-cost-trend"];

  const balanceAccounts = [...new Set(balanceTrend.map((row) => row.account_id))];
  const balanceMonths = [...new Set(balanceTrend.map((row) => row.booking_month))].sort();
  const balanceSeries = balanceAccounts.map((account, index) => {
    const colors = [
      "var(--ok)",
      "var(--accent)",
      "var(--accent-cool)",
      "var(--accent-warm)",
    ];
    return {
      label: account,
      color: colors[index % colors.length],
      values: balanceMonths.map((month) => {
        const row = balanceTrend.find(
          (entry) => entry.account_id === account && entry.booking_month === month
        );
        return row ? Number(row.cumulative_balance) : null;
      }),
    };
  });

  const utilityTypes = [...new Set(utilityTrend.map((row) => row.utility_type))];

  return (
    <AppShell
      currentPath="/reports"
      user={user}
      title="Monthly Finance"
      eyebrow="Finance Read Surface"
      lede="This is the stable monthly finance read surface. Review cashflow here first, then hand off into the expense shock scenario when you need baseline, projected, and delta outcomes."
    >
      <section className="stack">
        <RendererDiscovery
          title="Published report views"
          eyebrow="Web renderer discovery"
          descriptors={discovery.reports}
        />

        {monthlyCashflowTrust && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Publication trust</div>
                <h2>Monthly cashflow snapshot</h2>
              </div>
              {monthlyCashflowTrust.via === "snapshot" ? (
                <Link className="inlineLink" href="/control/confidence">
                  Open confidence view
                </Link>
              ) : (
                <Link className="inlineLink" href="/briefing">
                  Open morning brief
                </Link>
              )}
            </div>
            <div className="metaGrid">
              <div className="metaItem">
                <div className="metricLabel">Verdict</div>
                <div>{formatConfidenceLabel(monthlyCashflowTrust.confidence_verdict)}</div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Freshness</div>
                <div>{formatConfidenceLabel(monthlyCashflowTrust.freshness_state)}</div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Completeness</div>
                <div>{monthlyCashflowTrust.completeness_pct ?? "—"}%</div>
              </div>
              <div className="metaItem">
                <div className="metricLabel">Assessed</div>
                <div>
                  {monthlyCashflowTrust.assessed_at
                    ? new Date(monthlyCashflowTrust.assessed_at).toLocaleString()
                    : "—"}
                </div>
              </div>
            </div>
            {monthlyCashflowTrust.remediation ? (
              <p className="muted" style={{ margin: "8px 0 0" }}>
                <strong>Next step:</strong> {monthlyCashflowTrust.remediation}{" "}
                {user?.role === "reader" ? null : (
                  <Link className="inlineLink" href="/sources">
                    Source freshness
                  </Link>
                )}
              </p>
            ) : null}
          </article>
        )}

        <article
          id={cashflowDescriptor?.anchor || "cashflow"}
          className="panel section"
        >
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">{cashflowDescriptor?.kind || "dashboard"}</div>
              <h2>{cashflowDescriptor?.nav_label || "Monthly cashflow"}</h2>
            </div>
          </div>
          <ResponsiveTable
            label="Monthly cashflow"
            rows={rows}
            rowKey="booking_month"
            empty={<div className="empty">No published rows yet.</div>}
            columns={[
              { key: "booking_month", header: "Booking month", primary: true },
              { key: "income", header: "Income", align: "end" },
              { key: "expense", header: "Expense", align: "end" },
              { key: "net", header: "Net", align: "end" },
              { key: "transaction_count", header: "Transactions", align: "end" },
            ]}
          />
          <div style={{ marginTop: "12px" }}>
            <Link className="inlineLink" href="#expense-shock">
              Expense shock handoff
            </Link>
          </div>
        </article>

        <ExpenseShockPanel />

        {balanceTrend.length > 0 && (
          <article
            id={balanceTrendDescriptor?.anchor || "balance-trend"}
            className="panel section"
          >
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">
                  {balanceTrendDescriptor?.kind || "dashboard"}
                </div>
                <h2>
                  {balanceTrendDescriptor?.nav_label || "Account balance trend"}
                </h2>
              </div>
            </div>
            <SparklineChart
              series={balanceSeries}
              labels={balanceMonths}
              height={120}
              width={600}
            />
          </article>
        )}

        <article
          id={spendingDescriptor?.anchor || "spending-by-category"}
          className="panel section"
        >
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">{spendingDescriptor?.kind || "report"}</div>
              <h2>{spendingDescriptor?.nav_label || "Spend by category"}</h2>
            </div>
          </div>
          <ResponsiveTable
            label="Spend by category"
            rows={spendByCategory}
            empty={<div className="empty">No category spend data yet.</div>}
            columns={[
              { key: "category", header: "Category", primary: true },
              { key: "booking_month", header: "Month" },
              { key: "counterparty_name", header: "Counterparty" },
              { key: "total_expense", header: "Total Expense", align: "end" },
              { key: "transaction_count", header: "Count", align: "end" },
            ]}
          />
        </article>

        <article
          id={subscriptionsDescriptor?.anchor || "subscriptions"}
          className="panel section"
        >
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">
                {subscriptionsDescriptor?.kind || "report"}
              </div>
              <h2>
                {subscriptionsDescriptor?.nav_label || "Subscription summary"}
              </h2>
            </div>
          </div>
          <ResponsiveTable
            label="Subscription summary"
            rows={subscriptions}
            empty={<div className="empty">No subscription data yet.</div>}
            columns={[
              { key: "contract_name", header: "Name", primary: true },
              { key: "provider", header: "Provider" },
              { key: "billing_cycle", header: "Billing cycle" },
              { key: "monthly_equivalent", header: "Monthly equiv", align: "end" },
              {
                key: "status",
                header: "Status",
                cell: (row) => <span className={`statusPill status-${row.status}`}>{row.status}</span>,
              },
            ]}
          />
        </article>

        {utilityTrend.length > 0 && (
          <article
            id={utilityTrendDescriptor?.anchor || "utility-cost-trend"}
            className="panel section"
          >
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">
                  {utilityTrendDescriptor?.kind || "dashboard"}
                </div>
                <h2>{utilityTrendDescriptor?.nav_label || "Utility cost trend"}</h2>
              </div>
            </div>
            <div style={{ display: "grid", gap: "18px" }}>
              {utilityTypes.map((utilityType) => {
                const typeRows = utilityTrend.filter(
                  (row) => row.utility_type === utilityType
                );
                const months = [
                  ...new Set(typeRows.map((row) => row.billing_month)),
                ].sort();
                const series = [
                  {
                    label: utilityType,
                    color: "var(--accent-warm)",
                    values: months.map((month) => {
                      const row = typeRows.find(
                        (entry) => entry.billing_month === month
                      );
                      return row ? Number(row.total_cost) : null;
                    }),
                  },
                ];
                return (
                  <section key={utilityType}>
                    <div
                      className="metricLabel"
                      style={{ marginBottom: "10px" }}
                    >
                      {utilityType}
                    </div>
                    <SparklineChart
                      series={series}
                      labels={months}
                      height={100}
                      width={500}
                    />
                  </section>
                );
              })}
            </div>
          </article>
        )}

        <IncomeScenarioPanel />

        <div className="buttonRow">
          <Link className="ghostButton" href="#expense-shock">
            Expense shock handoff
          </Link>
          {user?.role === "admin" ? (
            <Link className="ghostButton" href="/control/confidence">
              Publication confidence
            </Link>
          ) : (
            <Link className="ghostButton" href="/briefing">
              Morning brief
            </Link>
          )}
        </div>
      </section>
    </AppShell>
  );
}
