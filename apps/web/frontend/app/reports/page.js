import { AppShell } from "@/components/app-shell";
import { SparklineChart } from "@/components/sparkline-chart";
import {
  getAccountBalanceTrend,
  getCurrentUser,
  getMonthlyCashflow,
  getSpendByCategoryMonthly,
  getSubscriptionSummary,
  getUtilityCostTrend,
} from "@/lib/backend";

export default async function ReportsPage() {
  const user = await getCurrentUser();
  const [rows, balanceTrend, spendByCategory, subscriptions, utilityTrend] =
    await Promise.all([
      getMonthlyCashflow(),
      getAccountBalanceTrend(),
      getSpendByCategoryMonthly(),
      getSubscriptionSummary(),
      getUtilityCostTrend(),
    ]);

  // Group balance trend rows by account_id for SparklineChart
  const balanceAccounts = [...new Set(balanceTrend.map((r) => r.account_id))];
  const balanceMonths = [...new Set(balanceTrend.map((r) => r.booking_month))].sort();
  const balanceSeries = balanceAccounts.map((account, idx) => {
    const colors = ["var(--ok)", "var(--accent)", "var(--accent-cool)", "var(--accent-warm)"];
    return {
      label: account,
      color: colors[idx % colors.length],
      values: balanceMonths.map((month) => {
        const row = balanceTrend.find((r) => r.account_id === account && r.booking_month === month);
        return row ? Number(row.balance) : null;
      }),
    };
  });

  // Group utility trend by utility_type
  const utilityTypes = [...new Set(utilityTrend.map((r) => r.utility_type))];

  return (
    <AppShell
      currentPath="/reports"
      user={user}
      title="Published Reports"
      eyebrow="Published Access"
      lede="This shell is intentionally narrow. It renders published reporting models without embedding source-specific logic."
    >
      <section className="stack">
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Built-In Mart</div>
              <h2>Monthly cashflow</h2>
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
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Accounts</div>
                <h2>Account balance trend</h2>
              </div>
            </div>
            <SparklineChart series={balanceSeries} labels={balanceMonths} height={120} width={600} />
          </article>
        )}

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Spend</div>
              <h2>Spend by category</h2>
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
                  {spendByCategory.map((row, i) => (
                    <tr key={i}>
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

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Subscriptions</div>
              <h2>Subscription summary</h2>
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
                  {subscriptions.map((row, i) => (
                    <tr key={i}>
                      <td>{row.subscription_name}</td>
                      <td>{row.provider_name}</td>
                      <td>{row.billing_cycle}</td>
                      <td>{row.monthly_equivalent_cost}</td>
                      <td>
                        <span className={`statusPill status-${row.status}`}>{row.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        {utilityTrend.length > 0 &&
          utilityTypes.map((utilityType) => {
            const typeRows = utilityTrend.filter((r) => r.utility_type === utilityType);
            const months = [...new Set(typeRows.map((r) => r.booking_month))].sort();
            const series = [
              {
                label: utilityType,
                color: "var(--accent-warm)",
                values: months.map((month) => {
                  const row = typeRows.find((r) => r.booking_month === month);
                  return row ? Number(row.total_cost) : null;
                }),
              },
            ];
            return (
              <article key={utilityType} className="panel section">
                <div className="sectionHeader">
                  <div>
                    <div className="eyebrow">Utilities</div>
                    <h2>{utilityType} cost trend</h2>
                  </div>
                </div>
                <SparklineChart series={series} labels={months} height={100} width={500} />
              </article>
            );
          })}
      </section>
    </AppShell>
  );
}
