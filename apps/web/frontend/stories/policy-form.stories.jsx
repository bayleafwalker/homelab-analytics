import React from "react";

import { PolicyForm } from "../components/policy-form";

const PUBLICATIONS = [
  {
    publication_key: "household_overview",
    display_name: "Household Overview",
    description: "Single-row summary of the latest month.",
    columns: [
      {
        name: "utility_cost_total",
        json_type: "string",
        description: "Total utility cost of the most recent billing month.",
        unit: "currency",
        semantic_role: "measure",
        comparable: true
      },
      {
        name: "currency",
        json_type: "string",
        description: "Currency code.",
        unit: null,
        semantic_role: "dimension",
        comparable: false
      }
    ]
  }
];

// Mirrors the shipped utility-cost template: everything is decided except the
// threshold, which is the operator's judgement to make.
const UTILITY_TEMPLATE = {
  id: "utility-cost-above-threshold",
  name: "Utility cost above a threshold",
  requiredInputs: ["threshold"],
  rule: {
    rule_kind: "publication_value_comparison",
    publication_key: "household_overview",
    field_name: "utility_cost_total",
    operator: "gt"
  }
};

const meta = {
  title: "Control Plane/PolicyForm",
  component: PolicyForm
};

export default meta;

/**
 * A template with an unsupplied required input cannot be submitted.
 *
 * This is the template discipline as behaviour rather than as prose: the
 * template is parameterized and says what it needs, and refuses until it has
 * it.
 */
export const TemplateRequiresThreshold = {
  args: {
    publications: PUBLICATIONS,
    ruleSchemaVersion: "1.0",
    template: UTILITY_TEMPLATE,
    action: "/control/policies/create"
  }
};
