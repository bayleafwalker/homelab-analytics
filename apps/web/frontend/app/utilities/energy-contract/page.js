import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import {
  getCurrentUser,
  getDecisionRecords,
  getDecisionReviews,
  getDecisionSubjects
} from "@/lib/backend";

import {
  CommitmentTerms,
  DecisionForm,
  DecisionHistory,
  EvidenceTraceForm,
  decisionErrorCopy,
  decisionNoticeCopy
} from "../_decisions/decision-ledger";

const DECISION_KEY = "electricity_contract_keep_or_switch";
const BASE_PATH = "/utilities/energy-contract";

const VERDICT_COPY = {
  insufficient_evidence: {
    tone: "warn",
    label: "Insufficient evidence",
    detail: "No keep-or-switch estimate can be made from this evidence. Follow the remediation."
  },
  current_contract_competitive: {
    tone: "ok",
    label: "Current contract competitive",
    detail:
      "No recorded alternative is estimated more than 5% cheaper per year. An estimate, not realized cash."
  },
  alternative_estimated_cheaper: {
    tone: "warm",
    label: "Alternative estimated cheaper",
    detail:
      "A recorded alternative is estimated more than 5% cheaper per year for this usage. An estimate, not a switch instruction."
  }
};

function eur(value) {
  return value == null ? "missing" : `${value} EUR`;
}

function SubjectCard({ subject, decision, canDecide }) {
  const assessment = subject.snapshot?.assessment || {};
  const verdict = VERDICT_COPY[subject.verdict] || VERDICT_COPY.insufficient_evidence;
  const disclosures = assessment.value_disclosures || {};
  return (
    <section className="stack">
      <section className="cards">
        <article className="panel metricCard">
          <div className="metricLabel">
            {assessment.contract_name || subject.period} · {assessment.provider || "unknown"}
          </div>
          <div className="metricValue">
            <span className="pill" data-tone={verdict.tone}>
              {verdict.label}
            </span>
          </div>
          <div className="muted">{verdict.detail}</div>
        </article>
        <article className="panel metricCard">
          <div className="metricLabel">Estimated annual cost (current)</div>
          <div className="metricValue">{eur(assessment.estimated_annual_cost_current_eur)}</div>
          <div className="muted">
            Energy {assessment.energy_unit_price ?? "missing"} {assessment.currency}/
            {assessment.quantity_unit || "unit"} + base fee {assessment.monthly_base_fee ?? "0"}
            /month ({disclosures.energy_unit_price}).
          </div>
        </article>
        <article className="panel metricCard">
          <div className="metricLabel">Best recorded alternative</div>
          <div className="metricValue">
            {eur(assessment.estimated_annual_cost_best_alternative_eur)}
          </div>
          <div className="muted">
            {assessment.best_alternative_provider || "none"} · difference{" "}
            {eur(assessment.estimated_annual_difference_eur)} per year (
            {disclosures.estimated_annual_difference_eur}).
          </div>
        </article>
        <article className="panel metricCard">
          <div className="metricLabel">Usage basis</div>
          <div className="metricValue">{assessment.usage_month_count ?? 0} months</div>
          <div className="muted">
            {assessment.usage_months_from || "—"} to {assessment.usage_months_to || "—"};{" "}
            {assessment.trailing_usage_amount ?? "missing"} kWh ({disclosures.trailing_usage_amount}
            ).
          </div>
        </article>
      </section>
      {assessment.remediation ? (
        <div className="errorBanner">
          <strong>Remediation.</strong> {assessment.remediation} (
          {subject.reason_codes.join(", ")})
        </div>
      ) : null}
      <article className="panel stack">
        <div className="sectionHeader">
          <h2>Limitations and lineage</h2>
        </div>
        <ul>
          {(assessment.limitations || []).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p className="muted">
          Review candidate: {assessment.review_candidate_reason || "not flagged"}; renewal{" "}
          {assessment.renewal_date
            ? `${assessment.renewal_date} (${assessment.days_until_renewal} days)`
            : "not within the watchlist"}
          . Assessment {subject.row_ref}; evidence fingerprint {subject.evidence_fingerprint};
          publications {(subject.lineage_reference?.publication_keys || []).join(", ")}.
        </p>
      </article>
      {canDecide && decision ? (
        <article className="panel stack">
          <div className="sectionHeader">
            <h2>Record a decision or explicit non-decision</h2>
          </div>
          <DecisionForm
            action={`${BASE_PATH}/decisions`}
            decision={decision}
            period={subject.period}
            rowRef={subject.row_ref}
            reasonCodes={subject.reason_codes}
          />
        </article>
      ) : null}
    </section>
  );
}

export default async function EnergyContractPage({ searchParams }) {
  const user = await getCurrentUser();
  const [evidence, decisionRecords, reviews] = await Promise.all([
    getDecisionSubjects(DECISION_KEY, searchParams?.contract_id || undefined),
    getDecisionRecords(DECISION_KEY),
    getDecisionReviews(DECISION_KEY)
  ]);
  const canDecide = user.role === "operator" || user.role === "admin";
  const decision = evidence.decision;
  const notice = decisionNoticeCopy(searchParams?.notice);
  const error = decisionErrorCopy(searchParams?.error);

  return (
    <AppShell
      currentPath="/utilities"
      user={user}
      title="Electricity Contract Review"
      eyebrow="Reader Access"
      lede="Whether the current electricity contract still costs no more per year than the alternatives you have recorded, for your own usage — with inputs, estimates and limitations disclosed. Nothing here can switch or cancel a contract."
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
            .
          </div>
        ) : null}

        <CommitmentTerms decision={decision} />

        {evidence.subjects.length === 0 ? (
          <div className="empty">
            No electricity contract is published. Land a contract price file with the current
            contract and at least one alternative offer, then refresh.
          </div>
        ) : null}
        {evidence.subjects.map((subject) => (
          <SubjectCard
            key={subject.period}
            subject={subject}
            decision={decision}
            canDecide={canDecide}
          />
        ))}

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
