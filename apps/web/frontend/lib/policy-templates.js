// @ts-check

/**
 * Policy templates that are honestly expressible in the shipped rule kinds.
 *
 * A template is parameterized, not misleading. Each one below names the exact
 * publication and field it reads, states which inputs the operator must
 * supply, and is refused enablement until they are. No template approximates
 * one measure with a semantically different field.
 *
 * All value templates read `household_overview`, which is materialized as a
 * single row (`refresh_household_overview` deletes and inserts exactly one row
 * built from scalar subqueries). That matters: `publication_value_comparison`
 * evaluates `rows[0]`, and publication reads are `SELECT * FROM <relation>
 * LIMIT n` with no ORDER BY. On a multi-row publication `rows[0]` is an
 * arbitrary row, so a value template written against one would compare an
 * unspecified period while claiming to describe the current one. See
 * TEMPLATE_EXCLUSIONS.
 */
export const POLICY_TEMPLATES = [
  {
    id: "negative-monthly-cashflow",
    name: "Monthly cashflow went negative",
    summary:
      "Breaches when the latest month's net cashflow is below zero — more money left than arrived.",
    reads:
      "household_overview.cashflow_net, the net cashflow of the most recent booking month.",
    requiredInputs: [],
    rule: {
      rule_kind: "publication_value_comparison",
      publication_key: "household_overview",
      field_name: "cashflow_net",
      operator: "lt",
      threshold: 0
    }
  },
  {
    id: "utility-cost-above-threshold",
    name: "Utility cost above a threshold",
    summary:
      "Breaches when the latest month's total utility cost rises above a limit you set.",
    reads:
      "household_overview.utility_cost_total, the total utility cost of the most recent billing month.",
    // No default threshold is offered: what counts as too much is the
    // household's judgement, and inventing a number would author a policy the
    // operator did not choose.
    requiredInputs: ["threshold"],
    rule: {
      rule_kind: "publication_value_comparison",
      publication_key: "household_overview",
      field_name: "utility_cost_total",
      operator: "gt"
    }
  },
  {
    id: "stale-critical-source",
    name: "A source you depend on has gone stale",
    summary:
      "Breaches when a publication has not been assessed for longer than you allow.",
    reads:
      "the confidence snapshot of the publication you choose — its assessment age, not its values.",
    requiredInputs: ["publication_key", "threshold_hours"],
    rule: {
      rule_kind: "publication_freshness_comparison",
      operator: "gt"
    }
  }
];

/**
 * Candidates considered and deliberately not shipped, with the reason.
 *
 * Recorded rather than dropped silently: an operator who expects an obvious
 * template and does not find it deserves to know it was rejected on purpose.
 */
export const TEMPLATE_EXCLUSIONS = [
  {
    id: "monthly-cashflow-publication",
    reason:
      "A cashflow rule reading the monthly_cashflow publication directly cannot be written honestly. That publication holds one row per booking month, and a value rule evaluates whichever row comes back first from an unordered read — so it would compare an arbitrary month while claiming to describe the current one. The shipped cashflow template reads household_overview instead, which is materialized as a single row for the latest month."
  },
  {
    id: "subscription-variance",
    reason:
      "Subscription cost variance has no field expressing it. Approximating it with subscription_total_monthly would compare a different quantity than the name promises, so it is omitted rather than faked."
  }
];

/**
 * Required inputs a template still needs, given the current form values.
 *
 * @param {{ requiredInputs: string[] }} template
 * @param {Record<string, unknown>} values
 */
export function templateInputsOutstanding(template, values) {
  return template.requiredInputs.filter((input) => {
    const value = values[input];
    return value === undefined || value === null || value === "";
  });
}
