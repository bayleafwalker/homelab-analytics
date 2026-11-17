import { WallClock, WallRefresh } from "@/components/wallboard-live";
import { WallboardView, latestUtilityBill } from "@/components/wallboard-view";
import { loadExplanation } from "@/lib/explain";
import { optional } from "@/lib/optional";
import {
  getAttentionItems,
  getCurrentUser,
  getDeviceReadings,
  getEventFeed,
  getHaBridgeStatus,
  getHouseholdOverviewRows,
  getMonthlyCashflow,
  getPowerSeries,
  getServiceHealth,
  getUpcomingFixedCosts,
  getUtilityCostTrend,
} from "@/lib/backend";

export const metadata = {
  title: "Wallboard | Kotona",
};

export default async function WallboardPage({ searchParams }) {
  const user = await getCurrentUser();
  // URL-only: the kiosk's bookmark decides the mode; nothing is remembered.
  const compact = searchParams?.compact === "1";
  const [overviewRows, attentionItems, upcomingCosts, cashflowRows, bridge, services, devices, events, power, utilityTrend] =
    await Promise.all([
      getHouseholdOverviewRows(),
      getAttentionItems(),
      getUpcomingFixedCosts(),
      getMonthlyCashflow(),
      optional(getHaBridgeStatus(), null),
      optional(getServiceHealth(), null),
      optional(getDeviceReadings(), null),
      compact ? null : optional(getEventFeed(), null),
      optional(getPowerSeries(24), null),
      compact ? [] : optional(getUtilityCostTrend(), []),
    ]);
  const renderedAt = new Date().toISOString();
  const moneyExplanation = overviewRows.some((row) => row.currency)
    ? await loadExplanation("mart_household_overview", { user })
    : null;

  return (
    <main id="main-content" aria-label="Household wallboard">
      <h1 className="srOnly">Household wallboard</h1>
      <WallboardView
        now={renderedAt}
        overviewRows={overviewRows}
        attentionItems={attentionItems}
        upcomingCosts={upcomingCosts}
        bridge={bridge}
        latestMonth={cashflowRows.at(-1)?.booking_month || null}
        services={services}
        devices={devices}
        events={events}
        power={power}
        utilityLatest={latestUtilityBill(utilityTrend)}
        compact={compact}
        clock={<WallClock initial={renderedAt} />}
        status={<WallRefresh renderedAt={renderedAt} />}
        explanations={{ money: moneyExplanation }}
      />
    </main>
  );
}
