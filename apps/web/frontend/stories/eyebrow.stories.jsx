import React from "react";
import { expect, within } from "@storybook/test";

import { Eyebrow } from "../components/eyebrow";

const meta = {
  title: "Primitives/Eyebrow",
  component: Eyebrow,
  parameters: {
    layout: "padded",
  },
};

export default meta;

export const DefaultAccent = {
  args: {
    children: "Household Intelligence",
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const el = canvas.getByText("Household Intelligence");
    await expect(el).toBeInTheDocument();
    await expect(el).toHaveClass("eyebrow");
  },
};

export const CustomColor = {
  args: {
    children: "Confidence",
    color: "var(--accent-warm)",
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const el = canvas.getByText("Confidence");
    // Check the specified inline style rather than the resolved computed
    // color, since jsdom/browser computed-style resolution of a custom
    // property is environment-dependent.
    await expect(el.getAttribute("style") || "").toContain("var(--accent-warm)");
  },
};
