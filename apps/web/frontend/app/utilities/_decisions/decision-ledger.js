/**
 * Shared decision-ledger UI for the decision pages under /utilities.
 *
 * Server components only: they render a declared decision's commitment
 * terms, the decision form, and each recorded decision's commitment
 * lifecycle (state, why it is active, what reopens or stops it, superseded
 * evidence, history) with follow-up / stop / reopen forms. Every form posts
 * to a route handler under the page (see ./handlers.js); none of them can
 * change a tariff, contract or device.
 */

const LIFECYCLE_COPY = {
  active: { tone: "ok", label: "Active" },
  review_due: { tone: "warm", label: "Review due" },
  review_required: { tone: "warn", label: "Review required" },
  stopped: { tone: "neutral", label: "Stopped" }
};

const EVIDENCE_COPY = {
  as_recorded: { tone: "ok", label: "Evidence as recorded" },
  insufficient: { tone: "warn", label: "Recorded on insufficient evidence" },
  superseded: { tone: "warn", label: "Evidence superseded" }
};

const SUCCESS_COPY = {
  met: { tone: "ok", label: "success measure met" },
  not_met: { tone: "warm", label: "success measure not met" },
  unmeasured: { tone: "neutral", label: "unmeasured" }
};

export function decisionNoticeCopy(notice) {
  switch (notice) {
    case "decision-recorded":
      return "Decision recorded against the published evidence.";
    case "follow-up-recorded":
      return "Follow-up observation recorded.";
    case "commitment-stopped":
      return "Commitment stopped. It no longer appears in the review queue; its history stays readable.";
    case "commitment-reopened":
      return "Commitment reopened.";
    case "evidence-traced":
      return "Evidence corrections traced. Decisions made on corrected evidence are marked superseded.";
    default:
      return "";
  }
}

export function decisionErrorCopy(error) {
  switch (error) {
    case "decision-failed":
      return "Could not record the decision. Insufficient evidence must be acknowledged, a changed publication must be reviewed again, and the follow-up date may not precede the observation window.";
    case "follow-up-failed":
      return "Could not record the follow-up. Check the observation time, evidence effect and value status.";
    case "stop-failed":
      return "Could not stop the commitment. Choose one of its stop conditions and give a reason.";
    case "reopen-failed":
      return "Could not reopen the commitment. Only a stopped commitment can be reopened.";
    case "trace-failed":
      return "Could not trace evidence corrections.";
    default:
      return "";
  }
}

function Pill({ copy, fallback }) {
  const entry = copy || fallback;
  return (
    <span className="pill" data-tone={entry.tone}>
      {entry.label}
    </span>
  );
}

