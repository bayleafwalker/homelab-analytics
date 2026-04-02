import Link from "next/link";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { UploadDetectionWizard } from "@/components/upload-detection-wizard";
import { getCurrentUser, getSourceAssets, getSourceFreshness } from "@/lib/backend";
import { ONBOARDING_SOURCES } from "@/lib/onboarding-sources";

export default async function OnboardingPage() {
  const user = await getCurrentUser();
  if (user.role === "reader") {
    redirect("/");
  }

  const [sourceAssets, freshnessDatasets] = await Promise.all([
    getSourceAssets({ includeArchived: false }),
    getSourceFreshness(),
  ]);

  const activeSourceAssets = sourceAssets.filter(
    (record) => record.enabled && !record.archived
  );

  const freshDatasets = new Set(
    freshnessDatasets
      .filter((ds) => {
        if (!ds.landed_at) return false;
        const diffDays = (Date.now() - new Date(ds.landed_at)) / (1000 * 60 * 60 * 24);
        return diffDays < 7;
      })
      .map((ds) => ds.dataset_name)
  );

  const onboardingRows = ONBOARDING_SOURCES.map((src) => ({
    ...src,
    status: freshDatasets.has(src.dataset) ? "active" : "pending",
  }));

  const activeCount = onboardingRows.filter((r) => r.status === "active").length;
  const requiredCount = onboardingRows.filter((r) => r.required).length;
  const activeRequiredCount = onboardingRows.filter((r) => r.required && r.status === "active").length;
  const allCoreActive = activeRequiredCount >= requiredCount;

  return (
    <AppShell
      currentPath="/onboarding"
      user={user}
      title="Onboarding"
      eyebrow="Operator Access"
      lede="Get your data sources connected. Upload your first files here to populate the operating picture. The detection wizard identifies the file type and validates before ingestion."
    >
      <section className="stack">
        <section className="cards">
          <article className="panel metricCard">
            <div className="metricLabel">Sources active</div>
            <div
              className="metricValue"
              style={{ color: activeCount > 0 ? "var(--ok)" : "var(--error)" }}
            >
              {activeCount} / {onboardingRows.length}
            </div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Core sources ready</div>
            <div
              className="metricValue"
              style={{ color: allCoreActive ? "var(--ok)" : "var(--warning)" }}
            >
              {activeRequiredCount} / {requiredCount}
            </div>
          </article>
          <article className="panel metricCard">
            <div className="metricLabel">Operating picture</div>
            <div
              className="metricValue"
              style={{ color: allCoreActive ? "var(--ok)" : "var(--warning)" }}
            >
              {allCoreActive ? "Ready" : "Needs data"}
            </div>
          </article>
        </section>

        {allCoreActive ? (
          <article className="panel section">
            <div className="successBanner">
              Core sources are active. Your operating picture is populated.{" "}
              <Link className="inlineLink" href="/">
                View dashboard
              </Link>{" "}
              or{" "}
              <Link className="inlineLink" href="/sources">
                inspect source freshness.
              </Link>
            </div>
          </article>
        ) : null}

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Checklist</div>
              <h2>Source onboarding progress</h2>
            </div>
          </div>
          <div className="stack compactStack">
            {onboardingRows.map((src) => (
              <div
                key={src.dataset}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "12px",
                  padding: "12px 0",
                  borderBottom: "1px solid var(--border)",
                }}
              >
                <span
                  style={{
                    display: "inline-block",
                    width: "12px",
                    height: "12px",
                    borderRadius: "50%",
                    background: src.status === "active" ? "var(--ok)" : "var(--muted-text)",
                    flexShrink: 0,
                    marginTop: "4px",
                  }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <strong>{src.label}</strong>
                    {src.required && (
                      <span className="statusPill status-pending">required</span>
                    )}
                    {src.status === "active" && (
                      <span className="statusPill status-landed">active</span>
                    )}
                  </div>
                  <div className="muted" style={{ fontSize: "0.85rem", marginTop: "2px" }}>
                    {src.description}
                  </div>
                </div>
                {src.status !== "active" && (
                  <Link className="ghostButton" href={src.uploadPath}>
                    Upload
                  </Link>
                )}
                {src.status === "active" && (
                  <Link className="ghostButton" href={src.uploadPath}>
                    Refresh
                  </Link>
                )}
              </div>
            ))}
          </div>
        </article>

        <UploadDetectionWizard activeSourceAssets={activeSourceAssets} />

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">What each source unlocks</div>
              <h2>Progressive disclosure</h2>
            </div>
          </div>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Unlocks</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Account transactions</td>
                  <td>Monthly cashflow, category spend, anomalies, attention items</td>
                  <td>
                    <span className={`statusPill ${freshDatasets.has("account_transactions") ? "status-landed" : "status-pending"}`}>
                      {freshDatasets.has("account_transactions") ? "active" : "needed"}
                    </span>
                  </td>
                </tr>
                <tr>
                  <td>Subscriptions</td>
                  <td>Recurring cost baseline, subscription review, cost model</td>
                  <td>
                    <span className={`statusPill ${freshDatasets.has("subscriptions") ? "status-landed" : "status-pending"}`}>
                      {freshDatasets.has("subscriptions") ? "active" : "needed"}
                    </span>
                  </td>
                </tr>
                <tr>
                  <td>Contract prices</td>
                  <td>Affordability ratios, contract renewal watchlist, utility contracts</td>
                  <td>
                    <span className={`statusPill ${freshDatasets.has("contract_prices") ? "status-landed" : "status-pending"}`}>
                      {freshDatasets.has("contract_prices") ? "active" : "optional"}
                    </span>
                  </td>
                </tr>
                <tr>
                  <td>Budgets</td>
                  <td>Budget variance, envelope tracking, spend-vs-target</td>
                  <td>
                    <span className={`statusPill ${freshDatasets.has("budgets") ? "status-landed" : "status-pending"}`}>
                      {freshDatasets.has("budgets") ? "active" : "optional"}
                    </span>
                  </td>
                </tr>
                <tr>
                  <td>Loan repayments</td>
                  <td>Loan overview, debt service ratio, loan schedule</td>
                  <td>
                    <span className={`statusPill ${freshDatasets.has("loan_repayments") ? "status-landed" : "status-pending"}`}>
                      {freshDatasets.has("loan_repayments") ? "active" : "optional"}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </AppShell>
  );
}
