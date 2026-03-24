import Link from "next/link";

import { RetroShell } from "@/components/retro-shell";
import { SparklineChart } from "@/components/sparkline-chart";
import {
  getContractRenewalWatchlist,
  getContractReviewCandidates,
  getCurrentUser,
  getUsageVsPrice,
  getUtilityCostSummary,
  getUtilityCostTrend,
} from "@/lib/backend";
import { getWebRendererDiscovery } from "@/lib/renderer-discovery";

const PRIMARY_DESCRIPTOR_KEYS = new Set([
  "utility-costs",
  "utility-cost-trend",
  "usage-vs-price",
  "contract-review",
  "contract-renewals",
]);

export default async function RetroUtilitiesPage({ searchParams }) {
  const user = await getCurrentUser();
  const utilityType = searchParams?.utility_type || "";
  const meterId = searchParams?.meter_id || "";

  const [discovery, trend, usageVsPrice, summary, reviewCandidates, renewalWatchlist] =
    await Promise.all([
      getWebRendererDiscovery(),
      getUtilityCostTrend(utilityType || undefined),
      getUsageVsPrice(utilityType || undefined),
      getUtilityCostSummary(utilityType || undefined, meterId || undefined),
      getContractReviewCandidates(),
      getContractRenewalWatchlist(),
    ]);

  const utilityDescriptors = discovery.reports.filter(
    (descriptor) => descriptor.navGroup === "Utilities"
  );
  const descriptorByKey = Object.fromEntries(
    utilityDescriptors.map((descriptor) => [descriptor.key, descriptor])
  );
  const discoveryOnlyDescriptors = utilityDescriptors.filter(
    (descriptor) => !PRIMARY_DESCRIPTOR_KEYS.has(descriptor.key)
  );
  const trendDescriptor = descriptorByKey["utility-cost-trend"];
  const usageDescriptor = descriptorByKey["usage-vs-price"];
  const reviewDescriptor = descriptorByKey["contract-review"];
  const renewalDescriptor = descriptorByKey["contract-renewals"];
  const summaryDescriptor = descriptorByKey["utility-costs"];
  const utilityTypes = [...new Set(trend.map((row) => row.utility_type))].sort();
  const trendMonths = [...new Set(trend.map((row) => row.billing_month))].sort();
  const colors = ["var(--retro-warn)", "var(--retro-ok)", "var(--retro-accent)", "#ff8f8f"];
  const trendSeries = utilityTypes.map((type, index) => ({
    label: type,
    color: colors[index % colors.length],
    values: trendMonths.map((month) => {
      const row = trend.find(
        (entry) => entry.utility_type === type && entry.billing_month === month
      );
      return row ? Number(row.total_cost) : null;
    }),
  }));
  const meterIds = [...new Set(summary.map((row) => row.meter_id).filter(Boolean))].sort();

  return (
    <RetroShell
      currentPath="/retro/utilities"
      user={user}
      title="CRT Deck / Utilities"
      eyebrow="Retro Detail View"
      lede="Utility costs, contract watchlists, and usage-versus-price signals rendered inside the retro shell from the same reporting endpoints as the classic utilities page."
    >
      <section className="retroMetricGrid">
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Utility Types</span>
          <strong>{utilityTypes.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Summary Rows</span>
          <strong>{summary.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Review Candidates</span>
          <strong>{reviewCandidates.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Renewals</span>
          <strong>{renewalWatchlist.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Published Views</span>
          <strong>{utilityDescriptors.length}</strong>
        </article>
        <article className="retroMetricBox retroPanel">
          <span className="retroMetricLabel">Filter</span>
          <strong>{utilityType || meterId ? "SCOPED" : "ALL"}</strong>
        </article>
      </section>

      {discoveryOnlyDescriptors.length > 0 ? (
        <article className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Published Views</div>
              <h2>Additional utility discovery</h2>
            </div>
          </div>
          <div className="retroModuleGrid">
            {discoveryOnlyDescriptors.map((descriptor) => (
              <article key={descriptor.key} id={descriptor.anchor} className="retroSubPanel">
                <div className="retroMonoStrong">{descriptor.nav_label}</div>
                <div className="retroMuted">
                  {descriptor.publications.map((publication) => publication.display_name).join(" / ") ||
                    "Published utility view"}
                </div>
                <Link className="retroActionLink" href={descriptor.nav_path}>
                  Classic route
                </Link>
              </article>
            ))}
          </div>
        </article>
      ) : null}

      <article className="retroPanel">
        <div className="retroSectionHeader">
          <div>
            <div className="retroEyebrow">Filter Bus</div>
            <h2>Utility type and meter</h2>
          </div>
          <Link className="retroActionLink" href="/utilities">
            Classic utilities
          </Link>
        </div>
        <form className="formGrid fourCol" method="get">
          <div className="field">
            <label htmlFor="utility_type">Utility type</label>
            <input
              id="utility_type"
              name="utility_type"
              type="text"
              defaultValue={utilityType}
              placeholder="electricity"
            />
          </div>
          <div className="field">
            <label htmlFor="meter_id">Meter ID</label>
            <input
              id="meter_id"
              name="meter_id"
              type="text"
              defaultValue={meterId}
              placeholder="meter-001"
              list="retro-meter-options"
            />
            {meterIds.length > 0 ? (
              <datalist id="retro-meter-options">
                {meterIds.map((id) => (
                  <option key={id} value={id} />
                ))}
              </datalist>
            ) : null}
          </div>
          <div className="field" style={{ display: "flex", alignItems: "flex-end", gap: "10px" }}>
            <button className="primaryButton" type="submit">
              Apply
            </button>
            <Link className="ghostButton" href="/retro/utilities">
              Reset
            </Link>
          </div>
        </form>
      </article>

      <article id={trendDescriptor?.anchor || "utility-cost-trend"} className="retroPanel">
        <div className="retroSectionHeader">
          <div>
            <div className="retroEyebrow">Trend Bus</div>
            <h2>{trendDescriptor?.nav_label || "Monthly cost by utility type"}</h2>
          </div>
        </div>
        {trendSeries.length === 0 ? (
          <div className="retroEmptyState">No utility trend data for the selected filters.</div>
        ) : (
          <SparklineChart series={trendSeries} labels={trendMonths} height={132} width={720} />
        )}
      </article>

      <section className="retroSplit">
        <article id={usageDescriptor?.anchor || "usage-vs-price"} className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Driver Split</div>
              <h2>{usageDescriptor?.nav_label || "Usage vs price drivers"}</h2>
            </div>
          </div>
          {usageVsPrice.length === 0 ? (
            <div className="retroEmptyState">No usage-versus-price rows published.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Period</th>
                    <th>Usage</th>
                    <th>Price</th>
                    <th>Cost</th>
                    <th>Driver</th>
                  </tr>
                </thead>
                <tbody>
                  {usageVsPrice.slice(0, 12).map((row, index) => (
                    <tr key={`${row.utility_type}-${row.period}-${index}`}>
                      <td>{row.utility_type}</td>
                      <td>{row.period}</td>
                      <td>{row.usage_change_pct != null ? `${Number(row.usage_change_pct).toFixed(1)}%` : "—"}</td>
                      <td>{row.price_change_pct != null ? `${Number(row.price_change_pct).toFixed(1)}%` : "—"}</td>
                      <td>{row.cost_change_pct != null ? `${Number(row.cost_change_pct).toFixed(1)}%` : "—"}</td>
                      <td>{row.dominant_driver || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        <article id={summaryDescriptor?.anchor || "utility-costs"} className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Meter Summary</div>
              <h2>{summaryDescriptor?.nav_label || "Cost summary by meter"}</h2>
            </div>
          </div>
          {summary.length === 0 ? (
            <div className="retroEmptyState">No utility summary rows for the selected filters.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Meter</th>
                    <th>Type</th>
                    <th>Usage</th>
                    <th>Unit</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.slice(0, 12).map((row, index) => (
                    <tr key={`${row.period}-${row.meter_id}-${index}`}>
                      <td>{row.period}</td>
                      <td>{row.meter_name || row.meter_id}</td>
                      <td>{row.utility_type}</td>
                      <td>
                        {row.usage_quantity != null ? Number(row.usage_quantity).toFixed(2) : "—"}
                      </td>
                      <td>{row.usage_unit}</td>
                      <td>{row.billed_amount != null ? Number(row.billed_amount).toFixed(2) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>

      <section className="retroSplit">
        <article id={reviewDescriptor?.anchor || "contract-review"} className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Contract Queue</div>
              <h2>{reviewDescriptor?.nav_label || "Review candidates"}</h2>
            </div>
          </div>
          {reviewCandidates.length === 0 ? (
            <div className="retroEmptyState">No contracts flagged for review.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Type</th>
                    <th>Reason</th>
                    <th>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {reviewCandidates.slice(0, 12).map((row, index) => (
                    <tr key={`${row.provider}-${row.utility_type}-${index}`}>
                      <td>{row.provider}</td>
                      <td>{row.utility_type}</td>
                      <td>{row.reason}</td>
                      <td>{row.score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        <article id={renewalDescriptor?.anchor || "contract-renewals"} className="retroPanel">
          <div className="retroSectionHeader">
            <div>
              <div className="retroEyebrow">Renewal Watch</div>
              <h2>{renewalDescriptor?.nav_label || "Renewal watchlist"}</h2>
            </div>
          </div>
          {renewalWatchlist.length === 0 ? (
            <div className="retroEmptyState">No contracts approaching renewal.</div>
          ) : (
            <div className="retroTableWrap">
              <table className="retroTable">
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Type</th>
                    <th>Renewal</th>
                    <th>Days</th>
                    <th>Current Price</th>
                  </tr>
                </thead>
                <tbody>
                  {renewalWatchlist.slice(0, 12).map((row, index) => (
                    <tr key={`${row.provider}-${row.renewal_date}-${index}`}>
                      <td>{row.provider}</td>
                      <td>{row.utility_type}</td>
                      <td>{row.renewal_date}</td>
                      <td>{row.days_until_renewal}d</td>
                      <td>{row.current_price != null ? Number(row.current_price).toFixed(4) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>
    </RetroShell>
  );
}
