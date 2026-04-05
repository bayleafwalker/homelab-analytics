import React from "react";
import { expect, within } from "@storybook/test";

import { SparklineChart } from "../components/sparkline-chart";
import { sparklineLabels, sparklineSeries } from "./support/fixtures.jsx";

const meta = {
  title: "Primitives/SparklineChart",
  component: SparklineChart,
  parameters: {
    layout: "padded",
  },
};

export default meta;

export const MonthlyTrend = {
  args: {
    labels: sparklineLabels,
    series: sparklineSeries,
    width: 560,
    height: 180,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Cashflow")).toBeInTheDocument();
    await expect(canvas.getByText("Baseline")).toBeInTheDocument();
  },
};
