import React from "react";

import { formatMoney, formatMonth, monthsBetween, toNumber } from "../lib/format";
import { ExplainBox } from "./explain";
import { DevicePanel, EventFeed, PowerChart, ServicesPanel } from "./wallboard-panels";

// Ambient household status for a wall tablet or TV. Read from across the
// room: mono type only, nothing under 18px, status words 24px+, colour
// reserved for state. Data arrives as props so the view renders identically
// in Storybook and on the live /wallboard route.
//
// Layout: a household strip under the clock (Money, Next payment, Needs a
// decision, Data, Utilities), then the specified kiosk grid
//   [services 1.4fr][events 1fr] / [devices 1fr][power-24h 1fr] / [ticker]
// The Utilities tile lives in the strip, which has no fixed slot count, so
// restoring it leaves the kiosk grid untouched. ?compact=1 hides the event
// feed and the Utilities tile, doubles the room readings and drops the
// ticker's hotkey hint.

// Latest billing month's total across utility types, from
// /reports/utility-cost-trend rows; null when there are no bills.
// Totals are summed within a currency only: `totals` has one entry per billed
// currency. `total`/`currency` are set only when exactly one currency was
// billed, so a mixed answer is never presented as a single amount. Periods
// with no currency (usage without a bill) are not bills.
export function latestUtilityBill(rows) {
  const list = (Array.isArray(rows) ? rows : []).filter((row) => row.currency);
  const months = [...new Set(list.map((row) => row.billing_month).filter(Boolean))].sort();
  const month = months.at(-1);
  if (!month) return null;
  const byCurrency = new Map();
  for (const row of list.filter((r) => r.billing_month === month)) {
    byCurrency.set(row.currency, (byCurrency.get(row.currency) || 0) + (toNumber(row.total_cost) || 0));
  }
  const totals = [...byCurrency.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([currency, total]) => ({ currency, total }));
  const single = totals.length === 1 ? totals[0] : null;
  return { month, totals, total: single ? single.total : null, currency: single ? single.currency : null };
}

function daysUntil(dateText, today) {
  if (!dateText) return null;
  const target = new Date(`${dateText}T00:00:00`);
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((target - start) / 86400000);
}

function dueLabel(days) {
  if (days == null) return "";
  if (days < 0) return `${-days}d late`;
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  return `${days} days`;
}

