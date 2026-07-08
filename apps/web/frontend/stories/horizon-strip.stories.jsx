import React from "react";
import { expect, within } from "@storybook/test";

import { HorizonStrip } from "../components/horizon-strip";
import { horizonDays } from "./support/fixtures.jsx";

const meta = {
  title: "OperatingPicture/HorizonStrip",
  component: HorizonStrip,
  parameters: {
    layout: "padded",
  },
};

export default meta;

export const SevenDays = {
  args: {
    days: horizonDays,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Mortgage payment")).toBeInTheDocument();
    await expect(canvas.getByText("+1 more")).toBeInTheDocument();
    // Two empty days ("Wed 30", "Sat 03") render a placeholder dash.
    await expect(canvas.getAllByText("—")).toHaveLength(2);
  },
};
