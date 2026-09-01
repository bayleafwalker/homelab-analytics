const COMPARISON_PHRASES = {
  gt: "is greater than",
  gte: "is greater than or equal to",
  lt: "is less than",
  lte: "is less than or equal to",
  eq: "equals",
  neq: "differs from"
};

/**
 * Comparison operators the evaluator implements.
 *
 * `in` and `not_in` were retired: they validated but never fired. Offering
 * them again would put a control on the form that does nothing.
 */
export const COMPARISON_OPERATORS = Object.keys(COMPARISON_PHRASES);

export function comparisonPhrase(operator) {
  return COMPARISON_PHRASES[operator] || `is compared (${operator}) to`;
}

/**
 * Describe a rule document in the terms the operator authored it in.
 *
 * Template discipline: the surface must show the publication, the field, the
 * unit and the comparison actually being evaluated, rather than a friendly
 * label that hides which number is being read.
 */
export function describeRule(ruleDocument) {
  if (!ruleDocument || typeof ruleDocument !== "object") {
    return { kind: "unknown", summary: "No rule document." };
  }
  const unit = ruleDocument.unit ? ` ${ruleDocument.unit}` : "";
  switch (ruleDocument.rule_kind) {
    case "publication_value_comparison":
      return {
        kind: "Value comparison",
        publicationKey: ruleDocument.publication_key,
        summary:
          `${ruleDocument.field_name} ${comparisonPhrase(ruleDocument.operator)} ` +
          `${ruleDocument.threshold}${unit}`
      };
    case "publication_freshness_comparison":
      return {
        kind: "Freshness comparison",
        publicationKey: ruleDocument.publication_key,
        summary:
          `time since last assessment ${comparisonPhrase(ruleDocument.operator)} ` +
          `${ruleDocument.threshold_hours}h`
      };
    case "ha_helper_state_comparison":
      return {
        kind: "Helper state comparison",
        entityId: ruleDocument.entity_id,
        summary:
          `${ruleDocument.entity_id} ${comparisonPhrase(ruleDocument.operator)} ` +
          `"${ruleDocument.expected_value}"`
      };
    default:
      return {
        kind: "Unsupported",
        summary: `Rule kind "${ruleDocument.rule_kind}" is not supported.`
      };
  }
}

export function PolicyRuleSummary({ ruleDocument }) {
  const described = describeRule(ruleDocument);
  return (
    <div className="specBlock">
      <div className="muted">{described.kind}</div>
      <div>{described.summary}</div>
      {described.publicationKey ? (
        <div className="muted">Reads publication {described.publicationKey}</div>
      ) : null}
    </div>
  );
}
