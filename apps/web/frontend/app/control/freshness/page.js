import Link from "next/link";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ControlNav } from "@/components/control-nav";
import { getCurrentUser, getRuns } from "@/lib/backend";

const BUILTIN_DATASETS = [
  { dataset: "account_transactions", label: "Account transactions", uploadPath: "/upload/account-transactions" },
  { dataset: "subscriptions", label: "Subscriptions", uploadPath: "/upload/subscriptions" },
  { dataset: "contract_prices", label: "Contract prices", uploadPath: "/upload/contract-prices" },
  { dataset: "utility_usage", label: "Utility usage", uploadPath: null },
  { dataset: "utility_bills", label: "Utility bills", uploadPath: null },
  { dataset: "budgets", label: "Budgets", uploadPath: "/upload/budgets" },
  { dataset: "loan_repayments", label: "Loan repayments", uploadPath: "/upload/loan-repayments" },
];

function stalenessLabel(lastRunAt) {
  if (!lastRunAt) return { label: "Never loaded", color: "var(--error)", indicator: "red" };
  const now = new Date();
  const then = new Date(lastRunAt);
  const diffDays = (now - then) / (1000 * 60 * 60 * 24);
  if (diffDays < 2)  return { label: "Fresh", color: "var(--ok)", indicator: "green" };
  if (diffDays < 7)  return { label: `${Math.floor(diffDays)}d ago`, color: "var(--warning)", indicator: "yellow" };
  return { label: `${Math.floor(diffDays)}d ago — stale`, color: "var(--error)", indicator: "red" };
}

function nextActionFor(lastRun, uploadPath) {
  if (!lastRun) {
    return {
      label: uploadPath ? "Upload first file" : "Set up source",
      href: uploadPath || "/control/catalog",
    };
  }

  if (lastRun.status === "rejected" || lastRun.status === "failed") {
    return {
      label: "Open failed run",
      href: `/runs/${lastRun.run_id}`,
    };
  }

  if (uploadPath) {
    return {
      label: "Upload next export",
      href: uploadPath,
    };
  }

  return {
    label: "Review schedule",
    href: "/control/execution",
  };
}

export default async function FreshnessPage() {
  const user = await getCurrentUser();
  if (user.role === "reader") {
    redirect("/");
  }

  // Fetch recent runs (large limit to get latest per dataset)
  const runs = await getRuns(200);

  // Build last-run-per-dataset map
  const lastRunByDataset = {};
  for (const run of runs) {
    const ds = run.dataset_name;
    if (!ds) continue;
    if (!lastRunByDataset[ds] || run.created_at > lastRunByDataset[ds].created_at) {
      lastRunByDataset[ds] = run;
    }
  }

  return (
    <AppShell
      currentPath="/control"
      user={user}
      title="Source freshness"
      eyebrow="Operator Access"
      lede="Staleness indicators for all built-in data sources. Green = ingested within 48h, yellow = within 7d, red = stale or never loaded."
    >
      <section className="stack">
        <ControlNav currentPath="/control" />

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Data Sources</div>
              <h2>Ingestion freshness</h2>
            </div>
          </div>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Dataset</th>
                  <th>Last run</th>
                  <th>Run status</th>
                  <th>Source</th>
                  <th>Next action</th>
                </tr>
              </thead>
              <tbody>
                {BUILTIN_DATASETS.map(({ dataset, label, uploadPath }) => {
                  const last = lastRunByDataset[dataset];
                  const { label: staleLabel, color, indicator } = stalenessLabel(last?.created_at);
                  const nextAction = nextActionFor(last, uploadPath);
                  return (
                    <tr key={dataset}>
                      <td>
                        <span
                          style={{
                            display: "inline-block",
                            width: "10px",
                            height: "10px",
                            borderRadius: "50%",
                            background: color,
                          }}
                          title={staleLabel}
                        />
                      </td>
                      <td>{label}</td>
                      <td>
                        {last ? (
                          <Link className="inlineLink" href={`/runs/${last.run_id}`}>
                            {last.created_at}
                          </Link>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>
                        {last ? (
                          <span
                            className={`statusPill ${
                              last.status === "landed" || last.status === "promoted"
                                ? "status-landed"
                                : last.status === "rejected"
                                ? "status-rejected"
                                : "status-pending"
                            }`}
                          >
                            {last.status}
                          </span>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>
                        <span className="muted">{last?.source_name || "—"}</span>
                      </td>
                      <td>
                        <Link className="inlineLink" href={nextAction.href}>
                          {nextAction.label}
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </AppShell>
  );
}
