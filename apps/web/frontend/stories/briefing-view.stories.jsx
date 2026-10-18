import React from "react";
import { expect, within } from "@storybook/test";

import { AppShell } from "../components/app-shell";
import { BriefingView } from "../components/briefing-view";
import fixtures from "./support/briefing-fixtures.json";
import { adminUser } from "./support/fixtures.jsx";

// `withheld` is the real /api/briefing payload for a fresh install (nothing
// has a confidence snapshot yet). `mixed` derives from it: cashflow confirmed,
// attention items provisional with a warning, the rest as captured.

const withheld = fixtures.withheld;

function confirmItem(item, overrides) {
  return {
    ...item,
    claim_status: "confirmed",
    caveats: [],
    remediation: null,
    confidence: {
      ...item.confidence,
      verdict: "trustworthy",
      freshness_state: "current",
      completeness_pct: 100,
      validation_state: "passed",
      assessed_at: "2026-10-18T05:55:00+00:00",
    },
    evidence: [...item.evidence, { kind: "run", ref: "run-2026-10-17", label: "Run run-2026-10-17" }],
    ...overrides,
  };
}

const mixed = {
  ...withheld,
  headline: "One item needs attention; cashflow is on track.",
  overall_severity: "warning",
  counts: { ...withheld.counts, confirmed: 2, provisional: 1, withheld: 4, warning: 1, notice: 6 },
  sections: withheld.sections.map((section) => {
    if (section.key === "money") {
      return {
        ...section,
        status: "ok",
        summary: "September closed 2,474.98 EUR ahead.",
        items: section.items.map((item) =>
          confirmItem(item, { severity: "info", headline: "Kept 2,474.98 EUR in September.", detail: "4,343.35 in, 1,868.37 out." })
        ),
      };
    }
    if (section.key === "attention") {
      return {
        ...section,
        status: "attention",
        summary: "One open item, from a degraded publication.",
        items: section.items.map((item) => ({
          ...confirmItem(item, {
            severity: "warning",
            headline: "Review contract: Helen.",
            detail: "Price rose 12% at renewal.",
          }),
          claim_status: "provisional",
          caveats: ["The attention mart was refreshed 30 hours ago."],
          confidence: { ...item.confidence, verdict: "degraded", freshness_state: "stale", completeness_pct: 92, validation_state: "passed", assessed_at: "2026-10-17T00:10:00+00:00" },
        })),
      };
    }
    return section;
  }),
};

function Page({ brief }) {
  return (
    <AppShell
      currentPath="/briefing"
      user={adminUser}
      title="Morning brief"
      eyebrow="Kotona Operating Picture"
      lede="What needs attention today, stated only as far as the data supports it."
    >
      <BriefingView
        brief={brief}
        surfaces={{
          money: { href: "/reports", label: "Open monthly finance" },
          sources: { href: "/sources", label: "Open source freshness" },
        }}
      />
    </AppShell>
  );
}

const meta = {
  title: "Pages/Briefing",
  component: BriefingView,
  parameters: { layout: "fullscreen" },
  render: (args) => <Page {...args} />,
};

export default meta;

export const Mixed = {
  args: { brief: mixed },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Kept 2,474.98 EUR in September.")).toBeInTheDocument();
    await expect(canvas.getByTestId("brief-item-attention:items")).toHaveAttribute("data-claim", "provisional");
    await expect(canvas.getByTestId("brief-surface-money")).toHaveAttribute("href", "/reports");
    await expect(canvas.getByTestId("brief-lineage-money:cashflow")).toHaveAttribute(
      "href",
      "/briefing/lineage?publication_key=mart_monthly_cashflow"
    );
  },
};

export const NothingTrustedYet = {
  args: { brief: withheld },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText(withheld.headline)).toBeInTheDocument();
    await expect(canvas.getAllByText("Next step:").length).toBeGreaterThan(0);
  },
};
