import React from "react";

export const readerUser = {
  username: "reader",
  role: "reader",
};

export const operatorUser = {
  username: "operator",
  role: "operator",
};

export const adminUser = {
  username: "admin",
  role: "admin",
};

export const sparklineLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];

export const sparklineSeries = [
  {
    label: "Cashflow",
    color: "var(--accent)",
    values: [920, 1180, 1040, 1325, 1260, 1420],
  },
  {
    label: "Baseline",
    color: "var(--accent-warm)",
    values: [980, 1000, 1010, 1030, 1050, 1075],
  },
];

export const freshnessDomains = [
  { name: "Finance", band: "green", color: "var(--ok)", fill: "92%", detail: "account_transactions · 16h ago" },
  { name: "Recurring", band: "green", color: "var(--ok)", fill: "92%", detail: "subscriptions · 2d ago" },
  { name: "Utilities", band: "yellow", color: "var(--accent-warm)", fill: "54%", detail: "contract_prices · 5d ago" },
  { name: "Loans", band: "green", color: "var(--ok)", fill: "92%", detail: "loan_repayments · 1d ago" },
  { name: "Budgets", band: "red", color: "var(--warn)", fill: "12%", detail: "budgets · 14d — stale" },
];

export const horizonDays = [
  { dateLabel: "Mon 28", empty: false, tone: "cool", title: "Energy bill", amountLabel: "EUR 172.18", moreCount: 0 },
  { dateLabel: "Tue 29", empty: false, tone: "neutral", title: "Netflix renewal", amountLabel: "EUR 15.99", moreCount: 0 },
  { dateLabel: "Wed 30", empty: true, tone: "neutral", title: "—", amountLabel: "", moreCount: 0 },
  { dateLabel: "Thu 01", empty: false, tone: "accent", title: "Mortgage payment", amountLabel: "EUR 1,284", moreCount: 0 },
  { dateLabel: "Fri 02", empty: false, tone: "neutral", title: "Spotify", amountLabel: "EUR 11.99", moreCount: 1 },
  { dateLabel: "Sat 03", empty: true, tone: "neutral", title: "—", amountLabel: "", moreCount: 0 },
  { dateLabel: "Sun 04", empty: false, tone: "warm", title: "Energy contract review", amountLabel: "", moreCount: 0 },
];

export const rankedAttentionItems = [
  {
    item_id: "a-1",
    severity: 1,
    title: "Energy contract renewal in 12 days",
    source_domain: "utilities",
    detail: "Current fixed price expires 07 May; market index +14% YoY",
  },
  {
    item_id: "a-2",
    severity: 2,
    title: "Mortgage rate review window opens",
    source_domain: "loans",
    detail: "Bank offer letter received 22 Apr · 4 wk window",
  },
  {
    item_id: "a-3",
    severity: 3,
    title: "Account import 9 days stale",
    source_domain: "sources",
    detail: "op_account · last landed 16 Apr",
  },
];

export const affordabilityRatioFixtures = [
  { ratio_name: "housing_income", ratio: "0.268", state: "ok" },
  { ratio_name: "total_cost_income", ratio: "0.704", state: "warning" },
  { ratio_name: "debt_service_ratio", ratio: "0.182", state: "ok" },
];

export const topCategoryFixtures = [
  { category: "Housing", amount: 1284.0, delta: -0.4 },
  { category: "Groceries", amount: 612.4, delta: 3.1 },
  { category: "Utilities", amount: 172.18, delta: -7.2 },
  { category: "Transport", amount: 148.6, delta: 1.6 },
  { category: "Subscriptions", amount: 94.3, delta: 0.0 },
];

export const recentChangeFixtures = [
  { change_type: "increase", metric_name: "Groceries spend", direction: "up", current_value: "612.40", previous_value: "594.10", booking_month: "2026-04" },
  { change_type: "decrease", metric_name: "Utilities spend", direction: "down", current_value: "172.18", previous_value: "185.60", booking_month: "2026-04" },
];

export function storyBody(title, copy) {
  return (
    <section className="panel section">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">Story Surface</div>
          <h2>{title}</h2>
        </div>
        <span className="statusPill">Reviewable</span>
      </div>
      <p className="lede">{copy}</p>
    </section>
  );
}

export function retroStoryBody(title, copy) {
  return (
    <section className="retroPanel">
      <div className="retroSectionHeader">
        <div>
          <div className="retroEyebrow">Story Surface</div>
          <h2>{title}</h2>
        </div>
        <span className="retroTag" data-variant="ok">
          Stable
        </span>
      </div>
      <p className="retroLede">{copy}</p>
    </section>
  );
}