function shortDate(dateText) {
  const date = new Date(`${dateText}T00:00:00`);
  if (Number.isNaN(date.getTime())) return String(dateText);
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

// Same-title items (one contract flagged for two reasons) read as one line.
function groupByTitle(items) {
  const groups = new Map();
  for (const item of items) {
    const key = item.title || item.item_id;
    groups.set(key, (groups.get(key) || 0) + 1);
  }
  return [...groups.entries()].map(([title, count]) => ({ title, count }));
}

function Tile({ label, tone = "neutral", children }) {
  return (
    <section className="wallTile" data-tone={tone}>
      <h2 className="wallTileLabel">{label}</h2>
      {children}
    </section>
  );
}

export function WallboardView({
  now,
  overview,
  // Every overview row, one per currency. `overview` (a single row) stays for
  // callers that only have one denomination.
  overviewRows = null,
  attentionItems = [],
  upcomingCosts = [],
  bridge = null,
  latestMonth = null,
  services = null,
  devices = null,
  events = null,
  power = null,
  utilityLatest = null,
  compact = false,
  clock = null,
  status = null,
  // Optional preloaded <Explain> data per tile ({ money }); the page loads it
  // server-side, stories leave it out.
  explanations = {},
}) {
  const today = now instanceof Date ? now : new Date(now);
  const moneyRows = (overviewRows ?? (overview ? [overview] : [])).filter(
    (row) => toNumber(row?.cashflow_net) != null && (row.currency || overviewRows == null)
  );
  const money = moneyRows[0];
  // A fallback currency exists only when the household has exactly one.
  const currency = moneyRows.length === 1 ? money.currency || null : null;
  const nets = moneyRows.map((row) => toNumber(row.cashflow_net));
  const net = nets.length ? (nets.every((n) => n >= 0) ? 1 : -1) : null;
  const thisMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
  const lag = latestMonth ? monthsBetween(latestMonth, thisMonth) : null;
  const upcoming = [...upcomingCosts]
    .filter((row) => row.expected_date)
    .sort((a, b) => String(a.expected_date).localeCompare(String(b.expected_date)));
  const next = upcoming[0];
  const nextDays = next ? daysUntil(next.expected_date, today) : null;
  const urgent = attentionItems.filter((item) => Number(item.severity) >= 2);

  return (
    <div className="wall" data-compact={compact}>
      <header className="wallHeader">
        <div className="wallClock">{clock}</div>
        <div className="wallMeta">
          <span className="wallBrand">
            Kotona<span className="wallCursor" aria-hidden="true">_</span>
          </span>
          {status}
        </div>
      </header>

      <div className="wallStrip">
        <Tile label={money?.current_month ? `Money, ${formatMonth(money.current_month)}` : "Money"} tone={net == null ? "muted" : net >= 0 ? "ok" : "warn"}>
          {net == null ? (
            <p className="wallBig">No figures yet</p>
          ) : (
            <>
              {moneyRows.map((row) => {
                const rowNet = toNumber(row.cashflow_net);
                return (
                  <React.Fragment key={row.currency || "none"}>
                    <p className="wallBig">
                      {rowNet >= 0 ? "+" : "−"}
                      {formatMoney(Math.abs(rowNet), row.currency, { whole: true })}
                    </p>
                    <p className="wallLine">
                      {rowNet >= 0 ? "kept" : "overspent"} from {formatMoney(row.cashflow_income, row.currency, { whole: true })} in and{" "}
                      {formatMoney(row.cashflow_expense, row.currency, { whole: true })} out
                    </p>
                  </React.Fragment>
                );
              })}
              {explanations.money ? (
                <div className="wallExplain">
                  <ExplainBox
                    explanation={explanations.money}
                    tone="wall"
                    placement="start"
                    label={`Money, ${formatMonth(money.current_month)}`}
                    field="cashflow_net"
                  />
                </div>
              ) : null}
            </>
          )}
        </Tile>

        <Tile label="Next payment" tone={nextDays != null && nextDays <= 2 ? "warn" : "neutral"}>
          {next ? (
            <>
              <p className="wallBig">{dueLabel(nextDays)}</p>
              <p className="wallLine">
                {nextDays != null && nextDays > 1 ? "until " : ""}
                {next.contract_name}, {formatMoney(next.expected_amount, next.currency || currency)}
              </p>
            </>
          ) : (
            <p className="wallBig wallQuiet">Nothing due in 30 days</p>
          )}
        </Tile>

        <Tile label="Needs a decision" tone={urgent.length ? "warn" : attentionItems.length ? "accent" : "ok"}>
          <p className="wallBig">{attentionItems.length === 0 ? "All clear" : attentionItems.length}</p>
          {attentionItems.length ? (
            <ul className="wallList">
              {groupByTitle(attentionItems)
                .slice(0, 2)
                .map((item) => (
                  <li key={item.title}>
                    {item.title}
                    {item.count > 1 ? ` (${item.count})` : ""}
                  </li>
                ))}
            </ul>
          ) : null}
        </Tile>

        <Tile label="Data" tone={lag == null ? "muted" : lag > 1 ? "warn" : "ok"}>
          <p className="wallBig">{lag == null ? "No data" : lag <= 1 ? "Current" : `${lag} mo old`}</p>
          <p className="wallLine">
            {latestMonth ? `newest transactions ${formatMonth(latestMonth)}` : "upload a statement to begin"}
            {bridge ? `. Home bridge ${bridge.connected ? "connected" : bridge.enabled ? "offline" : "off"}.` : ""}
          </p>
        </Tile>

        {!compact ? (
          <Tile label="Utilities" tone={utilityLatest ? "neutral" : "muted"}>
            {utilityLatest ? (
              <>
                {(utilityLatest.totals ?? [{ currency: utilityLatest.currency ?? currency, total: utilityLatest.total }]).map(
                  (entry) => (
                    <p className="wallBig" key={entry.currency || "none"}>
                      {formatMoney(entry.total, entry.currency, { whole: true })}
                    </p>
                  )
                )}
                <p className="wallLine">billed for {formatMonth(utilityLatest.month)}</p>
              </>
            ) : (
              <p className="wallBig wallQuiet">No bills yet</p>
            )}
          </Tile>
        ) : null}
      </div>

      <div className="wallGrid">
        <ServicesPanel data={services} />
        {!compact ? <EventFeed data={events} /> : null}
        <DevicePanel data={devices} />
        <PowerChart data={power} />

        <footer className="wallTicker" data-area="ticker" aria-label="Upcoming payments">
          {upcoming.length ? (
            upcoming.slice(0, 6).map((row) => (
              <span key={`${row.contract_name}-${row.expected_date}`}>
                {shortDate(row.expected_date)} {row.contract_name}{" "}
                {formatMoney(row.expected_amount, row.currency || currency, { whole: true })}
              </span>
            ))
          ) : (
            <span>No payments due in 30 days</span>
          )}
          {!compact ? (
            <span className="wallHotkeys" data-hotkeys="true">
              R refresh · P pause
            </span>
          ) : null}
        </footer>
      </div>
    </div>
  );
}
