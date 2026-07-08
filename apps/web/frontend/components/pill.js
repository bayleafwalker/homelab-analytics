import React from "react";

// Tones map to the existing token palette. Keep this list in sync with the
// `.pill[data-tone]` rules in app/globals.css.
const TONES = new Set(["neutral", "ok", "warn", "cool", "accent", "warm"]);

// <Pill tone="ok">Fresh</Pill>
//
// Shared status-chip primitive. Replaces ad-hoc `.statusPill` + inline
// background/color spans with a single component driven by a `tone` prop.
export function Pill({ tone = "neutral", children, style, className = "" }) {
  const resolvedTone = TONES.has(tone) ? tone : "neutral";
  return (
    <span
      className={`pill ${className}`.trim()}
      data-tone={resolvedTone}
      style={style}
    >
      {children}
    </span>
  );
}
