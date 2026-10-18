import React from "react";
import Link from "next/link";

import { formatMoney, formatMonth, formatPercent, toNumber } from "../lib/format";
import { CommandPalette } from "./command-palette";
import { ConsolePanel, ConsoleShell } from "./console-shell";
import { ExplainBox } from "./explain";
import { HeatGrid } from "./heat-grid";
import { ResponsiveTable } from "./responsive-table";
import { Spark } from "./spark";

// <ConsoleView> — the six Ops Console panels over preloaded reporting data.
// Pure presentation so pages and stories share it; app/console/page.js does
// the fetching. Every figure is right-aligned, tabular, with no thousands
// separators.
//
//   F1 cashflow ticker | F2 spend heatmap    | F3 attention
//   F4 runs tail       | F5 categories+ratios| command stub (Cmd+K)

export const CONSOLE_PANELS = [
  { id: "cashflow", fkey: "F1", label: "cashflow" },
  { id: "heatmap", fkey: "F2", label: "heatmap" },
  { id: "attention", fkey: "F3", label: "attention" },
  { id: "runs", fkey: "F4", label: "runs" },
  { id: "categories", fkey: "F5", label: "categories" },
];

const RUNS_TAIL = 8;
const ATTENTION_LIMIT = 6;
const CATEGORY_LIMIT = 6;
const SCROLLBACK_LIMIT = 7;
const UNCATEGORISED = "Uncategorised";

function money(value, currency, options = {}) {
  return formatMoney(value, currency, { grouping: false, ...options });
}

// severity: 3 = high ... 1 = low; S1 is the most urgent.
export function severityRank(severity) {
  const value = Number(severity);
  if (value >= 3) return "S1";
  if (value === 2) return "S2";
  return "S3";
}

// "2025-11" -> "Nov ’25": short enough for the sparkline axis, still unique.
function shortMonth(value) {
  const label = formatMonth(value, { short: true });
  return /^\w{3} \d{4}$/.test(label) ? `${label.slice(0, 3)} ’${label.slice(-2)}` : label;
}

export function summariseCashflow(rows) {
  const ordered = [...(rows || [])]
    .filter((row) => row && row.booking_month)
    .sort((a, b) => String(a.booking_month).localeCompare(String(b.booking_month)));
  const latest = ordered.at(-1) || null;
  const previous = ordered.at(-2) || null;
  const net = latest ? toNumber(latest.net) : null;
  const previousNet = previous ? toNumber(previous.net) : null;
  return {
    latest,
    previous,
    net,
    delta: net != null && previousNet != null ? net - previousNet : null,
    series: ordered.slice(-12).map((row) => toNumber(row.net) || 0),
    labels: ordered.slice(-12).map((row) => shortMonth(row.booking_month)),
  };
}

export function topCategories(rows, limit = CATEGORY_LIMIT) {
  const months = [...new Set((rows || []).map((row) => row.booking_month).filter(Boolean))].sort();
  const month = months.at(-1) || null;
  const totals = new Map();
  for (const row of rows || []) {
    if (row.booking_month !== month) continue;
    const key = row.category || UNCATEGORISED;
    totals.set(key, (totals.get(key) || 0) + (toNumber(row.total_expense) || 0));
  }
  const sorted = [...totals.entries()]
    .map(([category, total]) => ({ category, total }))
    .sort((a, b) => b.total - a.total);
  return {
    month,
    rows: sorted.slice(0, limit),
    rest: sorted.slice(limit).reduce((sum, row) => sum + row.total, 0),
    restCount: Math.max(0, sorted.length - limit),
  };
}

function ratioLabel(name) {
  return String(name || "")
    .replace(/_/g, " ")
    .replace(/\bto\b/, "/");
}

function stamp(value) {
  if (!value) return "--";
  return String(value).replace("T", " ").slice(5, 16);
}

function CashflowTicker({ cashflowRows, currency, explanation }) {
  const summary = summariseCashflow(cashflowRows);
  if (!summary.latest) {
    return <p className="consoleEmpty">No cashflow published yet.</p>;
  }
  const { latest, net, delta } = summary;
  const tone = net >= 0 ? "ok" : "warn";
  return (
    <div className="ticker">
      <p className="tickerMonth">{formatMonth(latest.booking_month)}</p>
      <p className="tickerNet num" data-tone={tone}>
        {money(net, currency, { signed: true })}
      </p>
      <dl className="consoleFigures">
        <div>
          <dt>in</dt>
          <dd className="num">{money(latest.income, currency)}</dd>
        </div>
        <div>
          <dt>out</dt>
          <dd className="num">{money(latest.expense, currency)}</dd>
        </div>
        <div>
          <dt>vs {summary.previous ? formatMonth(summary.previous.booking_month, { short: true }) : "prev"}</dt>
          <dd className="num" data-tone={delta == null ? "neutral" : delta >= 0 ? "ok" : "warn"}>
            {delta == null ? "—" : money(delta, currency, { signed: true })}
          </dd>
        </div>
      </dl>
      {summary.series.length > 1 ? (
        <div className="tickerSpark">
          <Spark values={summary.series} labels={summary.labels} label="net" color="var(--retro-accent)" height={56} width={320} />
        </div>
      ) : null}
      {explanation ? (
        <div className="consoleExplain">
          <ExplainBox
            explanation={explanation}
            tone="wall"
            placement="start"
            label={`Net cashflow, ${formatMonth(latest.booking_month)}`}
            field="net"
          />
        </div>
      ) : null}
    </div>
  );
}

