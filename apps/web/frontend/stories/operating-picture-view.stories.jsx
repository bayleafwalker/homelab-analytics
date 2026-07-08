import React from "react";
import { expect, within } from "@storybook/test";

import { AppShell } from "../components/app-shell";
import { OperatingPictureView } from "../components/operating-picture-view";
import {
  adminUser,
  affordabilityRatioFixtures,
  freshnessDomains,
  horizonDays,
  rankedAttentionItems,
  recentChangeFixtures,
  topCategoryFixtures,
} from "./support/fixtures.jsx";

const netSeriesValues = [1710, 1530, 1840, 1580, 1700, 1360, 1470, 900, 1440, 1610, 1630, 1600];
const netSeriesLabels = ["May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"];

function PageSnapshot(args) {
  return (
    <AppShell
      currentPath="/operating-picture"
      user={adminUser}
      title="Operating Picture"
      eyebrow="Household Intelligence"
      lede="Structured view of your household's financial and operational state across all active domains."
    >
      <OperatingPictureView {...args} />
    </AppShell>
  );
}

const meta = {
  title: "OperatingPicture/PageSnapshot",
  component: OperatingPictureView,
  render: PageSnapshot,
};

export default meta;

export const V2Layout = {
  args: {
    monthLabel: "April 2026",
    latestCashflow: { booking_month: "2026-04", net: "1600.00", income: "5240.00", expense: "3640.00" },
    heroSummary:
      "2026-04: income 5240.00 against expense 3640.00, net positive. Recurring subscriptions add 94.30 per month. Utilities are down 7.2% vs 2026-03.",
    netSeriesValues,
    netSeriesLabels,
    freshnessDomains,
    horizonDays,
    rankedAttention: rankedAttentionItems,
    affordabilityRatios: affordabilityRatioFixtures,
    topCategories: topCategoryFixtures,
    recentChanges: recentChangeFixtures,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Hero
    await expect(canvas.getByText("1600.00")).toBeInTheDocument();
    // Freshness pulse — rendered in exactly one place
    await expect(canvas.getByText("Source freshness pulse")).toBeInTheDocument();
    await expect(canvas.getByText("Budgets", { selector: ".pulseCardName" })).toBeInTheDocument();
    // Horizon strip
    await expect(canvas.getByText("Horizon")).toBeInTheDocument();
    await expect(canvas.getByText("Mortgage payment")).toBeInTheDocument();
    // Attention queue
    await expect(canvas.getByText("Energy contract renewal in 12 days")).toBeInTheDocument();
    await expect(canvas.getByText("01")).toBeInTheDocument();
    // Right rail
    await expect(canvas.getByText("Affordability")).toBeInTheDocument();
    await expect(canvas.getByText("Groceries")).toBeInTheDocument();
  },
};

export const EmptyState = {
  args: {
    monthLabel: null,
    latestCashflow: null,
    heroSummary: "No cashflow data yet. Upload account transactions to populate the operating picture.",
    netSeriesValues: [],
    netSeriesLabels: [],
    freshnessDomains,
    horizonDays,
    rankedAttention: [],
    affordabilityRatios: [],
    topCategories: [],
    recentChanges: [],
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("No data")).toBeInTheDocument();
    await expect(canvas.getByText("No attention items. All clear.")).toBeInTheDocument();
  },
};
