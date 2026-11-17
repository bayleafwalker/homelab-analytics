import Link from "next/link";

import { RetroShell } from "@/components/retro-shell";
import { SparklineChart } from "@/components/sparkline-chart";
import { splitByCurrency, sumField } from "@/lib/currency-groups";
import { formatMoney } from "@/lib/format";
import {
  getAttentionItems,
  getCurrentUser,
  getHouseholdOverviewRows,
  getMonthlyCashflow,
  getRecentChanges,
  getRecurringCostBaseline,
  getRuns,
  getSubscriptionSummary,
  getUtilityCostTrend,
} from "@/lib/backend";
import { getWebRendererDiscovery } from "@/lib/renderer-discovery";

const MODULE_META = {
  Overview: {
    href: "/retro",
    label: "Overview",
    description: "Operating picture, launcher deck, and current baseline signals."
  },
  Money: {
    href: "/retro/money",
    label: "Money",
    description: "Cashflow, balances, subscriptions, and finance-driven report views."
  },
  Utilities: {
    href: "/retro/utilities",
    label: "Utilities",
    description: "Energy price, contract, and usage views with utility-focused reporting."
  },
  Operations: {
    href: "/retro/operations",
    label: "Operations",
    description: "Homelab service health, backups, storage risk, and workload visibility."
  },
  Control: {
    href: "/retro/control",
    label: "Control",
    description: "Admin-oriented security and control-plane summaries."
  },
  Terminal: {
    href: "/retro/terminal",
    label: "Terminal",
    description: "Allowlisted command launcher for control-plane diagnostics and queue actions."
  }
};
const MODULE_ORDER = ["Overview", "Money", "Utilities", "Operations", "Control", "Terminal"];
const EMPTY_DISCOVERY = { overview: [], reports: [], homelab: [] };

function optionalPanelData(promise, fallback) {
  return promise.catch(() => fallback);
}

function retroPathForModule(group, descriptor) {
  if (group === "Money") {
    return descriptor.anchor ? `/retro/money#${descriptor.anchor}` : "/retro/money";
  }
  if (group === "Utilities") {
    return descriptor.anchor
      ? `/retro/utilities#${descriptor.anchor}`
      : "/retro/utilities";
  }
  if (group === "Operations") {
    return descriptor.anchor
      ? `/retro/operations#${descriptor.anchor}`
      : "/retro/operations";
  }
  return "/retro";
}

function buildLauncherModules(discovery, user) {
  const grouped = new Map();
  const descriptors = [
    ...discovery.overview,
    ...discovery.reports,
    ...discovery.homelab,
  ];

  for (const descriptor of descriptors) {
    const group = descriptor.navGroup || "Overview";
    const current = grouped.get(group) || [];
    current.push({
      ...descriptor,
      nav_path: retroPathForModule(group, descriptor),
    });
    grouped.set(group, current);
  }

  const modules = MODULE_ORDER.map((name) => ({
    name,
    meta: MODULE_META[name],
    descriptors: grouped.get(name) || []
  })).filter((module) => {
    if (module.name === "Control" || module.name === "Terminal") {
      return user.role === "admin";
    }
    return Boolean(module.meta);
  });

  if (user.role === "admin") {
    modules.forEach((module) => {
      if (module.name === "Control") {
        module.descriptors = [
          { key: "retro-control", nav_label: "Retro control", nav_path: "/retro/control" },
          { key: "retro-catalog", nav_label: "Catalog", nav_path: "/retro/control/catalog" },
          { key: "retro-execution", nav_label: "Execution", nav_path: "/retro/control/execution" },
        ];
      }
      if (module.name === "Terminal") {
        module.descriptors = [
          { key: "retro-terminal", nav_label: "Admin terminal", nav_path: "/retro/terminal" },
        ];
      }
    });
  }

  return modules;
}

