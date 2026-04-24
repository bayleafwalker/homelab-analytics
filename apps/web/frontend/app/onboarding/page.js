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
      .filter((ds) => ds.freshness_state === "current")
      .map((ds) => ds.dataset_name)
  );

  // Pick the worst freshness_state across all source assets for a given dataset_name.
  const freshnessStateByDataset = {};
  for (const ds of freshnessDatasets) {
    const prev = freshnessStateByDataset[ds.dataset_name];
    if (!prev || ds.freshness_state !== "current") {
      freshnessStateByDataset[ds.dataset_name] = ds.freshness_state;
    }
  }

  const onboardingRows = ONBOARDING_SOURCES.map((src) => ({
    ...src,
    status: freshDatasets.has(src.dataset) ? "active" : "pending",
    freshnessState: freshnessStateByDataset[src.dataset] ?? null,
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
                {onboardingRows.map((src) => {
                  const state = src.freshnessState;
                  let pillClass = "status-pending";
                  let pillLabel = src.required ? "needed" : "optional";
                  if (state === "current") {
                    pillClass = "status-landed";
                    pillLabel = "active";
                  } else if (state === "overdue" || state === "missing_period" || state === "parse_failed") {
                    pillClass = "status-failed";
                    pillLabel = state === "overdue" ? "overdue" : state === "missing_period" ? "missing" : "failed";
                  } else if (state === "due_soon") {
                    pillClass = "status-warning";
                    pillLabel = "due soon";
                  }
                  return (
                    <tr key={src.dataset}>
                      <td>{src.label}</td>
                      <td>{src.unlocks}</td>
                      <td>
                        <span className={`statusPill ${pillClass}`}>{pillLabel}</span>
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
