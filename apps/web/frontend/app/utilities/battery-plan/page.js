import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import {
  getBatteryPlanOutcome,
  getCurrentUser,
  getDecisionRecords
} from "@/lib/backend";

const DECISION_KEY = "kotiakku_battery_plan_review";

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

function noticeCopy(notice) {
  switch (notice) {
    case "decision-recorded":
      return "Decision recorded against the published evidence.";
    case "follow-up-recorded":
      return "Follow-up observation recorded.";
    default:
      return "";
  }
}

function errorCopy(error) {
  switch (error) {
    case "decision-failed":
      return "Could not record the decision. Insufficient evidence must be acknowledged, and a changed publication must be reviewed again.";
    case "follow-up-failed":
      return "Could not record the follow-up. Check the observation time, evidence effect and value status.";
    default:
      return "";
  }
}

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

function DecisionForm({ outcome, decision }) {
  const reasonCodes = parseJson(outcome.reason_codes_json, []);
  return (
    <form className="stack" action="/utilities/battery-plan/decisions" method="post">
      <input name="decision_key" type="hidden" value={DECISION_KEY} />
      <input name="subject_period" type="hidden" value={outcome.decision_month} />
      <input name="subject_row_ref" type="hidden" value={outcome.assessment_id} />
      <div className="formGrid">
        <div className="field">
          <label htmlFor="decision-outcome">Decision</label>
          <select id="decision-outcome" name="outcome" required>
            {(decision?.outcome_options || []).map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="decision-follow-up">Follow-up due</label>
          <input id="decision-follow-up" name="follow_up_due_on" type="date" />
        </div>
        <div className="field spanTwo">
          <label htmlFor="decision-rationale">
            Rationale <span className="muted">(required)</span>
          </label>
          <textarea id="decision-rationale" name="rationale" rows={3} required />
        </div>
        <div className="field spanTwo">
          <label htmlFor="decision-uncertainty">Uncertainty</label>
          <input id="decision-uncertainty" name="uncertainty" type="text" />
        </div>
      </div>
      {reasonCodes.length > 0 ? (
        <fieldset className="stack">
          <legend>Acknowledge evidence gaps (required for insufficient evidence)</legend>
          {reasonCodes.map((code) => (
            <label key={code}>
              <input name="evidence_gaps_acknowledged" type="checkbox" value={code} /> {code}
            </label>
          ))}
        </fieldset>
      ) : null}
      <p className="muted">
        Recording a decision authorizes nothing: tariff, contract or battery changes happen
        outside HLA, and any device action needs its own Home Assistant approval.
      </p>
      <div className="buttonRow">
        <button type="submit">Record decision</button>
      </div>
    </form>
  );
}

function FollowUpForm({ decisionRecord }) {
  return (
    <form
      className="stack"
      action={`/utilities/battery-plan/decisions/${decisionRecord.decision_id}/follow-ups`}
      method="post"
    >
      <div className="formGrid">
        <div className="field">
          <label htmlFor={`fu-observed-${decisionRecord.decision_id}`}>Observed at</label>
          <input
            id={`fu-observed-${decisionRecord.decision_id}`}
            name="observed_at"
            type="datetime-local"
            required
          />
        </div>
        <div className="field">
          <label htmlFor={`fu-effect-${decisionRecord.decision_id}`}>Evidence effect</label>
          <select id={`fu-effect-${decisionRecord.decision_id}`} name="evidence_effect" required>
            <option value="confirmed_decision">Confirmed the decision</option>
            <option value="changed_decision">Changed the decision</option>
            <option value="preserved_non_decision">Preserved a deliberate non-decision</option>
            <option value="exposed_source_defect">Exposed a source defect</option>
            <option value="exposed_model_defect">Exposed a model defect</option>
            <option value="inconclusive">Inconclusive</option>
          </select>
        </div>
        <div className="field spanTwo">
          <label htmlFor={`fu-result-${decisionRecord.decision_id}`}>Realized result</label>
          <textarea
            id={`fu-result-${decisionRecord.decision_id}`}
            name="realized_result"
            rows={2}
            required
          />
        </div>
        <div className="field">
          <label htmlFor={`fu-value-${decisionRecord.decision_id}`}>Realized value (EUR)</label>
          <input
            id={`fu-value-${decisionRecord.decision_id}`}
            name="realized_value_eur"
            type="number"
            step="0.01"
          />
        </div>
        <div className="field">
          <label htmlFor={`fu-status-${decisionRecord.decision_id}`}>Value status</label>
          <select id={`fu-status-${decisionRecord.decision_id}`} name="realized_value_status">
            <option value="">—</option>
            <option value="observed">observed (bill, meter)</option>
            <option value="user_entered">user_entered</option>
          </select>
        </div>
      </div>
      <div className="buttonRow">
        <button className="ghostButton" type="submit">
          Record follow-up
        </button>
      </div>
    </form>
  );
}

export default async function BatteryPlanPage({ searchParams }) {
  const user = await getCurrentUser();
  const [outcome, decisionRecords] = await Promise.all([
    getBatteryPlanOutcome(searchParams?.decision_month || undefined),
    getDecisionRecords(DECISION_KEY)
  ]);
  const canDecide = user.role === "operator" || user.role === "admin";
  const decision = outcome.decision;
  const notice = noticeCopy(searchParams?.notice);
  const error = errorCopy(searchParams?.error);

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

        {decision ? (
          <article className="panel stack">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">
                  Decision {decision.decision_key} · v{decision.version}
                </div>
                <h2>{decision.question}</h2>
              </div>
            </div>
            <p className="muted">
              Decision-maker role: {decision.decision_maker_role}. Evidence window:{" "}
              {decision.evidence_window}
            </p>
            <details>
              <summary>What would count as insufficient evidence</summary>
              <ul>
                {decision.insufficient_evidence_criteria.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </details>
            <details>
              <summary>What evidence could change the decision</summary>
              <ul>
                {decision.evidence_that_could_change_decision.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </details>
            <p className="muted">{decision.authorization_boundary}</p>
          </article>
        ) : null}

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
                  <DecisionForm outcome={row} decision={decision} />
                </article>
              ) : null}
            </section>
          );
        })}

        <article className="panel stack">
          <div className="sectionHeader">
            <h2>Decision history</h2>
          </div>
          {decisionRecords.length === 0 ? (
            <div className="empty">No decision or non-decision has been recorded yet.</div>
          ) : (
            <div className="entityList">
              {decisionRecords.map((record) => (
                <article className="entityCard" key={record.decision_id}>
                  <div className="entityHeader">
                    <div>
                      <strong>{record.outcome}</strong>
                      <div className="muted">
                        {record.subject.period} · evidence {record.subject.verdict} · row{" "}
                        {record.subject.row_ref}
                      </div>
                    </div>
                    <div className="buttonRow">
                      {record.is_non_decision ? (
                        <span className="pill" data-tone="neutral">
                          non-decision
                        </span>
                      ) : null}
                      <span
                        className="pill"
                        data-tone={record.status === "followed_up" ? "ok" : "warm"}
                      >
                        {record.status}
                      </span>
                    </div>
                  </div>
                  <p>{record.rationale}</p>
                  <p className="muted">
                    By {record.actor.actor}
                    {record.actor.authenticated ? "" : " (identity disabled — unauthenticated)"} on{" "}
                    {record.created_at}; follow-up due {record.follow_up_due_on}.
                    {record.evidence_gaps_acknowledged.length > 0
                      ? ` Gaps acknowledged: ${record.evidence_gaps_acknowledged.join(", ")}.`
                      : ""}
                  </p>
                  {record.follow_ups.map((followUp) => (
                    <div className="muted" key={followUp.follow_up_id}>
                      Observed {followUp.observed_at}: {followUp.realized_result} (
                      {followUp.evidence_effect}
                      {followUp.realized_value_eur
                        ? `; realized ${followUp.realized_value_eur} EUR, ${followUp.realized_value_status}`
                        : ""}
                      )
                    </div>
                  ))}
                  {canDecide ? (
                    <details>
                      <summary>Record a follow-up observation</summary>
                      <FollowUpForm decisionRecord={record} />
                    </details>
                  ) : null}
                </article>
              ))}
            </div>
          )}
        </article>
      </section>
    </AppShell>
  );
}
