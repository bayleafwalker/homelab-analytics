import React from "react";

import { StatePanel } from "@/components/state-panel";
import { formatDay, formatMonth } from "@/lib/format";

// Presentation for panels read from the reporting layer's dated snapshots
// (GET /reports/...?as_of=YYYY-MM). A read is { rows, status, snapshot }:
//   current     today's publication, no marking
//   snapshot    rows as published when that month was the newest one
//   no_history  no snapshot for that month; rows are empty, never today's

export function currentRead(rows) {
  return { rows: rows || [], status: "current", snapshot: null };
}

// Small pill next to a panel heading saying which snapshot it shows.
export function HistoryTag({ read }) {
  if (!read || read.status === "current") return null;
  if (read.status === "snapshot") {
    const day = read.snapshot?.captured_at ? formatDay(read.snapshot.captured_at) : null;
    return (
      <span className="pill" data-tone="neutral" title={day ? `Snapshot taken ${day}` : undefined}>
        {day ? `As published ${day}` : "As published"}
      </span>
    );
  }
  return (
    <span className="pill" data-tone="warn">
      No history
    </span>
  );
}

// Body shown instead of rows when a month has no snapshot.
export function NoHistory({ month, what }) {
  return (
    <StatePanel tone="empty" compact title={`No history for ${formatMonth(month)}`}>
      <p>
        The reporting layer has no snapshot of {what} from when {formatMonth(month)} was the newest
        month, so it is not shown rather than showing today&apos;s figures.
      </p>
    </StatePanel>
  );
}

export function historyNote(read) {
  if (read?.status !== "snapshot" || !read.snapshot) return null;
  return `As published on ${formatDay(read.snapshot.captured_at)}, when ${formatMonth(
    read.snapshot.reference_month
  )} was the newest month.`;
}
