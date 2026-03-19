import { AppShell } from "@/components/app-shell";
import {
  getAttentionItems,
  getCategoryDimension,
  getCurrentUser,
  getRecentLargeTransactions,
  getTransactionAnomalies,
  getUpcomingFixedCosts,
} from "@/lib/backend";

export default async function ReviewPage({ searchParams }) {
  const user = await getCurrentUser();
  const [attentionItems, anomalies, largeTxs, upcomingCosts, categories] =
    await Promise.all([
      getAttentionItems(),
      getTransactionAnomalies(),
      getRecentLargeTransactions(),
      getUpcomingFixedCosts(),
      getCategoryDimension(),
    ]);

  const notice = searchParams?.notice;
  const error = searchParams?.error;

  const today = new Date();
  const daysAway = (dateStr) => {
    if (!dateStr) return null;
    const diff = new Date(dateStr) - today;
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
  };

  return (
    <AppShell
      currentPath="/review"
      user={user}
      title="Transaction Review"
      eyebrow="Review Queue"
      lede="Anomalies, large transactions, and upcoming fixed costs requiring attention."
    >
      {notice && <div className="successBanner">{notice}</div>}
      {error && <div className="errorBanner">{error}</div>}

      <div className="stack">
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Flagged</div>
              <h2>Attention items</h2>
            </div>
          </div>
          {attentionItems.length === 0 ? (
            <div className="empty">No attention items.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Title</th>
                    <th>Domain</th>
                  </tr>
                </thead>
                <tbody>
                  {attentionItems
                    .sort((a, b) => (a.severity ?? 9) - (b.severity ?? 9))
                    .map((item, i) => (
                      <tr key={i}>
                        <td>
                          <span className={`statusPill ${item.severity === 1 ? "status-failed" : "status-enqueued"}`}>
                            {item.item_type || "item"}
                          </span>
                        </td>
                        <td>{item.title}</td>
                        <td className="muted">{item.source_domain}</td>
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
              <div className="eyebrow">Analysis</div>
              <h2>Transaction anomalies</h2>
            </div>
          </div>
          {anomalies.length === 0 ? (
            <div className="empty">No anomalies detected.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Transaction ID</th>
                    <th>Counterparty</th>
                    <th>Amount</th>
                    <th>Type</th>
                    <th>Reason</th>
                    <th>Category</th>
                  </tr>
                </thead>
                <tbody>
                  {anomalies.map((row, i) => (
                    <tr key={i}>
                      <td className="muted" style={{ fontSize: "0.82rem" }}>{row.transaction_id}</td>
                      <td>{row.counterparty_name}</td>
                      <td>{row.amount}</td>
                      <td>{row.anomaly_type}</td>
                      <td>{row.reason}</td>
                      <td>
                        <form action="/review/category-override" method="POST">
                          <input type="hidden" name="counterparty_name" value={row.counterparty_name} />
                          <select name="category">
                            <option value="">— assign category —</option>
                            {categories.map((c) => (
                              <option key={c.category} value={c.category}>{c.category}</option>
                            ))}
                          </select>
                          <button type="submit">Save</button>
                        </form>
                      </td>
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
              <div className="eyebrow">Transactions</div>
              <h2>Large transactions</h2>
            </div>
          </div>
          {largeTxs.length === 0 ? (
            <div className="empty">No large transactions in recent months.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Counterparty</th>
                    <th>Amount</th>
                    <th>Direction</th>
                    <th>Description</th>
                    <th>Category</th>
                  </tr>
                </thead>
                <tbody>
                  {largeTxs.map((row, i) => (
                    <tr key={i}>
                      <td>{row.booked_at || row.booking_month}</td>
                      <td>{row.counterparty_name}</td>
                      <td>{row.amount}</td>
                      <td>{row.direction}</td>
                      <td className="muted">{row.description}</td>
                      <td>
                        <form action="/review/category-override" method="POST">
                          <input type="hidden" name="counterparty_name" value={row.counterparty_name} />
                          <select name="category">
                            <option value="">— assign category —</option>
                            {categories.map((c) => (
                              <option key={c.category} value={c.category}>{c.category}</option>
                            ))}
                          </select>
                          <button type="submit">Save</button>
                        </form>
                      </td>
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
              <div className="eyebrow">Fixed Costs</div>
              <h2>Upcoming fixed costs</h2>
            </div>
          </div>
          {upcomingCosts.length === 0 ? (
            <div className="empty">No upcoming fixed costs.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Provider</th>
                    <th>Amount</th>
                    <th>Expected Date</th>
                    <th>Days Away</th>
                  </tr>
                </thead>
                <tbody>
                  {upcomingCosts.map((row, i) => (
                    <tr key={i}>
                      <td>{row.name}</td>
                      <td>{row.provider}</td>
                      <td>{row.amount}</td>
                      <td>{row.expected_date}</td>
                      <td>{daysAway(row.expected_date) ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </div>
    </AppShell>
  );
}
