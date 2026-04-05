import React from "react";

export function SparklineChart({ series = [], labels = [], height = 100, width = 400 }) {
  const yPad = 18;
  const xPad = 8;
  const allValues = series.flatMap((s) => s.values).filter((v) => v != null);
  if (allValues.length === 0) return null;

  const globalMin = Math.min(...allValues, 0);  // always include 0 for zero-line
  const globalMax = Math.max(...allValues, 0);
  const range = globalMax - globalMin || 1;

  const toY = (v) => height - yPad - ((v - globalMin) / range) * (height - 2 * yPad);
  const toX = (i, total) => xPad + (i / Math.max(total - 1, 1)) * (width - 2 * xPad);

  const zeroY = toY(0);

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
                      strokeLinejoin="round" strokeLinecap="round" />
          );
        })}
        {/* x-axis labels */}
        {labels.map((label, i) => (
          <text key={label} x={toX(i, labels.length)} y={height - 4}
                textAnchor="middle" fontSize="9" fill="var(--muted)">
            {label}
          </text>
        ))}
      </svg>
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
