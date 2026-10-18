import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { CashflowFlowList, CashflowSankey, BUCKET_COLOR } from "@/components/cashflow-sankey";
import { StatePanel } from "@/components/state-panel";
import { TrendBars } from "@/components/trend-bars";
import {
  getCashflowMap,
  getCurrentUser,
  getPublicationConfidenceDetail,
  getPublicationLineage,
} from "@/lib/backend";
import { formatMoney, formatMonth, monthsBetween } from "@/lib/format";

function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

const MONTH_RE = /^\d{4}-\d{2}$/;

function hrefFor({ month, transfers, focus }) {
  const params = new URLSearchParams();
  if (month) params.set("m", month);
  if (transfers) params.set("transfers", "include");
  if (focus) params.set("focus", focus);
  const query = params.toString();
  return query ? `/cashflow?${query}` : "/cashflow";
}

async function safely(promise) {
  try {
    return await promise;
  } catch (error) {
    if (error && typeof error === "object" && "digest" in error && String(error.digest).startsWith("NEXT_REDIRECT")) {
      throw error;
    }
    return null;
  }
}

function confidenceTone(verdict) {
  if (verdict === "trustworthy") return "ok";
  if (verdict === "degraded" || verdict === "stale") return "warm";
  if (verdict === "unreliable" || verdict === "untrustworthy") return "warn";
  return "neutral";
}

