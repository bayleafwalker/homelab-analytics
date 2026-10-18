import React from "react";
import { expect, within } from "@storybook/test";

import { WallboardView } from "../components/wallboard-view";
import { NOW, devicesData, eventsData, powerData, servicesData } from "./wallboard-fixtures";

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
    services: servicesData,
    devices: devicesData,
    events: eventsData,
    power: powerData,
    bridge: { enabled: true, connected: true },
    latestMonth: "2026-09",
    utilityLatest: { month: "2026-09", total: 142.6 },
    clock: <Clock />,
    status: <span className="wallStatus">Live, updated 07:42</span>,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("2 days")).toBeInTheDocument();
    await expect(canvas.getByText("2/4 up")).toBeInTheDocument();
    await expect(canvas.getByText("Review contract: Helen (2)")).toBeInTheDocument();
    await expect(canvas.getByLabelText("Events, last 12h")).toBeInTheDocument();
    await expect(canvas.getByText("R refresh · P pause")).toBeInTheDocument();
    await expect(canvas.getByText("Utilities")).toBeInTheDocument();
    await expect(canvas.getByText("billed for September 2026")).toBeInTheDocument();
  },
};

// Page snapshot, compact: no event feed, no hotkey hint, bigger room readings.
export const Compact = {
  args: { ...Standard.args, compact: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.queryByLabelText("Events, last 12h")).toBeNull();
    await expect(canvas.queryByText("R refresh · P pause")).toBeNull();
    await expect(canvas.getByLabelText("Rooms")).toBeInTheDocument();
    await expect(canvas.queryByText("Utilities")).toBeNull();
  },
};

export const NothingConnected = {
  args: {
    now: NOW,
    overview: null,
    attentionItems: [],
    upcomingCosts: [],
    services: { available: true, services: [] },
    devices: null,
    events: null,
    power: null,
    bridge: { enabled: false, connected: false },
    latestMonth: null,
    clock: <Clock />,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("No services reporting")).toBeInTheDocument();
    await expect(canvas.getAllByText("Not connected").length).toBe(3);
    await expect(canvas.getByText("All clear")).toBeInTheDocument();
    await expect(canvas.getByText("No bills yet")).toBeInTheDocument();
  },
};
