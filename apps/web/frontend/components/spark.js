import React from "react";

import { SparklineChart } from "./sparkline-chart";

// <Spark values={[...]} />
//
// Lightweight single-series adapter around the existing SparklineChart.
// No new chart logic — this just saves callers from hand-building the
// `series` array for the common case of "one line, sensible defaults".
export function Spark({
  values = [],
  labels = [],
  label = "value",
  color = "var(--accent)",
  height = 60,
  width = 240,
}) {
  if (!values || values.length === 0) return null;

  const series = [{ label, color, values }];
  return <SparklineChart series={series} labels={labels} height={height} width={width} />;
}
