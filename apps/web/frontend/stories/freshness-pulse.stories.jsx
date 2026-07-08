import React from "react";
import { expect, within } from "@storybook/test";

import { FreshnessPulse } from "../components/freshness-pulse";
import { freshnessDomains } from "./support/fixtures.jsx";

const meta = {
  title: "OperatingPicture/FreshnessPulse",
  component: FreshnessPulse,
  parameters: {
    layout: "padded",
  },
};

export default meta;

export const FiveDomains = {
  args: {
    domains: freshnessDomains,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Finance")).toBeInTheDocument();
    await expect(canvas.getByText("Budgets")).toBeInTheDocument();
    await expect(canvas.getByText("budgets · 14d — stale")).toBeInTheDocument();
  },
};
