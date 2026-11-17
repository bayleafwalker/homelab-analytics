import Link from "next/link";

import { RetroShell } from "@/components/retro-shell";
import { SparklineChart } from "@/components/sparkline-chart";
import { latestMonthRows, splitByCurrency } from "@/lib/currency-groups";
import { formatMoney } from "@/lib/format";
import {
  getAccountBalanceTrend,
  getAffordabilityRatios,
  getCurrentUser,
  getMonthlyCashflow,
  getRecurringCostBaseline,
  getSpendByCategoryMonthly,
  getSubscriptionSummary,
} from "@/lib/backend";
import { getWebRendererDiscovery } from "@/lib/renderer-discovery";

const AFFORDABILITY_LABELS = {
  housing_to_income: "Housing / income",
  total_cost_to_income: "Total cost / income",
  debt_service_ratio: "Debt service ratio",
};
const PRIMARY_DESCRIPTOR_KEYS = new Set([
  "cashflow",
  "balance-trend",
  "spending-by-category",
  "subscriptions",
]);

export default async function RetroMoneyPage() {
  const user = await getCurrentUser();
  const [
    discovery,
    cashflowRows,
    balanceTrend,
    spendByCategory,
    subscriptions,
    recurringBaseline,
    affordability,
  ] = await Promise.all([
    getWebRendererDiscovery(),
    getMonthlyCashflow(),
    getAccountBalanceTrend(),
    getSpendByCategoryMonthly(),
    getSubscriptionSummary(),
    getRecurringCostBaseline(),
    getAffordabilityRatios(),
  ]);

  const moneyDescriptors = discovery.reports.filter(
    (descriptor) => descriptor.navGroup === "Money"
  );
  const descriptorByKey = Object.fromEntries(
    moneyDescriptors.map((descriptor) => [descriptor.key, descriptor])
  );
  const cashflowDescriptor = descriptorByKey.cashflow;
  const balanceTrendDescriptor = descriptorByKey["balance-trend"];
  const spendingDescriptor = descriptorByKey["spending-by-category"];
  const subscriptionsDescriptor = descriptorByKey.subscriptions;
  const discoveryOnlyDescriptors = moneyDescriptors.filter(
    (descriptor) => !PRIMARY_DESCRIPTOR_KEYS.has(descriptor.key)
  );
  const activeSubscriptions = subscriptions.filter((row) => row.status === "active");
  // Every figure stays inside its own currency: the newest month has one row
  // per currency, balances are one series per (account, currency), and the
  // cashflow trend is one chart per currency.
  const latestCashflowRows = latestMonthRows(cashflowRows, "booking_month");
  const latestCashflow = latestCashflowRows[0];
  const balanceAccounts = [
    ...new Map(
      balanceTrend.map((row) => [`${row.account_id}|${row.currency}`, { account: row.account_id, currency: row.currency }])
    ).values(),
  ];
  const balanceMonths = [...new Set(balanceTrend.map((row) => row.booking_month))].sort();
  const balanceSeries = balanceAccounts.map(({ account, currency }, index) => {
    const colors = [
      "var(--retro-ok)",
      "var(--retro-accent)",
      "var(--retro-warn)",
      "#ff8f8f",
    ];
    return {
      label: currency ? `${account} (${currency})` : account,
      color: colors[index % colors.length],
      values: balanceMonths.map((month) => {
        const row = balanceTrend.find(
          (entry) =>
            entry.account_id === account && entry.currency === currency && entry.booking_month === month
        );
        return row ? Number(row.cumulative_balance) : null;
      }),
    };
  });
  const cashflowCharts = splitByCurrency(cashflowRows).map(({ currency, rows }) => ({
    currency,
    labels: rows.map((row) => row.booking_month),
    series: [
      { label: "Income", color: "var(--retro-ok)", values: rows.map((row) => Number(row.income || 0)) },
      { label: "Expense", color: "var(--retro-warn)", values: rows.map((row) => Number(row.expense || 0)) },
      { label: "Net", color: "var(--retro-accent)", values: rows.map((row) => Number(row.net || 0)) },
    ],
  }));
  const affordabilityRows = splitByCurrency(affordability)
    .map(
      ({ rows }) =>
        rows.find((row) => row.ratio_name === "housing_to_income") || rows[0] || null
    )
    .filter(Boolean);

  return (
    <RetroShell
      currentPath="/retro/money"
      user={user}
      title="CRT Deck / Money"
      eyebrow="Retro Detail View"
      lede="Published finance-facing reporting views rendered inside the CRT shell. The data stays on the same reporting APIs used by the classic reports page."
    >
      <section className="retroMetricGrid">
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Latest Month</span>
          <strong>{latestCashflow?.booking_month || "NO DATA"}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Net</span>
          <strong>
            {latestCashflowRows.length > 0
              ? latestCashflowRows.map((row) => formatMoney(row.net, row.currency)).join(" · ")
              : "0.00"}
          </strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Active Subs</span>
          <strong>{activeSubscriptions.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Baseline Rows</span>
          <strong>{recurringBaseline.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Affordability</span>
          <strong>
            {affordabilityRows.length > 0
              ? affordabilityRows
                  .map(
                    (row) =>
                      `${(Number(row.ratio) * 100).toFixed(1)}%${affordabilityRows.length > 1 ? ` ${row.currency}` : ""}`
                  )
                  .join(" · ")
              : "n/a"}
          </strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Published Views</span>
          <strong>{moneyDescriptors.length}</strong>
        </article>
      </section>

      {discoveryOnlyDescriptors.length > 0 ? (
        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Published Views</div>
              <h2>Additional money discovery</h2>
            </div>
          </div>
          <div className="retroModuleGrid">
            {discoveryOnlyDescriptors.map((descriptor) => (
              <article key={descriptor.key} id={descriptor.anchor} className="retroSubPanel">
                <div className="retroMonoStrong">{descriptor.nav_label}</div>
                <div className="retroMuted">
                  {descriptor.publications.map((publication) => publication.display_name).join(" / ") ||
                    "Published finance view"}
                </div>
                <Link className="retroActionLink" href={descriptor.nav_path}>
                  Classic route
                </Link>
              </article>
            ))}
          </div>
        </article>
      ) : null}

      <article id={cashflowDescriptor?.anchor || "cashflow"} className="retroPanel">
        <div className="retroSectionHeader">
          <div>
            <div className="retroEyebrow">Cashflow Bus</div>
            <h2>{cashflowDescriptor?.nav_label || "Monthly cashflow"}</h2>
          </div>
          <Link className="retroActionLink" href="/reports">
            Classic reports
          </Link>
        </div>
        {cashflowRows.length === 0 ? (
          <div className="retroEmptyState">No published cashflow rows yet.</div>
        ) : (
          <>
            {cashflowCharts.map((chart) => (
              <SparklineChart
                key={chart.currency || "none"}
                series={chart.series}
                labels={chart.labels}
                height={132}
                width={720}
              />
            ))}
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Currency</th>
                    <th>Income</th>
                    <th>Expense</th>
                    <th>Net</th>
                    <th>Transactions</th>
                  </tr>
                </thead>
                <tbody>
                  {cashflowRows.slice(-12).map((row) => (
                    <tr key={`${row.booking_month}-${row.currency}`}>
                      <td>{row.booking_month}</td>
                      <td>{row.currency}</td>
                      <td>{row.income}</td>
                      <td>{row.expense}</td>
                      <td>{row.net}</td>
                      <td>{row.transaction_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </article>

      <section className="retroSplit">
        <article id={balanceTrendDescriptor?.anchor || "balance-trend"} className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Balance Curve</div>
              <h2>{balanceTrendDescriptor?.nav_label || "Account balance trend"}</h2>
            </div>
          </div>
          {balanceSeries.length === 0 ? (
            <div className="retroEmptyState">No account balance trend data yet.</div>
          ) : (
            <SparklineChart series={balanceSeries} labels={balanceMonths} height={132} width={640} />
          )}
        </article>

        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Ratios</div>
              <h2>Affordability ratios</h2>
            </div>
          </div>
          {affordability.length === 0 ? (
            <div className="retroEmptyState">No affordability ratios published.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Ratio</th>
                    <th>Period</th>
                    <th>Numerator</th>
                    <th>Denominator</th>
                    <th>Ratio</th>
                    <th>Assessment</th>
                  </tr>
                </thead>
                <tbody>
                  {affordability.slice(0, 8).map((row, index) => (
                    <tr key={`${row.ratio_name}-${row.period_label || index}`}>
                      <td>{AFFORDABILITY_LABELS[row.ratio_name] || row.ratio_name}</td>
                      <td>{row.period_label || "latest"}</td>
                      <td>
                        {Number(row.numerator).toFixed(2)} {row.currency}
                      </td>
                      <td>
                        {Number(row.denominator).toFixed(2)} {row.currency}
                      </td>
                      <td>
                        {row.ratio != null
                          ? `${(Number(row.ratio) * 100).toFixed(1)}%`
                          : "n/a"}
                      </td>
                      <td>{row.assessment}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>

      <section className="retroSplit">
        <article id={spendingDescriptor?.anchor || "spending-by-category"} className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Spend Map</div>
              <h2>{spendingDescriptor?.nav_label || "Spend by category"}</h2>
            </div>
          </div>
          {spendByCategory.length === 0 ? (
            <div className="retroEmptyState">No category spend rows published.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Category</th>
                    <th>Counterparty</th>
                    <th>Expense</th>
                    <th>Count</th>
                  </tr>
                </thead>
                <tbody>
                  {spendByCategory.slice(0, 12).map((row, index) => (
                    <tr key={`${row.booking_month}-${row.category}-${index}`}>
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

        <article id={subscriptionsDescriptor?.anchor || "subscriptions"} className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Subscription Deck</div>
              <h2>{subscriptionsDescriptor?.nav_label || "Subscription summary"}</h2>
            </div>
          </div>
          {subscriptions.length === 0 ? (
            <div className="retroEmptyState">No subscription data yet.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Provider</th>
                    <th>Billing</th>
                    <th>Monthly</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {subscriptions.slice(0, 12).map((row, index) => (
                    <tr key={`${row.contract_id}-${index}`}>
                      <td>{row.contract_name}</td>
                      <td>{row.provider}</td>
                      <td>{row.billing_cycle}</td>
                      <td>{row.monthly_equivalent}</td>
                      <td>{row.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>

      <article className="retroPanel">
        <div className="retroSectionHeader">
          <div>
            <div className="retroEyebrow">Committed Load</div>
            <h2>Recurring baseline</h2>
          </div>
        </div>
        {recurringBaseline.length === 0 ? (
          <div className="retroEmptyState">No recurring baseline rows published.</div>
        ) : (
          <div className="retroTableWrap">
            <table className="retroTable">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Description</th>
                  <th>Monthly</th>
                  <th>Currency</th>
                </tr>
              </thead>
              <tbody>
                {recurringBaseline.slice(0, 12).map((row, index) => (
                  <tr key={`${row.cost_source}-${index}`}>
                    <td>{row.cost_source}</td>
                    <td>{row.counterparty_or_contract}</td>
                    <td>{row.monthly_amount}</td>
                    <td>{row.currency}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </article>
    </RetroShell>
  );
}
