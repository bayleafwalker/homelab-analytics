import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { AsOfScrubber } from "@/components/as-of-scrubber";
import { HistoryTag, NoHistory, currentRead, historyNote, isUnavailable } from "@/components/as-of-history";
import { Explain } from "@/components/explain-server";
import { ResponsiveTable } from "@/components/responsive-table";
import { OnboardingChecklist } from "@/components/onboarding-checklist";
import { ONBOARDING_SOURCES } from "@/lib/onboarding-sources";
import { SparklineChart } from "@/components/sparkline-chart";
import { stateIndicatorBadge } from "@/lib/state-indicators";
import { StatePanel } from "@/components/state-panel";
import { latestMonthRows, splitByCurrency, sumField } from "@/lib/currency-groups";
import { formatMoney, formatMonth, monthsBetween } from "@/lib/format";
import {
  getAffordabilityRatios,
  getAffordabilityRatiosAsOf,
  getAttentionItems,
  getAttentionItemsAsOf,
  getCurrentUser,
  getHouseholdOverviewAsOf,
  getHouseholdOverviewRows,
  getMonthlyCashflow,
  getRecentChanges,
  getRecentChangesAsOf,
  getRecurringCostBaseline,
  getRecurringCostBaselineAsOf,
  getRuns,
  getSourceFreshness,
  getSpendByCategoryMonthly,
  getSubscriptionSummary,
  getSubscriptionSummaryAsOf,
  getUtilityCostTrend,
} from "@/lib/backend";

const MONTH_RE = /^\d{4}-\d{2}$/;

function dashboardHref(month) {
  return month ? `/?asof=${month}` : "/";
}

// Snapshot reads for the current-only publications, fetched alongside the
// live reads whenever a month is requested. Used only if that month turns
// out to be a past published month.
function snapshotReads(month) {
  if (!month) return Promise.resolve(null);
  return Promise.all([
    getHouseholdOverviewAsOf(month),
    getAttentionItemsAsOf(month),
    getRecentChangesAsOf(month),
    getSubscriptionSummaryAsOf(month),
    getAffordabilityRatiosAsOf(month),
    getRecurringCostBaselineAsOf(month),
  ]).then(([overview, attention, changes, subscriptions, ratios, baseline]) => ({
    overview,
    attention,
    changes,
    subscriptions,
    ratios,
    baseline,
  }));
}

