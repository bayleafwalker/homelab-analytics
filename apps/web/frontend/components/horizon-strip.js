import React from "react";

import { NumMono } from "./num-mono";

// Kind labels are part of the Operating Picture vocabulary: every merged
// action says what it is, not just when it is due.
const KIND_LABEL = {
  approval: "Approval",
  export: "Manual export",
  fixed_cost: "Fixed cost",
  renewal: "Renewal",
};

const KIND_TONE = {
  approval: "warm",
  export: "neutral",
  fixed_cost: "cool",
  renewal: "warm",
};

function itemAmount(item) {
  if (item.amount == null) return "";
  return `${item.currency || ""} ${item.amount}`.trim();
}

// <HorizonStrip days={[{ dateLabel, items }]} />
//
// Seven day-cells for the next-7-days view. Every item in a day is shown, so
// two actions on the same day never collapse into a "+1 more" count. Empty
// days stay as visible cells. Older fixtures used a single-title day shape;
// that shape keeps rendering for the Storybook fixtures.
export function HorizonStrip({ days = [] }) {
  return (
    <div className="horizonGrid">
      {days.map((d, i) => {
        const items = d.items ?? [];
        const legacy = d.items === undefined;
        const tone = legacy
          ? d.empty
            ? "empty"
            : d.tone
          : items.length === 0
            ? "empty"
            : KIND_TONE[items[0].kind] || "neutral";
        return (
          <div className="horizonCell" data-tone={tone} key={d.date || d.dateLabel || i}>
            <div className="horizonDate">{d.dateLabel}</div>
            {legacy ? (
              <>
                <div className={d.empty ? "muted horizonLabel" : "horizonLabel"}>{d.title}</div>
                {!d.empty && d.amountLabel && <NumMono className="horizonAmount">{d.amountLabel}</NumMono>}
                {!d.empty && d.moreCount > 0 && <div className="muted horizonMore">+{d.moreCount} more</div>}
              </>
            ) : items.length === 0 ? (
              <div className="muted horizonLabel">—</div>
            ) : (
              items.map((item) => (
                <div className="horizonItem" key={item.id || `${item.kind}:${item.label}`}>
                  <span className="horizonKind">{KIND_LABEL[item.kind] || item.kind}</span>
                  <span className="horizonLabel">{item.label}</span>
                  {itemAmount(item) && <NumMono className="horizonAmount">{itemAmount(item)}</NumMono>}
                </div>
              ))
            )}
          </div>
        );
      })}
    </div>
  );
}
