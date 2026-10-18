import React from "react";
import Link from "next/link";

// One primitive for the four non-happy states a reporting surface has:
//   empty   nothing published yet -> say what to do next
//   stale   data exists but is old -> say how old and how to refresh
//   error   the request failed -> say what failed and how to retry
//   loading request in flight -> hold the layout steady
// Tone drives the marker colour and the live-region politeness.
const TONE_LABEL = {
  empty: "Nothing here yet",
  stale: "Data may be out of date",
  error: "Couldn't load",
  loading: "Loading",
};

export function StatePanel({ tone = "empty", title, children, action, secondaryAction, compact = false }) {
  const role = tone === "error" ? "alert" : "status";
  return (
    <div className="statePanel" data-tone={tone} data-compact={compact} role={role}>
      <span className="stateMarker" aria-hidden="true" />
      <div className="stateBody">
        <p className="stateTitle">{title || TONE_LABEL[tone]}</p>
        {children ? <div className="stateText">{children}</div> : null}
        {action || secondaryAction ? (
          <div className="stateActions">
            {action ? (
              <Link className="primaryButton" href={action.href}>
                {action.label}
              </Link>
            ) : null}
            {secondaryAction ? (
              <Link className="ghostButton" href={secondaryAction.href}>
                {secondaryAction.label}
              </Link>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

// Layout-holding placeholder lines for loading states.
export function SkeletonLines({ lines = 3 }) {
  return (
    <div className="skeleton" aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <span key={index} className="skeletonLine" style={{ width: `${92 - index * 14}%` }} />
      ))}
    </div>
  );
}
