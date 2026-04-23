import Link from "next/link";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { getCurrentUser, getSourceFreshness, getRuns } from "@/lib/backend";
import { ONBOARDING_SOURCES } from "@/lib/onboarding-sources";

const BUILTIN_UPLOAD_PATH = {
  account_transactions: "/upload/account-transactions",
  subscriptions: "/upload/subscriptions",
  contract_prices: "/upload/contract-prices",
  budgets: "/upload/budgets",
  loan_repayments: "/upload/loan-repayments",
};

function stalenessLabel(landedAt) {
  if (!landedAt) return { label: "Never loaded", color: "var(--error)", indicator: "red" };
  const now = new Date();
  const then = new Date(landedAt);
  const diffDays = (now - then) / (1000 * 60 * 60 * 24);
  if (diffDays < 2)  return { label: "Fresh", color: "var(--ok)", indicator: "green" };
  if (diffDays < 7)  return { label: `${Math.floor(diffDays)}d ago`, color: "var(--warning)", indicator: "yellow" };
  return { label: `${Math.floor(diffDays)}d ago — stale`, color: "var(--error)", indicator: "red" };
}

function formatDatasetLabel(datasetName) {
  return datasetName
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function remediationActions(dataset, status, uploadPath) {
  const actions = [];
  if (status === "rejected" || status === "failed") {
    actions.push({ label: "Open failed run", kind: "run" });
  }
  if (uploadPath) {
    actions.push({ label: "Upload new file", kind: "upload", href: uploadPath });
  }
  if (!uploadPath) {
    actions.push({ label: "Review schedule", kind: "schedule", href: "/control/execution" });
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

  // Build last-run-per-dataset for run status details
  const lastRunByDataset = {};
  for (const run of recentRuns) {
    const ds = run.dataset_name;
    if (!ds) continue;
    if (!lastRunByDataset[ds] || run.created_at > lastRunByDataset[ds].created_at) {
      lastRunByDataset[ds] = run;
    }
  }

  // Merge freshness API data with run details
  const rows = freshnessDatasets.map((ds) => {
    const lastRun = lastRunByDataset[ds.dataset_name];
    const uploadPath = BUILTIN_UPLOAD_PATH[ds.dataset_name] || null;
    const staleness = stalenessLabel(ds.landed_at);
    const actions = remediationActions(ds.dataset_name, ds.status, uploadPath);
    return { ...ds, lastRun, uploadPath, staleness, actions };
  });

  // Sort: stale/never first, then by dataset name
  rows.sort((a, b) => {
    const order = { red: 0, yellow: 1, green: 2 };
    const aOrd = order[a.staleness.indicator] ?? 3;
    const bOrd = order[b.staleness.indicator] ?? 3;
    if (aOrd !== bOrd) return aOrd - bOrd;
    return a.dataset_name.localeCompare(b.dataset_name);
  });

  const staleCount = rows.filter((r) => r.staleness.indicator === "red").length;
  const warnCount = rows.filter((r) => r.staleness.indicator === "yellow").length;

  // Recovery preview: map each dataset to the publications it unlocks
  const recoveryPreviewByDataset = Object.fromEntries(
    ONBOARDING_SOURCES.map((s) => [s.dataset, s.unlocksDetail || []])
  );

  return (
    <AppShell
      currentPath="/sources"
      user={user}
      title="Data Sources"
      eyebrow="Operator Access"
      lede="Freshness and remediation for all active data sources. Upload directly from this view to recover stale or failed datasets."
    >
      <section className="stack">
        <section className="cards">
          <article className="panel metricCard">
            <div className="metricLabel">Total sources</div>
            <div className="metricValue">{rows.length}</div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Stale / never loaded</div>
            <div className="metricValue" style={{ color: staleCount > 0 ? "var(--error)" : "var(--ok)" }}>
              {staleCount}
            </div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Getting stale</div>
            <div className="metricValue" style={{ color: warnCount > 0 ? "var(--warning)" : "var(--ok)" }}>
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
            <Link className="ghostButton" href="/upload">
              Bulk upload
            </Link>
          </div>
          {rows.length === 0 ? (
            <div className="empty">No source freshness data available. Run an ingestion first.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Dataset</th>
                    <th>Last ingested</th>
                    <th>Run status</th>
                    <th>Source</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.dataset_name}>
                      <td>
                        <span
                          title={row.staleness.label}
                          style={{
                            display: "inline-block",
                            width: "10px",
                            height: "10px",
                            borderRadius: "50%",
                            background: row.staleness.color,
                          }}
                        />
                        <span className="muted" style={{ marginLeft: "6px", fontSize: "0.82rem" }}>
                          {row.staleness.label}
                        </span>
                      </td>
                      <td>{formatDatasetLabel(row.dataset_name)}</td>
                      <td>
                        {row.latest_run_id ? (
                          <Link className="inlineLink" href={`/runs/${row.latest_run_id}`}>
                            {row.landed_at ? new Date(row.landed_at).toLocaleDateString() : row.latest_run_id}
                          </Link>
                        ) : (
                          <span className="muted">Never</span>
                        )}
                      </td>
                      <td>
                        {row.status ? (
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
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>
                        <span className="muted">
                          {row.lastRun?.source_name || "—"}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                          {row.actions.map((action) => (
                            action.kind === "run" && row.latest_run_id ? (
                              <Link
                                key={action.label}
                                className="inlineLink"
                                href={`/runs/${row.latest_run_id}`}
                              >
                                {action.label}
                              </Link>
                            ) : action.href ? (
                              <Link
                                key={action.label}
                                className="inlineLink"
                                href={action.href}
                              >
                                {action.label}
                              </Link>
                            ) : null
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Recovery</div>
              <h2>Upload in context</h2>
            </div>
          </div>
          <div className="muted" style={{ marginBottom: "12px" }}>
            Upload a new file directly for a stale or failed dataset. The detection wizard on the
            upload page will identify the target and validate before ingestion.
          </div>
          {rows.filter((r) => r.uploadPath && r.staleness.indicator !== "green").length === 0 ? (
            <div className="muted">All uploadable sources are fresh.</div>
          ) : (
            <div className="stack compactStack">
              {rows
                .filter((r) => r.uploadPath && r.staleness.indicator !== "green")
                .map((r) => {
                  const preview = recoveryPreviewByDataset[r.dataset_name] || [];
                  return (
                    <div key={r.dataset_name} style={{ display: "flex", alignItems: "flex-start", gap: "12px", padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600 }}>{formatDatasetLabel(r.dataset_name)}</div>
                        {preview.length > 0 && (
                          <div className="muted" style={{ fontSize: "0.82rem", marginTop: "2px" }}>
                            Refreshing unlocks: {preview.join(" · ")}
                          </div>
                        )}
                      </div>
                      <Link className="ghostButton" href={r.uploadPath}>
                        Upload
                      </Link>
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
