"use client";

import { useState } from "react";

import { COMPARISON_OPERATORS, comparisonPhrase } from "@/components/policy-rule-summary";

const RULE_KINDS = [
  {
    value: "publication_value_comparison",
    label: "Publication value",
    help: "Compare one numeric field of a publication against a threshold."
  },
  {
    value: "publication_freshness_comparison",
    label: "Publication freshness",
    help: "Compare how long ago a publication was assessed against a threshold in hours."
  },
  {
    value: "ha_helper_state_comparison",
    label: "Home Assistant helper state",
    help: "Compare a Home Assistant entity's state against an expected value."
  }
];

/**
 * Author or edit one policy.
 *
 * Template discipline is enforced here rather than described: required inputs
 * are marked and the submit is refused until they are supplied, the publication
 * and field pickers offer only what the API will accept, and the sentence the
 * rule will actually evaluate is shown back before it is saved.
 */
export function PolicyForm({
  publications,
  ruleSchemaVersion,
  policy = null,
  action,
  submitLabel = "Create policy"
}) {
  const existingRule = policy?.rule_document || {};
  const [ruleKind, setRuleKind] = useState(
    existingRule.rule_kind || RULE_KINDS[0].value
  );
  const [publicationKey, setPublicationKey] = useState(
    existingRule.publication_key || ""
  );
  const [fieldName, setFieldName] = useState(existingRule.field_name || "");
  const [operator, setOperator] = useState(existingRule.operator || "gt");
  const [threshold, setThreshold] = useState(
    existingRule.threshold !== undefined ? String(existingRule.threshold) : ""
  );
  const [thresholdHours, setThresholdHours] = useState(
    existingRule.threshold_hours !== undefined
      ? String(existingRule.threshold_hours)
      : ""
  );
  const [entityId, setEntityId] = useState(existingRule.entity_id || "");
  const [expectedValue, setExpectedValue] = useState(
    existingRule.expected_value !== undefined ? String(existingRule.expected_value) : ""
  );
  const [displayName, setDisplayName] = useState(policy?.display_name || "");

  const selectedPublication = publications.find(
    (publication) => publication.publication_key === publicationKey
  );
  // Only numerically-readable columns can be threshold-compared. Offering the
  // others would author a rule that always evaluates unavailable.
  const comparableColumns = (selectedPublication?.columns || []).filter(
    (column) => column.comparable
  );
  const selectedColumn = comparableColumns.find((column) => column.name === fieldName);
  const unit = selectedColumn?.unit || "";

  const missing = requiredInputsMissing({
    displayName,
    ruleKind,
    publicationKey,
    fieldName,
    threshold,
    thresholdHours,
    entityId,
    expectedValue
  });

  return (
    <form className="stack" action={action} method="post">
      <input name="policy_kind" type="hidden" value="declarative_rule" />
      <input name="rule_schema_version" type="hidden" value={ruleSchemaVersion || ""} />
      <input name="rule_kind" type="hidden" value={ruleKind} />
      <input name="operator" type="hidden" value={operator} />
      {unit ? <input name="unit" type="hidden" value={unit} /> : null}

      <div className="formGrid">
        <div className="field spanTwo">
          <label htmlFor="policy-display-name">
            Name <span className="muted">(required)</span>
          </label>
          <input
            id="policy-display-name"
            name="display_name"
            type="text"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            required
          />
        </div>
        <div className="field spanTwo">
          <label htmlFor="policy-description">Description</label>
          <input id="policy-description" name="description" type="text"
            defaultValue={policy?.description || ""} />
        </div>
      </div>

      <div className="field">
        <label htmlFor="policy-rule-kind">Rule kind</label>
        <select
          id="policy-rule-kind"
          value={ruleKind}
          onChange={(event) => setRuleKind(event.target.value)}
        >
          {RULE_KINDS.map((kind) => (
            <option key={kind.value} value={kind.value}>
              {kind.label}
            </option>
          ))}
        </select>
        <span className="muted">
          {RULE_KINDS.find((kind) => kind.value === ruleKind)?.help}
        </span>
      </div>

      {ruleKind !== "ha_helper_state_comparison" ? (
        <div className="field">
          <label htmlFor="policy-publication">
            Publication <span className="muted">(required)</span>
          </label>
          <select
            id="policy-publication"
            name="publication_key"
            value={publicationKey}
            onChange={(event) => {
              setPublicationKey(event.target.value);
              setFieldName("");
            }}
            required
          >
            <option value="">Select a publication…</option>
            {publications.map((publication) => (
              <option
                key={publication.publication_key}
                value={publication.publication_key}
              >
                {publication.display_name} ({publication.publication_key})
              </option>
            ))}
          </select>
        </div>
      ) : null}

      {ruleKind === "publication_value_comparison" ? (
        <div className="formGrid threeCol">
          <div className="field">
            <label htmlFor="policy-field">
              Field <span className="muted">(required)</span>
            </label>
            <select
              id="policy-field"
              name="field_name"
              value={fieldName}
              onChange={(event) => setFieldName(event.target.value)}
              required
              disabled={!publicationKey}
            >
              <option value="">
                {publicationKey ? "Select a field…" : "Select a publication first"}
              </option>
              {comparableColumns.map((column) => (
                <option key={column.name} value={column.name}>
                  {column.name}
                  {column.unit ? ` (${column.unit})` : ""}
                </option>
              ))}
            </select>
            {publicationKey && comparableColumns.length === 0 ? (
              <span className="muted">
                This publication has no numerically comparable field, so a value
                rule cannot be written against it.
              </span>
            ) : null}
          </div>
          <div className="field">
            <label htmlFor="policy-operator">Comparison</label>
            <select
              id="policy-operator"
              value={operator}
              onChange={(event) => setOperator(event.target.value)}
            >
              {COMPARISON_OPERATORS.map((candidate) => (
                <option key={candidate} value={candidate}>
                  {comparisonPhrase(candidate)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="policy-threshold">
              Threshold <span className="muted">(required)</span>
            </label>
            <input
              id="policy-threshold"
              name="threshold"
              type="number"
              step="any"
              value={threshold}
              onChange={(event) => setThreshold(event.target.value)}
              required
            />
            {unit ? <span className="muted">Unit: {unit}</span> : null}
          </div>
        </div>
      ) : null}

      {ruleKind === "publication_freshness_comparison" ? (
        <div className="formGrid threeCol">
          <div className="field">
            <label htmlFor="policy-freshness-operator">Comparison</label>
            <select
              id="policy-freshness-operator"
              value={operator}
              onChange={(event) => setOperator(event.target.value)}
            >
              {COMPARISON_OPERATORS.map((candidate) => (
                <option key={candidate} value={candidate}>
                  {comparisonPhrase(candidate)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="policy-threshold-hours">
              Threshold in hours <span className="muted">(required)</span>
            </label>
            <input
              id="policy-threshold-hours"
              name="threshold_hours"
              type="number"
              step="any"
              value={thresholdHours}
              onChange={(event) => setThresholdHours(event.target.value)}
              required
            />
          </div>
        </div>
      ) : null}

      {ruleKind === "ha_helper_state_comparison" ? (
        <div className="formGrid threeCol">
          <div className="field">
            <label htmlFor="policy-entity">
              Entity id <span className="muted">(required)</span>
            </label>
            <input
              id="policy-entity"
              name="entity_id"
              type="text"
              placeholder="input_boolean.example"
              value={entityId}
              onChange={(event) => setEntityId(event.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="policy-helper-operator">Comparison</label>
            <select
              id="policy-helper-operator"
              value={operator}
              onChange={(event) => setOperator(event.target.value)}
            >
              {COMPARISON_OPERATORS.map((candidate) => (
                <option key={candidate} value={candidate}>
                  {comparisonPhrase(candidate)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="policy-expected">
              Expected value <span className="muted">(required)</span>
            </label>
            <input
              id="policy-expected"
              name="expected_value"
              type="text"
              value={expectedValue}
              onChange={(event) => setExpectedValue(event.target.value)}
              required
            />
          </div>
        </div>
      ) : null}

      <div className="specBlock">
        <div className="muted">This policy will evaluate</div>
        <div>
          {sentenceFor({
            ruleKind,
            publicationKey,
            fieldName,
            operator,
            threshold,
            thresholdHours,
            entityId,
            expectedValue,
            unit
          })}
        </div>
      </div>

      {missing.length > 0 ? (
        <div className="muted">
          Supply {missing.join(", ")} before this policy can be saved.
        </div>
      ) : null}

      <div className="buttonRow">
        <button
          className="primaryButton inlineButton"
          type="submit"
          disabled={missing.length > 0}
        >
          {submitLabel}
        </button>
      </div>
    </form>
  );
}

/**
 * Required inputs still absent, named as the operator sees them.
 *
 * A template is parameterized, not misleading: rather than presenting a
 * ready-looking policy that fails on save, the surface refuses until the
 * inputs it needs are actually there.
 */
export function requiredInputsMissing({
  displayName,
  ruleKind,
  publicationKey,
  fieldName,
  threshold,
  thresholdHours,
  entityId,
  expectedValue
}) {
  const missing = [];
  if (!displayName) {
    missing.push("a name");
  }
  if (ruleKind === "publication_value_comparison") {
    if (!publicationKey) missing.push("a publication");
    if (!fieldName) missing.push("a field");
    if (threshold === "" || threshold === undefined) missing.push("a threshold");
  }
  if (ruleKind === "publication_freshness_comparison") {
    if (!publicationKey) missing.push("a publication");
    if (thresholdHours === "" || thresholdHours === undefined) {
      missing.push("a threshold in hours");
    }
  }
  if (ruleKind === "ha_helper_state_comparison") {
    if (!entityId) missing.push("an entity id");
    if (!expectedValue) missing.push("an expected value");
  }
  return missing;
}

function sentenceFor({
  ruleKind,
  publicationKey,
  fieldName,
  operator,
  threshold,
  thresholdHours,
  entityId,
  expectedValue,
  unit
}) {
  const suffix = unit ? ` ${unit}` : "";
  if (ruleKind === "publication_value_comparison") {
    return `${fieldName || "…"} of ${publicationKey || "…"} ${comparisonPhrase(
      operator
    )} ${threshold === "" ? "…" : threshold}${suffix}`;
  }
  if (ruleKind === "publication_freshness_comparison") {
    return `time since ${publicationKey || "…"} was assessed ${comparisonPhrase(
      operator
    )} ${thresholdHours === "" ? "…" : thresholdHours}h`;
  }
  if (ruleKind === "ha_helper_state_comparison") {
    return `${entityId || "…"} ${comparisonPhrase(operator)} "${
      expectedValue || "…"
    }"`;
  }
  return "…";
}
