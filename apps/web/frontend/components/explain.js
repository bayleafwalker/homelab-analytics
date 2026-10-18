import React from "react";
import Link from "next/link";

import { ExplainDisclosure } from "./explain-disclosure";

// <Explain> — "where does this number come from?" next to any figure.
//
// Two layers so it works in any tree:
//   <ExplainPanel explanation={…}>  pure presentation, usable from client
//                                    components and stories with preloaded data
//   <Explain publication="…">       async server component (explain-server.js)
//                                    that loads the explanation via lib/explain.js
//
// The panel states which publication, which row and column, the lineage
// recorded behind it (GET /api/lineage/publication/{key}) and, for admins, the
// publication's confidence verdict. When only the publication node is
// recorded it says so instead of drawing an imaginary chain.

const VERDICT_TONE = {
  trustworthy: "ok",
  degraded: "warm",
  unreliable: "warn",
  unavailable: "neutral",
};

// Walks upstream from the figure: what the mart was built from, the runs that
// loaded it, the source assets they landed and the systems those came from.
const THREAD = [
  { type: "relation", one: "relation it was built from", many: "relations it was built from", names: "relations" },
  { type: "run", one: "ingestion run behind it", many: "ingestion runs behind it" },
  { type: "asset", one: "source asset landed", many: "source assets landed", names: "assets" },
  { type: "source", one: "source system", many: "source systems", names: "sources" },
];

function lineageHref(key) {
  return `/briefing/lineage?publication_key=${encodeURIComponent(key)}`;
}

function formatAssessed(value) {
  if (!value) return null;
  return String(value).replace("T", " ").slice(0, 16) + " UTC";
}

function describeRow(filter) {
  if (!filter) return null;
  if (typeof filter === "string") return filter;
  return Object.entries(filter)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => `${key} = ${value}`)
    .join(", ");
}

export function ExplainPanel({ explanation, label, field, filter, note }) {
  const { publicationKey, publicationName, lineage, lineageError, confidence, canSeeControl } = explanation;
  const row = describeRow(filter);
  const verdict = confidence?.verdict || null;

  return (
    <>
      <p className="explainHeading">{label}</p>
      <dl className="explainFacts">
        <div>
          <dt>Read from</dt>
          <dd>
            {publicationName ? <span className="explainPubName">{publicationName}</span> : null}
            <code>{publicationKey}</code>
          </dd>
        </div>
        {field || row ? (
          <div>
            <dt>Value</dt>
            <dd>
              {field ? (
                <>
                  column <code>{field}</code>
                </>
              ) : null}
              {field && row ? ", " : null}
              {row ? <>row where <code>{row}</code></> : null}
            </dd>
          </div>
        ) : null}
        {verdict ? (
          <div>
            <dt>Confidence</dt>
            <dd>
              <span className="pill" data-tone={VERDICT_TONE[verdict] || "neutral"}>{verdict}</span>
              {confidence.freshness ? <span className="explainAside">freshness {confidence.freshness}</span> : null}
              {formatAssessed(confidence.assessedAt) ? (
                <span className="explainAside">assessed {formatAssessed(confidence.assessedAt)}</span>
              ) : null}
            </dd>
          </div>
        ) : null}
      </dl>

      {lineageError ? (
        <p className="explainNote" data-tone="error">Lineage couldn&apos;t be loaded: {lineageError}</p>
      ) : (
        <ol className="explainThread" aria-label="Lineage behind this figure">
          <li data-recorded="true" data-kind="publication">
            <span className="explainNode" aria-hidden="true" />
            <span>
              Publication <code>{publicationKey}</code>
            </span>
          </li>
          {lineage?.recorded ? (
            THREAD.map((step) => {
              const count = lineage.counts[step.type] || 0;
              return (
                <li key={step.type} data-recorded={count > 0 ? "true" : "false"} data-kind={step.type}>
                  <span className="explainNode" aria-hidden="true" />
                  <span>
                    {count > 0 ? (
                      <>
                        <span className="numMono">{count}</span> {count === 1 ? step.one : step.many}
                        {step.names && lineage[step.names]?.length ? (
                          <span className="explainAside">
                            {" "}
                            {lineage[step.names].slice(0, 3).join(", ")}
                            {lineage[step.names].length > 3 ? ` +${lineage[step.names].length - 3}` : ""}
                          </span>
                        ) : null}
                      </>
                    ) : (
                      <span className="explainMissing">No {step.many} recorded</span>
                    )}
                  </span>
                </li>
              );
            })
          ) : (
            <li data-recorded="false" data-kind="upstream">
              <span className="explainNode" aria-hidden="true" />
              <span className="explainMissing">
                No runs or sources recorded behind it yet. They appear here once a promotion records
                lineage for this publication.
              </span>
            </li>
          )}
        </ol>
      )}

      {note ? <p className="explainNote">{note}</p> : null}

      <p className="explainLinks">
        <Link className="inlineLink" href={lineageHref(publicationKey)}>
          Trace full lineage
        </Link>
        {canSeeControl ? (
          <Link className="inlineLink" href={verdict ? `/control/confidence?verdict=${encodeURIComponent(verdict)}` : "/control/confidence"}>
            Publication confidence
          </Link>
        ) : null}
      </p>
    </>
  );
}

export function ExplainBox({ explanation, label, field, filter, note, placement, tone }) {
  return (
    <ExplainDisclosure label={label} placement={placement} tone={tone}>
      <ExplainPanel explanation={explanation} label={label} field={field} filter={filter} note={note} />
    </ExplainDisclosure>
  );
}