function HeatmapPanelBody({ heatmap }) {
  if (!heatmap) return <p className="consoleEmpty">Spend heatmap unavailable.</p>;
  return (
    <>
      <p className="consoleMeta">
        {heatmap.window_start && heatmap.window_end ? (
          <>
            <span className="num">{heatmap.window_days}</span>d to {heatmap.window_end}
            {" · "}
            <span className="num">{money(heatmap.totals?.expense, heatmap.currency)}</span> over{" "}
            <span className="num">{heatmap.totals?.transaction_count ?? 0}</span> payments
          </>
        ) : (
          "No spending recorded yet."
        )}
      </p>
      <HeatGrid heatmap={heatmap} compact />
    </>
  );
}

function AttentionList({ items }) {
  const ordered = [...(items || [])].sort((a, b) => Number(b.severity || 0) - Number(a.severity || 0));
  if (ordered.length === 0) return <p className="consoleEmpty">Nothing needs attention.</p>;
  const shown = ordered.slice(0, ATTENTION_LIMIT);
  return (
    <>
      <ol className="consoleAttentionList">
        {shown.map((item) => {
          const rank = severityRank(item.severity);
          return (
            <li key={item.item_id || item.title} className="consoleAttentionItem" data-rank={rank}>
              <span className="consoleAttentionRank">{rank}</span>
              <span className="consoleAttentionTitle">{item.title}</span>
            </li>
          );
        })}
      </ol>
      {ordered.length > shown.length ? (
        <p className="consoleMeta">
          <Link className="consoleLink" href="/operating-picture">
            +{ordered.length - shown.length} more in the operating picture
          </Link>
        </p>
      ) : null}
    </>
  );
}

const RUN_COLUMNS = [
  {
    key: "created_at",
    header: "When",
    primary: true,
    cell: (run) => (
      <Link className="consoleLink" href={`/runs/${run.run_id}`}>
        <time dateTime={run.created_at}>{stamp(run.created_at)}</time>
      </Link>
    ),
  },
  {
    key: "status",
    header: "Status",
    cell: (run) => (
      <span className="runStatus" data-status={run.status}>
        {run.status}
      </span>
    ),
  },
  { key: "dataset_name", header: "Dataset" },
  { key: "row_count", header: "Rows", align: "end", cell: (run) => <span className="num">{run.row_count ?? "—"}</span> },
];

function RunsTail({ runs }) {
  const tail = (runs || []).slice(0, RUNS_TAIL);
  return (
    <ResponsiveTable
      label="Latest ingestion runs"
      columns={RUN_COLUMNS}
      rows={tail}
      rowKey="run_id"
      dense
      empty={<p className="consoleEmpty">No runs yet.</p>}
    />
  );
}

