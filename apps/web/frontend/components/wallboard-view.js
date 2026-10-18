import React from "react";

import { formatMoney, formatMonth, monthsBetween, toNumber } from "../lib/format";
import { ExplainBox } from "./explain";

// Ambient household status for a wall tablet or TV. Read from across the
// room: mono type only, nothing under 18px, one big number per tile, colour
// reserved for state. Data arrives as props so the view renders identically
// in Storybook and on the live /wallboard route.

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

function Tile({ label, tone = "neutral", wide = false, children }) {
  return (
    <section className="wallTile" data-tone={tone} data-wide={wide}>
      <h2 className="wallTileLabel">{label}</h2>
      {children}
    </section>
  );
}

export function WallboardView({
  now,
  overview,
  attentionItems = [],
  upcomingCosts = [],
  services = [],
  bridge = null,
  latestMonth = null,
  utilityLatest = null,
  compact = false,
  clock = null,
  status = null,
  // Optional preloaded <Explain> data per tile ({ money, data }); the page
  // loads it server-side, stories leave it out.
  explanations = {},
}) {
  const today = now instanceof Date ? now : new Date(now);
  const currency = overview?.currency || null;
  const net = toNumber(overview?.cashflow_net);
  const thisMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
  const lag = latestMonth ? monthsBetween(latestMonth, thisMonth) : null;
  const upcoming = [...upcomingCosts]
    .filter((row) => row.expected_date)
    .sort((a, b) => String(a.expected_date).localeCompare(String(b.expected_date)));
  const next = upcoming[0];
  const nextDays = next ? daysUntil(next.expected_date, today) : null;
  const urgent = attentionItems.filter((item) => Number(item.severity) >= 2);
  const servicesDown = services.filter((row) => {
    const state = String(row.status || row.health_status || row.state || "").toLowerCase();
    return state && !["ok", "healthy", "up", "running"].includes(state);
  });

  return (
    <div className="wall" data-compact={compact}>
      <header className="wallHeader">
        <div className="wallClock">{clock}</div>
        <div className="wallMeta">
          <span className="wallBrand">Kotona</span>
          {status}
        </div>
      </header>

      <div className="wallGrid">
        <Tile label={overview?.current_month ? `Money, ${formatMonth(overview.current_month)}` : "Money"} tone={net == null ? "muted" : net >= 0 ? "ok" : "warn"} wide>
          {net == null ? (
            <p className="wallBig">No figures yet</p>
          ) : (
            <>
              <p className="wallBig">
                {net >= 0 ? "+" : "−"}
                {formatMoney(Math.abs(net), currency, { whole: true })}
              </p>
              <p className="wallLine">
                {net >= 0 ? "kept" : "overspent"} from {formatMoney(overview.cashflow_income, currency, { whole: true })} in and{" "}
                {formatMoney(overview.cashflow_expense, currency, { whole: true })} out
              </p>
              {explanations.money ? (
                <div className="wallExplain">
                  <ExplainBox
                    explanation={explanations.money}
                    tone="wall"
                    placement="start"
                    label={`Money, ${formatMonth(overview.current_month)}`}
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
                .slice(0, compact ? 2 : 3)
                .map((item) => (
                  <li key={item.title}>
                    {item.title}
                    {item.count > 1 ? ` (${item.count})` : ""}
                  </li>
                ))}
            </ul>
          ) : null}
        </Tile>

        {!compact ? (
          <Tile label="Homelab" tone={services.length === 0 ? "muted" : servicesDown.length ? "warn" : "ok"}>
            {services.length === 0 ? (
              <>
                <p className="wallBig wallQuiet">No services reporting</p>
                <p className="wallLine">Connect the homelab bridge to see service health here.</p>
              </>
            ) : (
              <>
                <p className="wallBig">
                  {services.length - servicesDown.length}/{services.length} up
                </p>
                {servicesDown.length ? (
                  <ul className="wallList">
                    {servicesDown.slice(0, 3).map((row) => (
                      <li key={row.service_id || row.service_name}>{row.service_name || row.service_id} is {row.status}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="wallLine">every service healthy</p>
                )}
              </>
            )}
          </Tile>
        ) : null}

        {!compact ? (
          <Tile label="Utilities" tone="neutral">
            {utilityLatest ? (
              <>
                <p className="wallBig">{formatMoney(utilityLatest.total, currency, { whole: true })}</p>
                <p className="wallLine">billed for {formatMonth(utilityLatest.month)}</p>
              </>
            ) : (
              <p className="wallBig wallQuiet">No bills yet</p>
            )}
          </Tile>
        ) : null}

        <Tile label="Data" tone={lag == null ? "muted" : lag > 1 ? "warn" : "ok"}>
          <p className="wallBig">{lag == null ? "No data" : lag <= 1 ? "Current" : `${lag} mo old`}</p>
          <p className="wallLine">
            {latestMonth ? `newest transactions ${formatMonth(latestMonth)}` : "upload a statement to begin"}
            {bridge ? `. Home bridge ${bridge.connected ? "connected" : bridge.enabled ? "offline" : "off"}.` : ""}
          </p>
        </Tile>
      </div>

      {!compact && upcoming.length ? (
        <footer className="wallTicker" aria-label="Upcoming payments">
          {upcoming.slice(0, 6).map((row) => (
            <span key={`${row.contract_name}-${row.expected_date}`}>
              {shortDate(row.expected_date)} {row.contract_name}{" "}
              {formatMoney(row.expected_amount, row.currency || currency, { whole: true })}
            </span>
          ))}
        </footer>
      ) : null}
    </div>
  );
}
