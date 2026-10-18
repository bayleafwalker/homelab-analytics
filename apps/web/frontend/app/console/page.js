import { ConsoleView } from "@/components/console-view";
import { loadExplanation } from "@/lib/explain";
import { optional } from "@/lib/optional";
import { paletteEntriesForUser } from "@/lib/nav-model";
import {
  getAffordabilityRatios,
  getAttentionItems,
  getCurrentUser,
  getHouseholdOverview,
  getMonthlyCashflow,
  getPublicationConfidence,
  getRuns,
  getSpendByCategoryMonthly,
  getSpendHeatmap,
} from "@/lib/backend";

export const metadata = {
  title: "Ops console | Kotona",
};

// Single-screen power-user view (sprint console-grid-rise). Full-bleed like
// /wallboard, so it carries its own <CommandPalette> in the command stub
// rather than sitting inside AppShell next to a second one. Every panel reads
// a reporting endpoint and degrades to its own empty state.
export default async function ConsolePage() {
  const user = await getCurrentUser();
  const isAdmin = user?.role === "admin";
  const [overview, cashflowRows, heatmap, attentionItems, runs, categoryRows, ratios, confidence] =
    await Promise.all([
      optional(getHouseholdOverview(), null),
      optional(getMonthlyCashflow(), []),
      optional(getSpendHeatmap({ window: 28 }), null),
      optional(getAttentionItems(), []),
      optional(getRuns(8), []),
      optional(getSpendByCategoryMonthly(), []),
      optional(getAffordabilityRatios(), []),
      isAdmin ? optional(getPublicationConfidence(), null) : Promise.resolve(null),
    ]);
  const currency = overview?.currency || heatmap?.currency || null;
  const cashflowExplanation =
    cashflowRows.length > 0 ? await optional(loadExplanation("mart_monthly_cashflow", { user }), null) : null;

  return (
    <main id="main-content" aria-label="Ops console">
      <ConsoleView
        now={new Date().toISOString()}
        user={user}
        currency={currency}
        cashflowRows={cashflowRows}
        heatmap={heatmap}
        attentionItems={attentionItems}
        runs={runs}
        categoryRows={categoryRows}
        ratios={ratios}
        confidence={confidence?.publications || []}
        confidenceRestricted={!isAdmin}
        paletteEntries={paletteEntriesForUser(user)}
        currentPath="/console"
        explanations={{ cashflow: cashflowExplanation }}
      />
    </main>
  );
}
