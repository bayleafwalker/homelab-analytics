import { WallClock, WallRefresh } from "@/components/wallboard-live";
import { WallboardView } from "@/components/wallboard-view";
import { loadExplanation } from "@/lib/explain";
import {
  getAttentionItems,
  getCurrentUser,
  getHaBridgeStatus,
  getHomelabServices,
  getHouseholdOverview,
  getMonthlyCashflow,
  getUpcomingFixedCosts,
  getUtilityCostTrend,
} from "@/lib/backend";

export const metadata = {
  title: "Wallboard | Kotona",
};

// Optional panels must not take the whole board down; a missing adapter
// renders as that tile's empty state.
async function optional(promise, fallback) {
  try {
    return await promise;
  } catch (error) {
    if (error && typeof error === "object" && "digest" in error && String(error.digest).startsWith("NEXT_REDIRECT")) {
      throw error;
    }
    return fallback;
  }
}

export default async function WallboardPage({ searchParams }) {
  const user = await getCurrentUser();
  const compact = searchParams?.compact === "1";
  const [overview, attentionItems, upcomingCosts, cashflowRows, utilityTrend, services, bridge] =
    await Promise.all([
      getHouseholdOverview(),
      getAttentionItems(),
      getUpcomingFixedCosts(),
      getMonthlyCashflow(),
      optional(getUtilityCostTrend(), []),
      optional(getHomelabServices(), []),
      optional(getHaBridgeStatus(), null),
    ]);
  const months = [...new Set(utilityTrend.map((row) => row.billing_month))].sort();
  const utilityMonth = months.at(-1);
  const utilityLatest = utilityMonth
    ? {
        month: utilityMonth,
        total: utilityTrend
          .filter((row) => row.billing_month === utilityMonth)
          .reduce((sum, row) => sum + Number(row.total_cost || 0), 0),
      }
    : null;
  const renderedAt = new Date().toISOString();
  const moneyExplanation = overview ? await loadExplanation("mart_household_overview", { user }) : null;

  return (
    <main id="main-content" aria-label="Household wallboard">
      <h1 className="srOnly">Household wallboard</h1>
      <WallboardView
        now={renderedAt}
        overview={overview}
        attentionItems={attentionItems}
        upcomingCosts={upcomingCosts}
        services={services}
        bridge={bridge}
        latestMonth={cashflowRows.at(-1)?.booking_month || null}
        utilityLatest={utilityLatest}
        compact={compact}
        clock={<WallClock initial={renderedAt} />}
        status={<WallRefresh renderedAt={renderedAt} />}
        explanations={{ money: moneyExplanation }}
      />
    </main>
  );
}
