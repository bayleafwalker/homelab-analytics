import React from "react";
import { expect, within } from "@storybook/test";

import { SparklineChart } from "../components/sparkline-chart";
import { sparklineLabels, sparklineSeries } from "./support/fixtures.jsx";

const meta = {
  title: "Primitives/SparklineChart",
  component: SparklineChart,
  parameters: {
    layout: "padded",
  },
};

export default meta;

export const MonthlyTrend = {
  args: {
    labels: sparklineLabels,
    series: sparklineSeries,
    width: 560,
    height: 180,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Cashflow")).toBeInTheDocument();
    await expect(canvas.getByText("Baseline")).toBeInTheDocument();
  },
};

const twelveMonths = [
  "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
  "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
];

// The dashboard trend: twelve month labels in a 600-unit chart, rendered in a
// phone-width and a desktop-width card. Labels must never overlap.
export const DashboardTrendWidths = {
  render: () => (
    <div style={{ display: "grid", gap: 24 }}>
      {[300, 1000].map((cardWidth) => (
        <article
          key={cardWidth}
          className="panel section"
          data-testid={`trend-${cardWidth}`}
          style={{ width: cardWidth }}
        >
          <SparklineChart
            labels={twelveMonths}
            series={[
              { label: "Income", color: "var(--ok)", values: twelveMonths.map((_, i) => 4300 + (i % 3) * 20) },
              { label: "Expense", color: "var(--warn)", values: twelveMonths.map((_, i) => 1850 + (i % 4) * 15) },
            ]}
            width={600}
            height={120}
          />
        </article>
      ))}
    </div>
  ),
};
