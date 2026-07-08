import React from "react";
import { expect, within } from "@storybook/test";

import { NumMono } from "../components/num-mono";

const meta = {
  title: "Primitives/NumMono",
  component: NumMono,
  parameters: {
    layout: "padded",
  },
};

export default meta;

export const MoneyValue = {
  args: {
    children: "€1,600.00",
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const el = canvas.getByText("€1,600.00");
    await expect(el).toBeInTheDocument();
    await expect(el).toHaveClass("numMono");
  },
};

export const StackedColumn = {
  render: () => (
    <div style={{ display: "grid", gap: 4, width: 120 }}>
      <NumMono>1,284.00</NumMono>
      <NumMono>612.40</NumMono>
      <NumMono>94.30</NumMono>
    </div>
  ),
};
