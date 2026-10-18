import React from "react";
import Link from "next/link";

import styles from "../app/briefing/briefing.module.css";
import { Eyebrow } from "./eyebrow";
import { NumMono } from "./num-mono";
import { Pill } from "./pill";

// Morning brief body (Kotona B1), shared by /briefing and its Storybook
// story. Pure presentation over the /api/briefing payload: every line shows
// its claim status and confidence, and links to the lineage drill for the
// publication behind it. The page passes `renderExplain` to attach the
// server-side <Explain> panel; stories leave it out.

const SEVERITY_TONE = { critical: "warn", warning: "warm", notice: "cool", info: "neutral" };
const CLAIM_TONE = { confirmed: "ok", provisional: "warm", withheld: "neutral" };
const CLAIM_LABEL = { confirmed: "Confirmed", provisional: "Provisional", withheld: "Withheld" };
const SECTION_TONE = { ok: "ok", attention: "warm", degraded: "cool", unavailable: "neutral" };

function lineageDrillHref(publicationKey) {
  return `/briefing/lineage?publication_key=${encodeURIComponent(publicationKey)}`;
}

function formatTimestamp(value) {
  if (!value) return "not assessed";
  return value.replace("T", " ").slice(0, 16) + " UTC";
}

function ConfidenceLine({ confidence }) {
  if (!confidence) return null;
  return (
    <div className={styles.confidence} data-testid="brief-confidence">
      <span>Confidence {confidence.verdict}</span>
      <span>Freshness {confidence.freshness_state}</span>
      {confidence.completeness_pct !== null && confidence.completeness_pct !== undefined ? (
        <span>
          Completeness <NumMono>{confidence.completeness_pct}%</NumMono>
        </span>
      ) : null}
      <span>Validation {confidence.validation_state}</span>
      <span>Assessed {formatTimestamp(confidence.assessed_at)}</span>
    </div>
  );
}

function EvidenceLine({ item, renderExplain }) {
  const runs = item.evidence.filter((ref) => ref.kind === "run");
  if (!item.lineage_publication_key && runs.length === 0) return null;
  return (
    <div className={styles.evidence}>
      {item.lineage_publication_key && renderExplain ? renderExplain(item) : null}
      {item.lineage_publication_key ? (
        <Link
          href={lineageDrillHref(item.lineage_publication_key)}
          data-testid={`brief-lineage-${item.item_id}`}
        >
          Trace lineage of {item.lineage_publication_key}
        </Link>
      ) : null}
      {runs.map((ref) => (
        <Link key={ref.ref} href={`/runs/${encodeURIComponent(ref.ref)}`}>
          {ref.label}
        </Link>
      ))}
    </div>
  );
}

function BriefItem({ item, renderExplain }) {
  return (
    <li
      className={styles.item}
      data-severity={item.severity}
      data-claim={item.claim_status}
      data-testid={`brief-item-${item.item_id}`}
    >
      <div className={styles.itemTop}>
        <Pill tone={SEVERITY_TONE[item.severity]}>{item.severity}</Pill>
        <Pill tone={CLAIM_TONE[item.claim_status]}>{CLAIM_LABEL[item.claim_status]}</Pill>
        <span className={styles.itemHeadline}>{item.headline}</span>
      </div>
      {item.detail ? <div className={styles.detail}>{item.detail}</div> : null}
      {item.caveats.length > 0 ? (
        <ul className={styles.caveats}>
          {item.caveats.map((caveat) => (
            <li key={caveat}>{caveat}</li>
          ))}
        </ul>
      ) : null}
      {item.remediation ? (
        <div className={styles.remediation}>
          <strong>Next step:</strong> {item.remediation}
        </div>
      ) : null}
      <ConfidenceLine confidence={item.confidence} />
      <EvidenceLine item={item} renderExplain={renderExplain} />
    </li>
  );
}

function BriefSection({ section, renderExplain, surface = null }) {
  return (
    <section className={styles.section} data-testid={`brief-section-${section.key}`}>
      <div className={styles.sectionHeader}>
        <h2>{section.title}</h2>
        <Pill tone={SECTION_TONE[section.status]}>{section.status}</Pill>
      </div>
      <p className={styles.summary}>
        {section.summary}
        {surface ? (
          <>
            {" "}
            <Link className="inlineLink" href={surface.href} data-testid={`brief-surface-${section.key}`}>
              {surface.label}
            </Link>
          </>
        ) : null}
      </p>
      <ul className={styles.items}>
        {section.items.map((item) => (
          <BriefItem key={item.item_id} item={item} renderExplain={renderExplain} />
        ))}
      </ul>
    </section>
  );
}

// `surfaces` maps a section key to the { href, label } the operator acts on
// (already filtered for the viewer's role by the page).
export function BriefingView({ brief, renderExplain = null, surfaces = {} }) {
  const { counts } = brief;
  return (
    <article className={styles.brief}>
      <header className={styles.masthead}>
        <div>
          <Eyebrow>Brief for {brief.as_of}</Eyebrow>
          <p className={styles.headline}>{brief.headline}</p>
        </div>
        <div className={styles.meta}>
          <Pill tone={SEVERITY_TONE[brief.overall_severity]}>{brief.overall_severity}</Pill>
          <span>Generated {formatTimestamp(brief.generated_at)}</span>
        </div>
      </header>

      <div className={styles.counts} aria-label="Brief counts">
        <span>
          <strong><NumMono>{counts.confirmed}</NumMono></strong>confirmed
        </span>
        <span>
          <strong><NumMono>{counts.provisional}</NumMono></strong>provisional
        </span>
        <span>
          <strong><NumMono>{counts.withheld}</NumMono></strong>withheld
        </span>
        <span>
          <strong><NumMono>{counts.warning + counts.critical}</NumMono></strong>need attention
        </span>
      </div>

      {brief.sections.map((section) => (
        <BriefSection
          key={section.key}
          section={section}
          renderExplain={renderExplain}
          surface={surfaces[section.key] || null}
        />
      ))}

      <footer className={styles.footer}>
        Composed deterministically from reporting publications, policy verdicts, source
        freshness and publication confidence. No language model is involved: lines are
        confirmed only when their publication is trustworthy, marked provisional when it is
        degraded, and withheld with a next step when data is stale or unknown. Content hash{" "}
        <NumMono>{brief.content_hash.slice(0, 12)}</NumMono> · schema {brief.schema_version}.
      </footer>
    </article>
  );
}
