"use client";

import React, { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

export const REFRESH_MS = 30_000;

function formatClock(date) {
  return date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

function formatDay(date) {
  return date.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });
}

// Wall clock. Updates every 15s; minute precision is all a wall needs.
export function WallClock({ initial }) {
  const [now, setNow] = useState(() => new Date(initial));
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 15_000);
    setNow(new Date());
    return () => window.clearInterval(id);
  }, []);
  return (
    <>
      <time className="wallTime" dateTime={now.toISOString()}>
        {formatClock(now)}
      </time>
      <span className="wallDay">{formatDay(now)}</span>
    </>
  );
}

// Why the board is not refreshing right now, or null when it is live.
// Exported for tests; the order is the order the status line reports.
export function pauseReason({ hidden, hovering, manual }) {
  if (manual) return "Paused";
  if (hovering) return "Frozen";
  if (hidden) return "Paused, hidden";
  return null;
}

function isHidden() {
  return document.visibilityState === "hidden";
}

// Refresh loop without the Next router, so Storybook can drive it.
// Gates on page visibility, not on window focus: a wall-mounted TV or
// tablet browser usually never receives focus, and hasFocus gating starves
// kiosk displays. Pauses while the page is hidden (visibilitychange) and
// refreshes at once when it becomes visible again; freezes while the
// pointer is over the board. R refreshes now, P toggles a manual pause.
export function WallRefreshControl({ renderedAt, refresh, intervalMs = REFRESH_MS }) {
  const [state, setState] = useState({ hidden: false, hovering: false, manual: false });
  const stateRef = useRef(state);
  const refreshRef = useRef(refresh);
  refreshRef.current = refresh;

  useEffect(() => {
    function update(patch) {
      stateRef.current = { ...stateRef.current, ...patch };
      setState(stateRef.current);
    }
    const onEnter = () => update({ hovering: true });
    const onLeave = () => update({ hovering: false });
    function onVisibility() {
      const hidden = isHidden();
      const wasHidden = stateRef.current.hidden;
      update({ hidden });
      if (wasHidden && !hidden && !pauseReason(stateRef.current)) refreshRef.current();
    }
    function onKey(event) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const target = event.target;
      if (target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))) return;
      const key = String(event.key).toLowerCase();
      if (key === "r") refreshRef.current();
      if (key === "p") update({ manual: !stateRef.current.manual });
    }
    const root = document.querySelector(".wall");
    root?.addEventListener("pointerenter", onEnter);
    root?.addEventListener("pointerleave", onLeave);
    document.addEventListener("visibilitychange", onVisibility);
    document.addEventListener("keydown", onKey);
    update({ hidden: isHidden() });
    const id = window.setInterval(() => {
      if (!pauseReason({ ...stateRef.current, hidden: isHidden() })) refreshRef.current();
    }, intervalMs);
    return () => {
      root?.removeEventListener("pointerenter", onEnter);
      root?.removeEventListener("pointerleave", onLeave);
      document.removeEventListener("visibilitychange", onVisibility);
      document.removeEventListener("keydown", onKey);
      window.clearInterval(id);
    };
  }, [intervalMs]);

  const reason = pauseReason(state);
  return (
    <span className="wallStatus" role="status" data-paused={Boolean(reason)}>
      {reason || "Live"}, updated {formatClock(new Date(renderedAt))}
    </span>
  );
}

// Re-renders the server page every 30s through the App Router.
export function WallRefresh({ renderedAt }) {
  const router = useRouter();
  return <WallRefreshControl renderedAt={renderedAt} refresh={() => router.refresh()} />;
}
