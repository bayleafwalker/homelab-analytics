/**
 * Canonical list of onboarding source definitions.
 * Used by /onboarding, /first-answer, dashboard OnboardingChecklist, and
 * related components to ensure consistent ordering, labels, and upload paths.
 */
export const ONBOARDING_SOURCES = [
  {
    dataset: "account_transactions",
    label: "Account transactions",
    description: "Cashflow, categories, anomalies",
    uploadPath: "/upload/account-transactions",
    required: true,
    unlocks: "cashflow, categories, anomalies",
    unlocksDetail: [
      "Monthly cashflow trend",
      "Spend-by-category breakdown",
      "Transaction anomalies",
      "Attention items",
    ],
  },
  {
    dataset: "subscriptions",
    label: "Subscriptions",
    description: "Recurring cost baseline",
    uploadPath: "/upload",
    required: true,
    unlocks: "recurring cost baseline, subscription review",
    unlocksDetail: [
      "Recurring cost baseline",
      "Subscription review queue",
      "Cost model (subscription layer)",
    ],
  },
  {
    dataset: "contract_prices",
    label: "Contract prices",
    description: "Affordability ratios, contract watchlist",
    uploadPath: "/upload",
    required: false,
    unlocks: "affordability ratios, contract watchlist",
    unlocksDetail: [
      "Affordability ratios",
      "Contract renewal watchlist",
      "Utility contract pricing",
    ],
  },
  {
    dataset: "budgets",
    label: "Budgets",
    description: "Budget variance, envelopes",
    uploadPath: "/upload",
    required: false,
    unlocks: "budget variance, envelope tracking",
    unlocksDetail: [
      "Budget variance report",
      "Envelope tracking",
    ],
  },
  {
    dataset: "loan_repayments",
    label: "Loan repayments",
    description: "Debt service ratio, loan schedule",
    uploadPath: "/upload",
    required: false,
    unlocks: "loan overview, debt service ratio",
    unlocksDetail: [
      "Loan overview",
      "Debt service ratio",
      "Loan repayment schedule",
    ],
  },
];
