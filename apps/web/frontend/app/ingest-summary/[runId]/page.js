import Link from "next/link";
import { notFound } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import {
  getCurrentUser,
  getMonthlyCashflow,
  getPublicationAudit,
  getRecurringCostBaseline,
  getRun,
  getAffordabilityRatios,
  getAttentionItems,
} from "@/lib/backend";

function formatDatasetLabel(datasetName) {
  if (!datasetName) return "Unknown dataset";
  return datasetName
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default async function IngestSummaryPage({ params }) {
  const user = await getCurrentUser();
  const runId = params.runId;

  let run;
  try {
    run = await getRun(runId);
  } catch {
    notFound();
  }
  if (!run) notFound();

  const [publicationAudit, cashflowRows, recurringBaseline, affordabilityRatios, attentionItems] =
    await Promise.all([
      getPublicationAudit({ runId }),
      getMonthlyCashflow(),
      getRecurringCostBaseline(),
      getAffordabilityRatios(),
      getAttentionItems(),
    ]);

  const latestCashflow = cashflowRows.at(-1);
  const publishedRelations = publicationAudit.filter(
    (r) => r.status === "published" || r.status === "refreshed"
  );
  const runSucceeded = run.status === "landed" || run.status === "promoted";

  return (
    <AppShell
      currentPath="/upload"
      user={user}
      title="Ingest Summary"
      eyebrow="Upload Received"
      lede="Your file has been processed. Here is a summary of what arrived and what it populated in the operating picture."
    >
      <section className="stack">
        <div className="buttonRow">
          <Link className="ghostButton" href="/upload">
            Upload another file
          </Link>
          <Link className="ghostButton" href="/sources">
            Source freshness
          </Link>
          <Link className="ghostButton" href="/reports">
            Monthly finance
          </Link>
        </div>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Ingestion run</div>
              <h2>{formatDatasetLabel(run.dataset_name)}</h2>
            </div>
            <span className={`statusPill status-${run.status}`}>{run.status}</span>
          </div>
          <div className="metaGrid">
            <div className="metaItem">
              <div className="metricLabel">Dataset</div>
              <div>{formatDatasetLabel(run.dataset_name)}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">File</div>
              <div>{run.file_name || "—"}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Rows ingested</div>
              <div>{run.row_count ?? "—"}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Source</div>
              <div>{run.source_name || "—"}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Processed at</div>
              <div>{run.created_at ? new Date(run.created_at).toLocaleString() : "—"}</div>
            </div>
            <div className="metaItem">
              <div className="metricLabel">Validation</div>
              <div>
                {run.issues?.length > 0 ? (
                  <span className="warnText">{run.issues.length} issue(s)</span>
                ) : (
                  <span style={{ color: "var(--ok)" }}>Clean</span>
                )}
              </div>
            </div>
          </div>
          {!runSucceeded && run.issues?.length > 0 && (
            <div className="stack compactStack" style={{ marginTop: "12px" }}>
              <div className="metricLabel">Validation issues</div>
              {run.issues.slice(0, 4).map((issue, i) => (
                <div key={i} className="muted" style={{ fontSize: "0.85rem" }}>
                  {issue.code}: {issue.message}
                </div>
              ))}
              {run.issues.length > 4 && (
                <Link className="inlineLink" href={`/runs/${runId}`}>
                  View all {run.issues.length} issues
                </Link>
              )}
            </div>
          )}
        </article>

        {publishedRelations.length > 0 && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Publications refreshed</div>
                <h2>What this upload populated</h2>
              </div>
            </div>
            <div className="entityList">
              {publishedRelations.map((record) => (
                <article className="entityCard" key={record.publication_audit_id}>
                  <div className="entityHeader">
                    <div>
                      <div className="metricLabel">{record.publication_key}</div>
                      <h3>{record.relation_name}</h3>
                    </div>
                    <span className="statusPill status-landed">{record.status}</span>
                  </div>
                </article>
              ))}
            </div>
          </article>
        )}

        {runSucceeded && (
          <section className="cards">
            <article className="panel section">
              <div className="eyebrow">Cashflow snapshot</div>
              <h3 style={{ margin: "4px 0 8px" }}>
                {latestCashflow
                  ? `${latestCashflow.booking_month}: net ${latestCashflow.net}`
                  : "No cashflow data yet"}
              </h3>
              {latestCashflow && (
                <div className="muted" style={{ fontSize: "0.85rem" }}>
                  Income: {latestCashflow.income} &nbsp;·&nbsp; Expense: {latestCashflow.expense}
                </div>
              )}
              <div style={{ marginTop: "12px" }}>
                <Link className="inlineLink" href="/reports#expense-shock">
                  Open monthly finance
                </Link>
              </div>
            </article>

            {recurringBaseline.length > 0 && (
              <article className="panel section">
                <div className="eyebrow">Recurring baseline</div>
                <h3 style={{ margin: "4px 0 8px" }}>
                  {recurringBaseline.length} committed costs
                </h3>
                <div className="muted" style={{ fontSize: "0.85rem" }}>
                  Total:{" "}
                  {recurringBaseline
                    .reduce((sum, r) => sum + Number(r.monthly_amount || 0), 0)
                    .toFixed(2)}{" "}
                  / mo
                </div>
                <div style={{ marginTop: "12px" }}>
                  <Link className="inlineLink" href="/costs">
                    Cost model
                  </Link>
                </div>
              </article>
            )}

            {affordabilityRatios.length > 0 && (
              <article className="panel section">
                <div className="eyebrow">Affordability</div>
                <h3 style={{ margin: "4px 0 8px" }}>
                  {affordabilityRatios.length} ratio(s) updated
                </h3>
                <div className="stack compactStack">
                  {affordabilityRatios.slice(0, 2).map((r) => (
                    <div key={r.ratio_name} style={{ fontSize: "0.85rem" }}>
                      <span className="muted">
                        {r.ratio_name.replace(/_/g, " ")}:{" "}
                      </span>
                      {(Number(r.ratio) * 100).toFixed(1)}%
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: "12px" }}>
                  <Link className="inlineLink" href="/reports#expense-shock">
                    Expense shock handoff
                  </Link>
                </div>
              </article>
            )}
          </section>
        )}

        {attentionItems.length > 0 && runSucceeded && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Attention</div>
                <h2>Items to review after this upload</h2>
              </div>
              <Link className="inlineLink" href="/review">
                See all
              </Link>
            </div>
            <div className="stack compactStack">
              {attentionItems.slice(0, 5).map((item, i) => (
                <div key={i} style={{ display: "flex", gap: "8px", alignItems: "flex-start" }}>
                  {item.severity === 1 && (
                    <span className="statusPill status-failed">warn</span>
                  )}
                  <div>
                    <div style={{ fontWeight: 700 }}>{item.title}</div>
                    {item.source_domain && (
                      <div className="muted" style={{ fontSize: "0.82rem" }}>
                        {item.source_domain}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </article>
        )}

        <div className="buttonRow">
          <Link className="ghostButton" href={`/runs/${runId}`}>
            Full run detail
          </Link>
          <Link className="ghostButton" href="/sources">
            Source freshness
          </Link>
          <Link className="ghostButton" href="/reports#expense-shock">
            Expense shock handoff
          </Link>
          <Link className="ghostButton" href="/onboarding">
            Onboarding
          </Link>
        </div>
      </section>
    </AppShell>
  );
}
