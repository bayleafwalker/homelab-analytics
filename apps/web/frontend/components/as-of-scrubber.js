import React from "react";
import Link from "next/link";

import { formatMonth } from "../lib/format";

// <AsOfScrubber> — step a page back through the months the reporting layer
// has published.
//
// The reporting layer keeps history only where a publication is keyed by
// month (monthly cashflow, spend by category, utility trend, the cashflow
// map). Snapshot publications — household overview, attention items,
// affordability ratios, recurring baseline — hold the current state only, and
// the API has no as_of read for them. So the scrubber offers exactly the
// months that exist, one row per year with a slot per month: months with
// published data are links, months without are shown but inert, so gaps in
// the history are visible rather than skipped over. State lives in the URL.
//
// months:   sorted "YYYY-MM" strings that have data
// value:    the month being viewed
// hrefFor:  (month | null) => href; null means "latest"
// note:     optional sentence saying what the page does and doesn't rewind

const LETTERS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
const ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function yearsOf(months) {
  const years = new Map();
  for (const month of months) {
    const [year, mm] = month.split("-");
    if (!years.has(year)) years.set(year, new Set());
    years.get(year).add(Number(mm));
  }
  return [...years.entries()].sort(([a], [b]) => Number(a) - Number(b));
}

export function AsOfScrubber({ months, value, hrefFor, label = "View as of month", note = null }) {
  const sorted = [...new Set((months || []).filter((m) => /^\d{4}-\d{2}$/.test(m)))].sort();
  if (sorted.length === 0) return null;
  const latest = sorted.at(-1);
  const selected = sorted.includes(value) ? value : latest;
  const index = sorted.indexOf(selected);
  const previous = index > 0 ? sorted[index - 1] : null;
  const next = index < sorted.length - 1 ? sorted[index + 1] : null;
  const isLatest = selected === latest;

  return (
    <nav className="asof" aria-label={label}>
      <div className="asofHeader">
        <p className="asofTitle">
          {isLatest ? "Latest month " : "Viewing "}
          <strong>{formatMonth(selected)}</strong>
        </p>
        <div className="asofSteps">
          {previous ? (
            <Link className="inlineLink" href={hrefFor(previous)} rel="prev">
              Earlier: {formatMonth(previous, { short: true })}
            </Link>
          ) : (
            <span aria-disabled="true">No earlier month</span>
          )}
          {next ? (
            <Link className="inlineLink" href={hrefFor(next === latest ? null : next)} rel="next">
              Later: {formatMonth(next, { short: true })}
            </Link>
          ) : null}
          {!isLatest ? (
            <Link className="inlineLink" href={hrefFor(null)}>
              Back to latest
            </Link>
          ) : null}
        </div>
      </div>
      <ol className="asofYears">
        {yearsOf(sorted).map(([year, present]) => (
          <li key={year} className="asofYear">
            <span className="asofYearLabel">{year}</span>
            <ol className="asofMonths">
              {ABBR.map((abbr, i) => {
                const month = `${year}-${String(i + 1).padStart(2, "0")}`;
                const face = (
                  <>
                    <span className="asofAbbr" aria-hidden="true">{abbr}</span>
                    <span className="asofLetter" aria-hidden="true">{LETTERS[i]}</span>
                  </>
                );
                if (!present.has(i + 1)) {
                  return (
                    <li key={month}>
                      <span className="asofMonth" title={`${formatMonth(month)}: no published data`}>
                        {face}
                        <span className="srOnly">{formatMonth(month)}, no published data</span>
                      </span>
                    </li>
                  );
                }
                return (
                  <li key={month}>
                    <Link
                      className="asofMonth"
                      href={hrefFor(month === latest ? null : month)}
                      aria-current={month === selected ? "true" : undefined}
                      title={formatMonth(month)}
                    >
                      {face}
                      <span className="srOnly">{formatMonth(month)}</span>
                    </Link>
                  </li>
                );
              })}
            </ol>
          </li>
        ))}
      </ol>
      {note ? <p className="asofNote">{note}</p> : null}
    </nav>
  );
}
