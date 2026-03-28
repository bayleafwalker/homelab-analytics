const STATE_COPY = {
  good: { label: "Good", color: "var(--ok)" },
  warning: { label: "Warning", color: "var(--warning)" },
  needs_action: { label: "Needs action", color: "var(--error)" },
};

const STATE_ALIASES = {
  good: "good",
  healthy: "good",
  under_budget: "good",
  under_target: "good",
  warning: "warning",
  caution: "warning",
  on_budget: "warning",
  on_target: "warning",
  needs_action: "needs_action",
  "needs-action": "needs_action",
  critical: "needs_action",
  over_budget: "needs_action",
  over_target: "needs_action",
};

function toStateKey(value) {
  if (typeof value !== "string") {
    return "";
  }
  return STATE_ALIASES[value] || value.toLowerCase().replace(/\s+/g, "_");
}

export function stateIndicatorBadge(value) {
  const stateKey = toStateKey(value);
  if (stateKey in STATE_COPY) {
    return STATE_COPY[stateKey];
  }
  if (!stateKey) {
    return { label: "Unknown", color: "var(--accent)" };
  }
  return {
    label: stateKey.replace(/_/g, " "),
    color: "var(--accent)",
  };
}
