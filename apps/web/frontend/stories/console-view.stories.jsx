import React from "react";
import { expect, userEvent, within } from "@storybook/test";

import { ConsoleView } from "../components/console-view";
import { paletteEntriesForUser } from "../lib/nav-model";
import {
  cashflowRows,
  consoleAttention,
  consoleCategories,
  consoleConfidence,
  consoleRatios,
  consoleRuns,
  dateOnlyHeatmap,
  emptyHeatmap,
  fullHeatmap,
} from "./support/console-fixtures.js";
import { adminUser, readerUser } from "./support/fixtures.jsx";

const NOW = "2026-10-18T07:42:00";

const meta = {
  title: "Console/ConsoleView",
  component: ConsoleView,
  parameters: { layout: "fullscreen" },
  render: (args) => (
    <main aria-label="Ops console">
      <ConsoleView {...args} />
    </main>
  ),
};

export default meta;

const fullArgs = {
  now: NOW,
  user: adminUser,
  currency: "EUR",
  cashflowRows,
  heatmap: fullHeatmap,
  attentionItems: consoleAttention,
  runs: consoleRuns,
  categoryRows: consoleCategories,
  ratios: consoleRatios,
  confidence: consoleConfidence,
  confidenceRestricted: false,
  paletteEntries: paletteEntriesForUser(adminUser),
};

export const Admin = {
  args: fullArgs,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText(/^\+€2474\.98$/)).toBeInTheDocument();
    // Attention ranks S1..S3, capped at six with a link to the rest.
    await expect(canvas.getAllByText("S1")).toHaveLength(1);
    await expect(canvas.getByText("+2 more in the operating picture")).toBeInTheDocument();
    // Runs tail is eight rows (plus the header row).
    const runs = canvas.getByRole("region", { name: "Latest ingestion runs" });
    await expect(within(runs).getAllByRole("row")).toHaveLength(9);
    // Keyboard map lives in the command stub header, not a tooltip.
    const keyMap = canvas.getByRole("group", { name: "Keyboard map" });
    await expect(keyMap.closest("[data-panel-id]").dataset.panelId).toBe("command");
    // No thousands separators inside panels.
    await expect(canvas.getByText(/^€1556\.33$/)).toBeInTheDocument();
    // F2 focuses the heatmap panel.
    await userEvent.keyboard("{F2}");
    await expect(canvasElement.querySelector('[data-panel-id="heatmap"]')).toHaveFocus();
  },
};

export const Reader = {
  args: {
    ...fullArgs,
    user: readerUser,
    confidence: [],
    confidenceRestricted: true,
    heatmap: dateOnlyHeatmap,
    paletteEntries: paletteEntriesForUser(readerUser),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("confidence log needs the admin role")).toBeInTheDocument();
  },
};

export const NothingYet = {
  args: {
    now: NOW,
    user: adminUser,
    currency: null,
    cashflowRows: [],
    heatmap: emptyHeatmap,
    attentionItems: [],
    runs: [],
    categoryRows: [],
    ratios: [],
    confidence: [],
    paletteEntries: paletteEntriesForUser(adminUser),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("No cashflow published yet.")).toBeInTheDocument();
    await expect(canvas.getByText("Nothing needs attention.")).toBeInTheDocument();
    await expect(canvas.getByText("No runs yet.")).toBeInTheDocument();
    await expect(canvas.getByText("no confidence checks recorded yet")).toBeInTheDocument();
  },
};