export default async function CashflowPage({ searchParams }) {
  const requestedMonth = MONTH_RE.test(searchParams?.m || "") ? searchParams.m : undefined;
  const includeTransfers = searchParams?.transfers === "include";
  const focusId = typeof searchParams?.focus === "string" ? searchParams.focus : null;

  const [user, payload] = await Promise.all([
    getCurrentUser(),
    getCashflowMap({ month: requestedMonth, includeTransfers }),
  ]);
  const publications = payload?.provenance?.publications || [];
  const isAdmin = user?.role === "admin";
  const [lineage, confidence] = await Promise.all([
    Promise.all(publications.map((key) => safely(getPublicationLineage(key)))),
    isAdmin
      ? Promise.all(publications.map((key) => safely(getPublicationConfidenceDetail(key))))
      : Promise.resolve(publications.map(() => null)),
  ]);

  const month = payload?.month || null;
  const currency = payload?.currency || null;
  const money = (value, options) => formatMoney(value, currency, options);
  const totals = payload?.totals || {};
  const nodes = payload?.nodes || [];
  const disclosures = payload?.disclosures || [];
  const stale = disclosures.find((item) => item.code === "stale_data");
  const notes = disclosures.filter((item) => item.code !== "stale_data" && item.code !== "no_data");
  const focus = nodes.find((node) => node.id === focusId && node.column === 3) || null;
  const focusBucketLink = focus ? payload.links.find((link) => link.target === focus.id) : null;
  const focusBucket = focusBucketLink ? nodes.find((node) => node.id === focusBucketLink.source) : null;
  const buckets = nodes.filter((node) => node.column === 2);
  const spendingTotal = Number(totals.mapped_expense || 0);
  const kept = Number(totals.kept || 0);
  const drawn = Number(totals.drawn_from_savings || 0);
  const nodeHref = (node) =>
    hrefFor({ month, transfers: includeTransfers, focus: focusId === node.id ? null : node.id });

  // Destinations whose spend moved most against the previous month.
  const movers = nodes
    .filter((node) => node.column === 3 && node.trend?.length > 1 && !node.members?.length)
    .map((node) => ({ node, delta: Number(node.amount) - Number(node.trend.at(-2).amount) }))
    .filter((item) => Math.abs(item.delta) >= 0.5)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
    .slice(0, 5);

  // Disclosures carry raw numbers; restate the two that involve money or
  // dates in display formatting.
  const describeNote = (note) => {
    if (note.code === "transfers_excluded") {
      const count = payload.transfers.length;
      return `${count} pair${count === 1 ? "" : "s"} of matching payments in and out, ${money(totals.transfers)} in total, look like moves between your own accounts. They're left out so income and spending aren't counted twice.`;
    }
    return note.message;
  };
  const staleMessage = stale
    ? `The newest transactions are from ${formatMonth(payload.provenance.data_through)}, ${monthsBetween(payload.provenance.data_through, currentMonth())} months ago. Upload a newer statement to bring the map up to date.`
    : null;

  const focusTrend = focus?.trend || [];
  const focusPrev = focusTrend.length > 1 ? Number(focusTrend.at(-2).amount) : null;
  const focusAvg = focusTrend.length
    ? focusTrend.reduce((sum, point) => sum + Number(point.amount), 0) / focusTrend.length
    : null;

  return (
    <AppShell
      currentPath="/cashflow"
      user={user}
      title="Cashflow map"
      eyebrow={month ? formatMonth(month) : "Cashflow"}
      lede="Where the household's money came from and where it went, from published reporting."
    >
      <nav className="cashflowBar" aria-label="Month">
        {payload?.previous_month ? (
          <Link className="ghostButton" href={hrefFor({ month: payload.previous_month, transfers: includeTransfers })}>
            ← {formatMonth(payload.previous_month, { short: true })}
          </Link>
        ) : (
          <span className="ghostButton" aria-disabled="true" data-disabled="true">← Earlier</span>
        )}
        <form className="cashflowMonthForm" action="/cashflow" method="get">
          <label className="srOnly" htmlFor="cashflow-month">Month</label>
          <select id="cashflow-month" name="m" defaultValue={month || ""}>
            {(payload?.months_available || []).slice().reverse().map((value) => (
              <option key={value} value={value}>
                {formatMonth(value)}
              </option>
            ))}
          </select>
          {includeTransfers ? <input type="hidden" name="transfers" value="include" /> : null}
          <button className="ghostButton" type="submit">Show</button>
        </form>
        {payload?.next_month ? (
          <Link className="ghostButton" href={hrefFor({ month: payload.next_month, transfers: includeTransfers })}>
            {formatMonth(payload.next_month, { short: true })} →
          </Link>
        ) : (
          <span className="ghostButton" aria-disabled="true" data-disabled="true">Later →</span>
        )}
        {Number(totals.transfers || 0) > 0 || includeTransfers ? (
          <Link
            className="inlineLink cashflowToggle"
            href={hrefFor({ month, transfers: !includeTransfers, focus: focusId })}
          >
            {includeTransfers ? "Hide transfers between own accounts" : "Show transfers between own accounts"}
          </Link>
        ) : null}
      </nav>

      {stale ? (
        <StatePanel
          tone="stale"
          title="This map is built from old transactions"
          action={user?.role === "reader" ? null : { href: "/upload", label: "Upload a statement" }}
        >
          <p>{staleMessage}</p>
        </StatePanel>
      ) : null}

      {!nodes.length ? (
        <section className="panel section">
          <StatePanel
            tone="empty"
            title="No money flows to draw yet"
            action={user?.role === "reader" ? null : { href: "/upload", label: "Upload a statement" }}
          >
            <p>
              The map needs at least one month of published account transactions. Once a statement
              is imported, income and spending appear here as flows.
            </p>
          </StatePanel>
        </section>
      ) : (
        <>
          <section className="cashflowLede" aria-labelledby="cashflow-map-title">
            <h2 id="cashflow-map-title" className="cashflowSentence">
              {drawn > 0 ? (
                <>
                  {money(totals.mapped_income)} came in and {money(spendingTotal)} went out, so{" "}
                  <span className="cashflowFigure" data-tone="warn">{money(drawn)}</span> came from savings.
                </>
              ) : (
                <>
                  Of {money(totals.mapped_income)} that came in, {money(spendingTotal)} went to
                  spending and <span className="cashflowFigure" data-tone="kept">{money(kept)}</span> was kept.
                </>
              )}
            </h2>
            <dl className="cashflowLedger">
              {buckets.map((bucket) => (
                <div key={bucket.id} style={{ "--swatch": BUCKET_COLOR[bucket.kind] }}>
                  <dt>{bucket.label}</dt>
                  <dd className="numMono">
                    {money(bucket.amount)} <span className="muted">{Math.round(bucket.share * 100)}%</span>
                  </dd>
                </div>
              ))}
              {Number(totals.transfers || 0) > 0 ? (
                <div style={{ "--swatch": "var(--line-strong)" }}>
                  <dt>{includeTransfers ? "Transfers, included" : "Transfers, left out"}</dt>
                  <dd className="numMono">{money(totals.transfers)}</dd>
                </div>
              ) : null}
            </dl>
          </section>

          <section className="panel cashflowCanvas">
            <div className="cashflowSvgWrap">
              <CashflowSankey payload={payload} focusId={focus?.id || null} hrefForNode={nodeHref} />
            </div>
            <div className="cashflowFlowListWrap">
              <CashflowFlowList payload={payload} focusId={focus?.id || null} hrefForNode={nodeHref} />
            </div>
            <p className="cashflowCanvasHint muted">
              Select a payee to see its last six months. Hover a flow for its amount.
            </p>
          </section>

          <div className="cashflowDetail">
            <section className="panel section cashflowFocus" aria-live="polite">
              {focus ? (
                <>
                  <div className="sectionHeader">
                    <div>
                      <div className="eyebrow">{focusBucket?.label || "Spending"}</div>
                      <h2>{focus.label}</h2>
                    </div>
                    <Link className="inlineLink" href={hrefFor({ month, transfers: includeTransfers })}>
                      Clear selection
                    </Link>
                  </div>
                  <p className="cashflowFocusFigure numMono">
                    {money(focus.amount)}
                    <span className="muted"> in {formatMonth(month)}, {focus.transaction_count} transaction{focus.transaction_count === 1 ? "" : "s"}</span>
                  </p>
                  <TrendBars
                    points={focusTrend}
                    currency={currency}
                    selectedMonth={month}
                    color={BUCKET_COLOR[focusBucket?.kind] || "var(--accent-cool)"}
                  />
                  <p className="muted">
                    {focusAvg != null ? `Six-month average ${money(focusAvg)}.` : null}{" "}
                    {focusPrev != null
                      ? Number(focus.amount) > focusPrev
                        ? `Up ${money(Number(focus.amount) - focusPrev)} on the month before.`
                        : Number(focus.amount) < focusPrev
                          ? `Down ${money(focusPrev - Number(focus.amount))} on the month before.`
                          : "Same as the month before."
                      : null}
                  </p>
                  {focus.members?.length ? (
                    <p className="muted">Includes {focus.members.join(", ")}.</p>
                  ) : null}
                </>
              ) : (
                <>
                  <div className="eyebrow">Drill down</div>
                  <h2>{movers.length ? `Biggest changes since ${formatMonth(payload.previous_month, { short: true })}` : "Pick a payee"}</h2>
                  {movers.length ? (
                    <ul className="cashflowMovers">
                      {movers.map(({ node, delta }) => (
                        <li key={node.id}>
                          <Link className="inlineLink" href={nodeHref(node)}>
                            {node.label}
                          </Link>
                          <span className="numMono" data-tone={delta > 0 ? "up" : "down"}>
                            {money(delta, { signed: true })}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  <p className="muted">
                    Select any payee to see what it cost over the last six months and how this
                    month compares.
                  </p>
                </>
              )}
            </section>

            <section className="panel section cashflowProvenance" aria-labelledby="cashflow-provenance">
              <div className="eyebrow">Explain these numbers</div>
              <h2 id="cashflow-provenance">How the map is built</h2>
              <p className="muted">
                Built from {payload.provenance.transaction_count} transactions in {formatMonth(month)}.
                Newest data: {formatMonth(payload.provenance.data_through)}.
                Payees count as regular when they were paid in at least three of the last four months.
              </p>
              {notes.length ? (
                <ol className="cashflowNotes">
                  {notes.map((note) => (
                    <li key={note.code} data-severity={note.severity}>
                      {describeNote(note)}
                    </li>
                  ))}
                </ol>
              ) : null}
              {payload.transfers.length ? (
                <details className="cashflowTransfers">
                  <summary>
                    {payload.transfers.length} matched transfer{payload.transfers.length === 1 ? "" : "s"}
                  </summary>
                  <ul>
                    {payload.transfers.map((transfer) => (
                      <li key={`${transfer.expense_counterparty}>${transfer.income_counterparty}`}>
                        {transfer.expense_counterparty} → {transfer.income_counterparty}{" "}
                        <span className="numMono">{money(transfer.amount)}</span>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
              <h3 className="cashflowSubhead">Publications read</h3>
              <ul className="cashflowSources">
                {publications.map((key, index) => {
                  const graph = lineage[index];
                  const upstream = graph ? Math.max(0, (graph.nodes || []).length - 1) : null;
                  const verdict = confidence[index]?.confidence_verdict;
                  return (
                    <li key={key}>
                      {isAdmin ? (
                        <Link className="inlineLink" href={`/control/lineage?publication_key=${encodeURIComponent(key)}`}>
                          <code>{key}</code>
                        </Link>
                      ) : (
                        <code>{key}</code>
                      )}
                      <span className="muted">
                        {upstream == null
                          ? "lineage unavailable"
                          : upstream === 0
                            ? "no lineage recorded yet"
                            : `${upstream} upstream node${upstream === 1 ? "" : "s"}`}
                      </span>
                      {verdict ? (
                        <span className="pill" data-tone={confidenceTone(verdict)}>
                          {verdict}
                        </span>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </section>
          </div>
        </>
      )}
    </AppShell>
  );
}
