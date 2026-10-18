import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import {
  getBatteryPlanOutcome,
  getCurrentUser,
  getDecisionRecords,
  getDecisionReviews
} from "@/lib/backend";

import {
  CommitmentTerms,
  DecisionForm,
  DecisionHistory,
  EvidenceTraceForm,
  decisionErrorCopy,
  decisionNoticeCopy
} from "../_decisions/decision-ledger";

const DECISION_KEY = "kotiakku_battery_plan_review";
const BASE_PATH = "/utilities/battery-plan";

const VERDICT_COPY = {
  insufficient_evidence: {
    tone: "warn",
    label: "Insufficient evidence",
    detail: "No savings claim can be made from this evidence. Follow the remediation below."
  },
  no_benefit_estimated: {
    tone: "warm",
    label: "No estimated benefit",
    detail:
      "Estimated savings stay below the effective monthly battery cost. This is a source estimate, not realized cash."
  },
  benefit_estimated: {
    tone: "ok",
    label: "Benefit estimated",
    detail:
      "Estimated savings cover the effective monthly battery cost. This is a source estimate, not realized cash, and not causal."
  }
};

const STATUS_TONES = {
  observed: "ok",
  derived: "cool",
  estimated: "warm",
  heuristic: "warn",
  user_entered: "accent"
};

const ROLE_SECTIONS = [
  { role: "actual", title: "Observed flows (actuals)" },
  { role: "estimate", title: "Estimates" },
  { role: "assumption", title: "Assumptions and user-entered inputs" },
  { role: "quality", title: "Evidence quality" }
];

