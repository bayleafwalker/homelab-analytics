import React from "react";

import { formatMoney, formatMonth } from "../lib/format";

// Six-month bar strip for a Cashflow Map drill-down. The selected month is
// drawn solid; earlier months are drawn as outlines so the eye lands on now.
export function TrendBars({ points = [], currency, selectedMonth, color = "var(--accent-cool)" }) {
  if (!points.length) return null;
  const values = points.map((point) => Number(point.amount) || 0);
  const max = Math.max(...values, 1);
  const W = 320;
  const H = 120;
  const barW = Math.min(36, (W - 8 * (points.length - 1)) / points.length);
  const step = (W - barW) / Math.max(1, points.length - 1);
  return (
    <figure className="trendBars">
      <svg viewBox={`0 0 ${W} ${H + 24}`} role="img" aria-label="Spending by month">
        {points.map((point, index) => {
          const h = Math.max(2, (values[index] / max) * H);
          const x = index * step;
          const selected = point.month === selectedMonth;
          return (
            <g key={point.month}>
              <rect
                x={x}
                y={H - h}
                width={barW}
                height={h}
                rx={4}
                fill={selected ? color : "transparent"}
                stroke={color}
                strokeWidth={selected ? 0 : 1.5}
              >
                <title>{`${formatMonth(point.month)}: ${formatMoney(point.amount, currency)}`}</title>
              </rect>
              <text x={x + barW / 2} y={H + 17} textAnchor="middle" className="trendBarsLabel">
                {formatMonth(point.month, { short: true }).slice(0, 3)}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption className="srOnly">
        {points.map((point) => `${formatMonth(point.month)} ${formatMoney(point.amount, currency)}`).join(", ")}
      </figcaption>
    </figure>
  );
}
