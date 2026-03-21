import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { SparklineChart } from "@/components/sparkline-chart";
import {
  getContractRenewalWatchlist,
  getContractReviewCandidates,
  getCurrentUser,
  getUsageVsPrice,
  getUtilityCostSummary,
  getUtilityCostTrend,
} from "@/lib/backend";

export default async function UtilitiesPage({ searchParams }) {
  const user = await getCurrentUser();
  const utilityType = searchParams?.utility_type || "";
  const meterId = searchParams?.meter_id || "";

  const [trend, usageVsPrice, summary, reviewCandidates, renewalWatchlist] = await Promise.all([
    getUtilityCostTrend(utilityType || undefined),
    getUsageVsPrice(utilityType || undefined),
    getUtilityCostSummary(utilityType || undefined, meterId || undefined),
    getContractReviewCandidates(),
    getContractRenewalWatchlist(),
  ]);

  // Build per-type SparklineChart series
  const utilityTypes = [...new Set(trend.map((r) => r.utility_type))].sort();
  const trendMonths = [...new Set(trend.map((r) => r.billing_month))].sort();
  const colors = ["var(--accent-warm)", "var(--ok)", "var(--accent)", "var(--accent-cool)"];
  const trendSeries = utilityTypes.map((type, idx) => ({
    label: type,
    color: colors[idx % colors.length],
    values: trendMonths.map((month) => {
      const row = trend.find((r) => r.utility_type === type && r.billing_month === month);
      return row ? Number(row.total_cost) : null;
    }),
  }));

  // Unique meter ids from summary for filter dropdown
  const meterIds = [...new Set(summary.map((r) => r.meter_id).filter(Boolean))].sort();

  return (
    <AppShell
      currentPath="/utilities"
      user={user}
      title="Utility Costs"
      eyebrow="Reader Access"
      lede="Metered usage and billing data by utility type and period."
    >
      <section className="stack">
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Filters</div>
              <h2>Utility type &amp; meter</h2>
            </div>
          </div>
          <form className="formGrid fourCol" method="get">
            <div className="field">
              <label htmlFor="utility_type">Utility type</label>
              <input
                id="utility_type"
                name="utility_type"
                type="text"
                defaultValue={utilityType}
                placeholder="e.g. electricity"
              />
            </div>
            <div className="field">
              <label htmlFor="meter_id">Meter ID</label>
              <input
                id="meter_id"
                name="meter_id"
                type="text"
                defaultValue={meterId}
                placeholder="e.g. elec-001"
                list="meter-options"
              />
              {meterIds.length > 0 && (
                <datalist id="meter-options">
                  {meterIds.map((id) => (
                    <option key={id} value={id} />
                  ))}
                </datalist>
              )}
            </div>
            <div className="field" style={{ display: "flex", alignItems: "flex-end", gap: "8px" }}>
              <button className="primaryButton" type="submit">Apply</button>
              <Link className="ghostButton" href="/utilities">Reset</Link>
            </div>
          </form>
        </article>

        {trendSeries.length > 0 && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Trend</div>
                <h2>Monthly cost by utility type</h2>
              </div>
            </div>
            <SparklineChart series={trendSeries} labels={trendMonths} height={120} width={600} />
          </article>
        )}

        {usageVsPrice.length > 0 && (
          <article className="panel section">
            <div className="sectionHeader">
              <div>
                <div className="eyebrow">Period-on-Period</div>
                <h2>Usage vs price drivers</h2>
              </div>
            </div>
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Utility type</th>
                    <th>Period</th>
                    <th>Usage change</th>
                    <th>Price change</th>
                    <th>Cost change</th>
                    <th>Driver</th>
                  </tr>
                </thead>
                <tbody>
                  {usageVsPrice.map((row, i) => (
                    <tr key={i}>
                      <td>{row.utility_type}</td>
                      <td>{row.period}</td>
                      <td>
                        {row.usage_change_pct != null
                          ? `${Number(row.usage_change_pct) >= 0 ? "▲" : "▼"} ${Math.abs(Number(row.usage_change_pct)).toFixed(1)}%`
                          : "—"}
                      </td>
                      <td>
                        {row.price_change_pct != null
                          ? `${Number(row.price_change_pct) >= 0 ? "▲" : "▼"} ${Math.abs(Number(row.price_change_pct)).toFixed(1)}%`
                          : "—"}
                      </td>
                      <td>
                        {row.cost_change_pct != null
                          ? `${Number(row.cost_change_pct) >= 0 ? "▲" : "▼"} ${Math.abs(Number(row.cost_change_pct)).toFixed(1)}%`
                          : "—"}
                      </td>
                      <td>{row.dominant_driver || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        )}

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Contracts</div>
              <h2>Review candidates</h2>
            </div>
          </div>
          {reviewCandidates.length === 0 ? (
            <div className="empty">No contracts flagged for review.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Type</th>
                    <th>Reason</th>
                    <th>Score</th>
                    <th>Current price</th>
                    <th>Market ref</th>
                  </tr>
                </thead>
                <tbody>
                  {reviewCandidates.map((row, i) => (
                    <tr key={i}>
                      <td>{row.provider}</td>
                      <td>{row.utility_type}</td>
                      <td>{row.reason}</td>
                      <td>
                        <span className={`statusPill ${row.score >= 3 ? "status-failed" : "status-enqueued"}`}>
                          {row.score}
                        </span>
                      </td>
                      <td>{row.current_price != null ? Number(row.current_price).toFixed(4) : "—"}</td>
                      <td>{row.market_reference != null ? Number(row.market_reference).toFixed(4) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Contracts</div>
              <h2>Renewal watchlist</h2>
            </div>
          </div>
          {renewalWatchlist.length === 0 ? (
            <div className="empty">No contracts approaching renewal.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Type</th>
                    <th>Renewal date</th>
                    <th>Days away</th>
                    <th>Current price</th>
                    <th>Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {renewalWatchlist.map((row, i) => (
                    <tr key={i}>
                      <td>{row.provider}</td>
                      <td>{row.utility_type}</td>
                      <td>{row.renewal_date}</td>
                      <td>
                        <span className={`statusPill ${row.days_until_renewal <= 14 ? "status-failed" : row.days_until_renewal <= 30 ? "status-enqueued" : "status-completed"}`}>
                          {row.days_until_renewal}d
                        </span>
                      </td>
                      <td>{row.current_price != null ? Number(row.current_price).toFixed(4) : "—"}</td>
                      <td>{row.contract_duration || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Detail</div>
              <h2>Cost summary by meter</h2>
            </div>
          </div>
          {summary.length === 0 ? (
            <div className="empty">No utility data for the selected filters.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Meter</th>
                    <th>Type</th>
                    <th>Usage</th>
                    <th>Unit</th>
                    <th>Billed</th>
                    <th>Currency</th>
                    <th>Unit cost</th>
                    <th>Coverage</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.map((row, i) => (
                    <tr key={i}>
                      <td>{row.period}</td>
                      <td>{row.meter_name || row.meter_id}</td>
                      <td>{row.utility_type}</td>
                      <td>{row.usage_quantity != null ? Number(row.usage_quantity).toFixed(2) : "—"}</td>
                      <td>{row.usage_unit}</td>
                      <td>{row.billed_amount != null ? Number(row.billed_amount).toFixed(2) : "—"}</td>
                      <td>{row.currency}</td>
                      <td>{row.unit_cost != null ? Number(row.unit_cost).toFixed(4) : "—"}</td>
                      <td>
                        <span className={`statusPill status-${row.coverage_status === "full" ? "completed" : "enqueued"}`}>
                          {row.coverage_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>
    </AppShell>
  );
}
