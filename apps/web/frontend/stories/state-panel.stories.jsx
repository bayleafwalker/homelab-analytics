import React from "react";
import { expect, within } from "@storybook/test";

import { SkeletonLines, StatePanel } from "../components/state-panel";

const meta = {
  title: "Primitives/StatePanel",
  component: StatePanel,
  parameters: { layout: "padded" },
};

export default meta;

export const AllTones = {
  render: () => (
    <main style={{ display: "grid", gap: 16, maxWidth: 720 }}>
      <StatePanel tone="empty" title="No money flows to draw yet" action={{ href: "#upload", label: "Upload a statement" }}>
        <p>The map needs at least one month of published account transactions.</p>
      </StatePanel>
      <StatePanel tone="stale" title="This map is built from old transactions">
        <p>The newest transactions are from December 2025, 10 months ago.</p>
      </StatePanel>
      <StatePanel tone="error" title="This page couldn't load" secondaryAction={{ href: "#home", label: "Go to dashboard" }}>
        <p>The API answered /reports/cashflow-map with 500. Check the API logs, then try again.</p>
      </StatePanel>
      <StatePanel tone="loading" title="Loading the latest published figures">
        <SkeletonLines lines={3} />
      </StatePanel>
    </main>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole("alert")).toHaveTextContent("This page couldn't load");
    await expect(canvas.getAllByRole("status")).toHaveLength(3);
  },
};
