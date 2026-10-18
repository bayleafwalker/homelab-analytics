import React from "react";
import { expect, within } from "@storybook/test";

import { CashflowFlowList, CashflowLedger, CashflowSankey } from "../components/cashflow-sankey";
import fixtures from "./support/cashflow-map-fixtures.json";

// Fixtures are produced by the real API builder
// (packages/domains/finance/pipelines/cashflow_map.py): the seeded demo month,
// a categorised household with occasional spending, an overspent month, a
// sparse first month (one payer, one payee) and an empty install.

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
    await expect(canvas.getAllByText("Money in").length).toBeGreaterThan(0);
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

// Sparse: a first month with one income and one payee. Short history, so all
// spending is one bucket and the map says so in its disclosures.
export const Sparse = {
  args: { payload: fixtures.sparse, focusId: null },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole("link", { name: /Landlord Oy/ })).toBeInTheDocument();
    await expect(canvas.getByText("Kept")).toBeInTheDocument();
    await expect(canvasElement.querySelectorAll("path.sankeyLink").length).toBeGreaterThan(1);
  },
};

// Empty: nothing published yet. The Sankey draws nothing (the page shows its
// own empty state) and the flow list stays empty rather than inventing rows.
export const Empty = {
  render: () => (
    <section className="panel cashflowCanvas" aria-labelledby="cashflow-map-title">
      <h2 id="cashflow-map-title">Cashflow map</h2>
      <CashflowSankey payload={fixtures.empty} hrefForNode={(node) => `#${node.id}`} />
      <p>{fixtures.empty.disclosures[0].message}</p>
    </section>
  ),
  play: async ({ canvasElement }) => {
    await expect(canvasElement.querySelector("svg.sankey")).toBeNull();
    await expect(within(canvasElement).getByText("No account transactions have been published yet.")).toBeInTheDocument();
  },
};

function LedgerStory({ payload }) {
  return (
    <section className="cashflowLede" aria-label="Cashflow buckets">
      <CashflowLedger payload={payload} />
    </section>
  );
}

// The bucket ledger that replaced the KPI cards on /cashflow.
export const BucketLedger = {
  render: () => <LedgerStory payload={fixtures.demo} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Kept")).toBeInTheDocument();
    await expect(canvas.getByText("Transfers, left out")).toBeInTheDocument();
  },
};

export const BucketLedgerOverspent = {
  render: () => <LedgerStory payload={fixtures.overspend} />,
};

export const BucketLedgerSparse = {
  render: () => <LedgerStory payload={fixtures.sparse} />,
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).queryByText(/Transfers/)).toBeNull();
  },
};

export const BucketLedgerEmpty = {
  render: () => <LedgerStory payload={fixtures.empty} />,
  play: async ({ canvasElement }) => {
    await expect(canvasElement.querySelectorAll(".cashflowLedger > div").length).toBe(0);
  },
};
