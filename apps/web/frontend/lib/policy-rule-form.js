// @ts-check

/**
 * Build a rule document from the authoring form's flat fields.
 *
 * The form posts one flat field set and this assembles the nested document
 * the API expects. Only the fields belonging to the chosen rule kind are
 * included: every rule model forbids extra keys, so carrying an unused field
 * across from another kind would be a 422.
 *
 * Nothing is defaulted or guessed. A missing required input is left absent so
 * the API rejects it, rather than being filled with a plausible value that
 * would silently create a rule the operator did not author.
 *
 * @param {FormData} formData
 * @returns {Record<string, unknown>}
 */
export function ruleDocumentFromForm(formData) {
  const ruleKind = String(formData.get("rule_kind") || "");
  const operator = String(formData.get("operator") || "");

  if (ruleKind === "publication_value_comparison") {
    const unit = String(formData.get("unit") || "");
    /** @type {Record<string, unknown>} */
    const rule = {
      rule_kind: ruleKind,
      publication_key: String(formData.get("publication_key") || ""),
      field_name: String(formData.get("field_name") || ""),
      operator,
      threshold: numberOrRaw(formData.get("threshold"))
    };
    if (unit) {
      rule.unit = unit;
    }
    return rule;
  }

  if (ruleKind === "publication_freshness_comparison") {
    return {
      rule_kind: ruleKind,
      publication_key: String(formData.get("publication_key") || ""),
      operator,
      threshold_hours: numberOrRaw(formData.get("threshold_hours"))
    };
  }

  if (ruleKind === "ha_helper_state_comparison") {
    return {
      rule_kind: ruleKind,
      entity_id: String(formData.get("entity_id") || ""),
      operator,
      expected_value: String(formData.get("expected_value") || "")
    };
  }

  // Unknown kind is passed through so the API reports it, rather than being
  // silently coerced into one of the supported kinds here.
  return { rule_kind: ruleKind };
}

/**
 * Numeric form values arrive as strings. Send a number when the value is one,
 * and otherwise pass the raw string through so the API's own validation
 * produces the error rather than this helper inventing a fallback.
 *
 * @param {FormDataEntryValue | null} value
 * @returns {number | string}
 */
function numberOrRaw(value) {
  const raw = String(value ?? "");
  const parsed = Number(raw);
  return raw !== "" && Number.isFinite(parsed) ? parsed : raw;
}
