import React from "react";
import { expect, within } from "@storybook/test";

import { Spark } from "../components/spark";

const meta = {
  title: "Primitives/Spark",
  component: Spark,
  parameters: {
    layout: "padded",
  },
};

export default meta;

export const MonthlyNet = {
  args: {
    label: "Net",
    values: [1710, 1530, 1840, 1580, 1700, 1360, 1470, 900, 1440, 1610, 1630, 1600],
    labels: ["May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"],
    color: "var(--accent)",
    width: 280,
    height: 80,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Net")).toBeInTheDocument();
  },
};

export const EmptyValuesRenderNothing = {
  args: {
    values: [],
  },
  play: async ({ canvasElement }) => {
    await expect(canvasElement.querySelector("svg")).not.toBeInTheDocument();
  },
};
