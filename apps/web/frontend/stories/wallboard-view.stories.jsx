import React from "react";
import { expect, within } from "@storybook/test";

import { WallboardView } from "../components/wallboard-view";

const NOW = "2026-10-18T07:42:00";

const overview = {
  current_month: "2026-09",
  cashflow_income: "4343.35",
  cashflow_expense: "1868.37",
  cashflow_net: "2474.98",
  currency: "EUR",
};

const attentionItems = [
  { item_id: "a", title: "Review contract: Helen", severity: 2 },
  { item_id: "b", title: "Review contract: Helen", severity: 1 },
  { item_id: "c", title: "Budget over: Groceries", severity: 1 },
];

const upcomingCosts = [
  { contract_name: "Netflix", expected_amount: "15.99", currency: "EUR", expected_date: "2026-10-20" },
  { contract_name: "Spotify", expected_amount: "9.99", currency: "EUR", expected_date: "2026-11-01" },
  { contract_name: "Home Mortgage", expected_amount: "1556.33", currency: "EUR", expected_date: "2026-11-05" },
];

const services = [
  { service_id: "ha", service_name: "Home Assistant", status: "healthy" },
  { service_id: "nas", service_name: "NAS", status: "healthy" },
  { service_id: "backup", service_name: "Backups", status: "degraded" },
];

function Clock() {
  return (
    <>
      <time className="wallTime" dateTime={NOW}>
        07:42
      </time>
      <span className="wallDay">Sunday 18 October</span>
    </>
  );
}

const meta = {
  title: "Wallboard/WallboardView",
  component: WallboardView,
  parameters: { layout: "fullscreen" },
  render: (args) => (
    <main aria-label="Household wallboard">
      <WallboardView {...args} />
    </main>
  ),
};

export default meta;

export const Standard = {
  args: {
    now: NOW,
    overview,
    attentionItems,
    upcomingCosts,
    services,
    bridge: { enabled: true, connected: true },
    latestMonth: "2026-09",
    utilityLatest: { month: "2026-09", total: 81.9 },
    clock: <Clock />,
    status: <span className="wallStatus">Live, updated 07:42</span>,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("2 days")).toBeInTheDocument();
    await expect(canvas.getByText("2/3 up")).toBeInTheDocument();
    await expect(canvas.getByText("Review contract: Helen (2)")).toBeInTheDocument();
  },
};

export const Compact = {
  args: { ...Standard.args, compact: true },
};

export const NothingConnected = {
  args: {
    now: NOW,
    overview: null,
    attentionItems: [],
    upcomingCosts: [],
    services: [],
    bridge: { enabled: false, connected: false },
    latestMonth: null,
    utilityLatest: null,
    clock: <Clock />,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("No services reporting")).toBeInTheDocument();
    await expect(canvas.getByText("All clear")).toBeInTheDocument();
  },
};