export function CommitmentTerms({ decision }) {
  if (!decision) {
    return null;
  }
  const measure = decision.success_measure || {};
  const window = decision.observation_window || {};
  return (
    <article className="panel stack">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">
            Decision {decision.decision_key} · v{decision.version}
          </div>
          <h2>{decision.question}</h2>
        </div>
      </div>
      <p>
        <strong>Purpose.</strong> {decision.purpose}
      </p>
      <p className="muted">
        Owner: {decision.owner?.principal || `any ${decision.decision_maker_role}`} (
        {decision.owner?.description}). Evidence window: {decision.evidence_window}
      </p>
      <p className="muted">
        <strong>Baseline.</strong> {decision.baseline?.description}{" "}
        <strong>Success measure.</strong> {measure.description} ({measure.comparison}{" "}
        {measure.threshold} {measure.unit}). <strong>Observation window.</strong>{" "}
        {window.description}
      </p>
      <details>
        <summary>What would count as insufficient evidence</summary>
        <ul>
          {(decision.insufficient_evidence_criteria || []).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </details>
      <details>
        <summary>What evidence could change the decision (review triggers)</summary>
        <ul>
          {(decision.evidence_that_could_change_decision || []).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <ul>
          {(decision.review_triggers || []).map((trigger) => (
            <li key={trigger.key}>
              <code>{trigger.key}</code> ({trigger.kind}): {trigger.description}
            </li>
          ))}
        </ul>
      </details>
      <details>
        <summary>What stops the commitment</summary>
        <ul>
          {(decision.stop_conditions || []).map((condition) => (
            <li key={condition.key}>
              <code>{condition.key}</code>: {condition.description}
            </li>
          ))}
        </ul>
      </details>
      <p className="muted">{decision.authorization_boundary}</p>
    </article>
  );
}

export function DecisionForm({ action, decision, period, rowRef, reasonCodes, idSuffix }) {
  const suffix = idSuffix || period;
  return (
    <form className="stack" action={action} method="post">
      <input name="decision_key" type="hidden" value={decision.decision_key} />
      <input name="subject_period" type="hidden" value={period} />
      <input name="subject_row_ref" type="hidden" value={rowRef} />
      <div className="formGrid">
        <div className="field">
          <label htmlFor={`decision-outcome-${suffix}`}>Decision</label>
          <select id={`decision-outcome-${suffix}`} name="outcome" required>
            {(decision.outcome_options || []).map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`decision-follow-up-${suffix}`}>
            Review due <span className="muted">(default: after the observation window)</span>
          </label>
          <input id={`decision-follow-up-${suffix}`} name="follow_up_due_on" type="date" />
        </div>
        <div className="field spanTwo">
          <label htmlFor={`decision-rationale-${suffix}`}>
            Rationale <span className="muted">(required)</span>
          </label>
          <textarea id={`decision-rationale-${suffix}`} name="rationale" rows={3} required />
        </div>
        <div className="field spanTwo">
          <label htmlFor={`decision-uncertainty-${suffix}`}>Uncertainty</label>
          <input id={`decision-uncertainty-${suffix}`} name="uncertainty" type="text" />
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

function FollowUpForm({ basePath, record }) {
  const id = record.decision_id;
  const baselineValues = record.commitment?.baseline?.values || {};
  const baselineKeys = Object.keys(baselineValues).filter(
    (key) => baselineValues[key]?.value !== null && baselineValues[key]?.value !== undefined
  );
  return (
    <form className="stack" action={`${basePath}/decisions/${id}/follow-ups`} method="post">
      <div className="formGrid">
        <div className="field">
          <label htmlFor={`fu-observed-${id}`}>Observed at</label>
          <input id={`fu-observed-${id}`} name="observed_at" type="datetime-local" required />
        </div>
        <div className="field">
          <label htmlFor={`fu-effect-${id}`}>Evidence effect</label>
          <select id={`fu-effect-${id}`} name="evidence_effect" required>
            <option value="confirmed_decision">Confirmed the decision</option>
            <option value="changed_decision">Changed the decision</option>
            <option value="preserved_non_decision">Preserved a deliberate non-decision</option>
            <option value="exposed_source_defect">Exposed a source defect</option>
            <option value="exposed_model_defect">Exposed a model defect</option>
            <option value="inconclusive">Inconclusive</option>
          </select>
        </div>
        <div className="field spanTwo">
          <label htmlFor={`fu-result-${id}`}>Realized result</label>
          <textarea id={`fu-result-${id}`} name="realized_result" rows={2} required />
        </div>
        <div className="field">
          <label htmlFor={`fu-value-${id}`}>Realized value (EUR, success measure)</label>
          <input id={`fu-value-${id}`} name="realized_value_eur" type="number" step="0.01" />
        </div>
        <div className="field">
          <label htmlFor={`fu-status-${id}`}>Value status</label>
          <select id={`fu-status-${id}`} name="realized_value_status">
            <option value="">—</option>
            <option value="observed">observed (bill, meter)</option>
            <option value="user_entered">user_entered</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor={`fu-baseline-${id}`}>Compare with estimate</label>
          <select id={`fu-baseline-${id}`} name="baseline_value_key">
            <option value="">— no estimate</option>
            {baselineKeys.map((key) => (
              <option key={key} value={key}>
                {key} ({baselineValues[key].value} {baselineValues[key].unit || ""})
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`fu-attention-${id}`}>Your time on this review (minutes)</label>
          <input id={`fu-attention-${id}`} name="attention_minutes" type="number" min="0" step="1" />
        </div>
        <div className="field spanTwo">
          <label htmlFor={`fu-hypothesis-${id}`}>Attribution hypothesis</label>
          <textarea id={`fu-hypothesis-${id}`} name="attribution_hypothesis" rows={2} />
        </div>
        <div className="field">
          <label htmlFor={`fu-confounders-${id}`}>Confounders (one per line)</label>
          <textarea id={`fu-confounders-${id}`} name="confounders" rows={2} />
        </div>
        <div className="field">
          <label htmlFor={`fu-missing-${id}`}>Missing evidence (one per line)</label>
          <textarea id={`fu-missing-${id}`} name="missing_evidence" rows={2} />
        </div>
        <div className="field spanTwo">
          <label htmlFor={`fu-uncertainty-${id}`}>Uncertainty</label>
          <input id={`fu-uncertainty-${id}`} name="attribution_uncertainty" type="text" />
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

function AttributionReview({ followUp }) {
  const review = followUp.attribution_review;
  if (!review) {
    return null;
  }
  const attention = followUp.attention?.minutes;
  return (
    <ul>
      <li>
        Measured:{" "}
        {review.measured.value_eur !== null
          ? `${review.measured.value_eur} EUR (${review.measured.value_status})`
          : "not measured"}
        {" · "}Estimate:{" "}
        {review.estimated_baseline
          ? `${review.estimated_baseline.value_eur} EUR (estimated; ${review.estimated_baseline.basis})`
          : "none recorded"}
        {review.measured_minus_estimate_eur !== null
          ? ` · Measured minus estimate: ${review.measured_minus_estimate_eur} EUR (not a causal claim)`
          : ""}
      </li>
      {review.attribution_hypothesis ? <li>Hypothesis: {review.attribution_hypothesis}</li> : null}
      {review.confounders.length > 0 ? <li>Confounders: {review.confounders.join("; ")}</li> : null}
      {review.uncertainty ? <li>Uncertainty: {review.uncertainty}</li> : null}
      {review.missing_evidence.length > 0 ? (
        <li>Missing evidence: {review.missing_evidence.join("; ")}</li>
      ) : null}
      {review.not_recorded.length > 0 ? <li>Not recorded: {review.not_recorded.join(", ")}</li> : null}
      <li>Operator time: {attention !== null && attention !== undefined ? `${attention} min` : "not captured"}</li>
    </ul>
  );
}

function StopForm({ basePath, record }) {
  const id = record.decision_id;
  const conditions = record.commitment?.stop_conditions || [];
  return (
    <form className="stack" action={`${basePath}/decisions/${id}/stop`} method="post">
      <div className="formGrid">
        <div className="field">
          <label htmlFor={`stop-condition-${id}`}>Stop condition</label>
          <select id={`stop-condition-${id}`} name="stop_condition_key" required>
            {conditions.map((condition) => (
              <option key={condition.key} value={condition.key}>
                {condition.key}
              </option>
            ))}
          </select>
        </div>
        <div className="field spanTwo">
          <label htmlFor={`stop-reason-${id}`}>Reason</label>
          <input id={`stop-reason-${id}`} name="reason" type="text" required />
        </div>
      </div>
      <div className="buttonRow">
        <button className="ghostButton" type="submit">
          Stop commitment
        </button>
      </div>
    </form>
  );
}

function ReopenForm({ basePath, record }) {
  const id = record.decision_id;
  return (
    <form className="stack" action={`${basePath}/decisions/${id}/reopen`} method="post">
      <div className="field">
        <label htmlFor={`reopen-reason-${id}`}>Reason to reopen</label>
        <input id={`reopen-reason-${id}`} name="reason" type="text" required />
      </div>
      <div className="buttonRow">
        <button className="ghostButton" type="submit">
          Reopen commitment
        </button>
      </div>
    </form>
  );
}

function SupersededNotice({ superseded }) {
  if (!superseded) {
    return null;
  }
  return (
    <div className="errorBanner">
      <strong>Evidence superseded.</strong> A newer assessment{" "}
      <code>{superseded.superseding_row_ref}</code> replaced{" "}
      <code>{superseded.superseded_row_ref}</code>:{" "}
      {(superseded.correction_kinds || []).join(", ")} corrected (
      {(superseded.changed_components || []).join(", ")}). Affected publications:{" "}
      {(superseded.affected_publication_keys || []).join(", ")}. Verdict{" "}
      {superseded.verdict_before} → {superseded.verdict_after}. Traced {superseded.traced_at}.
      The original evidence snapshot stays on the record.
    </div>
  );
}

export function EvidenceTraceForm({ action }) {
  return (
    <form action={action} method="post">
      <button className="ghostButton" type="submit">
        Check for evidence corrections
      </button>
    </form>
  );
}

export function DecisionHistory({ records, canDecide, basePath }) {
  if (records.length === 0) {
    return <div className="empty">No decision or non-decision has been recorded yet.</div>;
  }
  return (
    <div className="entityList">
      {records.map((record) => {
        const lifecycle = record.lifecycle || {};
        const commitment = record.commitment;
        return (
          <article className="entityCard" key={record.decision_id}>
            <div className="entityHeader">
              <div>
                <strong>{record.outcome}</strong>
                <div className="muted">
                  {record.subject.period} · evidence {record.subject.verdict} · row{" "}
                  {record.subject.row_ref} · v{record.decision_version}
                </div>
              </div>
              <div className="buttonRow">
                {record.is_non_decision ? (
                  <span className="pill" data-tone="neutral">
                    non-decision
                  </span>
                ) : null}
                <Pill copy={LIFECYCLE_COPY[lifecycle.state]} fallback={LIFECYCLE_COPY.active} />
                <Pill
                  copy={EVIDENCE_COPY[lifecycle.evidence_status]}
                  fallback={EVIDENCE_COPY.as_recorded}
                />
              </div>
            </div>
            <p>{record.rationale}</p>
            <SupersededNotice superseded={lifecycle.superseded_by} />
            <ul className="muted">
              {(lifecycle.reasons || []).map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
            {commitment ? (
              <p className="muted">
                Observation window {commitment.observation_window.start} –{" "}
                {commitment.observation_window.end}; next review{" "}
                {lifecycle.next_review_due_on || "none (stopped)"}; owner{" "}
                {commitment.owner.verified ? "verified" : "not verified (identity disabled)"}.
              </p>
            ) : (
              <p className="muted">Recorded before commitment terms existed (v1.0.0).</p>
            )}
            <p className="muted">
              By {record.actor.actor}
              {record.actor.authenticated ? "" : " (identity disabled — unauthenticated)"} on{" "}
              {record.created_at}.
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
                ) <Pill copy={SUCCESS_COPY[followUp.success]} fallback={SUCCESS_COPY.unmeasured} />
                <AttributionReview followUp={followUp} />
              </div>
            ))}
            {record.history.length > 0 ? (
              <details>
                <summary>Commitment history</summary>
                <ul>
                  {record.history.map((event) => (
                    <li key={event.event_id}>
                      {event.occurred_at} · {event.event_kind} ({event.reason_code}):{" "}
                      {event.reason}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
            {canDecide ? (
              <details>
                <summary>Record a follow-up observation</summary>
                <FollowUpForm basePath={basePath} record={record} />
              </details>
            ) : null}
            {canDecide && commitment && lifecycle.state !== "stopped" ? (
              <details>
                <summary>Stop this commitment</summary>
                <StopForm basePath={basePath} record={record} />
              </details>
            ) : null}
            {canDecide && lifecycle.state === "stopped" ? (
              <details>
                <summary>Reopen this commitment</summary>
                <ReopenForm basePath={basePath} record={record} />
              </details>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
