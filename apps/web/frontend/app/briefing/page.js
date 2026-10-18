import { AppShell } from "@/components/app-shell";
import { BriefingView } from "@/components/briefing-view";
import { Explain } from "@/components/explain-server";
import { getBriefing, getCurrentUser } from "@/lib/backend";

// Morning brief (Kotona B1). Server component with zero client state: the
// backend composes a deterministic brief (no LLM) and BriefingView renders it.
// Every line shows its claim status and confidence, and links to the
// lineage drill for the publication behind it.

// Brief sections that belong to the finance operator loop link to the
// surface where the operator acts on them.
const SECTION_SURFACE = {
  money: { href: "/reports", label: "Open monthly finance" },
  sources: { href: "/sources", label: "Open source freshness", operatorOnly: true },
};

function surfacesFor(user) {
  return Object.fromEntries(
    Object.entries(SECTION_SURFACE).filter(([, surface]) => !(surface.operatorOnly && user?.role === "reader"))
  );
}

export default async function BriefingPage() {
  const user = await getCurrentUser();
  const brief = await getBriefing();

  // Presentation only: the brief already carries each line's confidence, so
  // the explanation reuses it instead of a second read.
  const renderExplain = (item) => (
    <Explain
      publication={item.lineage_publication_key}
      user={user}
      confidence={item.confidence || null}
      label={item.headline}
      placement="start"
    />
  );

  return (
    <AppShell
      currentPath="/briefing"
      user={user}
      title="Morning brief"
      eyebrow="Kotona Operating Picture"
      lede="What needs attention today, stated only as far as the data supports it."
    >
      <BriefingView brief={brief} renderExplain={renderExplain} surfaces={surfacesFor(user)} />
    </AppShell>
  );
}
