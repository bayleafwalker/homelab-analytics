import React from "react";
import { expect, within } from "@storybook/test";

import { Pill } from "../components/pill";

const meta = {
  title: "Primitives/Pill",
  component: Pill,
  parameters: {
    layout: "padded",
  },
};

export default meta;

function ToneRow() {
  return (
    <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
      <Pill tone="neutral">watch</Pill>
      <Pill tone="ok">fresh</Pill>
      <Pill tone="warn">urgent</Pill>
      <Pill tone="cool">completed</Pill>
      <Pill tone="accent">enqueued</Pill>
      <Pill tone="warm">soon</Pill>
    </div>
  );
}

export const AllTones = {
  render: () => <ToneRow />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("urgent")).toBeInTheDocument();
    await expect(canvas.getByText("fresh")).toBeInTheDocument();
  },
};

export const UnknownToneFallsBackToNeutral = {
  args: {
    tone: "not-a-real-tone",
    children: "watch",
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const pill = canvas.getByText("watch");
    await expect(pill).toHaveAttribute("data-tone", "neutral");
  },
};
