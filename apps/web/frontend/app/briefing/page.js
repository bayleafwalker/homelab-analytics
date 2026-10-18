import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { Explain } from "@/components/explain-server";
import { Eyebrow } from "@/components/eyebrow";
import { NumMono } from "@/components/num-mono";
import { Pill } from "@/components/pill";
import { getBriefing, getCurrentUser } from "@/lib/backend";

import styles from "./briefing.module.css";

// Morning brief (Kotona B1). Server component with zero client state: the
// backend composes a deterministic brief (no LLM) and this page renders it.
// Every line shows its claim status and confidence, and links to the
// lineage drill for the publication behind it.

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

function EvidenceLine({ item, user }) {
  const runs = item.evidence.filter((ref) => ref.kind === "run");
  if (!item.lineage_publication_key && runs.length === 0) return null;
  return (
    <div className={styles.evidence}>
      {item.lineage_publication_key ? (
        // Presentation only: the brief already carries this line's confidence,
        // so the explanation reuses it instead of a second read.
        <Explain
          publication={item.lineage_publication_key}
          user={user}
          confidence={item.confidence || null}
          label={item.headline}
          placement="start"
        />
      ) : null}
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

function BriefItem({ item, user }) {
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
      <EvidenceLine item={item} user={user} />
    </li>
  );
}

// Brief sections that belong to the finance operator loop link to the
// surface where the operator acts on them.
const SECTION_SURFACE = {
  money: { href: "/reports", label: "Open monthly finance" },
  sources: { href: "/sources", label: "Open source freshness", operatorOnly: true },
};

function BriefSection({ section, user }) {
  const candidate = SECTION_SURFACE[section.key];
  const surface = candidate?.operatorOnly && user?.role === "reader" ? null : candidate;
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
          <BriefItem key={item.item_id} item={item} user={user} />
        ))}
      </ul>
    </section>
  );
}

export default async function BriefingPage() {
  const user = await getCurrentUser();
  const brief = await getBriefing();
  const { counts } = brief;

  return (
    <AppShell
      currentPath="/briefing"
      user={user}
      title="Morning brief"
      eyebrow="Kotona Operating Picture"
      lede="What needs attention today, stated only as far as the data supports it."
    >
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
          <BriefSection key={section.key} section={section} user={user} />
        ))}

        <footer className={styles.footer}>
          Composed deterministically from reporting publications, policy verdicts, source
          freshness and publication confidence. No language model is involved: lines are
          confirmed only when their publication is trustworthy, marked provisional when it is
          degraded, and withheld with a next step when data is stale or unknown. Content hash{" "}
          <NumMono>{brief.content_hash.slice(0, 12)}</NumMono> · schema {brief.schema_version}.
        </footer>
      </article>
    </AppShell>
  );
}
