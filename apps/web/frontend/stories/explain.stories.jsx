import React from "react";

import { ExplainBox } from "../components/explain";

const meta = {
  title: "Primitives/Explain",
  component: ExplainBox,
  parameters: { layout: "padded" },
};

export default meta;

const singleNode = {
  publicationKey: "mart_monthly_cashflow",
  publicationName: "Monthly cashflow mart",
  lineage: {
    counts: { relation: 0, run: 0, asset: 0, source: 0 },
    runs: [],
    sources: [],
    relations: [],
    assets: [],
    recorded: false,
  },
  lineageError: null,
  confidence: { verdict: "degraded", freshness: "due_soon", completeness: 80, assessedAt: "2026-10-18T06:00:00Z" },
  canSeeControl: true,
};

const recorded = {
  publicationKey: "mart_spend_by_category_monthly",
  publicationName: "Spend by category",
  lineage: {
    counts: { relation: 2, run: 3, asset: 3, source: 2 },
    runs: ["run-a", "run-b", "run-c"],
    sources: ["demo_op_personal_export", "demo_revolut_export"],
    relations: ["fact_transaction", "dim_category"],
    assets: ["demo_op_personal", "demo_op_common", "demo_revolut"],
    recorded: true,
  },
  lineageError: null,
  confidence: null,
  canSeeControl: false,
};

function Card({ label, figure, children }) {
  return (
    <article className="panel metricCard" style={{ maxWidth: 360 }}>
      <div className="metricLabel metricLabelRow">
        <span>{label}</span>
        {children}
      </div>
      <div className="metricValue numMono">{figure}</div>
    </article>
  );
}

export const NoLineageRecorded = {
  render: () => (
    <main style={{ minHeight: 560 }}>
      <Card label="Income" figure="€4,343.35">
        <ExplainBox
          explanation={singleNode}
          label="Income, December 2025"
          field="income"
          filter={{ booking_month: "2025-12" }}
          placement="start"
        />
      </Card>
    </main>
  ),
};

export const RecordedLineage = {
  render: () => (
    <main style={{ minHeight: 560 }}>
      <Card label="Top categories" figure="€1,868.37">
        <ExplainBox
          explanation={recorded}
          label="Top categories, December 2025"
          field="total_expense"
          filter={{ booking_month: "2025-12" }}
          placement="start"
          note="The five categories with the most spending that month, summed across accounts."
        />
      </Card>
    </main>
  ),
};

export const TruncatedLineage = {
  render: () => (
    <main style={{ minHeight: 560 }}>
      <Card label="Top categories" figure="€1,868.37">
        <ExplainBox
          explanation={{
            ...recorded,
            lineage: {
              ...recorded.lineage,
              counts: { ...recorded.lineage.counts, run: 50 },
              truncated: true,
              totalRuns: 212,
            },
          }}
          label="Top categories, December 2025"
          field="total_expense"
          placement="start"
        />
      </Card>
    </main>
  ),
};

export const LineageUnavailable = {
  render: () => (
    <main style={{ minHeight: 400 }}>
      <Card label="Net" figure="€2,474.98">
        <ExplainBox
          explanation={{ ...singleNode, lineage: null, lineageError: "Backend request failed for /api/lineage: 503", confidence: null }}
          label="Net, December 2025"
          placement="start"
        />
      </Card>
    </main>
  ),
};

export const Wallboard = {
  render: () => (
    <main className="wall" style={{ minHeight: 640 }}>
      <section className="wallTile" data-tone="ok" style={{ maxWidth: 520 }}>
        <h2 className="wallTileLabel">Money, December 2025</h2>
        <p className="wallBig">+€2,475</p>
        <div className="wallExplain">
          <ExplainBox explanation={singleNode} tone="wall" placement="start" label="Money, December 2025" field="cashflow_net" />
        </div>
      </section>
    </main>
  ),
};
