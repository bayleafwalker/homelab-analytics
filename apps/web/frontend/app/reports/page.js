import { AppShell } from "@/components/app-shell";
import { RendererDiscovery } from "@/components/renderer-discovery";
import { SparklineChart } from "@/components/sparkline-chart";
import { IncomeScenarioPanel } from "@/components/income-scenario-panel";
import { ExpenseShockPanel } from "@/components/expense-shock-panel";
import {
  getAccountBalanceTrend,
  getCurrentUser,
  getMonthlyCashflow,
  getSpendByCategoryMonthly,
  getSubscriptionSummary,
  getUtilityCostTrend,
} from "@/lib/backend";
import { getWebRendererDiscovery } from "@/lib/renderer-discovery";

export default async function ReportsPage() {
  const user = await getCurrentUser();
  const [discovery, rows, balanceTrend, spendByCategory, subscriptions, utilityTrend] =
    await Promise.all([
      getWebRendererDiscovery(),
      getMonthlyCashflow(),
      getAccountBalanceTrend(),
      getSpendByCategoryMonthly(),
      getSubscriptionSummary(),
      getUtilityCostTrend(),
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
      title="Published Reports"
      eyebrow="Published Access"
      lede="The web renderer discovers report views from backend-owned publication and UI descriptor contracts before it renders any page-local detail."
    >
      <section className="stack">
        <RendererDiscovery
          title="Published report views"
          eyebrow="Web renderer discovery"
          descriptors={discovery.reports}
        />

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
          {rows.length === 0 ? (
            <div className="empty">No published rows yet.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Booking month</th>
                    <th>Income</th>
                    <th>Expense</th>
                    <th>Net</th>
                    <th>Transactions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
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
          {spendByCategory.length === 0 ? (
            <div className="empty">No category spend data yet.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Category</th>
                    <th>Counterparty</th>
                    <th>Total Expense</th>
                    <th>Count</th>
                  </tr>
                </thead>
                <tbody>
                  {spendByCategory.map((row, index) => (
                    <tr key={index}>
                      <td>{row.booking_month}</td>
                      <td>{row.category}</td>
                      <td>{row.counterparty_name}</td>
                      <td>{row.total_expense}</td>
                      <td>{row.transaction_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
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
          {subscriptions.length === 0 ? (
            <div className="empty">No subscription data yet.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Provider</th>
                    <th>Billing cycle</th>
                    <th>Monthly equiv</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {subscriptions.map((row, index) => (
                    <tr key={index}>
                      <td>{row.subscription_name}</td>
                      <td>{row.provider_name}</td>
                      <td>{row.billing_cycle}</td>
                      <td>{row.monthly_equivalent_cost}</td>
                      <td>
                        <span className={`statusPill status-${row.status}`}>
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
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
        <ExpenseShockPanel />
      </section>
    </AppShell>
  );
}