export default async function RetroDashboardPage() {
  const user = await getCurrentUser();
  const [
    discovery,
    cashflowRows,
    overviewRows,
    attentionItems,
    recentChanges,
    runs,
    recurringBaseline,
    utilityTrend,
    subscriptions,
  ] = await Promise.all([
    optionalPanelData(getWebRendererDiscovery(), EMPTY_DISCOVERY),
    optionalPanelData(getMonthlyCashflow(), []),
    optionalPanelData(getHouseholdOverviewRows(), []),
    optionalPanelData(getAttentionItems(), []),
    optionalPanelData(getRecentChanges(), []),
    optionalPanelData(getRuns(6), []),
    optionalPanelData(getRecurringCostBaseline(), []),
    optionalPanelData(getUtilityCostTrend(undefined), []),
    optionalPanelData(getSubscriptionSummary(), []),
  ]);
  const modules = buildLauncherModules(discovery, user);
  // Every figure stays inside its own currency (no conversion, no blending).
  const latestMonth = [...new Set(cashflowRows.map((row) => row.booking_month))].sort().at(-1);
  const amountsText = (amounts) => amounts.map((a) => formatMoney(a.value, a.currency)).join(" · ");
  const recurringAmounts = splitByCurrency(subscriptions.filter((row) => row.status === "active")).map(
    ({ currency, rows }) => ({ currency, value: sumField(rows, "monthly_equivalent") })
  );
  const trendCharts = splitByCurrency(cashflowRows).map(({ currency, rows }) => {
    const recent = rows.slice(-12);
    return {
      currency,
      labels: recent.map((row) => row.booking_month),
      series: [
        { label: "Income", color: "var(--retro-ok)", values: recent.map((row) => Number(row.income || 0)) },
        { label: "Expense", color: "var(--retro-warn)", values: recent.map((row) => Number(row.expense || 0)) },
        { label: "Net", color: "var(--retro-accent)", values: recent.map((row) => Number(row.net || 0)) },
      ],
    };
  });
  const utilityAmounts = splitByCurrency(utilityTrend.filter((row) => row.currency)).map(
    ({ currency, rows }) => {
      const months = [...new Set(rows.map((row) => row.billing_month))].sort();
      const month = months.at(-1);
      return { currency, month, value: sumField(rows.filter((row) => row.billing_month === month), "total_cost") };
    }
  );
  const overviewWithCashflow = overviewRows.filter((row) => row.currency && row.cashflow_net != null);

  return (
    <RetroShell
      currentPath="/retro"
      user={user}
      title="Homelab Analytics // CRT Deck"
      eyebrow="Parallel Retro Shell"
      lede="A route-scoped CRT renderer over the same reporting and control-plane APIs. Use this shell as a themed launcher and operating picture, not a second product stack."
    >
      <section className="retroHero retroPanel">
        <div>
          <div className="retroEyebrow">Operating Picture</div>
          <h2>
            {overviewWithCashflow.length > 0
              ? `NET ${amountsText(overviewWithCashflow.map((row) => ({ value: row.cashflow_net, currency: row.currency })))}`
              : "SIGNAL ACQUIRED"}
          </h2>
          <p className="retroLede">
            {overviewWithCashflow.length > 0
              ? `${overviewWithCashflow
                  .map(
                    (row) =>
                      `${row.currency}: income ${formatMoney(row.cashflow_income, row.currency)} // expense ${formatMoney(row.cashflow_expense, row.currency)}`
                  )
                  .join(" | ")} // This shell stays API-backed and reads reporting outputs only.`
              : "The retro overview stays thin: reporting snapshots, recent runs, and launcher modules over the existing web/API contracts."}
          </p>
        </div>
        <div className="retroMetricStrip">
          <div className="retroMetricBox">
            <span className="retroMetricLabel">Latest Month</span>
            <strong>{latestMonth || "NO DATA"}</strong>
          </div>
          <div className="retroMetricBox">
            <span className="retroMetricLabel">Recurring / Mo</span>
            <strong>{recurringAmounts.length > 0 ? amountsText(recurringAmounts) : "0.00"}</strong>
          </div>
          <div className="retroMetricBox">
            <span className="retroMetricLabel">Utility Snapshot</span>
            <strong>{utilityAmounts.length > 0 ? amountsText(utilityAmounts) : "0.00"}</strong>
          </div>
          <div className="retroMetricBox">
            <span className="retroMetricLabel">Recent Runs</span>
            <strong>{runs.length}</strong>
          </div>
        </div>
      </section>

      <section className="retroModuleGrid">
        {modules.map((module) => (
          <article key={module.name} className="retroModuleCard retroPanel">
            <div className="retroSectionHeader">
              <div>
                <div className="retroEyebrow">Module</div>
                <h2>{module.meta.label}</h2>
              </div>
              <Link className="retroActionLink" href={module.meta.href}>
                Launch
              </Link>
            </div>
            <p className="retroMuted">{module.meta.description}</p>
            <div className="retroModuleLinks">
              {module.descriptors.length > 0 ? (
                module.descriptors.map((descriptor) => (
                  <Link key={descriptor.key} className="retroModuleLink" href={descriptor.nav_path}>
                    {descriptor.nav_label}
                  </Link>
                ))
              ) : (
                <div className="retroMuted">No renderer-discovered entries published for this module.</div>
              )}
            </div>
          </article>
        ))}
      </section>

      {trendCharts.map((chart) => (
        <article className="retroPanel" key={chart.currency || "none"}>
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Trend Bus{chart.currency ? ` / ${chart.currency}` : ""}</div>
              <h2>Cashflow Signal / Last 12 Months</h2>
            </div>
            <span className="retroTag">REPORTING LAYER</span>
          </div>
          <SparklineChart series={chart.series} labels={chart.labels} height={132} width={720} />
        </article>
      ))}

      <section className="retroSplit">
        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Attention Queue</div>
              <h2>Items needing review</h2>
            </div>
            <Link className="retroActionLink" href="/reports">
              Reports
            </Link>
          </div>
          {attentionItems.length === 0 ? (
            <div className="retroEmptyState">No attention items published.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Domain</th>
                    <th>Item</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {attentionItems.slice(0, 6).map((row, index) => (
                    <tr key={`${row.item_key || row.title || index}`}>
                      <td>{row.domain || "system"}</td>
                      <td>{row.title || row.description || row.item_key}</td>
                      <td>{row.status || row.severity || "review"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Run Feed</div>
              <h2>Recent ingestion runs</h2>
            </div>
            <Link className="retroActionLink" href="/runs">
              Full history
            </Link>
          </div>
          {runs.length === 0 ? (
            <div className="retroEmptyState">No runs recorded yet.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Run</th>
                    <th>Status</th>
                    <th>Dataset</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.run_id}>
                      <td>
                        <Link className="retroModuleLink" href={`/runs/${run.run_id}`}>
                          {run.run_id}
                        </Link>
                      </td>
                      <td>{run.status}</td>
                      <td>{run.dataset_name}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>

      <section className="retroSplit">
        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Recurring Baseline</div>
              <h2>Committed monthly load</h2>
            </div>
            <Link className="retroActionLink" href="/costs">
              Costs
            </Link>
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
                  </tr>
                </thead>
                <tbody>
                  {recurringBaseline.slice(0, 6).map((row, index) => (
                    <tr key={`${row.cost_source}-${index}`}>
                      <td>{row.cost_source}</td>
                      <td>{row.counterparty_or_contract}</td>
                      <td>{Number(row.monthly_amount).toFixed(2)} {row.currency}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Recent Changes</div>
              <h2>What moved most recently</h2>
            </div>
            <Link className="retroActionLink" href="/reports">
              Inspect
            </Link>
          </div>
          {recentChanges.length === 0 ? (
            <div className="retroEmptyState">No recent-change rows published.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Domain</th>
                    <th>Change</th>
                    <th>Period</th>
                  </tr>
                </thead>
                <tbody>
                  {recentChanges.slice(0, 6).map((row, index) => (
                    <tr key={`${row.change_key || index}`}>
                      <td>{row.domain || "system"}</td>
                      <td>{row.title || row.description || row.change_key}</td>
                      <td>{row.period_label || row.booking_month || "latest"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>
    </RetroShell>
  );
}
