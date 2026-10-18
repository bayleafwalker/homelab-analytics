import Link from "next/link";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ControlNav } from "@/components/control-nav";
import { Pill } from "@/components/pill";
import { ResponsiveTable } from "@/components/responsive-table";
import { StatePanel } from "@/components/state-panel";
import { getCurrentUser, getPublicationConfidence } from "@/lib/backend";

// Server component (ADR web-surface-shell-decision §4.3). The previous client
// version fetched /auth/me and /api/control/confidence from the browser; in
// split-origin deployments nothing routes those to the API, so the page
// bounced to /login. Filters now live in the URL (?stale=1&verdict=…) and the
// read goes through lib/backend.ts like every other page.

const VERDICTS = ["trustworthy", "degraded", "unreliable", "unavailable"];

const VERDICT_TONE = { trustworthy: "ok", degraded: "warm", unreliable: "warn", unavailable: "neutral" };
const FRESHNESS_TONE = { current: "ok", due_soon: "warm", stale: "warn", unavailable: "neutral" };

function label(value) {
  const text = String(value || "unavailable").replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function formatAssessedAt(value, now) {
  if (!value) return "Not assessed";
  const hoursAgo = Math.floor((now - new Date(value)) / (1000 * 60 * 60));
  if (hoursAgo < 1) return "Just now";
  if (hoursAgo < 24) return `${hoursAgo}h ago`;
  return `${Math.floor(hoursAgo / 24)}d ago`;
}

function CompletenessBar({ value }) {
  const bounded = Math.max(0, Math.min(100, Number(value || 0)));
  return (
    <span className="confidenceBar">
      <span className="confidenceBarTrack" aria-hidden="true">
        <span className="confidenceBarFill" data-complete={bounded >= 100 ? "true" : "false"} style={{ width: `${bounded}%` }} />
      </span>
      <span className="numMono">{bounded}%</span>
    </span>
  );
}

function isRedirect(error) {
  return Boolean(
    error && typeof error === "object" && "digest" in error && String(error.digest).startsWith("NEXT_REDIRECT")
  );
}

export default async function ConfidencePage({ searchParams }) {
  const user = await getCurrentUser();
  if (!user || user.role === "reader") {
    redirect("/");
  }

  const staleOnly = searchParams?.stale === "1";
  const verdict = VERDICTS.includes(searchParams?.verdict) ? searchParams.verdict : "";

  let data = null;
  let loadError = null;
  try {
    data = await getPublicationConfidence({ staleOnly, ...(verdict ? { verdict } : {}) });
  } catch (error) {
    if (isRedirect(error)) throw error;
    loadError = error instanceof Error ? error.message : String(error);
  }

  const publications = data?.publications || [];
  const domains = data?.domain_summaries || [];
  const now = Date.now();
  const filtered = staleOnly || verdict;

  return (
    <AppShell
      currentPath="/control/confidence"
      user={user}
      title="Publication confidence"
      eyebrow="Admin control plane"
      lede="How far each published figure can be trusted, from source freshness, completeness and validation."
    >
      <ControlNav currentPath="/control/confidence" />

      {loadError ? (
        <StatePanel tone="error" title="Couldn't load publication confidence">
          <p>{loadError}</p>
        </StatePanel>
      ) : (
        <div className="stack">
          <section className="panel section" aria-labelledby="confidence-domains">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">By domain</div>
                <h2 id="confidence-domains">Domain summary</h2>
              </div>
            </div>
            {domains.length === 0 ? (
              <StatePanel tone="empty" compact title="No publications assessed yet" />
            ) : (
              <ul className="confidenceDomains">
                {domains.map((domain) => (
                  <li key={domain.domain}>
                    <div>
                      <p className="confidenceDomainName">{label(domain.domain)}</p>
                      <p className="muted">
                        {domain.count} publication{domain.count === 1 ? "" : "s"}, {domain.degraded_count} degraded,{" "}
                        {domain.stale_count} stale
                      </p>
                    </div>
                    <Pill tone={VERDICT_TONE[domain.verdict] || "neutral"}>{label(domain.verdict)}</Pill>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel section" aria-labelledby="confidence-publications">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">
                  {publications.length} publication{publications.length === 1 ? "" : "s"}
                  {filtered ? " matching" : ""}
                </div>
                <h2 id="confidence-publications">Publications</h2>
              </div>
            </div>
            <form className="confidenceFilters" action="/control/confidence" method="get">
                <label>
                  <input type="checkbox" name="stale" value="1" defaultChecked={staleOnly} /> Stale only
                </label>
                <label className="srOnly" htmlFor="confidence-verdict">
                  Verdict
                </label>
                <select id="confidence-verdict" name="verdict" defaultValue={verdict}>
                  <option value="">All verdicts</option>
                  {VERDICTS.map((value) => (
                    <option key={value} value={value}>
                      {label(value)}
                    </option>
                  ))}
                </select>
                <button className="ghostButton" type="submit">
                  Apply
                </button>
                {filtered ? (
                  <Link className="inlineLink" href="/control/confidence">
                    Clear filters
                  </Link>
                ) : null}
            </form>
            <ResponsiveTable
              label="Publication confidence"
              rows={publications}
              rowKey="publication_key"
              empty={
                <StatePanel tone="empty" compact title="No publications match these filters">
                  {filtered ? <p>Clear the filters to see every publication.</p> : null}
                </StatePanel>
              }
              columns={[
                {
                  key: "publication_key",
                  header: "Publication",
                  primary: true,
                  cell: (pub) => (
                    <>
                      <span style={{ display: "block" }}>{pub.publication_name || pub.publication_key}</span>
                      <code className="muted" style={{ fontSize: "0.78rem", fontWeight: 400 }}>
                        {pub.publication_key}
                      </code>
                    </>
                  ),
                },
                { key: "domain", header: "Domain", cell: (pub) => label(pub.domain || "platform") },
                {
                  key: "confidence_verdict",
                  header: "Verdict",
                  cell: (pub) => (
                    <Pill tone={VERDICT_TONE[pub.confidence_verdict] || "neutral"}>{label(pub.confidence_verdict)}</Pill>
                  ),
                },
                {
                  key: "freshness_state",
                  header: "Freshness",
                  cell: (pub) => (
                    <Pill tone={FRESHNESS_TONE[pub.freshness_state] || "neutral"}>{label(pub.freshness_state)}</Pill>
                  ),
                },
                { key: "completeness_pct", header: "Complete", cell: (pub) => <CompletenessBar value={pub.completeness_pct} /> },
                { key: "source_count", header: "Sources", align: "end", cell: (pub) => pub.source_count || 0 },
                { key: "assessed_at", header: "Assessed", cell: (pub) => formatAssessedAt(pub.assessed_at, now) },
                {
                  key: "lineage",
                  header: "Lineage",
                  hideLabel: true,
                  cell: (pub) => (
                    <Link
                      className="inlineLink"
                      href={`/control/lineage?publication_key=${encodeURIComponent(pub.publication_key)}`}
                      data-testid={`lineage-link-${pub.publication_key}`}
                    >
                      Lineage<span className="srOnly"> of {pub.publication_key}</span>
                    </Link>
                  ),
                },
              ]}
            />
          </section>
        </div>
      )}
    </AppShell>
  );
}
