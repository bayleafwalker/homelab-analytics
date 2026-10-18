import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { AsOfScrubber } from "@/components/as-of-scrubber";
import { ExplainBox } from "@/components/explain";
import { CashflowFlowList, CashflowLedger, CashflowSankey, BUCKET_COLOR } from "@/components/cashflow-sankey";
import { StatePanel } from "@/components/state-panel";
import { TrendBars } from "@/components/trend-bars";
import { getCashflowMap, getCurrentUser } from "@/lib/backend";
import { loadExplanation } from "@/lib/explain";
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

export default async function CashflowPage({ searchParams }) {
  const requestedMonth = MONTH_RE.test(searchParams?.m || "") ? searchParams.m : undefined;
  const includeTransfers = searchParams?.transfers === "include";
  const focusId = typeof searchParams?.focus === "string" ? searchParams.focus : null;

  const [user, payload] = await Promise.all([
    getCurrentUser(),
    getCashflowMap({ month: requestedMonth, includeTransfers }),
  ]);
  const publications = payload?.provenance?.publications || [];
  // Lineage for every publication the map reads, plus (admins only, inside
  // loadExplanation) each publication's confidence verdict.
  const explanations = await Promise.all(publications.map((key) => loadExplanation(key, { user })));
  const sentenceExplanation =
    explanations.find((item) => item.publicationKey === "mart_monthly_cashflow_by_counterparty") ||
    explanations[0] ||
    null;

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
      <AsOfScrubber
        months={payload?.months_available || []}
        value={month}
        hrefFor={(value) => hrefFor({ month: value, transfers: includeTransfers })}
        label="Choose the month to map"
      />
      {Number(totals.transfers || 0) > 0 || includeTransfers ? (
        <p className="cashflowBar">
          <Link
            className="inlineLink cashflowToggle"
            href={hrefFor({ month, transfers: !includeTransfers, focus: focusId })}
          >
            {includeTransfers ? "Hide transfers between own accounts" : "Show transfers between own accounts"}
          </Link>
        </p>
      ) : null}

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
            {sentenceExplanation ? (
              <div className="cashflowExplain">
                <ExplainBox
                  explanation={sentenceExplanation}
                  label={drawn > 0 ? `Drawn from savings, ${formatMonth(month)}` : `Kept, ${formatMonth(month)}`}
                  filter={{ booking_month: month }}
                  placement="start"
                  note={`Money in minus money out, summed per payee for ${formatMonth(month)}${includeTransfers ? "" : ", leaving out transfers between own accounts"}. The total is checked against the monthly cashflow mart and any gap is listed under How the map is built.`}
                />
              </div>
            ) : null}
            <CashflowLedger payload={payload} />
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
                {explanations.map((explanation) => (
                  <li key={explanation.publicationKey}>
                    <code>{explanation.publicationKey}</code>
                    <ExplainBox
                      explanation={explanation}
                      label={explanation.publicationName || explanation.publicationKey}
                      filter={{ booking_month: month }}
                      placement="start"
                    />
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </>
      )}
    </AppShell>
  );
}
