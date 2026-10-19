// Fixtures for the Ops Console stories. Shapes match the reporting API:
// GET /reports/spend-heatmap, /reports/monthly-cashflow, /reports/attention-items,
// /runs, /reports/spend-by-category-monthly, /reports/affordability-ratios and
// /control/confidence (publications).

const ZERO_ROW = () => Array.from({ length: 24 }, () => "0.00");

function heatmapFrom(cells, untimed, overrides = {}) {
  const counts = cells.map((row) => row.map((value) => (Number(value) > 0 ? 1 : 0)));
  const flat = cells.flat().map(Number);
  const timed = flat.reduce((sum, value) => sum + value, 0);
  const untimedTotal = untimed.map(Number).reduce((sum, value) => sum + value, 0);
  const timedCount = counts.flat().reduce((sum, value) => sum + value, 0);
  const untimedCount = untimed.filter((value) => Number(value) > 0).length;
  return {
    window_days: 28,
    window_start: "2026-09-21",
    window_end: "2026-10-18",
    data_through: "2026-10-18",
    currency: "EUR",
    hour_basis: "utc",
    timezone: "UTC",
    day_labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    cells,
    counts,
    untimed,
    untimed_counts: untimed.map((value) => (Number(value) > 0 ? 1 : 0)),
    max_cell: Math.max(0, ...flat).toFixed(2),
    max_untimed: Math.max(0, ...untimed.map(Number)).toFixed(2),
    coverage: timedCount && untimedCount ? "mixed" : timedCount ? "timed" : untimedCount ? "date_only" : "empty",
    totals: {
      expense: (timed + untimedTotal).toFixed(2),
      timed_expense: timed.toFixed(2),
      untimed_expense: untimedTotal.toFixed(2),
      transaction_count: timedCount + untimedCount,
      timed_count: timedCount,
      untimed_count: untimedCount,
      active_days: 20,
    },
    publications: ["mart_spend_by_weekday_hour"],
    ...overrides,
  };
}

// A busy week: commute coffee, lunch, evening groceries, weekend shopping.
const fullCells = Array.from({ length: 7 }, (_, day) =>
  Array.from({ length: 24 }, (_, hour) => {
    const weekend = day >= 5;
    let value = 0;
    if (!weekend && hour === 7) value = 4.2 + day;
    if (!weekend && hour === 12) value = 11.5 + day * 1.5;
    if (hour >= 17 && hour <= 19) value = 22 + day * 6 + (hour - 17) * 4;
    if (weekend && hour >= 10 && hour <= 15) value = 30 + (hour - 10) * 9;
    if (hour >= 1 && hour <= 5) value = 0;
    return value.toFixed(2);
  })
);

export const fullHeatmap = heatmapFrom(fullCells, ["0.00", "84.15", "0.00", "0.00", "15.99", "0.00", "0.00"]);

