import React from "react";

// <Eyebrow color="var(--accent-warm)">Household Intelligence</Eyebrow>
//
// The small-caps line every panel uses above its title. Defaults to the
// existing `.eyebrow` look (var(--accent)); pass `color` to retint it.
export function Eyebrow({ children, color, style, className = "" }) {
  return (
    <div className={`eyebrow ${className}`.trim()} style={{ color: color || "var(--accent)", ...style }}>
      {children}
    </div>
  );
}
