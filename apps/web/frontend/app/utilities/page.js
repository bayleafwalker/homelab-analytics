import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { ResponsiveTable } from "@/components/responsive-table";
import { SparklineChart } from "@/components/sparkline-chart";
import {
  getContractRenewalWatchlist,
  getContractReviewCandidates,
  getCurrentUser,
  getUsageVsPrice,
  getUtilityCostSummary,
  getUtilityCostTrend,
} from "@/lib/backend";

function fixed(value, digits) {
  return value != null ? Number(value).toFixed(digits) : "—";
}

function changePct(value) {
  if (value == null) return "—";
  const pct = Number(value);
  return `${pct >= 0 ? "▲" : "▼"} ${Math.abs(pct).toFixed(1)}%`;
}

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
        <div className="buttonRow">
          <Link className="ghostButton" href="/utilities/battery-plan">
            Battery plan outcome and decisions
          </Link>
          <Link className="ghostButton" href="/utilities/energy-contract">
            Electricity contract review
          </Link>
        </div>
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
            <ResponsiveTable
              label="Usage vs price drivers"
              rows={usageVsPrice}
              columns={[
                { key: "utility_type", header: "Utility type", primary: true },
                { key: "period", header: "Period" },
                { key: "usage_change_pct", header: "Usage change", align: "end", cell: (row) => changePct(row.usage_change_pct) },
                { key: "price_change_pct", header: "Price change", align: "end", cell: (row) => changePct(row.price_change_pct) },
                { key: "cost_change_pct", header: "Cost change", align: "end", cell: (row) => changePct(row.cost_change_pct) },
                { key: "dominant_driver", header: "Driver", cell: (row) => row.dominant_driver || "—" },
              ]}
            />
          </article>
        )}

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Contracts</div>
              <h2>Review candidates</h2>
            </div>
          </div>
          <ResponsiveTable
            label="Contract review candidates"
            rows={reviewCandidates}
            empty={<div className="empty">No contracts flagged for review.</div>}
            columns={[
              { key: "provider", header: "Provider", primary: true },
              { key: "utility_type", header: "Type" },
              { key: "reason", header: "Reason" },
              {
                key: "score",
                header: "Score",
                cell: (row) => (
                  <span className={`statusPill ${row.score >= 3 ? "status-failed" : "status-enqueued"}`}>{row.score}</span>
                ),
              },
              { key: "current_price", header: "Current price", align: "end", cell: (row) => fixed(row.current_price, 4) },
              { key: "market_reference", header: "Market ref", align: "end", cell: (row) => fixed(row.market_reference, 4) },
            ]}
          />
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Contracts</div>
              <h2>Renewal watchlist</h2>
            </div>
          </div>
          <ResponsiveTable
            label="Contract renewal watchlist"
            rows={renewalWatchlist}
            empty={<div className="empty">No contracts approaching renewal.</div>}
            columns={[
              { key: "provider", header: "Provider", primary: true },
              { key: "utility_type", header: "Type" },
              { key: "renewal_date", header: "Renewal date" },
              {
                key: "days_until_renewal",
                header: "Days away",
                cell: (row) => (
                  <span
                    className={`statusPill ${row.days_until_renewal <= 14 ? "status-failed" : row.days_until_renewal <= 30 ? "status-enqueued" : "status-completed"}`}
                  >
                    {row.days_until_renewal}d
                  </span>
                ),
              },
              { key: "current_price", header: "Current price", align: "end", cell: (row) => fixed(row.current_price, 4) },
              { key: "contract_duration", header: "Duration", cell: (row) => row.contract_duration || "—" },
            ]}
          />
        </article>

        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Detail</div>
              <h2>Cost summary by meter</h2>
            </div>
          </div>
          <ResponsiveTable
            label="Cost summary by meter"
            rows={summary}
            empty={<div className="empty">No utility data for the selected filters.</div>}
            columns={[
              { key: "meter", header: "Meter", primary: true, cell: (row) => row.meter_name || row.meter_id },
              { key: "period", header: "Period" },
              { key: "utility_type", header: "Type" },
              { key: "usage_quantity", header: "Usage", align: "end", cell: (row) => fixed(row.usage_quantity, 2) },
              { key: "usage_unit", header: "Unit" },
              { key: "billed_amount", header: "Billed", align: "end", cell: (row) => fixed(row.billed_amount, 2) },
              { key: "currency", header: "Currency" },
              { key: "unit_cost", header: "Unit cost", align: "end", cell: (row) => fixed(row.unit_cost, 4) },
              {
                key: "coverage_status",
                header: "Coverage",
                cell: (row) => (
                  <span className={`statusPill status-${row.coverage_status === "full" ? "completed" : "enqueued"}`}>
                    {row.coverage_status}
                  </span>
                ),
              },
            ]}
          />
        </article>
      </section>
    </AppShell>
  );
}
