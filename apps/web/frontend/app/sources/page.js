import Link from "next/link";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ResponsiveTable } from "@/components/responsive-table";
import { getCurrentUser, getSourceFreshness, getRuns } from "@/lib/backend";

// Links land on the matching upload card on /upload; the /upload/<dataset>
// paths themselves are POST-only route handlers.
const BUILTIN_UPLOAD_PATH = {
  account_transactions: "/upload#upload-account-transactions",
  subscriptions: "/upload#upload-subscriptions",
  contract_prices: "/upload#upload-contract-prices",
  budgets: "/upload#upload-budgets",
  loan_repayments: "/upload#upload-loan-repayments",
};

function stalenessLabel(landedAt) {
  if (!landedAt) return { label: "Never loaded", color: "var(--warn)", indicator: "red" };
  const now = new Date();
  const then = new Date(landedAt);
  const diffDays = (now - then) / (1000 * 60 * 60 * 24);
  if (diffDays < 2)  return { label: "Fresh", color: "var(--ok)", indicator: "green" };
  if (diffDays < 7)  return { label: `${Math.floor(diffDays)}d ago`, color: "var(--accent-warm)", indicator: "yellow" };
  return { label: `${Math.floor(diffDays)}d ago — stale`, color: "var(--warn)", indicator: "red" };
}

