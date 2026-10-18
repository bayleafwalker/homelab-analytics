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
export function pauseReason({ focused, hovering, manual }) {
  if (manual) return "Paused";
  if (hovering) return "Frozen";
  if (!focused) return "Paused, not focused";
  return null;
}

// Re-renders the server page every 30s. Skips a tick while the page does not
// have focus (document.hasFocus() is false) and freezes while the pointer is
// over the board, so nothing moves under someone reading it. R refreshes now,
// P toggles a manual pause.
export function WallRefresh({ renderedAt }) {
  const router = useRouter();
  const [state, setState] = useState({ focused: true, hovering: false, manual: false });
  const stateRef = useRef(state);

  useEffect(() => {
    function update(patch) {
      stateRef.current = { ...stateRef.current, ...patch };
      setState(stateRef.current);
    }
    const onEnter = () => update({ hovering: true });
    const onLeave = () => update({ hovering: false });
    const onFocusChange = () => update({ focused: document.hasFocus() });
    function onKey(event) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const target = event.target;
      if (target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))) return;
      const key = String(event.key).toLowerCase();
      if (key === "r") router.refresh();
      if (key === "p") update({ manual: !stateRef.current.manual });
    }
    const root = document.querySelector(".wall");
    root?.addEventListener("pointerenter", onEnter);
    root?.addEventListener("pointerleave", onLeave);
    window.addEventListener("focus", onFocusChange);
    window.addEventListener("blur", onFocusChange);
    document.addEventListener("visibilitychange", onFocusChange);
    document.addEventListener("keydown", onKey);
    update({ focused: document.hasFocus() });
    const id = window.setInterval(() => {
      const current = { ...stateRef.current, focused: document.hasFocus() };
      if (!pauseReason(current)) router.refresh();
    }, REFRESH_MS);
    return () => {
      root?.removeEventListener("pointerenter", onEnter);
      root?.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("focus", onFocusChange);
      window.removeEventListener("blur", onFocusChange);
      document.removeEventListener("visibilitychange", onFocusChange);
      document.removeEventListener("keydown", onKey);
      window.clearInterval(id);
    };
  }, [router]);

  const reason = pauseReason(state);
  return (
    <span className="wallStatus" role="status" data-paused={Boolean(reason)}>
      {reason || "Live"}, updated {formatClock(new Date(renderedAt))}
    </span>
  );
}
