import React from "react";
import { expect, within } from "@storybook/test";

import { HeatGrid } from "../components/heat-grid";
import { dateOnlyHeatmap, emptyHeatmap, fullHeatmap, sparseHeatmap } from "./support/console-fixtures.js";

const meta = {
  title: "Console/HeatGrid",
  component: HeatGrid,
  parameters: { layout: "padded" },
  render: (args) => (
    <main className="console" style={{ height: "auto", maxWidth: 560 }} aria-label="Heat grid">
      <HeatGrid {...args} />
    </main>
  ),
};

export default meta;

export const Full = {
  args: { heatmap: fullHeatmap },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const table = canvas.getByRole("table");
    // 7 day rows plus the hour header row.
    await expect(within(table).getAllByRole("row")).toHaveLength(8);
    await expect(within(table).getAllByRole("rowheader")).toHaveLength(7);
    // 24 hours plus the date-only column (Tue and Fri carry undated spend).
    await expect(within(table).getAllByRole("columnheader")).toHaveLength(25);
    await expect(canvasElement.querySelectorAll('.heatCell[data-level="4"]').length).toBeGreaterThan(0);
  },
};

export const Sparse = {
  args: { heatmap: sparseHeatmap },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(within(canvas.getByRole("table")).getAllByRole("columnheader")).toHaveLength(24);
    const lit = canvasElement.querySelectorAll('.heatCell:not([data-level="0"])');
    await expect(lit).toHaveLength(3);
  },
};

export const DateOnly = {
  args: { heatmap: dateOnlyHeatmap },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText(/Sources record dates only/)).toBeInTheDocument();
    // Nothing is drawn at midnight just because the source had no time.
    await expect(canvasElement.querySelectorAll('.heatCell:not(.heatUntimed):not([data-level="0"])')).toHaveLength(0);
  },
};

export const Empty = {
  args: { heatmap: emptyHeatmap },
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByText("No spending in this window.")).toBeInTheDocument();
  },
};
