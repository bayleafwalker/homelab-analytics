import React from "react";

// Axis labels used to be SVG <text> inside a viewBox that scales with the
// card: 9 viewBox units became ~5px on a phone and ~16px on a wide screen,
// and the thinning assumed a label width that only held at one size, so
// month labels overprinted each other (or each other's edges) depending on
// width and font. They are now HTML under the chart at a real font size,
// placed by percentage, picked evenly (at most five), and cut to first /
// middle / last in narrow containers (see .chartAxis in globals.css).

const MAX_LABELS = 5;

// Which labels to show, where (0..1 across the chart), how to anchor them,
// and their rank: rank 1 survives narrow containers, rank 2 does not.
export function axisLabels(labels, { width = 400, xPad = 8 } = {}) {
  const n = labels.length;
  if (n === 0) return [];
  const k = Math.min(MAX_LABELS, n);
  const picked = [];
  for (let j = 0; j < k; j += 1) {
    const index = k === 1 ? 0 : Math.round((j * (n - 1)) / (k - 1));
    if (picked.length && picked.at(-1).index === index) continue;
    picked.push({ index, j });
  }
  const middle = (k - 1) / 2;
  return picked.map(({ index, j }) => {
    const first = j === 0;
    const last = j === k - 1 && k > 1;
    const fraction = (xPad + (n === 1 ? 0 : index / (n - 1)) * (width - 2 * xPad)) / width;
    return {
      index,
      label: labels[index],
      left: Math.round(fraction * 10000) / 100,
      anchor: first ? "start" : last ? "end" : "middle",
      rank: first || last || j === middle ? 1 : 2,
    };
  });
}

export function SparklineChart({ series = [], labels = [], height = 100, width = 400 }) {
  const yPad = 10;
  const xPad = 8;
  const allValues = series.flatMap((s) => s.values).filter((v) => v != null);
  if (allValues.length === 0) return null;

  const globalMin = Math.min(...allValues, 0);  // always include 0 for zero-line
  const globalMax = Math.max(...allValues, 0);
  const range = globalMax - globalMin || 1;

  const toY = (v) => height - yPad - ((v - globalMin) / range) * (height - 2 * yPad);
  const toX = (i, total) => xPad + (i / Math.max(total - 1, 1)) * (width - 2 * xPad);

  const zeroY = toY(0);
  const ticks = axisLabels(labels, { width, xPad });

  return (
    <div className="chartWrap">
      <svg
        className="sparkline"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        {/* zero line */}
        <line x1={xPad} y1={zeroY} x2={width - xPad} y2={zeroY}
              stroke="var(--line)" strokeWidth="1" strokeDasharray="3 3" />
        {/* series polylines */}
        {series.map((s) => {
          const points = s.values
            .map((v, i) => `${toX(i, s.values.length)},${toY(v)}`)
            .join(" ");
          return (
            <polyline key={s.label} points={points}
                      fill="none" stroke={s.color} strokeWidth="2"
                      strokeLinejoin="round" strokeLinecap="round"
                      vectorEffect="non-scaling-stroke" />
          );
        })}
      </svg>
      {ticks.length ? (
        <div className="chartAxis" aria-hidden="true">
          {ticks.map((tick) => (
            <span
              key={`${tick.index}-${tick.label}`}
              className="chartAxisLabel"
              data-anchor={tick.anchor}
              data-rank={tick.rank}
              style={{ left: `${tick.left}%` }}
            >
              {tick.label}
            </span>
          ))}
        </div>
      ) : null}
      <div className="chartLegend">
        {series.map((s) => (
          <span key={s.label} className="chartLegendItem">
            <span className="chartLegendDot" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}
