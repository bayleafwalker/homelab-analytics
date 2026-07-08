import React from "react";
import Link from "next/link";

import { Eyebrow } from "./eyebrow";
import { FreshnessPulse } from "./freshness-pulse";
import { HorizonStrip } from "./horizon-strip";
import { NumMono } from "./num-mono";
import { Pill } from "./pill";
import { Spark } from "./spark";
import { stateIndicatorBadge } from "../lib/state-indicators";

const ATTENTION_TONE = {
  1: { tone: "warn", label: "urgent" },
  2: { tone: "warm", label: "soon" },
};

function attentionMeta(severity) {
  return ATTENTION_TONE[severity] || { tone: "neutral", label: "watch" };
}

// Pure, presentational view for the Operating Picture v2 layout. Page.js
// fetches data and reduces it to plain props; this component owns no
// data fetching, which is what lets it render inside Storybook (and any
// future test harness) with fixture data alone.
export function OperatingPictureView({
  monthLabel,
  latestCashflow,
  heroSummary,
  netSeriesValues,
  netSeriesLabels,
  freshnessDomains,
  horizonDays,
  rankedAttention,
  affordabilityRatios,
  topCategories,
  recentChanges,
}) {
  return (
    <section className="stack">
      {/* Hero: one big number, one trend, one summary */}
      <article className="panel section heroPicture">
        <div className="heroPictureCopy">
          <Eyebrow>{`Household Intelligence${monthLabel ? ` — ${monthLabel}` : ""}`}</Eyebrow>
          <h1 className="heroNumber">
            {latestCashflow ? (
              <>
                Net <NumMono>{latestCashflow.net}</NumMono>
              </>
            ) : (
              "No data"
            )}
          </h1>
          {heroSummary && <p className="heroPictureSummary">{heroSummary}</p>}
        </div>
        {netSeriesValues && netSeriesValues.length > 0 && (
          <div className="heroPictureSpark">
            <div className="eyebrow" style={{ color: "var(--muted)" }}>
              Cashflow · last {netSeriesValues.length} months
            </div>
            <Spark values={netSeriesValues} labels={netSeriesLabels} color="var(--accent)" width={280} height={80} />
          </div>
        )}
      </article>

      {/* Freshness pulse — replaces the source-confidence table */}
      <article className="panel section">
        <div className="sectionHeader">
          <div>
            <Eyebrow>Confidence</Eyebrow>
            <h2>Source freshness pulse</h2>
          </div>
          <Link className="inlineLink" href="/sources">
            Manage sources →
          </Link>
        </div>
        <FreshnessPulse domains={freshnessDomains} />
      </article>

      {/* Horizon strip — next 7 days */}
      <article className="panel section">
        <div className="sectionHeader">
          <div>
            <Eyebrow>Next seven days</Eyebrow>
            <h2>Horizon</h2>
          </div>
        </div>
        <HorizonStrip days={horizonDays} />
      </article>

      {/* Attention queue + right rail (ratios + categories) */}
      <div className="layout">
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <Eyebrow>Attention queue</Eyebrow>
              <h2>Decisions pending</h2>
            </div>
            <Link className="inlineLink" href="/review">
              See all →
            </Link>
          </div>
          {rankedAttention.length === 0 ? (
            <div className="empty">No attention items. All clear.</div>
          ) : (
            <div className="attentionList">
              {rankedAttention.slice(0, 8).map((item, i) => {
                const meta = attentionMeta(item.severity);
                return (
                  <div className="attentionRow" key={item.item_id ?? i}>
                    <div className="attentionIndex">{String(i + 1).padStart(2, "0")}</div>
                    <div>
                      <div className="attentionRowHead">
                        <Pill tone={meta.tone}>{meta.label}</Pill>
                        {item.source_domain && (
                          <span className="attentionDomain">{item.source_domain}</span>
                        )}
                      </div>
                      <div className="attentionTitle">{item.title}</div>
                      {item.detail && <div className="muted attentionDetail">{item.detail}</div>}
                    </div>
                    <Link className="inlineLink" href="/review">
                      Review →
                    </Link>
                  </div>
                );
              })}
            </div>
          )}
        </article>

        <div className="stack compactStack">
          <article className="panel section">
            <Eyebrow>Affordability</Eyebrow>
            <div className="ratioList">
              {affordabilityRatios.length === 0 ? (
                <div className="empty">No ratios yet.</div>
              ) : (
                affordabilityRatios.slice(0, 4).map((r) => {
                  const state = stateIndicatorBadge(r.state ?? r.assessment);
                  const pct = Number(r.ratio) * 100;
                  return (
                    <div className="ratioRow" key={r.ratio_name}>
                      <div className="ratioRowHead">
                        <span>{r.ratio_name.replace(/_/g, " ")}</span>
                        <NumMono style={{ fontWeight: 700, color: state.color }}>
                          {pct.toFixed(1)}%
                        </NumMono>
                      </div>
                      <div className="ratioTrack">
                        <div
                          className="ratioTrackFill"
                          style={{ width: `${Math.min(pct, 100)}%`, background: state.color }}
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </article>

          <article className="panel section">
            <Eyebrow>Top categories{monthLabel ? ` · ${monthLabel}` : ""}</Eyebrow>
            {topCategories.length === 0 ? (
              <div className="empty">No category spend yet.</div>
            ) : (
              <div className="categoryList">
                {topCategories.map((c) => (
                  <div className="categoryRow" key={c.category}>
                    <span>{c.category}</span>
                    <NumMono className="muted categoryDelta">
                      {c.delta === 0 ? "·" : `${c.delta > 0 ? "▲" : "▼"} ${Math.abs(c.delta).toFixed(1)}%`}
                    </NumMono>
                    <NumMono style={{ fontWeight: 700 }}>{c.amount.toFixed(2)}</NumMono>
                  </div>
                ))}
              </div>
            )}
          </article>
        </div>
      </div>

      {/* Recent changes — kept as a compact editorial list, not a second freshness table */}
      {recentChanges && recentChanges.length > 0 && (
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <Eyebrow>Recent changes</Eyebrow>
              <h2>Last {Math.min(recentChanges.length, 5)} material changes</h2>
            </div>
          </div>
          <div className="stack compactStack">
            {recentChanges.slice(0, 5).map((row, i) => (
              <div className="recentChangeRow" key={i}>
                <Pill tone="cool">{row.change_type}</Pill>
                <span>{row.metric_name}</span>
                <NumMono>
                  {row.direction === "up" ? "▲" : "▼"} {row.current_value}
                  {row.previous_value != null && <span className="muted"> / {row.previous_value}</span>}
                </NumMono>
                <span className="muted">{row.booking_month || row.period_label || "—"}</span>
              </div>
            ))}
          </div>
        </article>
      )}
    </section>
  );
}