function parseJson(value, fallback) {
  if (typeof value !== "string" || !value) {
    return fallback;
  }
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function formatValue(value) {
  if (value.is_missing) {
    return <span className="pill" data-tone="warn">missing</span>;
  }
  const shown = value.value_numeric ?? value.value_text;
  return `${shown}${value.unit ? ` ${value.unit}` : ""}`;
}

function ValuesTable({ values }) {
  if (values.length === 0) {
    return <div className="empty">No values in this group.</div>;
  }
  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Value</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Source</th>
            <th>Note</th>
          </tr>
        </thead>
        <tbody>
          {values.map((value) => (
            <tr key={value.value_key}>
              <td>{value.value_label}</td>
              <td>{formatValue(value)}</td>
              <td>
                <span className="pill" data-tone={STATUS_TONES[value.value_status] || "neutral"}>
                  {value.value_status}
                </span>
              </td>
              <td className="muted">{value.source_reference || "—"}</td>
              <td className="muted">{value.note || ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function BatteryPlanPage({ searchParams }) {
  const user = await getCurrentUser();
  const [outcome, decisionRecords, reviews] = await Promise.all([
    getBatteryPlanOutcome(searchParams?.decision_month || undefined),
    getDecisionRecords(DECISION_KEY),
    getDecisionReviews(DECISION_KEY)
  ]);
  const canDecide = user.role === "operator" || user.role === "admin";
  const decision = outcome.decision;
  const notice = decisionNoticeCopy(searchParams?.notice);
  const error = decisionErrorCopy(searchParams?.error);

  return (
    <AppShell
      currentPath="/utilities"
      user={user}
      title="Battery Plan Outcome"
      eyebrow="Reader Access"
      lede="Whether observed Kotiakku battery economics justify reviewing the battery plan, tariff or contract — with every value's source, status and limitation disclosed. Estimates are not realized cash, and nothing here can actuate the battery."
    >
      <section className="stack">
        <div className="buttonRow">
          <Link className="ghostButton" href="/utilities">
            Back to utilities
          </Link>
        </div>
        {notice ? <div className="successBanner">{notice}</div> : null}
        {error ? <div className="errorBanner">{error}</div> : null}
        {reviews.length > 0 ? (
          <div className="errorBanner">
            <strong>Reviews waiting.</strong>{" "}
            {reviews
              .map((review) => `${review.subject_period}: ${review.state.replace("_", " ")}`)
              .join("; ")}
            . Superseded evidence and closed observation windows are listed in the decision
            history below.
          </div>
        ) : null}

        <CommitmentTerms decision={decision} />

        {outcome.rows.length === 0 ? (
          <div className="empty">
            No battery-plan outcome has been published yet. Run the worker command
            refresh-battery-plan-outcome after Home Assistant history is ingested.
          </div>
        ) : null}

        {outcome.rows.map((row) => {
          const verdict = VERDICT_COPY[row.verdict] || VERDICT_COPY.insufficient_evidence;
          const reasonCodes = parseJson(row.reason_codes_json, []);
          const limitations = parseJson(row.limitations_json, []);
          const runIds = parseJson(row.source_run_ids_json, []);
          const entityIds = parseJson(row.source_entity_ids_json, {});
          const tariff = parseJson(row.tariff_snapshot_json, null);
          const values = outcome.values.filter(
            (value) => value.assessment_id === row.assessment_id
          );
          return (
            <section className="stack" key={row.assessment_id}>
              <section className="cards">
                <article className="panel metricCard">
                  <div className="metricLabel">Verdict · {row.decision_month}</div>
                  <div className="metricValue">
                    <span className="pill" data-tone={verdict.tone}>
                      {verdict.label}
                    </span>
                  </div>
                  <div className="muted">{verdict.detail}</div>
                </article>
                <article className="panel metricCard">
                  <div className="metricLabel">Coverage</div>
                  <div className="metricValue">{Number(row.coverage_pct)}%</div>
                  <div className="muted">
                    {row.complete_window_count} of {row.expected_window_count} five-minute
                    windows complete; {row.missing_window_count} missing,{" "}
                    {row.conflicting_window_count} conflicting.
                  </div>
                </article>
                <article className="panel metricCard">
                  <div className="metricLabel">Freshness</div>
                  <div className="metricValue">
                    <span
                      className="pill"
                      data-tone={row.freshness_status === "fresh" ? "ok" : "warn"}
                    >
                      {row.freshness_status}
                    </span>
                  </div>
                  <div className="muted">
                    Source age {row.freshness_age_minutes ?? "unknown"} min (limit{" "}
                    {row.freshness_limit_minutes} min). Backfill: {row.backfill_status}.
                  </div>
                </article>
                <article className="panel metricCard">
                  <div className="metricLabel">Estimated net benefit</div>
                  <div className="metricValue">
                    {row.estimated_net_benefit_eur == null
                      ? "missing"
                      : `${row.estimated_net_benefit_eur} EUR`}
                  </div>
                  <div className="muted">
                    Estimate {row.estimated_savings_eur ?? "missing"} EUR minus cost{" "}
                    {row.effective_monthly_cost_eur ?? "missing"} EUR ({row.claim_basis}).
                  </div>
                </article>
              </section>

              {row.remediation ? (
                <div className="errorBanner">
                  <strong>Remediation.</strong> {row.remediation}
                  {reasonCodes.length > 0 ? ` (${reasonCodes.join(", ")})` : ""}
                </div>
              ) : null}

              {ROLE_SECTIONS.map((section) => (
                <article className="panel stack" key={section.role}>
                  <div className="sectionHeader">
                    <h2>{section.title}</h2>
                  </div>
                  <ValuesTable
                    values={values.filter((value) => value.value_role === section.role)}
                  />
                </article>
              ))}

              <article className="panel stack">
                <div className="sectionHeader">
                  <h2>Tariff assumptions, limitations and lineage</h2>
                </div>
                <p className="muted">
                  Tariff snapshot {row.tariff_snapshot_id || "missing"}
                  {tariff ? `: ${JSON.stringify(tariff)}` : ""}. Calculation{" "}
                  {row.source_calculation_method || "unknown"}, evidence contract{" "}
                  {row.source_evidence_contract_version || "unknown"}.
                </p>
                <ul>
                  {limitations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <p className="muted">
                  Assessment {row.assessment_id} at {row.assessed_at}; source runs{" "}
                  {runIds.join(", ") || "none"}; publications{" "}
                  {outcome.publicationKeys.join(", ")}.
                </p>
                <details>
                  <summary>Source entity mapping</summary>
                  <ul>
                    {Object.entries(entityIds).map(([field, entityId]) => (
                      <li key={field}>
                        {field}: {String(entityId)}
                      </li>
                    ))}
                  </ul>
                </details>
              </article>

              {canDecide ? (
                <article className="panel stack">
                  <div className="sectionHeader">
                    <h2>Record a decision or explicit non-decision</h2>
                  </div>
                  <DecisionForm
                    action={`${BASE_PATH}/decisions`}
                    decision={decision}
                    period={row.decision_month}
                    rowRef={row.assessment_id}
                    reasonCodes={reasonCodes}
                  />
                </article>
              ) : null}
            </section>
          );
        })}

        <article className="panel stack">
          <div className="sectionHeader">
            <h2>Decision history</h2>
          </div>
          {canDecide ? <EvidenceTraceForm action={`${BASE_PATH}/evidence-trace`} /> : null}
          <DecisionHistory records={decisionRecords} canDecide={canDecide} basePath={BASE_PATH} />
        </article>
      </section>
    </AppShell>
  );
}