export default async function DashboardPage({ searchParams }) {
  const requestedAsOf = MONTH_RE.test(searchParams?.asof || "") ? searchParams.asof : null;
  const user = await getCurrentUser();
  const [cashflowRows, runs, liveOverviewRows, liveAttention, liveChanges, spendByCategory, liveSubscriptions, utilityTrend, liveRatios, liveBaseline, freshnessDatasets, pastReads] =
    await Promise.all([
      getMonthlyCashflow(),
      getRuns(8),
      getHouseholdOverviewRows(),
      getAttentionItems(),
      getRecentChanges(),
      getSpendByCategoryMonthly(),
      getSubscriptionSummary(),
      getUtilityCostTrend(),
      getAffordabilityRatios(),
      getRecurringCostBaseline(),
      // Source freshness is an admin control-plane read; other roles get the
      // checklist without per-source freshness instead of a failed page.
      user?.role === "admin" ? getSourceFreshness() : Promise.resolve([]),
      snapshotReads(requestedAsOf),
    ]);
  // As-of view: month-keyed publications (monthly cashflow, spend by
  // category, utility trend) rewind by filtering their own months. The
  // current-only publications (overview, attention items, recent changes,
  // subscriptions, ratios, recurring baseline) are read from the reporting
  // layer's dated snapshot for that month; a month without one shows
  // "No history" instead of today's rows.
  // Monetary publications hold one row per month AND currency: months are
  // unique, and every figure below stays inside its own currency.
  const publishedMonths = [...new Set(cashflowRows.map((r) => r.booking_month))].sort();
  const newestMonth = publishedMonths.at(-1) || null;
  const newestRows = latestMonthRows(cashflowRows, "booking_month");
  const newest = newestRows[0] ? { ...newestRows[0], transaction_count: sumField(newestRows, "transaction_count") } : undefined;
  const asOf = requestedAsOf && publishedMonths.includes(requestedAsOf) ? requestedAsOf : newestMonth;
  const viewingPast = Boolean(newestMonth && asOf && asOf !== newestMonth && pastReads);
  const reads = viewingPast
    ? pastReads
    : {
        overview: currentRead(liveOverviewRows),
        attention: currentRead(liveAttention),
        changes: currentRead(liveChanges),
        subscriptions: currentRead(liveSubscriptions),
        ratios: currentRead(liveRatios),
        baseline: currentRead(liveBaseline),
      };
  const overviewRows = reads.overview.rows;
  const attentionItems = reads.attention.rows;
  const recentChanges = reads.changes.rows;
  const subscriptions = reads.subscriptions.rows;
  const affordabilityRatios = reads.ratios.rows;
  const recurringBaseline = reads.baseline.rows;
  const noHistory = isUnavailable;
  const visibleCashflow = asOf ? cashflowRows.filter((r) => r.booking_month <= asOf) : cashflowRows;
  // Newest visible month: every currency's row, never one of them.
  const latestRows = latestMonthRows(visibleCashflow, "booking_month");
  const latest = latestRows[0];
  const money = (value, currency) => formatMoney(value, currency);
  const now = new Date();
  const dataLagMonths = newest
    ? monthsBetween(newest.booking_month, `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`)
    : null;

  // Top-5 categories for current month
  const latestMonth = latest?.booking_month;
  // Top categories are ranked and summed within each currency.
  const currentMonthSpend = spendByCategory.filter((r) => r.booking_month === latestMonth);
  const categoryGroups = splitByCurrency(currentMonthSpend).map(({ currency, rows }) => ({
    currency,
    totals: Object.values(
      rows.reduce((acc, r) => {
        const cat = r.category || "Uncategorised";
        acc[cat] = acc[cat] || { category: cat, total: 0 };
        acc[cat].total += Number(r.total_expense || 0);
        return acc;
      }, {})
    )
      .sort((a, b) => b.total - a.total)
      .slice(0, 5),
  }));

  // Utility snapshot: per currency, latest billed month and the previous one
  // for the delta. A usage-only period (no currency) is not a cost.
  const billedUtility = utilityTrend.filter((r) => r.currency);
  const utilityGroups = splitByCurrency(billedUtility).map(({ currency, rows }) => {
    const months = [...new Set(rows.map((r) => r.billing_month))]
      .filter((m) => !asOf || !MONTH_RE.test(m || "") || m <= asOf)
      .sort();
    const month = months.at(-1);
    const prevMonth = months.at(-2);
    const total = sumField(rows.filter((r) => r.billing_month === month), "total_cost");
    const prevTotal = sumField(rows.filter((r) => r.billing_month === prevMonth), "total_cost");
    return {
      currency,
      month,
      prevMonth,
      total,
      delta: prevTotal > 0 ? ((total - prevTotal) / prevTotal) * 100 : null,
    };
  });
  const utilityMonthsShown = [...new Set(utilityGroups.map((g) => g.month).filter(Boolean))].sort();
  const latestUtilityMonth = utilityMonthsShown.at(-1);

  // Recurring cost: active subscription monthly equivalents, per currency.
  const recurringGroups = splitByCurrency(subscriptions.filter((r) => r.status === "active")).map(
    ({ currency, rows }) => ({ currency, total: sumField(rows, "monthly_equivalent") })
  );

  // Onboarding checklist: compute fresh datasets and next suggestion
  const freshDatasetNames = freshnessDatasets
    .filter((ds) => {
      if (!ds.landed_at) return false;
      const diffDays = (Date.now() - new Date(ds.landed_at)) / (1000 * 60 * 60 * 24);
      return diffDays < 7;
    })
    .map((ds) => ds.dataset_name);

  const nextSuggestion = ONBOARDING_SOURCES.find((s) => !freshDatasetNames.includes(s.dataset)) || null;

  // One trend chart per currency; series never mix denominations.
  const trendCharts = splitByCurrency(visibleCashflow).map(({ currency, rows }) => {
    const trendRows = rows.slice(-12);
    return {
      currency,
      months: trendRows.length,
      labels: trendRows.map((r) => r.booking_month),
      series: [
        { label: "Income", color: "var(--ok)", values: trendRows.map((r) => Number(r.income)) },
        { label: "Expense", color: "var(--warn)", values: trendRows.map((r) => Number(r.expense)) },
        { label: "Net", color: "var(--accent)", values: trendRows.map((r) => Number(r.net)) },
      ],
    };
  });

  // A past month's hero comes from that month's overview snapshot when one
  // exists, and from the monthly cashflow mart otherwise.
  // One hero per currency: each currency keeps its own figures.
  const overviewHeroes = overviewRows
    .filter((r) => r.currency && r.cashflow_net != null && (!viewingPast || r.current_month === asOf))
    .map((r) => ({
      currency: r.currency,
      month: r.current_month,
      net: r.cashflow_net,
      income: r.cashflow_income,
      expense: r.cashflow_expense,
      subscriptions: r.subscription_total_monthly,
      publication: "mart_household_overview",
      field: "cashflow_net",
      filter: { currency: r.currency },
    }));
  const cashflowHeroes = latestRows.map((r) => ({
    currency: r.currency,
    month: r.booking_month,
    net: r.net,
    income: r.income,
    expense: r.expense,
    subscriptions: null,
    publication: "mart_monthly_cashflow",
    field: "net",
    filter: { booking_month: r.booking_month, currency: r.currency },
  }));
  const pastOverview = viewingPast && overviewHeroes.length > 0;
  const heroes = viewingPast && !pastOverview ? cashflowHeroes : overviewHeroes;
  const hero = heroes[0] || null;
  const overviewLegacy = viewingPast && reads.overview.status === "legacy_denomination_unavailable";
  const monthFilter = latest ? { booking_month: latest.booking_month } : null;
  const heroNote = !viewingPast
    ? null
    : pastOverview
      ? historyNote(reads.overview)
      : overviewLegacy
        ? "The household overview snapshot for this month predates per-currency totals and is unavailable; the figures are read from the monthly cashflow mart."
        : "No household overview snapshot for this month, so the figures are read from the monthly cashflow mart.";

  return (
    <AppShell
      currentPath="/"
      user={user}
      title="Dashboard"
      eyebrow="Household overview"
      lede="This month's money, commitments and the things that need a decision."
    >
      <section className="hero">
        <article className="panel heroCard heroCardMoney">
          <div className="eyebrow heroEyebrow">
            <span>{hero?.month ? formatMonth(hero.month) : "No month published yet"}</span>
            {hero ? (
              <Explain
                publication={hero.publication}
                user={user}
                label={`${Number(hero.net) >= 0 ? "Kept" : "Overspent"} in ${formatMonth(hero.month)}`}
                field={hero.field}
                filter={hero.filter}
                placement="start"
                note={heroNote}
              />
            ) : null}
          </div>
          {hero ? (
            <>
              {heroes.length === 1 ? (
                <>
                  <h1>
                    {Number(hero.net) >= 0 ? "Kept " : "Overspent "}
                    {formatMoney(Math.abs(Number(hero.net)), hero.currency)}
                  </h1>
                  <p className="heroCopy muted">
                    {money(hero.income, hero.currency)} came in and {money(hero.expense, hero.currency)} went out.
                    {hero.subscriptions != null
                      ? ` Recurring subscriptions add ${money(hero.subscriptions, hero.currency)} a month.`
                      : null}
                  </p>
                </>
              ) : (
                <>
                  <h1>Kept or overspent, by currency</h1>
                  {heroes.map((h) => (
                    <p className="heroCopy muted" key={h.currency}>
                      {h.currency}: {Number(h.net) >= 0 ? "kept " : "overspent "}
                      {formatMoney(Math.abs(Number(h.net)), h.currency)} ({money(h.income, h.currency)} in,{" "}
                      {money(h.expense, h.currency)} out
                      {h.subscriptions != null
                        ? `, ${money(h.subscriptions, h.currency)} a month in subscriptions`
                        : ""}
                      )
                    </p>
                  ))}
                </>
              )}
              {overviewLegacy ? (
                <p className="heroCopy muted" role="note">
                  Household overview for {formatMonth(asOf)} is unavailable: its snapshot predates
                  per-currency totals, so its currency is unknown. The cashflow figures above come from the
                  monthly cashflow mart.
                </p>
              ) : null}
              <p className="heroCopy">
                <Link className="inlineLink" href={`/cashflow?m=${hero.month}`}>
                  See where the money went
                </Link>
              </p>
            </>
          ) : (
            <>
              <h1>No household figures yet.</h1>
              <p className="heroCopy muted">
                Upload an account statement and the dashboard fills in from the published reporting layer.
              </p>
              <p className="heroCopy">
                <Link className="inlineLink" href="/upload">Upload a statement</Link>
              </p>
            </>
          )}
        </article>
        <section className="panel heroMetric" aria-label="Data through">
          <div className="eyebrow">Data through</div>
          <div className="value">{newest ? formatMonth(newest.booking_month, { short: true }) : "No imports yet"}</div>
          {newest && dataLagMonths > 1 ? (
            <StatePanel tone="stale" compact title={`${dataLagMonths} months behind`}>
              <p>Figures stop at {formatMonth(newest.booking_month)}. Upload newer statements to catch up.</p>
            </StatePanel>
          ) : (
            <div className="muted">
              {newest
                ? `${newest.transaction_count} transactions in the latest month.`
                : "Import a statement to populate the reporting layer."}
            </div>
          )}
        </section>
      </section>

      <AsOfScrubber
        months={publishedMonths}
        value={asOf}
        hrefFor={dashboardHref}
        label="View the dashboard as of a month"
        note={
          viewingPast
            ? "Money, categories, utilities and the trend are shown for this month. Ratios, fixed commitments, recurring costs, items to review and recent changes are shown as the reporting layer snapshotted them when this was the newest month; a panel with no snapshot for it says so instead of showing today."
            : null
        }
      />

      {viewingPast ? null : (
        <OnboardingChecklist freshDatasets={freshDatasetNames} nextSuggestion={nextSuggestion} />
      )}

      <section className="cards">
        {[
          { key: "income", label: "Income" },
          { key: "expense", label: "Expense" },
          { key: "net", label: "Net" },
        ].map((metric) => (
          <article key={metric.key} className="panel metricCard">
            <div className="metricLabel metricLabelRow">
              <span>{metric.label}</span>
              {latest ? (
                <Explain
                  publication="mart_monthly_cashflow"
                  user={user}
                  label={`${metric.label}, ${formatMonth(latest.booking_month)}`}
                  field={metric.key}
                  filter={monthFilter}
                />
              ) : null}
            </div>
            {latestRows.length === 0 ? (
              <div className="metricValue numMono">No data</div>
            ) : (
              latestRows.map((row) => (
                <div className="metricValue numMono" key={row.currency} title={row.currency}>
                  {money(row[metric.key], row.currency)}
                </div>
              ))
            )}
          </article>
        ))}
      </section>

      {noHistory(reads.ratios) && (
        <section className="panel section" aria-label="Affordability ratios">
          <div className="eyebrow">Affordability ratios</div>
          <NoHistory month={asOf} what="the affordability ratios" read={reads.ratios} />
        </section>
      )}

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
              <article key={`${r.ratio_name}-${r.currency}`} className="panel metricCard">
                <div className="metricLabel metricLabelRow">
                  <span>
                    {label}
                    {new Set(affordabilityRatios.map((x) => x.currency)).size > 1 ? ` (${r.currency})` : ""}
                  </span>
                  <HistoryTag read={reads.ratios} />
                </div>
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

      {(recurringBaseline.length > 0 || noHistory(reads.baseline)) && (
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Recurring baseline</div>
              <h2>Fixed monthly commitments <HistoryTag read={reads.baseline} /></h2>
            </div>
            <Link className="inlineLink" href="/costs">View cost model</Link>
          </div>
          {noHistory(reads.baseline) ? (
            <NoHistory month={asOf} what="the fixed monthly commitments" read={reads.baseline} />
          ) : (
          <ResponsiveTable
            label="Fixed monthly commitments"
            rows={recurringBaseline}
            columns={[
              { key: "counterparty_or_contract", header: "Description", primary: true },
              { key: "cost_source", header: "Source" },
              {
                key: "monthly_amount",
                header: "Monthly",
                align: "end",
                cell: (row) => <span className="numMono">{formatMoney(row.monthly_amount, row.currency)}</span>,
              },
              { key: "confidence", header: "Confidence", cell: (row) => <span className="muted">{row.confidence}</span> },
            ]}
          />
          )}
        </article>
      )}

      {trendCharts.map((chart) => (
        <article className="panel section" style={{ marginBottom: "24px" }} key={chart.currency}>
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Trend{trendCharts.length > 1 ? ` (${chart.currency})` : ""}</div>
              <h2>
                Cashflow, {chart.months === 1 ? "1 month" : `${chart.months} months`} to{" "}
                {formatMonth(chart.labels.at(-1), { short: true })}
                {trendCharts.length > 1 ? ` in ${chart.currency}` : ""}
              </h2>
            </div>
          </div>
          <SparklineChart series={chart.series} labels={chart.labels} height={120} width={600} />
        </article>
      ))}

      <section className="cards" style={{ marginBottom: "24px" }}>
        <article className="panel section">
          <div className="eyebrow metricLabelRow">
            <span>Top Categories</span>
            {latestMonth ? (
              <Explain
                publication="mart_spend_by_category_monthly"
                user={user}
                label={`Top categories, ${formatMonth(latestMonth)}`}
                field="total_expense"
                filter={{ booking_month: latestMonth }}
                note="The five categories with the most spending that month, summed across accounts."
              />
            ) : null}
          </div>
          <h3 style={{ margin: "4px 0 12px" }}>{latestMonth ? formatMonth(latestMonth) : "—"}</h3>
          {categoryGroups.every((g) => g.totals.length === 0) ? (
            <div className="empty">No category data yet.</div>
          ) : (
            categoryGroups.map((group) => (
              <ul
                key={group.currency || "none"}
                aria-label={group.currency ? `Top categories in ${group.currency}` : "Top categories"}
                style={{ listStyle: "none", margin: "0 0 8px", padding: 0, display: "grid", gap: "8px" }}
              >
                {group.totals.map((c) => (
                  <li key={c.category} style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>{c.category}</span>
                    <span className="muted numMono">{money(c.total, group.currency)}</span>
                  </li>
                ))}
              </ul>
            ))
          )}
        </article>

        <article className="panel section">
          <div className="eyebrow metricLabelRow">
            <span>Utilities</span>
            {latestUtilityMonth ? (
              <Explain
                publication="mart_utility_cost_trend_monthly"
                user={user}
                label={`Utilities, ${formatMonth(latestUtilityMonth)}`}
                field="total_cost"
                filter={{ billing_month: latestUtilityMonth }}
              />
            ) : null}
          </div>
          {utilityGroups.length === 0 || !latestUtilityMonth ? (
            <h3 style={{ margin: "4px 0 4px" }}>No data</h3>
          ) : (
            utilityGroups
              .filter((g) => g.month)
              .map((g) => (
                <div key={g.currency} style={{ margin: "4px 0 8px" }}>
                  <h3 style={{ margin: 0, display: "flex", gap: "8px", alignItems: "baseline" }}>
                    <span className="muted">{formatMonth(g.month, { short: true })}</span>
                    <span className="numMono">{money(g.total, g.currency)}</span>
                  </h3>
                  {g.delta !== null && (
                    <div className="muted" style={{ fontSize: "0.85rem" }}>
                      {g.delta >= 0 ? "▲" : "▼"} {Math.abs(g.delta).toFixed(1)}% vs {g.prevMonth}
                    </div>
                  )}
                </div>
              ))
          )}
        </article>

        <article className="panel section">
          <div className="eyebrow metricLabelRow">
            <span>Recurring Costs</span>
            <HistoryTag read={reads.subscriptions} />
            {subscriptions.length > 0 ? (
              <Explain
                publication="mart_subscription_summary"
                user={user}
                label="Recurring costs per month"
                field="monthly_equivalent"
                filter={{ status: "active" }}
                note={[
                  "Sum of the monthly equivalent of every active subscription.",
                  historyNote(reads.subscriptions),
                ]
                  .filter(Boolean)
                  .join(" ")}
              />
            ) : null}
          </div>
          {noHistory(reads.subscriptions) ? (
            <NoHistory month={asOf} what="the subscriptions" read={reads.subscriptions} />
          ) : (
            <>
              {recurringGroups.length > 0 ? (
                recurringGroups.map((g) => (
                  <h3 key={g.currency || "none"} style={{ margin: "4px 0 4px" }}>
                    {`${money(g.total, g.currency)} / mo`}
                  </h3>
                ))
              ) : (
                <h3 style={{ margin: "4px 0 4px" }}>No data</h3>
              )}
              <div className="muted" style={{ fontSize: "0.85rem" }}>
                {subscriptions.filter((r) => r.status === "active").length} active subscriptions
              </div>
            </>
          )}
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
          <ResponsiveTable
            label="Monthly cashflow"
            rows={visibleCashflow.slice().reverse()}
            rowKey={(row) => `${row.booking_month}-${row.currency}`}
            empty={<div className="empty">No successful imports yet.</div>}
            columns={[
              {
                key: "booking_month",
                header: "Month",
                primary: true,
                cell: (row) => (
                  <Link
                    className="inlineLink"
                    href={dashboardHref(row.booking_month === newest?.booking_month ? null : row.booking_month)}
                    aria-current={row.booking_month === asOf ? "true" : undefined}
                  >
                    {formatMonth(row.booking_month)}
                  </Link>
                ),
              },
              { key: "currency", header: "Currency" },
              { key: "income", header: "Income", align: "end", cell: (row) => <span className="numMono">{money(row.income, row.currency)}</span> },
              { key: "expense", header: "Expense", align: "end", cell: (row) => <span className="numMono">{money(row.expense, row.currency)}</span> },
              { key: "net", header: "Net", align: "end", cell: (row) => <span className="numMono">{money(row.net, row.currency)}</span> },
              { key: "transaction_count", header: "Rows", align: "end" },
            ]}
          />
        </article>

        <div className="stack">
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Attention</div>
                <h2>Items to review <HistoryTag read={reads.attention} /></h2>
              </div>
              <Link className="inlineLink" href="/review">See all →</Link>
            </div>
            {noHistory(reads.attention) ? (
              <NoHistory month={asOf} what="the items to review" read={reads.attention} />
            ) : attentionItems.length === 0 ? (
              <div className="empty">Nothing requires attention.</div>
            ) : (
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "10px" }}>
                {[...attentionItems]
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
                <h2>Recent changes <HistoryTag read={reads.changes} /></h2>
              </div>
            </div>
            <ResponsiveTable
              label="Recent changes"
              rows={recentChanges}
              dense
              empty={
                noHistory(reads.changes) ? (
                  <NoHistory month={asOf} what="the recent changes" read={reads.changes} />
                ) : (
                  <div className="empty">No recent changes recorded.</div>
                )
              }
              columns={[
                // The mart carries description + period; there is no metric_name.
                { key: "description", header: "What changed", primary: true },
                { key: "period", header: "Month", cell: (row) => formatMonth(row.period, { short: true }) },
                {
                  key: "current_value",
                  header: "Now",
                  align: "end",
                  cell: (row) => (
                    <span className="numMono">
                      {row.direction === "up" ? "▲" : "▼"} {money(row.current_value, row.currency)}
                    </span>
                  ),
                },
                {
                  key: "previous_value",
                  header: "Before",
                  align: "end",
                  cell: (row) => <span className="numMono muted">{money(row.previous_value, row.currency)}</span>,
                },
              ]}
            />
          </article>

          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Pipeline State</div>
                <h2>Recent runs</h2>
              </div>
            </div>
            <ResponsiveTable
              label="Recent runs"
              rows={runs}
              rowKey="run_id"
              dense
              empty={<div className="empty">No ingestion runs recorded yet.</div>}
              columns={[
                {
                  key: "source_name",
                  header: "Source",
                  primary: true,
                  cell: (run) => (
                    <Link className="inlineLink" href={`/runs/${run.run_id}`}>
                      {run.source_name}
                    </Link>
                  ),
                },
                {
                  key: "status",
                  header: "Status",
                  cell: (run) => (
                    <>
                      <span className={`statusPill status-${run.status}`}>{run.status}</span>
                      {(run.issues || []).slice(0, 2).map((issue) => (
                        <div className="issue" key={`${run.run_id}-${issue.code}-${issue.message}`}>
                          {issue.code}: {issue.message}
                        </div>
                      ))}
                    </>
                  ),
                },
                { key: "file_name", header: "File" },
                { key: "row_count", header: "Rows", align: "end" },
              ]}
            />
          </article>
        </div>
      </section>
    </AppShell>
  );
}
