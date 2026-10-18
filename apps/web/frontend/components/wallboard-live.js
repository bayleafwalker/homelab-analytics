"use client";

import React, { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const REFRESH_MS = 60_000;

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

// Re-renders the server page every minute. Pauses while the tab is hidden
// or the pointer is over the board (someone is reading it), and says so.
export function WallRefresh({ renderedAt }) {
  const router = useRouter();
  const [paused, setPaused] = useState(false);
  const hoverRef = useRef(false);

  useEffect(() => {
    function onEnter() {
      hoverRef.current = true;
      setPaused(true);
    }
    function onLeave() {
      hoverRef.current = false;
      setPaused(document.hidden);
    }
    function onVisibility() {
      setPaused(document.hidden || hoverRef.current);
    }
    const root = document.querySelector(".wall");
    root?.addEventListener("pointerenter", onEnter);
    root?.addEventListener("pointerleave", onLeave);
    document.addEventListener("visibilitychange", onVisibility);
    const id = window.setInterval(() => {
      if (!document.hidden && !hoverRef.current) router.refresh();
    }, REFRESH_MS);
    return () => {
      root?.removeEventListener("pointerenter", onEnter);
      root?.removeEventListener("pointerleave", onLeave);
      document.removeEventListener("visibilitychange", onVisibility);
      window.clearInterval(id);
    };
  }, [router]);

  return (
    <span className="wallStatus" role="status" data-paused={paused}>
      {paused ? "Paused" : "Live"}, updated {formatClock(new Date(renderedAt))}
    </span>
  );
}
