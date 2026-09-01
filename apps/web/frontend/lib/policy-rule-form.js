// @ts-check

/**
 * Build a rule document from already-extracted values.
 *
 * Single definition shared by the save path and the preview path. If the two
 * built the document separately they could drift, and a preview of a
 * different rule than the one that saves is worse than no preview at all.
 *
 * Only the fields belonging to the chosen rule kind are included: every rule
 * model forbids extra keys, so carrying a field across from another kind
 * would be a 422.
 *
 * Nothing is defaulted or guessed. A missing required input is left as it
 * arrived so the API rejects it, rather than being filled with a plausible
 * value that would silently create a rule the operator did not author.
 *
 * @param {{
 *   ruleKind: string,
 *   operator: string,
 *   publicationKey?: string,
 *   fieldName?: string,
 *   threshold?: string | number,
 *   thresholdHours?: string | number,
 *   entityId?: string,
 *   expectedValue?: string,
 *   unit?: string
 * }} values
 * @returns {Record<string, unknown>}
 */
export function buildRuleDocument(values) {
  const { ruleKind, operator } = values;

  if (ruleKind === "publication_value_comparison") {
    /** @type {Record<string, unknown>} */
    const rule = {
      rule_kind: ruleKind,
      publication_key: values.publicationKey || "",
      field_name: values.fieldName || "",
      operator,
      threshold: numberOrRaw(values.threshold)
    };
    if (values.unit) {
      rule.unit = values.unit;
    }
    return rule;
  }

  if (ruleKind === "publication_freshness_comparison") {
    return {
      rule_kind: ruleKind,
      publication_key: values.publicationKey || "",
      operator,
      threshold_hours: numberOrRaw(values.thresholdHours)
    };
  }

  if (ruleKind === "ha_helper_state_comparison") {
    return {
      rule_kind: ruleKind,
      entity_id: values.entityId || "",
      operator,
      expected_value: values.expectedValue || ""
    };
  }

  // Unknown kind is passed through so the API reports it, rather than being
  // silently coerced into one of the supported kinds here.
  return { rule_kind: ruleKind };
}

/**
 * Build a rule document from the authoring form's flat POST fields.
 *
 * @param {FormData} formData
 * @returns {Record<string, unknown>}
 */
export function ruleDocumentFromForm(formData) {
  return buildRuleDocument({
    ruleKind: String(formData.get("rule_kind") || ""),
    operator: String(formData.get("operator") || ""),
    publicationKey: String(formData.get("publication_key") || ""),
    fieldName: String(formData.get("field_name") || ""),
    threshold: String(formData.get("threshold") ?? ""),
    thresholdHours: String(formData.get("threshold_hours") ?? ""),
    entityId: String(formData.get("entity_id") || ""),
    expectedValue: String(formData.get("expected_value") || ""),
    unit: String(formData.get("unit") || "")
  });
}

/**
 * Numeric form values arrive as strings. Send a number when the value is one,
 * and otherwise pass the raw value through so the API's own validation
 * produces the error rather than this helper inventing a fallback.
 *
 * @param {string | number | undefined} value
 * @returns {number | string}
 */
function numberOrRaw(value) {
  const raw = String(value ?? "");
  const parsed = Number(raw);
  return raw !== "" && Number.isFinite(parsed) ? parsed : raw;
}
