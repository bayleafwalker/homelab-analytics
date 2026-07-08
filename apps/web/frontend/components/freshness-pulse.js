import React from "react";

// <FreshnessPulse domains={[{ name, band, color, fill, detail }]} />
//
// Replaces the old source-confidence table with one card per domain: a
// name, a status dot, a thin progress track, and a mono caption with the
// dataset driving that domain's staleness. Freshness renders in exactly
// one place on the Operating Picture — this component — not also a table.
export function FreshnessPulse({ domains = [] }) {
  return (
    <div className="pulseGrid">
      {domains.map((d) => (
        <div className="pulseCard" key={d.name}>
          <div className="pulseCardHead">
            <span className="pulseCardName">{d.name}</span>
            <span className="pulseDot" style={{ background: d.color, boxShadow: `0 0 8px ${d.color}` }} />
          </div>
          <div className="pulseTrack">
            <div className="pulseTrackFill" style={{ width: d.fill, background: d.color }} />
          </div>
          <div className="pulseCaption">{d.detail}</div>
        </div>
      ))}
    </div>
  );
}
