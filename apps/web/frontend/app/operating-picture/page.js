import { AppShell } from "@/components/app-shell";
import { OperatingPictureView } from "@/components/operating-picture-view";
import {
  getAffordabilityRatios,
  getAttentionItems,
  getCurrentUser,
  getMonthlyCashflow,
  getRecentChanges,
  getRecurringCostBaseline,
  getSourceFreshness,
  getSpendByCategoryMonthly,
  getSubscriptionSummary,
  getUpcomingFixedCosts,
  getUtilityCostTrend,
} from "@/lib/backend";

const FRESHNESS_COLOR = { green: "var(--ok)", yellow: "var(--accent-warm)", red: "var(--warn)" };
const FRESHNESS_FILL = { green: "92%", yellow: "54%", red: "12%" };
const FRESHNESS_RANK = { green: 0, yellow: 1, red: 2 };

function staleness(landedAt) {
  if (!landedAt) return { label: "Never", band: "red" };
  const diffDays = (Date.now() - new Date(landedAt)) / (1000 * 60 * 60 * 24);
  if (diffDays < 2) return { label: "Fresh", band: "green" };
  if (diffDays < 7) return { label: `${Math.floor(diffDays)}d ago`, band: "yellow" };
  return { label: `${Math.floor(diffDays)}d — stale`, band: "red" };
}

// Reused across the freshness pulse: pick the worst-staleness dataset for a
// domain and surface both the band (for the dot/track) and a mono caption
// ("account_transactions · 16h ago") for the card.
function domainFreshnessBand(freshDatasets, datasetNames) {
  let worst = null;
  for (const ds of datasetNames) {
    const match = freshDatasets.find((r) => r.dataset_name === ds);
    const s = staleness(match?.landed_at);
    if (!worst || FRESHNESS_RANK[s.band] > FRESHNESS_RANK[worst.band]) {
      worst = { ds, ...s };
    }
  }
  return {
    band: worst.band,
    color: FRESHNESS_COLOR[worst.band],
    fill: FRESHNESS_FILL[worst.band],
    label: worst.label,
    detail: `${worst.ds} · ${worst.label}`,
  };
}

function formatMonthLabel(bookingMonth) {
  if (!bookingMonth) return null;
  const [year, month] = bookingMonth.split("-").map(Number);
  if (!year || !month) return bookingMonth;
  return new Date(year, month - 1, 1).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });
}

function buildHeroSummary({ latestCashflow, recurringTotal, utilityDelta, prevUtilityMonth }) {
  if (!latestCashflow) {
    return "No cashflow data yet. Upload account transactions to populate the operating picture.";
  }
  const net = Number(latestCashflow.net);
  const parts = [
    `${latestCashflow.booking_month}: income ${latestCashflow.income} against expense ${latestCashflow.expense}, net ${
      net >= 0 ? "positive" : "negative"
    }.`,
  ];
  if (recurringTotal > 0) {
    parts.push(`Recurring subscriptions add ${recurringTotal.toFixed(2)} per month.`);
  }
  if (utilityDelta !== null) {
    parts.push(
      `Utilities are ${utilityDelta >= 0 ? "up" : "down"} ${Math.abs(utilityDelta).toFixed(1)}% vs ${prevUtilityMonth}.`
    );
  }
  return parts.join(" ");
}

// Heuristic tone for the horizon strip. UpcomingFixedCostsRow has no
// cost_type field, so infer a reasonable kind from the contract/provider
// name rather than inventing a fake field.
function horizonTone(row) {
  const text = `${row.contract_name || ""} ${row.provider || ""}`.toLowerCase();
  if (/mortgage|loan/.test(text)) return "accent";
  if (/energy|electric|gas|water|utilit/.test(text)) return "cool";
  if (/contract|renewal|review/.test(text)) return "warm";
  return "neutral";
}

