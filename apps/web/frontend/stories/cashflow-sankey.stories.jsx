import React from "react";
import { expect, within } from "@storybook/test";

import { CashflowFlowList, CashflowSankey } from "../components/cashflow-sankey";
import fixtures from "./support/cashflow-map-fixtures.json";

// Fixtures are produced by the real API builder
// (packages/domains/finance/pipelines/cashflow_map.py): the seeded demo month,
// a categorised household with occasional spending, and an overspent month.

function SankeyStory({ payload, focusId }) {
  return (
    <section className="panel cashflowCanvas" aria-labelledby="cashflow-map-title">
      <h2 id="cashflow-map-title" className="srOnly">
        Cashflow map
      </h2>
      <CashflowSankey payload={payload} focusId={focusId} hrefForNode={(node) => `#${node.id}`} />
    </section>
  );
}

const meta = {
  title: "Cashflow/CashflowSankey",
  component: CashflowSankey,
  render: SankeyStory,
  parameters: { layout: "padded" },
};

export default meta;

export const DemoMonth = {
  args: { payload: fixtures.demo, focusId: null },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Money in")).toBeInTheDocument();
    await expect(canvas.getByText("Kept")).toBeInTheDocument();
    await expect(canvas.getByRole("link", { name: /Supermarket Plus/ })).toBeInTheDocument();
  },
};

export const CategorisedWithOccasional = {
  args: { payload: fixtures.categorised, focusId: null },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Regular spending")).toBeInTheDocument();
    await expect(canvas.getByText("Occasional spending")).toBeInTheDocument();
  },
};

export const FocusedPayee = {
  args: { payload: fixtures.categorised, focusId: "out:groceries" },
};

export const Overspent = {
  args: { payload: fixtures.overspend, focusId: null },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Drawn from savings")).toBeInTheDocument();
  },
};

export const NarrowFlowList = {
  render: () => (
    <div style={{ maxWidth: 360 }}>
      <CashflowFlowList payload={fixtures.categorised} hrefForNode={(node) => `#${node.id}`} />
    </div>
  ),
};
