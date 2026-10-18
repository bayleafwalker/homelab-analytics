import React from "react";

import { AsOfScrubber } from "../components/as-of-scrubber";
import { ResponsiveTable } from "../components/responsive-table";

const meta = {
  title: "Primitives/ResponsiveTable",
  component: ResponsiveTable,
  parameters: { layout: "padded" },
};

export default meta;

const SOURCES = [
  { id: "personal", name: "OP personal account", dataset: "Account transactions", status: "landed", landed: "18/10/2026", run: "74550a26" },
  { id: "common", name: "OP common account", dataset: "Account transactions", status: "landed", landed: "18/10/2026", run: "7e3614e4" },
  { id: "revolut", name: "Revolut", dataset: "Account transactions", status: "rejected", landed: "02/10/2026", run: "92998ef8" },
];

const COLUMNS = [
  {
    key: "name",
    header: "Source",
    primary: true,
    cell: (row) => (
      <>
        <span style={{ display: "block" }}>{row.name}</span>
        <span className="muted" style={{ fontSize: "0.82rem", fontFamily: "var(--font-sans)", fontWeight: 400 }}>
          {row.dataset}
        </span>
      </>
    ),
  },
  { key: "landed", header: "Last ingested" },
  {
    key: "status",
    header: "Run status",
    cell: (row) => <span className={`statusPill status-${row.status === "landed" ? "landed" : "rejected"}`}>{row.status}</span>,
  },
  { key: "run", header: "Run", align: "end", cell: (row) => <code>{row.run}</code> },
  {
    key: "actions",
    header: "Actions",
    hideLabel: true,
    cell: (row) => <a className="inlineLink" href={`#upload-${row.id}`}>Upload corrected file</a>,
  },
];

export const Sources = {
  render: () => (
    <main className="panel section">
      <ResponsiveTable label="Source status" rows={SOURCES} rowKey="id" columns={COLUMNS} />
    </main>
  ),
};

export const Empty = {
  render: () => (
    <main className="panel section">
      <ResponsiveTable
        label="Source status"
        rows={[]}
        columns={COLUMNS}
        empty={<p className="empty">No source freshness data available.</p>}
      />
    </main>
  ),
};

const MONTHS = ["2024-11", "2024-12", "2025-01", "2025-02", "2025-03", "2025-05", "2025-06", "2025-07", "2025-08"];

export const AsOfScrubberWithGap = {
  name: "AsOfScrubber (gap in history)",
  render: () => (
    <main>
      <AsOfScrubber
        months={MONTHS}
        value="2025-03"
        hrefFor={(month) => (month ? `#asof-${month}` : "#latest")}
        label="View the dashboard as of a month"
        note="Money and the trend are shown as published for this month. Items to review keep no history and show today."
      />
    </main>
  ),
};