function formatDatasetLabel(datasetName) {
  return datasetName
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function remediationActions(status, uploadPath) {
  const actions = [];
  if (status === "rejected" || status === "failed") {
    actions.push({ label: "Inspect run", kind: "run" });
  }
  if (uploadPath) {
    actions.push({ label: "Upload corrected file", kind: "upload", href: uploadPath });
  }
  if (!uploadPath) {
    actions.push({ label: "Open run history", kind: "history", href: "/runs" });
  }
  return actions;
}

export default async function SourcesPage() {
  const user = await getCurrentUser();
  if (user.role === "reader") {
    redirect("/");
  }

  const [freshnessDatasets, recentRuns] = await Promise.all([
    getSourceFreshness(),
    getRuns(200),
  ]);

  // Each row is one source asset. Several assets can feed the same dataset
  // (three bank accounts into account_transactions), so run details are
  // joined on the asset's own latest_run_id from the freshness API — never on
  // the dataset's newest run, which made every row show the same source.
  const runsById = new Map(recentRuns.map((run) => [run.run_id, run]));

  const rows = freshnessDatasets.map((ds) => {
    const lastRun = ds.latest_run_id ? runsById.get(ds.latest_run_id) || null : null;
    const uploadPath = BUILTIN_UPLOAD_PATH[ds.dataset_name] || null;
    const staleness = stalenessLabel(ds.landed_at);
    const actions = remediationActions(ds.status, uploadPath);
    return { ...ds, lastRun, uploadPath, staleness, actions };
  });

  // Sort: stale/never first, then by dataset name
  rows.sort((a, b) => {
    const order = { red: 0, yellow: 1, green: 2 };
    const aOrd = order[a.staleness.indicator] ?? 3;
    const bOrd = order[b.staleness.indicator] ?? 3;
    if (aOrd !== bOrd) return aOrd - bOrd;
    return (a.name || a.dataset_name).localeCompare(b.name || b.dataset_name);
  });

  const staleCount = rows.filter((r) => r.staleness.indicator === "red").length;
  const warnCount = rows.filter((r) => r.staleness.indicator === "yellow").length;

  return (
    <AppShell
      currentPath="/sources"
      user={user}
      title="Data Sources"
      eyebrow="Operator Access"
      lede="Freshness and remediation for operational sources. Use this page to upload corrected files, inspect failed runs, and clear stale source state before it reaches reporting."
    >
      <section className="stack">
        <section className="cards">
          <article className="panel metricCard">
            <div className="metricLabel">Total sources</div>
            <div className="metricValue">{rows.length}</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Stale / never loaded</div>
            <div className="metricValue" style={{ color: staleCount > 0 ? "var(--warn)" : "var(--ok)" }}>
              {staleCount}
            </div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Getting stale</div>
            <div className="metricValue" style={{ color: warnCount > 0 ? "var(--accent-warm)" : "var(--ok)" }}>
              {warnCount}
            </div>
          </article>
        </section>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Ingestion Freshness</div>
              <h2>Source status &amp; remediation</h2>
            </div>
            <div className="buttonRow">
              <Link className="ghostButton" href="/upload">
                Upload files
              </Link>
              <Link className="ghostButton" href="/reports">
                Monthly finance
              </Link>
            </div>
          </div>
          <ResponsiveTable
            label="Source status and remediation"
            rows={rows}
            rowKey={(row) => row.source_asset_id || row.dataset_name}
            empty={<div className="empty">No source freshness data available. Run an upload or retry first.</div>}
            columns={[
              {
                key: "name",
                header: "Source",
                primary: true,
                cell: (row) => (
                  <>
                    <span style={{ display: "block" }}>{row.name || formatDatasetLabel(row.dataset_name)}</span>
                    <span className="muted" style={{ fontSize: "0.82rem", fontFamily: "var(--font-sans)", fontWeight: 400 }}>
                      {formatDatasetLabel(row.dataset_name)}
                    </span>
                  </>
                ),
              },
              {
                key: "staleness",
                header: "Status",
                cell: (row) => (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                    <span
                      aria-hidden="true"
                      style={{
                        display: "inline-block",
                        width: "10px",
                        height: "10px",
                        borderRadius: "50%",
                        background: row.staleness.color,
                      }}
                    />
                    <span className="muted" style={{ fontSize: "0.82rem" }}>{row.staleness.label}</span>
                  </span>
                ),
              },
              {
                key: "landed_at",
                header: "Last ingested",
                cell: (row) =>
                  row.latest_run_id ? (
                    <Link className="inlineLink" href={`/runs/${row.latest_run_id}`}>
                      {row.landed_at ? new Date(row.landed_at).toLocaleDateString("en-GB") : row.latest_run_id}
                    </Link>
                  ) : (
                    <span className="muted">Never</span>
                  ),
              },
              {
                key: "status",
                header: "Run status",
                cell: (row) =>
                  row.status ? (
                    <span
                      className={`statusPill ${
                        row.status === "landed" || row.status === "promoted"
                          ? "status-landed"
                          : row.status === "rejected" || row.status === "failed"
                          ? "status-rejected"
                          : "status-pending"
                      }`}
                    >
                      {row.status}
                    </span>
                  ) : null,
              },
              {
                key: "source_name",
                header: "Uploaded as",
                cell: (row) => <span className="muted">{row.lastRun?.source_name || null}</span>,
              },
              {
                key: "actions",
                header: "Actions",
                hideLabel: true,
                cell: (row) => (
                  <span style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {row.actions.map((action) =>
                      action.kind === "run" && row.latest_run_id ? (
                        <Link key={action.label} className="inlineLink" href={`/runs/${row.latest_run_id}`}>
                          {action.label}
                        </Link>
                      ) : action.href ? (
                        <Link key={action.label} className="inlineLink" href={action.href}>
                          {action.label}
                        </Link>
                      ) : null
                    )}
                  </span>
                ),
              },
            ]}
          />
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Recovery</div>
              <h2>Recover stale sources</h2>
            </div>
          </div>
          <div className="muted" style={{ marginBottom: "12px" }}>
            Upload a corrected file for a stale or failed source, or open the latest run to inspect
            validation, parser, and retry context. Publication trust stays in reporting surfaces.
          </div>
          {rows.filter((r) => r.uploadPath && r.staleness.indicator !== "green").length === 0 ? (
            <div className="muted">All uploadable sources are fresh.</div>
          ) : (
            <div className="stack compactStack">
              {rows
                .filter((r) => r.uploadPath && r.staleness.indicator !== "green")
                .map((r) => {
                  return (
                    <div key={r.source_asset_id || r.dataset_name} style={{ display: "flex", alignItems: "flex-start", gap: "12px", padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600 }}>{r.name || formatDatasetLabel(r.dataset_name)}</div>
                        <div className="muted" style={{ fontSize: "0.82rem", marginTop: "2px" }}>
                          {r.latest_run_id
                            ? "Open the latest run to inspect validation and remediation context."
                            : "Upload first, then inspect the resulting run when it appears."}
                        </div>
                        {r.latest_run_id ? (
                          <div className="muted" style={{ fontSize: "0.82rem", marginTop: "4px" }}>
                            Latest run:{" "}
                            <Link className="inlineLink" href={`/runs/${r.latest_run_id}`}>
                              {r.latest_run_id}
                            </Link>
                          </div>
                        ) : null}
                      </div>
                      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                        {r.latest_run_id ? (
                          <Link className="ghostButton" href={`/runs/${r.latest_run_id}`}>
                            Inspect run
                          </Link>
                        ) : null}
                        <Link className="ghostButton" href={r.uploadPath}>
                          Upload
                        </Link>
                      </div>
                    </div>
                  );
                })}
            </div>
          )}
        </article>
      </section>
    </AppShell>
  );
}