const sparseCells = Array.from({ length: 7 }, ZERO_ROW);
sparseCells[1][18] = "42.00";
sparseCells[4][12] = "9.80";
sparseCells[5][11] = "63.40";
export const sparseHeatmap = heatmapFrom(sparseCells, ["0.00", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00"]);

export const dateOnlyHeatmap = heatmapFrom(
  Array.from({ length: 7 }, ZERO_ROW),
  ["212.40", "84.15", "36.90", "120.00", "301.75", "455.10", "64.00"]
);

export const emptyHeatmap = heatmapFrom(Array.from({ length: 7 }, ZERO_ROW), Array(7).fill("0.00"), {
  window_start: null,
  window_end: null,
  data_through: null,
});

export const cashflowRows = [
  ["2025-11", "4100.00", "2950.10"],
  ["2025-12", "4600.00", "3920.55"],
  ["2026-01", "4100.00", "2610.00"],
  ["2026-02", "4100.00", "2480.35"],
  ["2026-03", "4150.00", "2890.10"],
  ["2026-04", "4150.00", "2701.00"],
  ["2026-05", "4150.00", "3105.40"],
  ["2026-06", "4343.35", "2650.00"],
  ["2026-07", "4343.35", "3998.20"],
  ["2026-08", "4343.35", "2101.00"],
  ["2026-09", "4343.35", "1868.37"],
].map(([booking_month, income, expense]) => ({
  booking_month,
  income,
  expense,
  net: (Number(income) - Number(expense)).toFixed(4),
  transaction_count: 40,
}));

export const consoleAttention = [
  { item_id: "a1", title: "Unusual amount: Verkkokauppa 1249.00", severity: 3 },
  { item_id: "a2", title: "Contract renewal: Helen electricity", severity: 2 },
  { item_id: "a3", title: "Review contract: Elisa broadband", severity: 2 },
  { item_id: "a4", title: "Budget over: Groceries", severity: 1 },
  { item_id: "a5", title: "First-time payee: Kotipizza", severity: 1 },
  { item_id: "a6", title: "Upcoming: Home mortgage 1556.33", severity: 1 },
  { item_id: "a7", title: "Upcoming: Netflix 15.99", severity: 1 },
  { item_id: "a8", title: "Upcoming: Spotify 9.99", severity: 1 },
];

export const consoleRuns = [
  ["run-0108", "2026-10-18T06:00:12", "landed", "account_transactions", 214],
  ["run-0107", "2026-10-17T06:00:09", "landed", "account_transactions", 12],
  ["run-0106", "2026-10-16T21:14:40", "failed", "utility_usage", 0],
  ["run-0105", "2026-10-16T06:00:05", "landed", "subscriptions", 9],
  ["run-0104", "2026-10-15T06:00:11", "rejected", "contract_prices", 3],
  ["run-0103", "2026-10-14T06:00:07", "landed", "account_transactions", 18],
  ["run-0102", "2026-10-13T06:00:10", "landed", "utility_usage", 744],
  ["run-0101", "2026-10-12T06:00:04", "landed", "account_transactions", 7],
  ["run-0100", "2026-10-11T06:00:04", "landed", "account_transactions", 5],
].map(([run_id, created_at, status, dataset_name, row_count]) => ({
  run_id,
  created_at,
  status,
  dataset_name,
  row_count,
}));

export const consoleCategories = [
  ["Housing", "1556.33"],
  ["Groceries", "612.40"],
  ["Utilities", "181.90"],
  ["Transport", "142.00"],
  ["Subscriptions", "61.96"],
  ["Eating out", "58.70"],
  ["Health", "32.00"],
  [null, "18.50"],
].map(([category, total_expense], index) => ({
  booking_month: "2026-09",
  counterparty_name: `Payee ${index}`,
  category,
  total_expense,
  transaction_count: 3,
}));

export const consoleRatios = [
  { ratio_name: "housing_to_income", ratio: "0.358", assessment: "caution", state: "warning" },
  { ratio_name: "total_cost_to_income", ratio: "0.430", assessment: "healthy", state: "good" },
  { ratio_name: "debt_service_ratio", ratio: "0.358", assessment: "healthy", state: "good" },
];

export const consoleConfidence = [
  ["mart_monthly_cashflow", "trustworthy", "2026-10-18T06:02:10", 100],
  ["mart_spend_by_category_monthly", "trustworthy", "2026-10-18T06:02:11", 100],
  ["mart_spend_by_weekday_hour", "trustworthy", "2026-10-18T06:02:12", 100],
  ["mart_utility_cost_summary", "degraded", "2026-10-17T21:15:02", 82],
  ["mart_contract_price_current", "unreliable", "2026-10-15T06:01:40", 40],
  ["mart_household_overview", "trustworthy", "2026-10-18T06:02:13", 100],
  ["mart_budget_variance", "unavailable", null, 0],
].map(([publication_key, confidence_verdict, assessed_at, completeness_pct]) => ({
  publication_key,
  confidence_verdict,
  assessed_at,
  completeness_pct,
}));
