import React from "react";

import { formatMoney } from "../lib/format";

// Plain-SVG Sankey for the /reports/cashflow-map payload. Layout is computed
// here from node amounts; no chart library. Four columns:
//   0 income sources | 1 money in | 2 regular / occasional / kept | 3 destinations

const VIEW_W = 1160;
const COLUMN_X = [176, 420, 664, 900];
const NODE_W = 14;
const PLOT_H = 500;
const GAP = 12;
const LABEL_SLOT = 38;
const TOP = 34;

export const BUCKET_COLOR = {
  income: "var(--ok)",
  savings_draw: "var(--warn)",
  pool: "var(--ink)",
  regular: "var(--accent-cool)",
  spending: "var(--accent-cool)",
  occasional: "var(--accent-warm)",
  kept: "var(--accent)",
};

const COLUMN_HEADINGS = ["Came from", "Money in", "Went to", "Paid to"];

function amountOf(node) {
  const value = Number(node.amount);
  return Number.isFinite(value) ? value : 0;
}

// Returns positioned nodes and link bands. Exported for tests and stories.
export function layoutCashflowMap(payload) {
  const nodes = payload?.nodes || [];
  const links = payload?.links || [];
  if (!nodes.length) return { nodes: [], links: [], height: 0 };

  const byColumn = [0, 1, 2, 3].map((column) => nodes.filter((node) => node.column === column));
  const inflow = byColumn[0].reduce((sum, node) => sum + amountOf(node), 0) || 1;
  const maxCount = Math.max(...byColumn.map((column) => column.length));
  const scale = (PLOT_H - GAP * Math.max(0, maxCount - 1)) / inflow;

  // Bucket colour per node: destinations inherit their bucket's colour.
  const bucketOf = {};
  for (const link of links) {
    if (link.source.startsWith("bucket:")) bucketOf[link.target] = link.source.slice(7);
  }

  const positioned = {};
  let height = 0;
  byColumn.forEach((columnNodes, column) => {
    let y = TOP;
    const labelled = column === 0 || column === 3;
    for (const node of columnNodes) {
      const h = Math.max(2, amountOf(node) * scale);
      const slot = labelled ? Math.max(h, LABEL_SLOT) : h;
      const kind = column === 3 ? bucketOf[node.id] || node.kind : node.kind;
      positioned[node.id] = {
        ...node,
        x: COLUMN_X[column],
        y,
        h,
        color: BUCKET_COLOR[kind] || "var(--muted)",
        outOffset: 0,
        inOffset: 0,
      };
      y += slot + GAP;
    }
    height = Math.max(height, y);
  });

  const bands = [];
  for (const link of links) {
    const source = positioned[link.source];
    const target = positioned[link.target];
    if (!source || !target) continue;
    const w = Math.max(1, Number(link.amount) * scale);
    const y0 = source.y + source.outOffset;
    const y1 = target.y + target.inOffset;
    source.outOffset += w;
    target.inOffset += w;
    const x0 = source.x + NODE_W;
    const x1 = target.x;
    const xm = (x0 + x1) / 2;
    bands.push({
      ...link,
      w,
      color: target.column >= 2 ? target.color : source.color,
      d:
        `M${x0},${y0} C${xm},${y0} ${xm},${y1} ${x1},${y1} ` +
        `L${x1},${y1 + w} C${xm},${y1 + w} ${xm},${y0 + w} ${x0},${y0 + w} Z`,
      sourceLabel: source.label,
      targetLabel: target.label,
    });
  }
  return { nodes: Object.values(positioned), links: bands, height: height + 8 };
}

function linkTouches(link, focusId, focusBucket) {
  if (!focusId) return true;
  if (link.source === focusId || link.target === focusId) return true;
  return focusBucket ? link.target === focusBucket : false;
}