function buildHorizonDays(upcomingFixedCosts) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const days = [];
  for (let i = 0; i < 7; i += 1) {
    const date = new Date(today.getTime() + i * 24 * 60 * 60 * 1000);
    const iso = date.toISOString().slice(0, 10);
    const matches = upcomingFixedCosts.filter(
      (row) => row.expected_date && row.expected_date.slice(0, 10) === iso
    );
    const first = matches[0];
    days.push({
      dateLabel: date.toLocaleDateString("en-US", { weekday: "short", day: "2-digit" }),
      empty: matches.length === 0,
      tone: first ? horizonTone(first) : "neutral",
      title: first ? first.contract_name || first.provider || "—" : "—",
      amountLabel:
        first && first.expected_amount != null
          ? `${first.currency || ""} ${first.expected_amount}`.trim()
          : "",
      moreCount: Math.max(matches.length - 1, 0),
    });
  }
  return days;
}

function buildTopCategories(categoryRows, limit = 5) {
  const months = [...new Set(categoryRows.map((r) => r.booking_month))].sort();
  const latestMonth = months.at(-1);
  const prevMonth = months.at(-2);
  if (!latestMonth) return [];

  const totals = new Map();
  const prevTotals = new Map();
  for (const row of categoryRows) {
    const category = row.category || "Uncategorized";
    const amount = Number(row.total_expense || 0);
    if (row.booking_month === latestMonth) {
      totals.set(category, (totals.get(category) || 0) + amount);
    } else if (row.booking_month === prevMonth) {
      prevTotals.set(category, (prevTotals.get(category) || 0) + amount);
    }
  }

  return [...totals.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([category, amount]) => {
      const prevAmount = prevTotals.get(category) || 0;
      const delta = prevAmount > 0 ? ((amount - prevAmount) / prevAmount) * 100 : 0;
      return { category, amount, delta };
    });
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
    categorySpend,
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
    getSpendByCategoryMonthly(),
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
  const utilityDelta =
    utilityPrevTotal > 0 ? ((utilityLatestTotal - utilityPrevTotal) / utilityPrevTotal) * 100 : null;

  // Hero: net + 12-month sparkline
  const netSeriesValues = cashflowRows.slice(-12).map((r) => Number(r.net));
  const netSeriesLabels = cashflowRows.slice(-12).map((r) => r.booking_month);
  const heroSummary = buildHeroSummary({ latestCashflow, recurringTotal, utilityDelta, prevUtilityMonth });
  const monthLabel = formatMonthLabel(latestCashflow?.booking_month);

  // Freshness pulse — one place, five domains, no duplicate table.
  const freshnessDomains = [
    { name: "Finance", ...domainFreshnessBand(freshnessDatasets, ["account_transactions"]) },
    { name: "Recurring", ...domainFreshnessBand(freshnessDatasets, ["subscriptions"]) },
    { name: "Utilities", ...domainFreshnessBand(freshnessDatasets, ["contract_prices"]) },
    { name: "Loans", ...domainFreshnessBand(freshnessDatasets, ["loan_repayments"]) },
    { name: "Budgets", ...domainFreshnessBand(freshnessDatasets, ["budgets"]) },
  ];

  // Horizon strip: next 7 days
  const horizonDays = buildHorizonDays(upcomingFixedCosts);

  // Urgency-ranked attention queue
  const rankedAttention = [...attentionItems].sort((a, b) => (a.severity ?? 9) - (b.severity ?? 9));

  // Right rail: ratios + top categories
  const topCategories = buildTopCategories(categorySpend);

  return (
    <AppShell
      currentPath="/operating-picture"
      user={user}
      title="Operating Picture"
      eyebrow="Household Intelligence"
      lede="Structured view of your household's financial and operational state across all active domains."
    >
      <OperatingPictureView
        monthLabel={monthLabel}
        latestCashflow={latestCashflow}
        heroSummary={heroSummary}
        netSeriesValues={netSeriesValues}
        netSeriesLabels={netSeriesLabels}
        freshnessDomains={freshnessDomains}
        horizonDays={horizonDays}
        rankedAttention={rankedAttention}
        affordabilityRatios={affordabilityRatios}
        topCategories={topCategories}
        recentChanges={recentChanges}
      />
      {/* recurringBaseline is intentionally unused today; the fetch is kept
          so this Promise.all stays a stable superset for future panels. */}
    </AppShell>
  );
}
