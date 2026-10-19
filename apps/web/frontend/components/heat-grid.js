import React from "react";

import { formatMoney, toNumber } from "../lib/format";

// <HeatGrid> — 7 rows (ISO weekday, Monday first) x 24 columns (hour of day)
// of spend from GET /reports/spend-heatmap. Hours are on the household clock
// the payload names in `timezone` (HOMELAB_ANALYTICS_HOUSEHOLD_TIMEZONE); the
// corner reads "UTC" or "local" and the caption names the zone.
//
// Intensity is quantised to five levels of --retro-accent; the busiest cells
// (level 4) switch to --retro-warn so the peak reads without a legend. Empty
// cells stay --retro-muted outlines. No other hues.
//
// Date-only bookings (most bank exports carry no time of day) are not drawn
// at 00:00: they get their own "date only" column, scaled on their own, so a
// grid full of untimed spend says so instead of pretending.
//
// The grid is a real <table>: row headers are days, column headers hours, and
// every cell carries its amount as screen-reader text.

const LEVELS = 4;
const HOUR_TICKS = new Set([0, 6, 12, 18]);
const DEFAULT_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAY_NAMES = {
  Mon: "Monday",
  Tue: "Tuesday",
  Wed: "Wednesday",
  Thu: "Thursday",
  Fri: "Friday",
  Sat: "Saturday",
  Sun: "Sunday",
};

export function heatLevel(value, max) {
  const number = toNumber(value) || 0;
  const peak = toNumber(max) || 0;
  if (number <= 0 || peak <= 0) return 0;
  return Math.max(1, Math.min(LEVELS, Math.ceil((number / peak) * LEVELS)));
}

function hourLabel(hour) {
  return String(hour).padStart(2, "0");
}

function coverageNote(heatmap) {
  switch (heatmap?.coverage) {
    case "empty":
      return "No spending in this window.";
    case "date_only":
      return "Sources record dates only, so all spend sits in the date-only column.";
    case "mixed":
      return "Some sources record dates only; that spend sits in the date-only column.";
    default:
      return null;
  }
}

export function HeatGrid({ heatmap, caption = "Spend by weekday and hour", compact = false }) {
  if (!heatmap || !Array.isArray(heatmap.cells)) {
    return <p className="heatEmpty">Spend heatmap unavailable.</p>;
  }
  const currency = heatmap.currency || null;
  const days = heatmap.day_labels?.length === 7 ? heatmap.day_labels : DEFAULT_DAYS;
  const showUntimed = (toNumber(heatmap.max_untimed) || 0) > 0;
  const note = coverageNote(heatmap);
  const amount = (value) => formatMoney(value, currency, { grouping: false });
  const zone = heatmap.timezone || (heatmap.hour_basis === "utc" ? "UTC" : "");
  const basis = zone === "UTC" ? "UTC" : zone ? "local" : "";

  return (
    <div className="heatGrid" data-compact={compact ? "true" : "false"} data-coverage={heatmap.coverage || "timed"}>
      <table className="heatTable">
        <caption className="srOnly">
          {caption}
          {heatmap.window_start && heatmap.window_end
            ? `, ${heatmap.window_start} to ${heatmap.window_end}`
            : ""}
          {zone ? `, hours in ${zone}` : ""}
        </caption>
        <thead>
          <tr>
            <td className="heatCorner" aria-hidden="true">
              {basis}
            </td>
            {Array.from({ length: 24 }, (_, hour) => (
              <th key={hour} scope="col" className="heatHour" data-tick={HOUR_TICKS.has(hour) ? "true" : "false"}>
                <span aria-hidden="true">{HOUR_TICKS.has(hour) ? hourLabel(hour) : ""}</span>
                <span className="srOnly">{`${hourLabel(hour)}:00`}</span>
              </th>
            ))}
            {showUntimed ? (
              <th scope="col" className="heatHour heatUntimedHead">
                date
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {heatmap.cells.map((row, dayIndex) => {
            const day = days[dayIndex] || DEFAULT_DAYS[dayIndex];
            return (
              <tr key={day}>
                <th scope="row" className="heatDay">
                  <abbr title={DAY_NAMES[day] || day}>{day}</abbr>
                </th>
                {row.map((value, hour) => {
                  const level = heatLevel(value, heatmap.max_cell);
                  return (
                    <td key={hour} className="heatCell" data-level={level}>
                      <span className="srOnly">{level ? amount(value) : "none"}</span>
                    </td>
                  );
                })}
                {showUntimed ? (
                  <td
                    className="heatCell heatUntimed"
                    data-level={heatLevel(heatmap.untimed?.[dayIndex], heatmap.max_untimed)}
                  >
                    <span className="srOnly">
                      {heatLevel(heatmap.untimed?.[dayIndex], heatmap.max_untimed)
                        ? `${amount(heatmap.untimed[dayIndex])} with no time recorded`
                        : "none"}
                    </span>
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="heatFoot">
        <span className="heatLegend" aria-hidden="true">
          <span className="heatSwatch" data-level="0" />
          <span className="heatSwatch" data-level="1" />
          <span className="heatSwatch" data-level="2" />
          <span className="heatSwatch" data-level="3" />
          <span className="heatSwatch" data-level="4" />
        </span>
        {(toNumber(heatmap.max_cell) || 0) > 0 ? (
          <span>
            peak hour <span className="num">{amount(heatmap.max_cell)}</span>
          </span>
        ) : showUntimed ? (
          <span>
            peak day <span className="num">{amount(heatmap.max_untimed)}</span>
          </span>
        ) : null}
        {note ? <span className="heatNote">{note}</span> : null}
      </p>
    </div>
  );
}