function CategoryBars({ categoryRows, ratios, currency }) {
  const { month, rows, rest, restCount } = topCategories(categoryRows);
  const peak = rows[0]?.total || 0;
  return (
    <div className="categoryPanel">
      {rows.length === 0 ? (
        <p className="consoleEmpty">No category spend yet.</p>
      ) : (
        <>
          <p className="consoleMeta">{formatMonth(month)}</p>
          <ul className="barList">
            {rows.map((row) => (
              <li key={row.category} className="barRow">
                <span className="barLabel">{row.category}</span>
                <span className="barTrack" aria-hidden="true">
                  <span className="barFill" style={{ width: `${peak ? Math.max(2, (row.total / peak) * 100) : 0}%` }} />
                </span>
                <span className="barValue num">{money(row.total, currency)}</span>
              </li>
            ))}
            {restCount > 0 ? (
              <li className="barRow" data-rest="true">
                <span className="barLabel">+{restCount} more</span>
                <span className="barTrack" aria-hidden="true" />
                <span className="barValue num">{money(rest, currency)}</span>
              </li>
            ) : null}
          </ul>
        </>
      )}
      {ratios && ratios.length ? (
        <dl className="consoleRatioList">
          {ratios.map((ratio) => (
            <div key={ratio.ratio_name} className="consoleRatioRow" data-state={ratio.state}>
              <dt>{ratioLabel(ratio.ratio_name)}</dt>
              <dd className="num">{formatPercent(ratio.ratio, { fromRatio: true })}</dd>
              <dd className="consoleRatioState">{ratio.assessment}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

function verdictTone(verdict) {
  if (verdict === "trustworthy") return "ok";
  if (verdict === "unreliable" || verdict === "degraded") return "warn";
  return "muted";
}

export function confidenceScrollback(publications, limit = SCROLLBACK_LIMIT) {
  return [...(publications || [])]
    .filter((row) => row && row.assessed_at)
    .sort((a, b) => String(b.assessed_at).localeCompare(String(a.assessed_at)))
    .slice(0, limit)
    .reverse();
}

export function ConsoleKeyMap() {
  return (
    <div className="keyMapWrap" role="group" aria-label="Keyboard map">
      <dl className="keyMap">
        {CONSOLE_PANELS.map((panel) => (
          <div key={panel.fkey}>
            <dt>
              <kbd>{panel.fkey}</kbd>
            </dt>
            <dd>{panel.label}</dd>
          </div>
        ))}
        <div>
          <dt>
            <kbd>Ctrl/⌘ K</kbd>
          </dt>
          <dd>jump</dd>
        </div>
      </dl>
    </div>
  );
}

function CommandStub({ confidence, confidenceRestricted, paletteEntries, currentPath }) {
  const lines = confidenceScrollback(confidence);
  return (
    <div className="commandStub">
      <ol className="scrollback" aria-label="Recent confidence checks">
        {confidenceRestricted ? (
          <li className="scrollLine" data-tone="muted">
            confidence log needs the admin role
          </li>
        ) : lines.length === 0 ? (
          <li className="scrollLine" data-tone="muted">
            no confidence checks recorded yet
          </li>
        ) : (
          lines.map((row) => (
            <li key={row.publication_key} className="scrollLine" data-tone={verdictTone(row.confidence_verdict)}>
              <time dateTime={row.assessed_at}>{stamp(row.assessed_at)}</time>{" "}
              <span className="scrollKey">{row.publication_key}</span>{" "}
              <span className="scrollVerdict">{row.confidence_verdict}</span>{" "}
              <span className="num">{row.completeness_pct ?? 0}%</span>
            </li>
          ))
        )}
      </ol>
      <div className="commandLine">
        <span className="commandPrompt" aria-hidden="true">
          &gt;
        </span>
        <CommandPalette entries={paletteEntries || []} currentPath={currentPath} />
        <span className="commandCursor" aria-hidden="true" />
      </div>
    </div>
  );
}

export function ConsoleView({
  now,
  user,
  currency,
  cashflowRows,
  heatmap,
  attentionItems,
  runs,
  categoryRows,
  ratios,
  confidence,
  confidenceRestricted = false,
  paletteEntries,
  currentPath = "/console",
  explanations = {},
}) {
  const openAttention = (attentionItems || []).length;
  const failedRuns = (runs || []).slice(0, RUNS_TAIL).filter((run) => run.status === "failed" || run.status === "rejected").length;
  return (
    <ConsoleShell
      user={user}
      stamp={now}
      status={[
        { label: "attention", value: openAttention, tone: openAttention ? "warn" : "ok" },
        { label: "failed runs", value: failedRuns, tone: failedRuns ? "warn" : "ok" },
      ]}
    >
      <ConsolePanel id="cashflow" fkey="F1" title="Cashflow">
        <CashflowTicker cashflowRows={cashflowRows} currency={currency} explanation={explanations.cashflow} />
      </ConsolePanel>
      <ConsolePanel id="heatmap" fkey="F2" title="Spend heatmap">
        <HeatmapPanelBody heatmap={heatmap} />
      </ConsolePanel>
      <ConsolePanel id="attention" fkey="F3" title="Attention">
        <AttentionList items={attentionItems} />
      </ConsolePanel>
      <ConsolePanel id="runs" fkey="F4" title="Runs">
        <RunsTail runs={runs} />
      </ConsolePanel>
      <ConsolePanel id="categories" fkey="F5" title="Categories">
        <CategoryBars categoryRows={categoryRows} ratios={ratios} currency={currency} />
      </ConsolePanel>
      <ConsolePanel id="command" title="Command" headerExtra={<ConsoleKeyMap />}>
        <CommandStub
          confidence={confidence}
          confidenceRestricted={confidenceRestricted}
          paletteEntries={paletteEntries}
          currentPath={currentPath}
        />
      </ConsolePanel>
    </ConsoleShell>
  );
}
