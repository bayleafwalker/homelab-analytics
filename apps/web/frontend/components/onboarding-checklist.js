"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";

const DISMISS_KEY = "onboarding_checklist_dismissed";

const SOURCE_STEPS = [
  {
    dataset: "account_transactions",
    label: "Account transactions",
    description: "Cashflow, categories, anomalies",
    uploadPath: "/upload/account-transactions",
    required: true,
  },
  {
    dataset: "subscriptions",
    label: "Subscriptions",
    description: "Recurring cost baseline",
    uploadPath: "/upload/subscriptions",
    required: true,
  },
  {
    dataset: "contract_prices",
    label: "Contract prices",
    description: "Affordability ratios, contract watchlist",
    uploadPath: "/upload/contract-prices",
    required: false,
  },
  {
    dataset: "budgets",
    label: "Budgets",
    description: "Budget variance, envelopes",
    uploadPath: "/upload/budgets",
    required: false,
  },
  {
    dataset: "loan_repayments",
    label: "Loan repayments",
    description: "Debt service ratio, loan schedule",
    uploadPath: "/upload/loan-repayments",
    required: false,
  },
];

/** @param {{ freshDatasets: string[], nextSuggestion: {dataset: string, label: string, uploadPath: string} | null }} props */
export function OnboardingChecklist({ freshDatasets, nextSuggestion }) {
  const [dismissed, setDismissed] = useState(false);
  const [compact, setCompact] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      const val = localStorage.getItem(DISMISS_KEY);
      if (val === "dismissed") setDismissed(true);
      if (val === "compact") setCompact(true);
    } catch {
      // localStorage not available
    }
  }, []);

  function dismiss() {
    try {
      localStorage.setItem(DISMISS_KEY, "dismissed");
    } catch {
      // ignore
    }
    setDismissed(true);
  }

  function collapseToCompact() {
    try {
      localStorage.setItem(DISMISS_KEY, "compact");
    } catch {
      // ignore
    }
    setCompact(true);
  }

  function expand() {
    try {
      localStorage.removeItem(DISMISS_KEY);
    } catch {
      // ignore
    }
    setCompact(false);
    setDismissed(false);
  }

  // Avoid hydration mismatch by not rendering until mounted
  if (!mounted) return null;
  if (dismissed) return null;

  const steps = SOURCE_STEPS.map((s) => ({
    ...s,
    active: freshDatasets.includes(s.dataset),
  }));
  const activeCount = steps.filter((s) => s.active).length;
  const requiredDone = steps.filter((s) => s.required && s.active).length;
  const requiredTotal = steps.filter((s) => s.required).length;
  const allCoreActive = requiredDone >= requiredTotal;
  const allActive = activeCount >= steps.length;

  // Compact badge: show when all core sources are active
  if (compact || allCoreActive) {
    return (
      <article className="panel section" style={{ padding: "10px 16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span
            style={{
              display: "inline-block",
              width: "10px",
              height: "10px",
              borderRadius: "50%",
              background: allActive ? "var(--ok)" : "var(--warning)",
              flexShrink: 0,
            }}
          />
          <span className="muted" style={{ fontSize: "0.85rem" }}>
            Onboarding: {activeCount}/{steps.length} sources active
            {allCoreActive && " — core sources ready"}
          </span>
          <button
            className="ghostButton"
            style={{ marginLeft: "auto", fontSize: "0.8rem", padding: "2px 8px" }}
            onClick={expand}
          >
            Expand
          </button>
          <button
            className="ghostButton"
            style={{ fontSize: "0.8rem", padding: "2px 8px" }}
            onClick={dismiss}
            aria-label="Dismiss onboarding checklist"
          >
            ✕
          </button>
        </div>
      </article>
    );
  }

  return (
    <article className="panel section">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">Onboarding</div>
          <h2>Get started — connect your data sources</h2>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            className="ghostButton"
            onClick={collapseToCompact}
            title="Collapse to badge"
          >
            Minimise
          </button>
          <button
            className="ghostButton"
            onClick={dismiss}
            aria-label="Dismiss onboarding checklist"
          >
            Dismiss
          </button>
        </div>
      </div>

      <div style={{ display: "flex", gap: "8px", marginBottom: "12px", flexWrap: "wrap" }}>
        <span className="muted" style={{ fontSize: "0.85rem" }}>
          {activeCount} of {steps.length} sources active
        </span>
        <span className="muted" style={{ fontSize: "0.85rem" }}>·</span>
        <span className="muted" style={{ fontSize: "0.85rem" }}>
          {requiredDone}/{requiredTotal} core sources ready
        </span>
      </div>

      <div className="stack compactStack">
        {steps.map((step) => (
          <div
            key={step.dataset}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "10px",
              padding: "8px 0",
              borderBottom: "1px solid var(--border)",
              opacity: step.active ? 0.7 : 1,
            }}
          >
            <span
              style={{
                display: "inline-block",
                width: "12px",
                height: "12px",
                borderRadius: "50%",
                background: step.active ? "var(--ok)" : "var(--muted-text)",
                flexShrink: 0,
                marginTop: "3px",
              }}
            />
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <strong style={{ textDecoration: step.active ? "line-through" : "none" }}>
                  {step.label}
                </strong>
                {step.required && !step.active && (
                  <span className="statusPill status-pending" style={{ fontSize: "0.7rem" }}>
                    required
                  </span>
                )}
                {step.active && (
                  <span className="statusPill status-landed" style={{ fontSize: "0.7rem" }}>
                    active
                  </span>
                )}
              </div>
              <div className="muted" style={{ fontSize: "0.82rem" }}>
                {step.description}
              </div>
            </div>
            {!step.active && (
              <Link className="ghostButton" href={step.uploadPath} style={{ fontSize: "0.82rem" }}>
                Upload
              </Link>
            )}
          </div>
        ))}
      </div>

      {nextSuggestion && (
        <div style={{ marginTop: "12px", padding: "10px", background: "var(--surface-alt, var(--panel-bg))", borderRadius: "4px" }}>
          <div className="metricLabel" style={{ marginBottom: "4px" }}>Suggested next source</div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{ flex: 1 }}>
              <strong>{nextSuggestion.label}</strong>
            </div>
            <Link className="primaryButton inlineButton" href={nextSuggestion.uploadPath} style={{ fontSize: "0.82rem" }}>
              Upload now
            </Link>
          </div>
        </div>
      )}

      <div style={{ marginTop: "12px" }}>
        <Link className="inlineLink" href="/onboarding">
          Full onboarding guide
        </Link>
      </div>
    </article>
  );
}
