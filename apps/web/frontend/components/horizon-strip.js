import React from "react";

import { NumMono } from "./num-mono";

// <HorizonStrip days={[{ dateLabel, empty, tone, title, amountLabel, moreCount }]} />
//
// Seven day-cells for the next-7-days obligations view, toned by kind
// (cool = utility-ish, accent = mortgage/loan-ish, warm = contract review,
// neutral = everything else; empty days render as a blank cell).
export function HorizonStrip({ days = [] }) {
  return (
    <div className="horizonGrid">
      {days.map((d, i) => (
        <div className="horizonCell" data-tone={d.empty ? "empty" : d.tone} key={i}>
          <div className="horizonDate">{d.dateLabel}</div>
          <div className={d.empty ? "muted horizonLabel" : "horizonLabel"}>{d.title}</div>
          {!d.empty && d.amountLabel && <NumMono className="horizonAmount">{d.amountLabel}</NumMono>}
          {!d.empty && d.moreCount > 0 && <div className="muted horizonMore">+{d.moreCount} more</div>}
        </div>
      ))}
    </div>
  );
}