export function CashflowSankey({ payload, focusId = null, hrefForNode, titleId = "cashflow-map-title" }) {
  const layout = layoutCashflowMap(payload);
  const currency = payload?.currency;
  if (!layout.nodes.length) return null;
  const focusBucket = focusId
    ? (payload.links.find((link) => link.target === focusId && link.source.startsWith("bucket:")) || {}).source
    : null;
  const descId = `${titleId}-desc`;

  return (
    <svg
      className="sankey"
      viewBox={`0 0 ${VIEW_W} ${layout.height}`}
      role="group"
      aria-labelledby={titleId}
      aria-describedby={descId}
      data-focus={focusId ? "true" : "false"}
    >
      <desc id={descId}>
        Money flowing from income sources on the left, through money in, to regular spending,
        occasional spending and money kept, then to payees on the right. The table below lists
        the same figures.
      </desc>
      {COLUMN_HEADINGS.map((heading, column) => (
        <text
          key={heading}
          x={column === 0 ? COLUMN_X[0] + NODE_W : COLUMN_X[column]}
          y={14}
          textAnchor={column === 0 ? "end" : "start"}
          className="sankeyHeading"
        >
          {heading}
        </text>
      ))}
      <g className="sankeyLinks">
        {layout.links.map((link) => (
          <path
            key={`${link.source}>${link.target}`}
            d={link.d}
            fill={link.color}
            className="sankeyLink"
            data-dim={linkTouches(link, focusId, focusBucket) ? "false" : "true"}
          >
            <title>
              {`${link.sourceLabel} to ${link.targetLabel}: ${formatMoney(link.amount, currency)}`}
            </title>
          </path>
        ))}
      </g>
      <g className="sankeyNodes">
        {layout.nodes.map((node) => {
          const labelLeft = node.column === 0 || node.column === 2 || node.column === 1;
          const tx = labelLeft ? node.x - 10 : node.x + NODE_W + 10;
          const anchor = labelLeft ? "end" : "start";
          const ty = node.column === 0 || node.column === 3 ? node.y + 13 : node.y + 15;
          const href = hrefForNode && node.column === 3 ? hrefForNode(node) : null;
          const focused = focusId === node.id;
          const amountText = `${formatMoney(node.amount, currency)}${node.column >= 2 ? "  00%" : ""}`;
          // Middle-column labels sit over flow bands; a paper chip keeps them legible.
          const chipW = Math.max(node.label.length * 7.7, amountText.length * 6.7) + 14;
          const body = (
            <>
              {node.column === 1 || node.column === 2 ? (
                <rect
                  x={tx - chipW + 6}
                  y={ty - 15}
                  width={chipW}
                  height={38}
                  rx={7}
                  className="sankeyChip"
                />
              ) : null}
              <rect
                x={node.x}
                y={node.y}
                width={NODE_W}
                height={node.h}
                rx={3}
                fill={node.color}
                className="sankeyNode"
              />
              <text x={tx} y={ty} textAnchor={anchor} className="sankeyLabel" data-focus={focused}>
                {node.label}
              </text>
              <text x={tx} y={ty + 17} textAnchor={anchor} className="sankeyAmount">
                {formatMoney(node.amount, currency)}
                {node.column >= 2 ? `  ${Math.round(node.share * 100)}%` : ""}
              </text>
            </>
          );
          return href ? (
            <a
              key={node.id}
              href={href}
              className="sankeyNodeLink"
              aria-label={`${node.label}, ${formatMoney(node.amount, currency)}. Show the last six months`}
              aria-current={focused ? "true" : undefined}
            >
              {body}
            </a>
          ) : (
            <g key={node.id}>{body}</g>
          );
        })}
      </g>
    </svg>
  );
}

// Same figures as stacked bars, for narrow screens and as the readable
// alternative to the SVG.
export function CashflowFlowList({ payload, focusId = null, hrefForNode }) {
  const nodes = payload?.nodes || [];
  const links = payload?.links || [];
  const currency = payload?.currency;
  const buckets = nodes.filter((node) => node.column === 2);
  const sources = nodes.filter((node) => node.column === 0);
  const childrenOf = (bucketId) =>
    links
      .filter((link) => link.source === bucketId)
      .map((link) => nodes.find((node) => node.id === link.target))
      .filter(Boolean);
  const pct = (node) => `${Math.max(1, Math.round(node.share * 100))}%`;
  return (
    <div className="flowList">
      <section className="flowGroup">
        <h3 className="flowGroupHead">
          <span>Came from</span>
          <span className="numMono">
            {formatMoney(sources.reduce((sum, node) => sum + Number(node.amount), 0), currency)}
          </span>
        </h3>
        <ul>
          {sources.map((node) => (
            <li key={node.id} className="flowRow">
              <span className="flowRowLabel">{node.label}</span>
              <span className="numMono">{formatMoney(node.amount, currency)}</span>
              <span className="flowBar" style={{ width: pct(node), background: BUCKET_COLOR[node.kind] }} />
            </li>
          ))}
        </ul>
      </section>
      {buckets.map((bucket) => (
        <section className="flowGroup" key={bucket.id}>
          <h3 className="flowGroupHead">
            <span>{bucket.label}</span>
            <span className="numMono">
              {formatMoney(bucket.amount, currency)} <span className="muted">{pct(bucket)}</span>
            </span>
          </h3>
          <ul>
            {childrenOf(bucket.id).map((node) => (
              <li key={node.id} className="flowRow" data-focus={focusId === node.id}>
                {hrefForNode ? (
                  <a className="flowRowLabel inlineLink" href={hrefForNode(node)}>
                    {node.label}
                  </a>
                ) : (
                  <span className="flowRowLabel">{node.label}</span>
                )}
                <span className="numMono">{formatMoney(node.amount, currency)}</span>
                <span className="flowBar" style={{ width: pct(node), background: BUCKET_COLOR[bucket.kind] }} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
